# -*- conding: utf-8 -*-

import socket
import time

HOST, PORT = 'localhost', 8888

connect_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
connect_socket.connect((HOST, PORT))

while True:
    message = "hello world"
    connect_socket.send(message)
    time.sleep(4)
