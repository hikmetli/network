import threading
import time
import socket

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind(("localhost", 8989))

while True:
    time.sleep(2)
    message, addres = server.recvfrom(1024)
    print(message)
