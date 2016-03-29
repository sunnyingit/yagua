# -*- coding: utf-8 -*-
import collections
import socket
import errno
import logging

from yagua import ioloop
from yagua.helper import errno_from_exception

_ERRNO_WOULDBLOCK = (errno.EWOULDBLOCK, errno.EAGAIN)


class IOStream(object):
    """
        每个accept fd都会有一个IOStream对象, 当可读事件发生的时候，IOStream对象会不停地
        从 fd data里面每次读取read_chunk_size的数据到read_buffer中，加入了buffer之后
        可以避免每次都向fd data里面读取数据

        向buffer读取数据的api:
        1:read_until 一直读取数据直到遇到_read_delimiter
        2:read_size 一直读取数据直到_read_bytes大小的数据

        通过调用read_until, read_size 注册__read_callback回调函数，读取的数据
        作为回调函数的参数，通过回调函数解析读取的数据
    """

    def __init__(self, socket, io_loop=None, max_buffer_size=104857600,
                 read_chunk_size=4096):
        self.socket = socket
        #  设置已连接的socket为非阻塞模式
        self.socket.setblocking(False)
        self.io_loop = io_loop or ioloop.IOLoop.instance()
        self.max_buffer_size = max_buffer_size
        self.read_chunk_size = read_chunk_size
        self._read_buffer = collections.deque()
        self._write_buffer = collections.deque()
        self._read_buffer_size = 0
        self._read_delimiter = None
        self._read_bytes = None
        self._read_callback = None
        self._read_max_bytes = None
        self.event = self.io_loop.READ

    def _close_fd(self):
        self.socket.close()

    def close(self, exc_info=None):
        pass

    def closed(self):
        return False

    def _read_from_socket(self):
        try:
            # 在非阻塞的模式下，如果client发送的数据还没有到服务器，此时reve返回-1，错误代号为EAGAIN
            chunk = self.socket.recv(self.read_chunk_size)
        except socket.error, e:
            if errno_from_exception(e) in _ERRNO_WOULDBLOCK:
                return None
            else:
                raise
        # If no messages are available to be received and the peer has performed  # noqa
        # an orderly shutdown, the value 0 is returned
        if not chunk:
            self.socket.close()
            return None
        return chunk

    def _read_to_buffer(self):
        while True:
            try:
                chunk = self._read_from_socket()
            except Exception, e:
                # 发送信号可导致recv中断，此时返回EINTER
                # 使用While的原因是忽略中断信号,知道读取到数据为止
                if errno_from_exception(e) == errno.EINTR:
                    continue
                self.close(exc_info=True)
            break
        if chunk is None:
            return 0
        self._read_buffer.append(chunk)
        self._read_buffer_size += len(chunk)
        if self._read_buffer_size > self.max_buffer_size:
            logging.error("Reached maximum read buffer size")
            self.close()
        return len(chunk)

    def _try_inline_read(self):
        """
            从_read_buffer里面读取target_size的数据, 如果buffer里面没有需要的数据，
            则调用_read_to_buffer_loop，从fd data里面获取，直到找到数据的position并
            返回
        """
        pos = self._find_pos_buffer()
        if pos is not None:
            return self._read_from_buffer(pos)

        # 如果buffer里面没有数据，则从fd data里面读取
        try:
            pos = self._read_to_buffer_loop()
        except Exception:
            # run close callbacks
            pass
        if pos is not None:
            return self._read_from_buffer(pos)
        # 如果socket是close状态,run close callbacks
        if self.closed():
            pass
        else:
            # 如果fd data里面还没有数据，说明client还没有发送任何数据过来
            self._add_io_stats(ioloop.IOLoop.READ)

    def _read_to_buffer_loop(self, target_size=0):
        """
            循环把fd data里面的数据读取到buffer中，直到读取到相应的大小
        """
        if self._read_bytes is not None:
            target_size = self._read_bytes
        elif self._read_max_bytes is not None:
            target_size = self._read_max_bytes
        while self.closed():
            # Read from the socket until we get EWOULDBLOCK
            if self._read_to_buffer() == 0:
                break
            if self._read_buffer_size > target_size:
                break

    def _read_from_buffer(self):
        pass

    def _add_io_stats(self, events):
        pass

    def read(self):
        self._read_to_buffer()
        print self._read_buffer
