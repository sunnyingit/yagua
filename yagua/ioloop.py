# -*- coding: utf-8 -*-

import select
import logging
import errno


class IOLoop(object):
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
        if not hasattr(cls, '_instance'):
            cls._instance = cls()
        return cls._instance

    def add_handler(self, socket, handler, events):
        fd = socket.fileno()
        self._sockets[fd] = socket
        self._impl.register(fd, events)
        self._handlers[fd] = handler

    def start(self):
        if self._stopped:
            self._stopped = False
            return
        self._running = True
        while True:
            try:
                events_pairs = self._impl.poll(self.poll_timeout)
                if events_pairs:
                    print events_pairs
            except Exception, e:
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
                        "Exception in I/O handler for fd %d", fd, exc_info=True) # noqa
        self._stopped = False


class _Select(object):

    def __init__(self):
        self.read_fds = set()
        self.write_fds = set()
        self.error_fds = set()

    def register(self, fd, events):
        if events == IOLoop.READ:
            self.read_fds.add(fd)
        if events == IOLoop.WRITE:
            self.write_fds.add(fd)
        if events == IOLoop.ERROR:
            self.error_fds.add(fd)

    def poll(self, timeout=0):
        # select把socket变成非阻塞，但是select本身是阻塞的，timeout就是其阻塞的时间
        readable, writeable, errors = select.select(
            self.read_fds, self.write_fds, self.error_fds, timeout)

        events = {}
        for fd in readable:
            events[fd] = IOLoop.READ
        for fd in writeable:
            events[fd] = IOLoop.WRITE
        for fd in errors:
            events[fd] = IOLoop.ERROR
        return events.items()


IOloop = IOLoop()
