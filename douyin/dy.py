import _thread
import gzip
import json
import logging
import re
import time
from queue import Queue

import requests
import websocket

import urllib
from google.protobuf import json_format

import main
from .dy_pb2 import PushFrame
from .dy_pb2 import Response
from .dy_pb2 import MatchAgainstScoreMessage
from .dy_pb2 import LikeMessage
from .dy_pb2 import MemberMessage
from .dy_pb2 import GiftMessage
from .dy_pb2 import ChatMessage
from .dy_pb2 import SocialMessage
from .dy_pb2 import RoomUserSeqMessage

liveRoomId = None
ttwid = None
roomStore = None
liveRoomTitle = None
q = None
ws = None
isCloseWss = True


def onMessage(ws: websocket.WebSocketApp, message: bytes):
    wssPackage = PushFrame()
    wssPackage.ParseFromString(message)
    logId = wssPackage.logId
    decompressed = gzip.decompress(wssPackage.payload)
    payloadPackage = Response()
    payloadPackage.ParseFromString(decompressed)
    # 发送ack包
    if payloadPackage.needAck:
        sendAck(ws, logId, payloadPackage.internalExt)
    # WebcastGiftMessage
    for msg in payloadPackage.messagesList:
        if msg.method == 'WebcastMatchAgainstScoreMessage':
            unPackMatchAgainstScoreMessage(msg.payload)
            continue

        if msg.method == 'WebcastLikeMessage':
            unPackWebcastLikeMessage(msg.payload)
            continue

        if msg.method == 'WebcastMemberMessage':
            unPackWebcastMemberMessage(msg.payload)
            continue
        if msg.method == 'WebcastGiftMessage':
            unPackWebcastGiftMessage(msg.payload)
            continue
        if msg.method == 'WebcastChatMessage':
            unPackWebcastChatMessage(msg.payload)
            continue

        if msg.method == 'WebcastSocialMessage':
            unPackWebcastSocialMessage(msg.payload)
            continue

        if msg.method == 'WebcastRoomUserSeqMessage':
            unPackWebcastRoomUserSeqMessage(msg.payload)
            continue

        logging.info('[onMessage] [⌛️方法' + msg.method + '等待解析～] [房间Id：' + liveRoomId + ']')


# 直播间人数消息
def unPackWebcastRoomUserSeqMessage(data):
    roomUserSeqMessage = RoomUserSeqMessage()
    roomUserSeqMessage.ParseFromString(data)
    data = json_format.MessageToDict(roomUserSeqMessage, preserving_proto_field_name=True)
    log = json.dumps(data, ensure_ascii=False)
    logging.info('[WebcastRoomUserSeqMessage] [直播间人数信息] [房间Id：' + liveRoomId + '] ｜ ' + log)
    q.put(json.dumps(data))
    return data


# 关注消息
def unPackWebcastSocialMessage(data):
    socialMessage = SocialMessage()
    socialMessage.ParseFromString(data)
    data = json_format.MessageToDict(socialMessage, preserving_proto_field_name=True)
    log = json.dumps(data, ensure_ascii=False)
    logging.info('[unPackWebcastSocialMessage] [➕直播间关注消息] [房间Id：' + liveRoomId + '] ｜ ' + log)
    q.put(json.dumps(data))
    return data


# 普通消息
def unPackWebcastChatMessage(data):
    chatMessage = ChatMessage()
    chatMessage.ParseFromString(data)
    data = json_format.MessageToDict(chatMessage, preserving_proto_field_name=True)
    # log = json.dumps(data, ensure_ascii=False)
    logging.info('[unPackWebcastChatMessage] [📧直播间弹幕消息] [房间Id：' + liveRoomId + '] ｜ ' + data['content'])
    # logging.info('[unPackWebcastChatMessage] [📧直播间弹幕消息] [房间Id：' + liveRoomId + '] ｜ ' + log)
    q.put(json.dumps(data))
    return data


# 礼物消息
def unPackWebcastGiftMessage(data):
    giftMessage = GiftMessage()
    giftMessage.ParseFromString(data)
    data = json_format.MessageToDict(giftMessage, preserving_proto_field_name=True)
    log = json.dumps(data, ensure_ascii=False)
    logging.info('[unPackWebcastGiftMessage] [🎁直播间礼物消息] [房间Id：' + liveRoomId + '] ｜ ' + log)
    q.put(json.dumps(data))
    return data


