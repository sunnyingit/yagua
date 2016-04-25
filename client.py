# -*- conding: utf-8 -*-
import socket

HOST, PORT = 'localhost', 8888

connect_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# client会随机分配一个端口号
fd = connect_socket.connect((HOST, PORT))
message = "hello world"
connect_socket.send(message)
while True:
    data = connect_socket.recv(5)
    print data
connect_socket.close()
