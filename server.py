# -*- coding: utf-8 -*-
from yagua import ioloop
from yagua import tcpserver

HOST, PORT = '', 8888
listenfd = tcpserver.open_listenfd(PORT, HOST)
listenfd_pair = {}
listenfd_pair[listenfd.fileno()] = listenfd


ioloop.IOloop.add_handler(
    listenfd, tcpserver.handle_listenfd, ioloop.IOloop.READ)
ioloop.IOloop.start()

# while True:
#     try:
#         client_connection, client_address = listenfd.accept()
#     except socket.error, e:
#         # 非阻塞的socket会直接返回EWOULDBLOCK错误
#         if e.args[0] in (errno.EWOULDBLOCK, errno.EAGAIN):
#             print e.errno
#             continue
#         raise
#     data = 'get socket' + str(client_connection.fileno())
#     request = ''
#     while True:
#         # block until clinet send FIN，then will execute close method
#         # which means this server only serve one client one time
#         data = client_connection.recv(5)
#         if len(data) <= 0:
#             client_connection.close()
#             break
#         print "request data is" + data
#         client_connection.sendall(data)
