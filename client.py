# -*- conding: utf-8 -*-

import socket

HOST, PORT = 'localhost', 8888

for i in range(10):
    connect_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    fd = connect_socket.connect((HOST, PORT))
    message = "hello world" * 100
    connect_socket.send(message)

    # while True:
    #     data = connect_socket.recv(5)
    #     time.sleep(1)
    # connect_socket.close()