# xx成员进入直播间消息
def unPackWebcastMemberMessage(data):
    memberMessage = MemberMessage()
    memberMessage.ParseFromString(data)
    data = json_format.MessageToDict(memberMessage, preserving_proto_field_name=True)
    log = json.dumps(data, ensure_ascii=False)
    logging.info('[unPackWebcastMemberMessage] [🚹🚺直播间成员加入消息] [房间Id：' + liveRoomId + '] ｜ ' + log)
    q.put(json.dumps(data))
    return data


# 点赞
def unPackWebcastLikeMessage(data):
    likeMessage = LikeMessage()
    likeMessage.ParseFromString(data)
    data = json_format.MessageToDict(likeMessage, preserving_proto_field_name=True)
    log = json.dumps(data, ensure_ascii=False)
    # logging.info('[unPackWebcastLikeMessage] [👍直播间点赞消息] [房间Id：' + liveRoomId + '] ｜ ' + log)
    q.put(json.dumps(data))
    return data


# 解析WebcastMatchAgainstScoreMessage消息包体
def unPackMatchAgainstScoreMessage(data):
    matchAgainstScoreMessage = MatchAgainstScoreMessage()
    matchAgainstScoreMessage.ParseFromString(data)
    data = json_format.MessageToDict(matchAgainstScoreMessage, preserving_proto_field_name=True)
    log = json.dumps(data, ensure_ascii=False)
    # logging.info('[unPackMatchAgainstScoreMessage] [🤷不知道是啥的消息] [房间Id：' + liveRoomId + '] ｜ ' + log)
    return data


# 发送Ack请求
def sendAck(ws, logId, internalExt):
    obj = PushFrame()
    obj.payloadType = 'ack'
    obj.logId = logId
    sdata = bytes(internalExt, encoding="utf8")
    obj.payloadType = sdata
    data = obj.SerializeToString()
    ws.send(data, websocket.ABNF.OPCODE_BINARY)
    # logging.info('[sendAck] [🌟发送Ack] [房间Id：' + liveRoomId + '] ====> 房间🏖标题【' + liveRoomTitle + '】')


def onError(ws, error):
    print("error", error)
    logging.error('[onError] [webSocket Error事件] [房间Id：' + liveRoomId + ']')


def onClose(ws, a, b):
    logging.info('[onClose] [webSocket Close事件] [房间Id：' + liveRoomId + ']')


def onOpen(ws):
    q.put(json.dumps(roomStore))
    _thread.start_new_thread(ping, (ws,))
    logging.info('[onOpen] [webSocket Open事件] [房间Id：' + liveRoomId + ']')


# 发送ping心跳包
def ping(ws):
    while isCloseWss:
        obj = PushFrame()
        obj.payloadType = 'hb'
        data = obj.SerializeToString()
        ws.send(data, websocket.ABNF.OPCODE_BINARY)
        # logging.info('[ping] [💗发送ping心跳] [房间Id：' + liveRoomId + '] ====> 房间🏖标题【' + liveRoomTitle + '】')
        time.sleep(10)


