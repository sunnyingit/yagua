# -*- coding: utf-8 -*-

import socket
import errno
import fcntl
import multiprocessing
import os
import logging

from yagua import iostream


def _cpu_count():
    if multiprocessing is not None:
        try:
            return multiprocessing.cpu_count()
        except NotImplementedError:
            pass
    try:
        return os.sysconf("SC_NPROCESSORS_CONF")
    except ValueError:
        pass
    return 1


def open_listenfd(port, address=None):
    port = 3000 if port <= 0 else port
    listenfd = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    listenfd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    flags = fcntl.fcntl(listenfd.fileno(), fcntl.F_GETFD)
    flags |= fcntl.FD_CLOEXEC
    fcntl.fcntl(listenfd.fileno(), fcntl.F_SETFD, flags)

    listenfd.setblocking(0)
    listenfd.bind((address, port))
    listenfd.listen(128)
    print 'Serving HTTP on port %s ...' % port
    return listenfd


def start(func, num_processes=1):
    if num_processes is None or num_processes <= 0:
        num_processes = _cpu_count()
    if num_processes > 1:
        for i in range(num_processes):
            if os.fork() == 0:
                func()
        # 子进程被kill的时候会向父进程发送SIGCHLD信号，如果多个子进程同时被kill，会发送多个
        # SIGCHLD信号，使用wait(),父进程只会处理一个信号，使用waitpid 会处理多个sigchld信号
        os.waitpid(-1, 0)


def handle_listenfd(listenfd, events):
    # 多个连接同时到达，服务器的TCP就绪队列瞬间积累多个就绪连接，如果是边缘触发模式，
    # epoll只会通知一次，accept只处理一个连接，只有等到下次有连接过来的时候触发，这样会
    # 导致TCP就绪队列中剩下的连接都得不到处理，解决方法是使用While, 处理完TCP就绪队列
    # 中的所有连接后再退出循环，原则就是，在ET模式下，Select/Epoll触发一次，我们需要处理读完fd的所有数据
    # 如果fd是可读的，那就读完所有的数据，如果是可写的，那就一次性写完所有的数
    while True:
        try:
            connection, address = listenfd.accept()
            logging.info('accept connection fileno is %r', connection.fileno())
        except socket.error, e:
            # 在非阻塞模式下，调用accept(阻塞操作)， 如果此时监听套接字队列里面还没有已经
            # 完成的套接字，将返回Resource temporarily unavailable，代号为11(EAGAIN)
            if e.args[0] in (errno.EWOULDBLOCK, errno.EAGAIN):
                return
        # print connection.recv(100)
        # 把connection交给iostream处理
        iofd = iostream.IOStream(connection)
        iofd.read()


def connnect(socket):
    pass
