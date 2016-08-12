# -*- coding: utf-8 -*-

import select
import logging
import errno


class IOLoop(object):
    """
        Ioloop是一个事件驱动器，首先在Ioloop中给fd注册对应函数，
        当select|epoll事件准备好后返回对应的fds，遍历fds并执行对应的函数
    """
    READ = 0x001
    WRITE = 0x004
    ERROR = 0x008 | 0x010 | 0x2000

    def __init__(self, impl=None):
        self._impl = impl or _Select()
        self._handlers = {}
        self._events = {}
        self._sockets = {}
        self._running = False
        self._stopped = False
        self.poll_timeout = 0.2

    @classmethod
    def instance(cls):
        # 使用静态方法的目的主要是为了保证只有一个loop的instance
        if not hasattr(cls, '_instance'):
            cls._instance = cls()
        return cls._instance

    def add_handler(self, socket, handler, events):
        # 加入到select都是fileno(), 这个特别注意一下
        fd = socket.fileno()
        self._sockets[fd] = socket
        self._impl.register(fd, events)
        self._handlers[fd] = handler

    def remove_hander(self, fd):
        self._handlers.pop(fd)
        self._sockets.pop(fd)
        try:
            self._impl.unregister(fd)
        except:
            logging.error('remove hander fd error')

    def start(self):
        if self._stopped:
            self._stopped = False
            return
        self._running = True
        while True:
            try:
                # 返回准备好的fd和注册好的事件
                events_pairs = self._impl.poll(self.poll_timeout)
            except Exception, e:
                # fd的触发事件给了select，但是select 本身是阻塞的
                # 忽略EINTR错误, 信号产生时会中断其调用
                if (getattr(e, 'errno', None) == errno.EINTR or
                    (isinstance(getattr(e, 'args', None), tuple) and
                     len(e.args) == 2 and e.args[0] == errno.EINTR)):
                    continue
                else:
                    raise
            # Select触发后返回的可能多个已经准备好的事件，使用while处理所有准备好的事件
            self._events.update(events_pairs)
            while self._events:
                fd, events = self._events.popitem()
                try:
                    self._handlers[fd](self._sockets[fd], events)
                except (OSError, IOError), e:
                    logging.error(
                        "Exception in I/O handler for fd %d", fd, exc_info=True)  # noqa
        self._stopped = False


class _Select(object):

    def __init__(self):
        self.read_fds = set()
        self.write_fds = set()
        self.error_fds = set()

    def register(self, fd, events):
        if events & IOLoop.READ:
            self.read_fds.add(fd)
        if events & IOLoop.WRITE:
            self.write_fds.add(fd)
        if events & IOLoop.ERROR:
            self.error_fds.add(fd)
            self.read_fds.add(fd)

    def unregister(self, fd):
        self.read_fds.discard(fd)
        self.write_fds.discard(fd)
        self.error_fds.discard(fd)

    def poll(self, timeout=0):
        # select把socket变成"非阻塞"，但是select本身是阻塞的，timeout就是其阻塞的时间
        # 0表示不阻塞，相当于轮询，不传表示阻塞
        # selelct 超时之后直接返回空的集合
        print "read set is %r" % str(self.read_fds)

        readable, writeable, errors = select.select(
            self.read_fds, self.write_fds, self.error_fds)

        events = {}
        for fd in readable:
            events[fd] = IOLoop.READ
        for fd in writeable:
            events[fd] = IOLoop.WRITE
        for fd in errors:
            events[fd] = IOLoop.ERROR
        return events.items()


IOloop = IOLoop.instance()
