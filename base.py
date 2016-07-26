# -*- coding: utf-8 -*-

from yagua import tcpserver

HOST, PORT = '', 8888
listenfd = tcpserver.open_listenfd(PORT, HOST)
connection = tcpserver.accept(listenfd)
connection.setblocking(1)
while True:
    # block until clinet send FIN，then will execute close method
    # which means this server only serve one client one time
    data = connection.recv(5)
    if len(data) < 3:
        connection.close()
        break
    print "request data is" + data
    connection.sendall(data)
