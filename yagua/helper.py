# -*- coding: utf-8 -*-


def errno_from_exception(e):
    if hasattr(e, 'errno'):
        return e.errno
    elif e.args:
        return e.args[0]
    return None