def wssServerStart(roomId):
    global liveRoomId, ws, isCloseWss
    isCloseWss = True
    liveRoomId = roomId
    websocket.enableTrace(False)
    webSocketUrl = 'wss://webcast3-ws-web-lf.douyin.com/webcast/im/push/v2/?app_name=douyin_web&version_code=180800&webcast_sdk_version=1.3.0&update_version_code=1.3.0&compress=gzip&internal_ext=internal_src:dim|wss_push_room_id:' + liveRoomId + '|wss_push_did:7139391558914393612|dim_log_id:2022113016104801020810207318AA8748|fetch_time:1669795848095|seq:1|wss_info:0-1669795848095-0-0|wrds_kvs:WebcastRoomStatsMessage-1669795848048115671_WebcastRoomRankMessage-1669795848064411370&cursor=t-1669795848095_r-1_d-1_u-1_h-1&host=https://live.douyin.com&aid=6383&live_id=1&did_rule=3&debug=false&endpoint=live_pc&support_wrds=1&im_path=/webcast/im/fetch/&device_platform=web&cookie_enabled=true&screen_width=1440&screen_height=900&browser_language=zh&browser_platform=MacIntel&browser_name=Mozilla&browser_version=5.0%20(Macintosh;%20Intel%20Mac%20OS%20X%2010_15_7)%20AppleWebKit/537.36%20(KHTML,%20like%20Gecko)%20Chrome/107.0.0.0%20Safari/537.36&browser_online=true&tz_name=Asia/Shanghai&identity=audience&room_id=' + liveRoomId + '&heartbeatDuration=0'
    h = {
        # 'Cookie': 'ttwid=' + ttwid,
        'Cookie': 'msToken=2NoPpNNHXXqR6Z-1IoAWie19MLGBEBR27I_upxgmOpdkZOt1OcZBT-Vq-PnqZFJxbBo6FY64RVCkskvbvgBgyCCF7SraDuuavlZ45VhX73LBqih0g7WToL_shb3KYA==; live_can_add_dy_2_desktop=%220%22; ttwid=1%7CzkRChajVHo-582RU6m-LUyy1qVtm3OvHlYbevNX2_0A%7C1669454993%7C94636934ecb129629e4520cbb33ff012eb5a6b8b3337f6c18d2fa96520f944cb; FOLLOW_NUMBER_YELLOW_POINT_INFO=%22MS4wLjABAAAAlc42G0Nktrm_CVQMfASabMRnI_6GlL2br1i7a8yqTEI%2F1669910400000%2F0%2F1669851346067%2F0%22; odin_tt=8b73feba91def09e7499f73fd72ca77aa2d971a8b535202683674bbc4ff3f76cda54a5d2a422cd9631f94a5c556d295c042c71f3959f0c326a536496816dd01f; passport_auth_status=ee5560b58d399a00ad4f0f1c8d6ae9d0%2C; passport_auth_status_ss=ee5560b58d399a00ad4f0f1c8d6ae9d0%2C; sessionid=2b3573264049cebe2157c6d64fcc3619; sessionid_ss=2b3573264049cebe2157c6d64fcc3619; sid_guard=2b3573264049cebe2157c6d64fcc3619%7C1669851342%7C5183998%7CSun%2C+29-Jan-2023+23%3A35%3A40+GMT; sid_tt=2b3573264049cebe2157c6d64fcc3619; sid_ucp_v1=1.0.0-KGY0ZjlmNWUxNzJhNWEzMzE3NDc3OTJkMGQzNDZkODRlYjQ2YzBlZGQKFwik8Iy7gQMQztGfnAYY7zEgDDgGQPQHGgJscSIgMmIzNTczMjY0MDQ5Y2ViZTIxNTdjNmQ2NGZjYzM2MTk; ssid_ucp_v1=1.0.0-KGY0ZjlmNWUxNzJhNWEzMzE3NDc3OTJkMGQzNDZkODRlYjQ2YzBlZGQKFwik8Iy7gQMQztGfnAYY7zEgDDgGQPQHGgJscSIgMmIzNTczMjY0MDQ5Y2ViZTIxNTdjNmQ2NGZjYzM2MTk; uid_tt=ee1582aad5159e3d9065b6dab0df20dc; uid_tt_ss=ee1582aad5159e3d9065b6dab0df20dc; n_mh=bUxOCHzZv5szT8QIHfxmgnjoVlZQ1kn7aM-ZW6ndDKY; passport_assist_user=Cj2rXeD7jz0C4ehbIPkAW0vpnV2K8AeMIbk7_x9zXNIuIu9Izs6OfGrLh9BxTE4-otIBe2OOv_h3MSsaqOZTGkgKPPg79xgWvInOGefX-UX59crjHTUIV2tXkbuPp3VXJuRITI6kMwaDYGofS6mm1Mc5YEAUcQlf9pgbaJ6mxRCR0qINGImv1lQiAQMeE2Ds; sid_ucp_sso_v1=1.0.0-KDk2ZjhkYTE2ZWE3NmNkY2VhN2UyODQ4OTVjNjVhOWNmNmQzYTdlMzcKHQik8Iy7gQMQzNGfnAYY7zEgDDCYxPfbBTgGQPQHGgJobCIgOTg1M2MzOWIwZWE3ODNmOTNhOTM2N2NkNDBjNThjNmI; ssid_ucp_sso_v1=1.0.0-KDk2ZjhkYTE2ZWE3NmNkY2VhN2UyODQ4OTVjNjVhOWNmNmQzYTdlMzcKHQik8Iy7gQMQzNGfnAYY7zEgDDCYxPfbBTgGQPQHGgJobCIgOTg1M2MzOWIwZWE3ODNmOTNhOTM2N2NkNDBjNThjNmI; sso_uid_tt=96165fbd66c002f8a17bc493b82dcd8e; sso_uid_tt_ss=96165fbd66c002f8a17bc493b82dcd8e; toutiao_sso_user=9853c39b0ea783f93a9367cd40c58c6b; toutiao_sso_user_ss=9853c39b0ea783f93a9367cd40c58c6b; strategyABtestKey=%221669748138.954%22; passport_csrf_token=828528a0cd2d8b92ab702b1cbb18bcbc; passport_csrf_token_default=828528a0cd2d8b92ab702b1cbb18bcbc; home_can_add_dy_2_desktop=%220%22; download_guide=%221%2F20221130%22'
        # 'Cookie': 'ttwid=1%7Ci4eax320w3bbvTc0HYa7mYGI6dDVxI4d4oKW5F6BicM%7C1662269142%7C5e99889e30f1a2443f6955b4a1314aefe1687f0ae2a48ebae3eb0fd818f67f58; MONITOR_WEB_ID=3229a16f-0061-4b18-83a5-804f7437e133; s_v_web_id=verify_lalvq69x_uQpevqlk_p2TI_4fap_BdQ1_AbYK78bmmTW7; passport_csrf_token=355d6df700037172efddceb1ba4fb7ce; passport_csrf_token_default=355d6df700037172efddceb1ba4fb7ce; n_mh=bUxOCHzZv5szT8QIHfxmgnjoVlZQ1kn7aM-ZW6ndDKY; passport_assist_user=Cj3yHzLk2FVbUsXhlyGaK-xm1ISJ3HQMmxSKQ48iFUQTfNatk4UEQDBvP4zmFV2ZpCM7mkjlGtJYkt5djvYNGkgKPEuOFVs5UFIHYQlynfcwbcs7pzE8GGCutmz3WWjn0C4MWUQ0H6vhRte6IpTnlUzorA6yYL1RY-fTkXy-zxDFw6ENGImv1lQiAQMmr0yi; sso_uid_tt=d7649bc4d7532d439d813608b5d445e4; sso_uid_tt_ss=d7649bc4d7532d439d813608b5d445e4; toutiao_sso_user=8f56058fbe2880018b680ec4a96d9b29; toutiao_sso_user_ss=8f56058fbe2880018b680ec4a96d9b29; sid_ucp_sso_v1=1.0.0-KDA4OWMxNGNjNGFiZjMyZTE2NGJkZGYwMDIwMjM1YTY1NGU2ZWNkNGIKHQik8Iy7gQMQ69zbmwYY7zEgDDCYxPfbBTgGQPQHGgJobCIgOGY1NjA1OGZiZTI4ODAwMThiNjgwZWM0YTk2ZDliMjk; ssid_ucp_sso_v1=1.0.0-KDA4OWMxNGNjNGFiZjMyZTE2NGJkZGYwMDIwMjM1YTY1NGU2ZWNkNGIKHQik8Iy7gQMQ69zbmwYY7zEgDDCYxPfbBTgGQPQHGgJobCIgOGY1NjA1OGZiZTI4ODAwMThiNjgwZWM0YTk2ZDliMjk; odin_tt=2a63201f2eaf0b6c0d42c042b8468dbe221aa2e38c891b155e1845111d81e91d3fe2847f6655c9f84f0c61882bce12200849c7112de61cef773cc0366977db48; passport_auth_status=f24f4516c18ee1b1771327f013e7bd5d%2C; passport_auth_status_ss=f24f4516c18ee1b1771327f013e7bd5d%2C; sid_guard=7bde62ce22de9398ea37d87a7027ce3c%7C1668738668%7C5183999%7CTue%2C+17-Jan-2023+02%3A31%3A07+GMT; uid_tt=3037bb2ecf54bf732a63bcdbe584c5ee; uid_tt_ss=3037bb2ecf54bf732a63bcdbe584c5ee; sid_tt=7bde62ce22de9398ea37d87a7027ce3c; sessionid=7bde62ce22de9398ea37d87a7027ce3c; sessionid_ss=7bde62ce22de9398ea37d87a7027ce3c; sid_ucp_v1=1.0.0-KGQ5M2NhNDE0NGI0ZmRhOTVjNjIxNjg2MWU3ODk2ZDFlOGI5OGUyNWUKFwik8Iy7gQMQ7NzbmwYY7zEgDDgGQPQHGgJscSIgN2JkZTYyY2UyMmRlOTM5OGVhMzdkODdhNzAyN2NlM2M; ssid_ucp_v1=1.0.0-KGQ5M2NhNDE0NGI0ZmRhOTVjNjIxNjg2MWU3ODk2ZDFlOGI5OGUyNWUKFwik8Iy7gQMQ7NzbmwYY7zEgDDgGQPQHGgJscSIgN2JkZTYyY2UyMmRlOTM5OGVhMzdkODdhNzAyN2NlM2M; csrf_session_id=c44573beaed6a20b3ae4e8d43250e56c; douyin.com; download_guide=%223%2F20221126%22; LOGIN_STATUS=1; msToken=R7IU6P9TAs7PVHo6q_PPo3TfR97icOgCeWrXlwnMlxB4Har2VDsu5OdtcL7OiLYMQA-xwow2YIBa7bVFR5iK5hLaLF661p1EbBHRo31TQXXhPOIzIJmYqw==; tt_scid=0IKxAdS1O4ndkMo3DSCXEP6GFzI6G2svaxnRAkJGqWX7PgeNBeFQuXE4a.V2efIU0d4e; FOLLOW_LIVE_POINT_INFO=%22MS4wLjABAAAAlc42G0Nktrm_CVQMfASabMRnI_6GlL2br1i7a8yqTEI%2F1669910400000%2F0%2F1669825948706%2F0%22; FOLLOW_NUMBER_YELLOW_POINT_INFO=%22MS4wLjABAAAAlc42G0Nktrm_CVQMfASabMRnI_6GlL2br1i7a8yqTEI%2F1669910400000%2F0%2F0%2F1669847749828%22; __ac_signature=_02B4Z6wo00f01H.1iwQAAIDD6yPQC29JO8R.1Y-AAHyCIL2aFC7gsn3v02ydb5hU.t-V2UfLaauV0EPsUeRrN0C.lbtYhZ7BtAkPyauNyCz.uw37eD9J4N1FlcAfcZwclEPs-ogoepnC9NOa39; strategyABtestKey=%221669846692.263%22; home_can_add_dy_2_desktop=%221%22; live_can_add_dy_2_desktop=%221%22; msToken=Tu7d3DMHr23lI2lehvzGHMIf6VGYKysS4biOrB8kK2e6gq-u369mC-RffjVPE4G8guth2Eyfjrn56c--ELPwJYUl9V-VO1zExpOogTXzYCkZbuCQ3_Kvjg=='
    }
    # 创建一个长连接
    ws = websocket.WebSocketApp(
        webSocketUrl, on_message=onMessage, on_error=onError, on_close=onClose,
        on_open=onOpen,
        header=h
    )
    ws.run_forever()
    ws.close()


def wssStop():
    global isCloseWss
    isCloseWss = False
    ws.close()


def parseLiveRoomUrl(url, q1: Queue):
    h = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,'
                  'application/signed-exchange;v=b3;q=0.9',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36',
        'cookie': '__ac_nonce=0638733a400869171be51',
    }
    res = requests.get(url=url, headers=h)
    global ttwid, roomStore, liveRoomId, liveRoomTitle, q
    q = q1
    data = res.cookies.get_dict()
    ttwid = data['ttwid']
    res = res.text
    res = re.search(r'<script id="RENDER_DATA" type="application/json">(.*?)</script>', res)
    res = res.group(1)
    res = urllib.parse.unquote(res, encoding='utf-8', errors='replace')
    res = json.loads(res)
    roomStore = res['app']['initialState']['roomStore']
    liveRoomId = roomStore['roomInfo']['roomId']
    liveRoomTitle = roomStore['roomInfo']['room']['title']
    wssServerStart(liveRoomId)
