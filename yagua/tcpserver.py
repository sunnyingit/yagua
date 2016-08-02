# -*- coding: utf-8 -*-

import socket
import errno
import fcntl
import multiprocessing
import os

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
    listenfd = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    # 主动调用close的一方会处于time_wait的状态，是是为了保证全双工的完全终止
    # 避免数据混乱， time_wait的时间是MSL的2倍，这样这个时间段的所有的数据都被丢弃了
    # 可配置 /proc/sys/net/ipv4/tcp_tw_reuse or tcp_tw_recycle
    listenfd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    flags = fcntl.fcntl(listenfd.fileno(), fcntl.F_GETFD)
    flags |= fcntl.FD_CLOEXEC
    fcntl.fcntl(listenfd.fileno(), fcntl.F_SETFD, flags)
    # 设置listenfd套接字为非阻塞模式, 默认套接字是阻塞的, 阻塞之后进程会挂起（ps aux | grep base.py）
    # 当有新的连接到达时，程序被唤起
    listenfd.setblocking(0)
    listenfd.bind((address, port))
    # 128是可监听套接字队列的size, 如果队列是满的，当client的SYN过来的时候，serve会忽略
    # 这个SYN，以期望client继续发送SYN直到队列里面有可用的空间
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


def accept(listenfd):
    pass


def handle_listenfd(listenfd, events):
    # 监听套接字的队列里面可能同时又多个连接已经可读了，服务器的TCP就绪队列瞬间积累多个就绪连接，如果是边缘触发模式，
    # epoll只会通知一次，accept只处理一个连接，只有等到下次有连接过来的时候触发，这样会
    # 导致TCP就绪队列中剩下的连接都得不到处理，解决方法是使用While, 处理完TCP就绪队列
    # 中的所有连接后再退出循环，原则就是，在ET模式下，Select/Epoll触发一次，我们需要处理读完fd的所有数据
    # 如果fd是可读的，那就读完所有的数据，如果是可写的，那就一次性写完所有的数
    while True:
        # 在三次握手之后数据已经开始传输，而不是在调用accept才开始传输数据。
        # 最大的数据量为已连接的套接字的接受缓冲区的大小
        try:
            connection, address = listenfd.accept()
        except socket.error, e:
            # 在非阻塞模式下，调用accept(阻塞操作)， 如果此时监听套接字队列里面还没有已经
            # 完成的套接字，将返回Resource temporarily unavailable，代号为11(EAGAIN)
            # 直接返回，跳出loop
            if e.args[0] in (errno.EWOULDBLOCK, errno.EAGAIN):
                # 注意这里终止了while，监听套接字队列没有准备好的套接字，直接返回
                return
            raise e
        connection.setblocking(1)
        # 1, 同时有多个fd经过三次握手，可准备好读了[1, 2, 3, 4], 把fd交给iostream处理
        # 2, 当数据准备好读的时候，ioloop直接触发对应的回调函数处理已经准备好的数据
        # 3, 在程序中也可以手动调用iostream的函数去获取数据，不必依赖ioloop的回调函数
        # 4, 需要注意的一点是fd为什么是数字
        io = iostream.IOStream(connection)
        # print io.read_from_socket()
        io.read_bytes(100)


def connnect(socket):
    pass
