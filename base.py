# -*- coding: utf-8 -*-
import socket
import errno
import time


def blockting_socket():
    HOST, PORT = '', 8888
    # AF_INET(协议族) SOCK_STREAM(tcp), SOCK_DGRAM(upd)
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    # 为何要使用so_reuseraddr?
    serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # 绑定host和port, bind就是把本地地址和端口绑定到一个套接字上
    serversocket.bind((HOST, PORT))
    # 指定连接队列的大小，这个队列是干嘛的，队列满了会怎么样？
    # serversocket监听套接字
    serversocket.listen(128)
    while True:
        # accept 做了什么样的事情，是否会阻塞??
        # connection 可连接的套接字
        connection, address = serversocket.accept()
        while True:
            now = time.time()
            # man recv: If no messages are available at the socket,
            # the receive call waits for amessage to arrive, unless the socket
            # is nonblocking, orderly shutdown, the value 0 is returned
            data = connection.recv(100)
            print 'blocking time is: %r' % str(int(time.time() - now))
            print "request data is:" + data


def noblockting_socket():
    HOST, PORT = '', 8888
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serversocket.bind((HOST, PORT))
    serversocket.listen(128)
    # 默认监听套接字是阻塞的
    serversocket.setblocking(0)
    while True:
        # 当队列里面还有准备好的可连接套接字返回Resource temporarily unavailable
        try:
            connection, address = serversocket.accept()
        except socket.error as e:
            if e.args[0] in (errno.EWOULDBLOCK, errno.EAGAIN):
                continue
        while True:
            now = time.time()
            try:
                data = connection.recv(100)
                # 关闭socket, 否则会一直死循环
                if len(data) == 0:
                    connection.close()
                    break
            except socket.error as e:
                if e.args[0] in (errno.EWOULDBLOCK, errno.EAGAIN):
                    print 'blocking time is: %r' % str(int(time.time() - now))
                    time.sleep(1)
                    continue

            print "request data is:" + data


def time_wait_socket():
    # 分析socket的各个状态[listen | time_wait | established]
    HOST, PORT = '', 8888
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
    # 请看一下如果没有配置这个选项会发生什么事情
    # 可配置选项 /proc/sys/net/ipv4/tcp_tw_reuse or tcp_tw_recycle
    serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serversocket.bind((HOST, PORT))
    # lsof -i:8888 查看监听套接字
    # netstat -an | grep LISTEN | 8888
    serversocket.listen(128)
    while True:
        connection, address = serversocket.accept()
        while True:
            data = connection.recv(1)
            if len(data) == 1:
                # 当服务器主动调用close 会触发四次握手，server的状态会经过
                # FIN_WAIT_1 -> FIN_WAIT_2 ->close_wait -> closed(关闭了)
                connection.close()
                break
            print "request data is:" + data

if __name__ == '__main__':
    time_wait_socket()
