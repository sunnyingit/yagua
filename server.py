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
