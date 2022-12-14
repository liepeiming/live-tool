import json
import logging
import sys
from queue import Queue


from douyin import dy

from PyQt6 import QtCore, QtGui
from PyQt6.QtWidgets import QWidget, QApplication, QLabel, QTextEdit, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, \
    QTextBrowser, QMainWindow, QCheckBox, QLineEdit, QMessageBox
from PyQt6.QtCore import Qt, QThread


class BarrageHelper(QWidget):

    def __init__(self):
        super().__init__()
        self.layout = None
        self.topWinCheckBox = None
        self.noticeLabel = None
        self.r = None
        self.dyThread = None
        self.win = None
        self.liveAddrLabel = None
        self.liveAddrEdit = None
        self.protcolLabel = None
        self.protcoComboBox = None
        self.connectButton = None
        self.initUI()
        global win
        win = self

    def initUI(self):
        # self.text = "快手抖音弹幕助手💉"
        self.setWindowOpacity(0.7)
        self.setWindowTitle('直播弹幕助手💉')
        self.resize(400, 150)
        self.liveAddrLabel = QLabel('直播地址：', self)
        self.noticeLabel = QLabel('🌈🌈🌈 WYI直播监控', self)
        self.noticeLabel.move(160, 10)
        self.noticeLabel.resize(300, 30)
        self.liveAddrEdit = QLineEdit('https://live.douyin.com/76663111946', self)
        self.protcolLabel = QLabel('弹幕类型：', self)
        self.protcoComboBox = QComboBox(self)
        self.connectButton = QPushButton('进入房间', self)
        self.protcoComboBox.addItem("抖音🔜")
        self.protcoComboBox.addItem("快手🎦")
        self.protcoComboBox.resize(50, 20)
        self.liveAddrEdit.setFixedSize(210, 20)
        self.layout = QHBoxLayout()
        self.layout.addWidget(self.liveAddrLabel)
        self.layout.addWidget(self.liveAddrEdit)
        self.layout.addWidget(self.protcolLabel)
        self.layout.addWidget(self.protcoComboBox)
        self.connectButton.move(20, 100)
        self.setLayout(self.layout)
        self.connectButton.clicked.connect(self.click)
        self.connectButton.setStyleSheet(
            '''QPushButton{background:#1E90FF;border-radius:5px;}QPushButton:hover{background:#00BFFF;}''')
        self.topWinCheckBox = QCheckBox('顶置弹幕窗口', self)
        self.topWinCheckBox.move(313, 100)
        self.show()

    def click(self):
        index = self.protcoComboBox.currentIndex()
        if index != 0:
            QMessageBox.warning(self, "系统提示", "当前协议不支持！")
            return
        winT = self.protcoComboBox.currentText()
        global winTitle
        winTitle = winT
        self.win = BarrageWin(winTitle=winT)
        if self.topWinCheckBox.isChecked():
            self.win.setWindowFlags(
                QtCore.Qt.WindowType.WindowStaysOnTopHint | QtCore.Qt.WindowType.FramelessWindowHint)

        title = self.connectButton.text().title()
        if title == '进入房间':
            self.win.show()
            self.connectButton.setText('退出房间')
            self.connectButton.setStyleSheet(
                '''QPushButton{background:#fe2a00;border-radius:5px;}QPushButton:hover{background:#fe2a00;}''')
            global url
            url = self.liveAddrEdit.text()
            self.r = printThread(textWritten=self.win.outputWritten)
            self.dyThread = douyinMsgThread()
            self.dyThread.start()
            self.r.start()
            return
        self.connectButton.setText('进入房间')
        self.connectButton.setStyleSheet(
            '''QPushButton{background:#1E90FF;border-radius:5px;}QPushButton:hover{background:#00BFFF;}''')
        self.win.close()
        self.dyThread.exit()
        self.r.exit()


class BarrageWin(QMainWindow):

    def __init__(self, winTitle):
        super().__init__()
        self.mflag = None
        self.textBrowser = None
        self.winTitle = winTitle
        self.initUI()

    def initUI(self):
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle(self.winTitle)
        self.setWindowOpacity(0.7)
        self.resize(300, 600)
        self.textBrowser = QTextBrowser(self)
        self.textBrowser.resize(100, 100)
        self.textBrowser.move(0, 50)
        self.outputWritten('Notice ==> 正在建立直播通道请稍等～～～')

    def outputWritten(self, text):
        if winTitle is not None:
            self.setWindowTitle(str(winTitle))
        self.textBrowser.append('\n')
        self.textBrowser.insertHtml(text)
        self.textBrowser.append('\n')
        #### 滚动到底部
        self.textBrowser.ensureCursorVisible()  # 游标可用
        cursor = self.textBrowser.textCursor()  # 设置游标
        pos = len(self.textBrowser.toPlainText())  # 获取文本尾部的位置
        cursor.setPosition(pos)  # 游标位置设置为尾部
        self.textBrowser.setTextCursor(cursor)  # 滚动到游标位置

    def resizeEvent(self, event):
        self.textBrowser.resize(event.size())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.mflag = True
            self.mPosition = event.pos() - self.pos()  # 获取鼠标相对窗口的位置
            event.accept()
            # self.setCursor(QCursor(Qt.MouseButton.OpenHandCursor))  # 更改鼠标图标

    def mouseMoveEvent(self, QMouseEvent):
        if Qt.MouseButton.LeftButton and self.mflag:
            self.move(QMouseEvent.pos() - self.mPosition)  # 更改窗口位置
            QMouseEvent.accept()

    def mouseReleaseEvent(self, QMouseEvent):
        self.mflag = False
        # self.setCursor(QCursor(Qt.MouseButton.ArrowCursor))



class douyinMsgThread(QThread):

    def run(self):
        dy.parseLiveRoomUrl(url, q)

    def exit(self, returnCode: int = ...):
        dy.wssStop()


class printThread(QThread):
    textWritten = QtCore.pyqtSignal(str)

    def run(self):
        while True:
            data = q.get()
            self.printF(data)

    def printF(self, data):
        data = json.loads(data)
        if 'roomInfo' in data.keys():
            roomTitle = data['roomInfo']['room']['title']
            global winTitle
            winTitle = winTitle + ' | ' + roomTitle
            return

        if 'common' not in data.keys():
            return

        if data['common']['method'] == 'WebcastMemberMessage':
            nickname = data['user']['nickName']
            self.textWritten.emit('👏 <font color="red">' + nickname + '</font>: 进入直播间')
            return

        if data['common']['method'] == 'WebcastLikeMessage':
            nickname = data['user']['nickName']
            self.textWritten.emit('💗 <font color="green">' + nickname + '</font>: 点亮了爱心')
            return

        if data['common']['method'] == 'WebcastGiftMessage':
            describe = data['common']['describe']
            self.textWritten.emit('🎁 <font color="red">' + describe + '</font>')
            return

        if data['common']['method'] == 'WebcastChatMessage':
            nickname = data['user']['nickName']
            self.textWritten.emit('💬 <font color="pink">' + nickname + '</font>: ' + data['content'])
            return


url = None
win = None
winTitle = None
q = Queue(100)


def main():
    print(sys.argv)
    app = QApplication(sys.argv)
    ex = BarrageHelper()
    sys.exit(app.exec())


if __name__ == '__main__':
    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)
    main()
