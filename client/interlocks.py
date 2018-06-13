# Embedded file name: client\interlocks.pyo
import sys
import os, os.path
import time
import base64
import subprocess

class SingleInstanceError:
    pass


InterProcessLock = None

class InterProcessLockFcntl:
    type = 'fcntl'

    def __init__(self, name = None):
        self.lockf = 0
        if not name:
            name = sys.argv[0]
        self.name = base64.b64encode(name).replace('=', '')
        self.fname = os.path.join('/tmp', self.name + '.lock')

    def lock(self):
        self.lockf = open(self.fname, 'w')
        try:
            fcntl.flock(self.lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            self.lockf.close()
            self.lockf = 0
            raise SingleInstanceError

    def unlock(self):
        os.unlink(self.fname)
        self.lockf.close()


class InterProcessLockWin32:
    type = 'win32'

    def __init__(self, name = None):
        self.mutex = None
        if not name:
            name = sys.argv[0]
        self.name = base64.b64encode(name).replace('=', '')
        return

    def lock(self):
        self.mutex = win32event.CreateMutex(None, 0, self.name)
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            self.mutex.Close()
            self.mutex = None
            raise SingleInstanceError
        return

    def unlock(self):
        self.mutex.Close()


class InterProcessLockSocket:
    type = 'socket'

    def __init__(self, name = None):
        self.socket = None
        if not name:
            name = sys.argv[0]
        self.name = base64.b64encode(name).replace('=', '')
        self.portno = 65530 - abs(self.name.__hash__()) % 32749
        return

    def lock(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.bind(('127.0.0.1', self.portno))
        except socket.error:
            self.socket.close()
            self.socket = None
            raise SingleInstanceError

        return

    def unlock(self):
        self.socket.close()
        self.socket = None
        return


try:
    import fcntl
    InterProcessLock = InterProcessLockFcntl
except ImportError:
    try:
        import win32event
        import win32api
        import winerror
        InterProcessLock = InterProcessLockWin32
    except ImportError:
        import socket
        InterProcessLock = InterProcessLockSocket

if os.path.exists('/usr/bin/python'):
    interpreter = '/usr/bin/python'

    def mykill(pid):
        import signal
        os.kill(pid, signal.SIGKILL)


else:
    interpreter = 'C:/Program Files/Python25/Python.exe'

    def mykill(pid):
        import win32api
        import win32con
        import pywintypes
        handle = win32api.OpenProcess(win32con.PROCESS_TERMINATE, pywintypes.FALSE, pid)
        return 0 != win32api.TerminateProcess(handle, 0)


if __name__ == '__main__':
    print 'testing %r locks' % InterProcessLock.type
    lock1 = InterProcessLock(name='test')
    lock1.lock()
    lock2 = InterProcessLock(name='test')
    lock3 = InterProcessLock(name='test')
    try:
        lock2.lock()
    except SingleInstanceError:
        print 'test1 ok'
    else:
        print 'test1 FAILED'

    lock1.unlock()
    try:
        lock2.lock()
    except SingleInstanceError:
        print 'test2 FAILED'
    else:
        print 'test2 ok'

    try:
        lock3.lock()
    except SingleInstanceError:
        print 'test3 ok'
    else:
        print 'test3 FAILED'

    lock2.unlock()
    try:
        lock1.lock()
    except SingleInstanceError:
        print 'test4 FAILED'
    else:
        print 'test4 ok'

    lock1.unlock()
    print 'testing multiple processes'

    def execute(cmd):
        cmd = 'import time;' + cmd + 'time.sleep(10);'
        process = subprocess.Popen([interpreter, '-c', cmd])
        pid = process.pid
        time.sleep(1)
        return pid


    pid = execute("import t1;a=t1.InterProcessLock('test');a.lock();")
    try:
        lock1.lock()
    except SingleInstanceError:
        print 'test5 ok'
    else:
        print 'test5 FAILED'

    mykill(pid)
    time.sleep(1)
    try:
        lock1.lock()
    except SingleInstanceError:
        print 'test6 FAILED'
    else:
        print 'test6 ok'

    lock1.unlock()