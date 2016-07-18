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
        self._close = False

    def _close_fd(self):
        """
            close fd
        """
        self.socket.close()

    def close(self, exc_info=None):
        """
            close一个fd的时候，首先需要close fd, 其次还需要从ioloop hander里面移掉
            对应的fd
        """
        if not self.closed():
            self.io_loop.remove_hander(self.socket.fileno())
            self._close_fd()
            self._close = True

    def closed(self):
        return self._close

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
        # 需要注意的是 当一个fd被select|epoll 返回回来说明fd已经准备好可以读了，如果此时
        # 读到的数据是0，说明对端发起了FIN，所以需要调用close关闭本次socket
        if not chunk:
            self.socket.close()
            return None
        return chunk

    def _read_to_buffer(self):
        """
            从socket里面读取数据到read_buffer中
            使用while True的原因是一次读完socket缓冲区里面的所有的数据，直到遇到
        """
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
        pos = self._find_read_pos()
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
            循环把fd data里面的数据读取到buffer中，直到读取到相应的大小,并返回对应的pos
        """
        if self._read_bytes is not None:
            target_size = self._read_bytes
        elif self._read_max_bytes is not None:
            target_size = self._read_max_bytes
        next_find_pos = 0
        while self.closed():
            # Read from the socket until we get EWOULDBLOCK
            if self._read_to_buffer() == 0:
                break
            if self._read_buffer_size > target_size:
                break
            if self._read_buffer_size >= next_find_pos:
                pos = self._find_read_pos()
                if pos is not None:
                    return pos
                next_find_pos = self._read_buffer_size * 2
            return self._find_read_pos()

    def _read_from_buffer(self, pos):
        """
            一旦找到了读取数据的pos,就说明了已经可以找到了相应的数据，那必须重置之前设置
            的标志，并执行read_callback回调函数
        """
        self._read_bytes = self._read_delimiter = None
        self._run_read_callback(pos)

    def _find_read_pos(self):
        # 如果是调用read_bytes, 则_read_bytes不为空
        if self._read_bytes:
            if self._read_buffer_size >= self._read_bytes:
                return self._read_bytes
        # 如果是调用read_until, 则_read_delimiter不为空, 这里需要注意的是
        # delimiter是多字符，例如'\r\n', 那么有可能这两个字符会跨chunk，一个chunk的size
        # 是4M， 一般在chunk[0]即可找到相关的数据，如果在第一个chunk没有找到，我们需要
        # 合并chunk, 直到找到相应的数据 chunk[0] = data，
        # 获取数据self._read_buffer.popleft()
        if self._read_delimiter and self._read_buffer:
            while True:
                loc = self._read_buffer[0].find(self._read_delimiter)
                if loc != -1:
                    delimiter_len = len(self._read_delimiter)
                    return loc + delimiter_len
                if len(self._read_buffer) == 1:
                    break
            self._double_prefix(self._read_buffer)
        return None

    def _add_io_stats(self, events):
        pass

    def _handle_events(self, fd, events):
        if self.closed():
            logging.warning("Got events for closed stream %s", fd)
            return
        try:
            if self.closed():
                return
            if events & self.io_loop.READ:
                self._handle_read()
            if self.closed():
                return
            if events & self.io_loop.WRITE:
                self._handle_write()
            if self.closed():
                return
            if events & self.io_loop.ERROR:
                self.error = self.get_fd_error()
                # We may have queued up a user callback in _handle_read or
                # _handle_write, so don't close the IOStream until those
                # callbacks have had a chance to run.
                self.io_loop.add_callback(self.close)
                return
        except Exception:
            logging.error("Uncaught exception, closing connection.")
            self.close()
            raise

    def read(self):
        self._read_to_buffer()
        print self._read_buffeur


def _double_prefix(deque):
    new_len = max(len(deque[0]) * 2,
                  (len(deque[0]) + len(deque[1])))
    _merge_prefix(deque, new_len)


def _merge_prefix(deque, size):
    """Replace the first entries in a deque of strings with a single
    string of up to size bytes.

    >>> d = collections.deque(['abc', 'de', 'fghi', 'j'])
    >>> _merge_prefix(d, 5); print(d)
    deque(['abcde', 'fghi', 'j'])

    Strings will be split as necessary to reach the desired size.
    >>> _merge_prefix(d, 7); print(d)
    deque(['abcdefg', 'hi', 'j'])

    >>> _merge_prefix(d, 3); print(d)
    deque(['abc', 'defg', 'hi', 'j'])

    >>> _merge_prefix(d, 100); print(d)
    deque(['abcdefghij'])
    """
    if len(deque) == 1 and len(deque[0]) <= size:
        return
    prefix = []
    remaining = size
    while deque and remaining > 0:
        chunk = deque.popleft()
        if len(chunk) > remaining:
            deque.appendleft(chunk[remaining:])
            chunk = chunk[:remaining]
        prefix.append(chunk)
        remaining -= len(chunk)
    # This data structure normally just contains byte strings, but
    # the unittest gets messy if it doesn't use the default str() type,
    # so do the merge based on the type of data that's actually present.
    if prefix:
        deque.appendleft(type(prefix[0])().join(prefix))
    if not deque:
        deque.appendleft(b"")
