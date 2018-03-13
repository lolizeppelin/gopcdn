from websocket import create_connection

def upload_file(path):
    ws = create_connection("ws://172.31.0.126:8999",
                           subprotocols=["binary"])
    print "connect websocket success"
    with open(path, 'rb') as f:
        while True:
            buffer = f.read(4096)
            if buffer:
                ws.send(buffer)
            else:
                print 'file send finish'
                break


path = r'C:\Users\loliz_000\Desktop\zhuomian5\hadoop-2.9.0.tar.gz'
upload_file(path)