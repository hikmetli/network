import socket

c_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
c_socket.bind(("127.0.0.1", 8990))

c_socket.sendto(b"serse", ("127.0.0.1", 8989))
