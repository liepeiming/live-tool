# bin/bash
for FILE in $(find . -name "*.proto");
do
  protoc -I . --python_out=.  $FILE
  echo "protoc -I . --python_out=.  $FILE";
done