# Embedded file name: logging\__init__.pyo
import sys, os, types, time, string, cStringIO, traceback
try:
    import codecs
except ImportError:
    codecs = None

try:
    import thread
    import threading
except ImportError:
    thread = None

__author__ = 'Vinay Sajip <vinay_sajip@red-dove.com>'
__status__ = 'production'
__version__ = '0.5.0.2'
__date__ = '16 February 2007'
if hasattr(sys, 'frozen'):
    _srcfile = 'logging%s__init__%s' % (os.sep, __file__[-4:])
elif string.lower(__file__[-4:]) in ('.pyc', '.pyo'):
    _srcfile = __file__[:-4] + '.py'
else:
    _srcfile = __file__
_srcfile = os.path.normcase(_srcfile)

def currentframe():
    try:
        raise Exception
    except:
        return sys.exc_traceback.tb_frame.f_back


if hasattr(sys, '_getframe'):
    currentframe = lambda : sys._getframe(3)
_startTime = time.time()
raiseExceptions = 1
logThreads = 1
logProcesses = 1
CRITICAL = 50
FATAL = CRITICAL
ERROR = 40
WARNING = 30
WARN = WARNING
INFO = 20
DEBUG = 10
NOTSET = 0
_levelNames = {CRITICAL: 'CRITICAL',
 ERROR: 'ERROR',
 WARNING: 'WARNING',
 INFO: 'INFO',
 DEBUG: 'DEBUG',
 NOTSET: 'NOTSET',
 'CRITICAL': CRITICAL,
 'ERROR': ERROR,
 'WARN': WARNING,
 'WARNING': WARNING,
 'INFO': INFO,
 'DEBUG': DEBUG,
 'NOTSET': NOTSET}

def getLevelName(level):
    return _levelNames.get(level, 'Level %s' % level)


def addLevelName(level, levelName):
    _acquireLock()
    try:
        _levelNames[level] = levelName
        _levelNames[levelName] = level
    finally:
        _releaseLock()


_lock = None

def _acquireLock():
    global _lock
    if not _lock and thread:
        _lock = threading.RLock()
    if _lock:
        _lock.acquire()


def _releaseLock():
    if _lock:
        _lock.release()


class LogRecord:

    def __init__(self, name, level, pathname, lineno, msg, args, exc_info, func = None):
        ct = time.time()
        self.name = name
        self.msg = msg
        if args and len(args) == 1 and args[0] and type(args[0]) == types.DictType:
            args = args[0]
        self.args = args
        self.levelname = getLevelName(level)
        self.levelno = level
        self.pathname = pathname
        try:
            self.filename = os.path.basename(pathname)
            self.module = os.path.splitext(self.filename)[0]
        except:
            self.filename = pathname
            self.module = 'Unknown module'

        self.exc_info = exc_info
        self.exc_text = None
        self.lineno = lineno
        self.funcName = func
        self.created = ct
        self.msecs = (ct - long(ct)) * 1000
        self.relativeCreated = (self.created - _startTime) * 1000
        if logThreads and thread:
            self.thread = thread.get_ident()
            self.threadName = threading.currentThread().getName()
        else:
            self.thread = None
            self.threadName = None
        if logProcesses and hasattr(os, 'getpid'):
            self.process = os.getpid()
        else:
            self.process = None
        return

    def __str__(self):
        return '<LogRecord: %s, %s, %s, %s, "%s">' % (self.name,
         self.levelno,
         self.pathname,
         self.lineno,
         self.msg)

    def getMessage(self):
        if not hasattr(types, 'UnicodeType'):
            msg = str(self.msg)
        else:
            msg = self.msg
            if type(msg) not in (types.UnicodeType, types.StringType):
                try:
                    msg = str(self.msg)
                except UnicodeError:
                    msg = self.msg

        if self.args:
            msg = msg % self.args
        return msg


def makeLogRecord(dict):
    rv = LogRecord(None, None, '', 0, '', (), None, None)
    rv.__dict__.update(dict)
    return rv


class Formatter:
    converter = time.localtime

    def __init__(self, fmt = None, datefmt = None):
        if fmt:
            self._fmt = fmt
        else:
            self._fmt = '%(message)s'
        self.datefmt = datefmt

    def formatTime(self, record, datefmt = None):
        ct = self.converter(record.created)
        if datefmt:
            s = time.strftime(datefmt, ct)
        else:
            t = time.strftime('%Y-%m-%d %H:%M:%S', ct)
            s = '%s,%03d' % (t, record.msecs)
        return s

    def formatException(self, ei):
        sio = cStringIO.StringIO()
        traceback.print_exception(ei[0], ei[1], ei[2], None, sio)
        s = sio.getvalue()
        sio.close()
        if s[-1:] == '\n':
            s = s[:-1]
        return s

    def format(self, record):
        record.message = record.getMessage()
        if string.find(self._fmt, '%(asctime)') >= 0:
            record.asctime = self.formatTime(record, self.datefmt)
        s = self._fmt % record.__dict__
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            if s[-1:] != '\n':
                s = s + '\n'
            s = s + record.exc_text
        return s


_defaultFormatter = Formatter()

class BufferingFormatter:

    def __init__(self, linefmt = None):
        if linefmt:
            self.linefmt = linefmt
        else:
            self.linefmt = _defaultFormatter

    def formatHeader(self, records):
        return ''

    def formatFooter(self, records):
        return ''

    def format(self, records):
        rv = ''
        if len(records) > 0:
            rv = rv + self.formatHeader(records)
            for record in records:
                rv = rv + self.linefmt.format(record)

            rv = rv + self.formatFooter(records)
        return rv


class Filter:

    def __init__(self, name = ''):
        self.name = name
        self.nlen = len(name)

    def filter(self, record):
        if self.nlen == 0:
            return 1
        elif self.name == record.name:
            return 1
        elif string.find(record.name, self.name, 0, self.nlen) != 0:
            return 0
        return record.name[self.nlen] == '.'


class Filterer:

    def __init__(self):
        self.filters = []

    def addFilter(self, filter):
        if filter not in self.filters:
            self.filters.append(filter)

    def removeFilter(self, filter):
        if filter in self.filters:
            self.filters.remove(filter)

    def filter(self, record):
        rv = 1
        for f in self.filters:
            if not f.filter(record):
                rv = 0
                break

        return rv


_handlers = {}
_handlerList = []

class Handler(Filterer):

    def __init__(self, level = NOTSET):
        Filterer.__init__(self)
        self.level = level
        self.formatter = None
        _acquireLock()
        try:
            _handlers[self] = 1
            _handlerList.insert(0, self)
        finally:
            _releaseLock()

        self.createLock()
        return

    def createLock(self):
        if thread:
            self.lock = threading.RLock()
        else:
            self.lock = None
        return

    def acquire(self):
        if self.lock:
            self.lock.acquire()

    def release(self):
        if self.lock:
            self.lock.release()

    def setLevel(self, level):
        self.level = level

    def format(self, record):
        if self.formatter:
            fmt = self.formatter
        else:
            fmt = _defaultFormatter
        return fmt.format(record)

    def emit(self, record):
        raise NotImplementedError, 'emit must be implemented by Handler subclasses'

    def handle(self, record):
        rv = self.filter(record)
        if rv:
            self.acquire()
            try:
                self.emit(record)
            finally:
                self.release()

        return rv

    def setFormatter(self, fmt):
        self.formatter = fmt

    def flush(self):
        pass

    def close(self):
        _acquireLock()
        try:
            del _handlers[self]
            _handlerList.remove(self)
        finally:
            _releaseLock()

    def handleError(self, record):
        if raiseExceptions:
            ei = sys.exc_info()
            traceback.print_exception(ei[0], ei[1], ei[2], None, sys.stderr)
            del ei
        return


class StreamHandler(Handler):

    def __init__(self, strm = None):
        Handler.__init__(self)
        if strm is None:
            strm = sys.stderr
        self.stream = strm
        self.formatter = None
        return

    def flush(self):
        self.stream.flush()

    def emit(self, record):
        try:
            msg = self.format(record)
            fs = '%s\n'
            if not hasattr(types, 'UnicodeType'):
                self.stream.write(fs % msg)
            else:
                try:
                    self.stream.write(fs % msg)
                except UnicodeError:
                    self.stream.write(fs % msg.encode('UTF-8'))

            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


class FileHandler(StreamHandler):

    def __init__(self, filename, mode = 'a', encoding = None):
        if codecs is None:
            encoding = None
        if encoding is None:
            stream = open(filename, mode)
        else:
            stream = codecs.open(filename, mode, encoding)
        StreamHandler.__init__(self, stream)
        self.baseFilename = os.path.abspath(filename)
        self.mode = mode
        return

    def close(self):
        self.flush()
        self.stream.close()
        StreamHandler.close(self)


class PlaceHolder:

    def __init__(self, alogger):
        self.loggerMap = {alogger: None}
        return

    def append(self, alogger):
        if not self.loggerMap.has_key(alogger):
            self.loggerMap[alogger] = None
        return


_loggerClass = None

def setLoggerClass(klass):
    global _loggerClass
    if klass != Logger:
        if not issubclass(klass, Logger):
            raise TypeError, 'logger not derived from logging.Logger: ' + klass.__name__
    _loggerClass = klass


def getLoggerClass():
    return _loggerClass


class Manager:

    def __init__(self, rootnode):
        self.root = rootnode
        self.disable = 0
        self.emittedNoHandlerWarning = 0
        self.loggerDict = {}

    def getLogger(self, name):
        rv = None
        _acquireLock()
        try:
            if self.loggerDict.has_key(name):
                rv = self.loggerDict[name]
                if isinstance(rv, PlaceHolder):
                    ph = rv
                    rv = _loggerClass(name)
                    rv.manager = self
                    self.loggerDict[name] = rv
                    self._fixupChildren(ph, rv)
                    self._fixupParents(rv)
            else:
                rv = _loggerClass(name)
                rv.manager = self
                self.loggerDict[name] = rv
                self._fixupParents(rv)
        finally:
            _releaseLock()

        return rv

    def _fixupParents(self, alogger):
        name = alogger.name
        i = string.rfind(name, '.')
        rv = None
        while i > 0 and not rv:
            substr = name[:i]
            if not self.loggerDict.has_key(substr):
                self.loggerDict[substr] = PlaceHolder(alogger)
            else:
                obj = self.loggerDict[substr]
                if isinstance(obj, Logger):
                    rv = obj
                else:
                    obj.append(alogger)
            i = string.rfind(name, '.', 0, i - 1)

        if not rv:
            rv = self.root
        alogger.parent = rv
        return

    def _fixupChildren(self, ph, alogger):
        name = alogger.name
        namelen = len(name)
        for c in ph.loggerMap.keys():
            if c.parent.name[:namelen] != name:
                alogger.parent = c.parent
                c.parent = alogger


class Logger(Filterer):

    def __init__(self, name, level = NOTSET):
        Filterer.__init__(self)
        self.name = name
        self.level = level
        self.parent = None
        self.propagate = 1
        self.handlers = []
        self.disabled = 0
        return

    def setLevel(self, level):
        self.level = level

    def debug(self, msg, *args, **kwargs):
        if self.manager.disable >= DEBUG:
            return
        if DEBUG >= self.getEffectiveLevel():
            apply(self._log, (DEBUG, msg, args), kwargs)

    def info(self, msg, *args, **kwargs):
        if self.manager.disable >= INFO:
            return
        if INFO >= self.getEffectiveLevel():
            apply(self._log, (INFO, msg, args), kwargs)

    def warning(self, msg, *args, **kwargs):
        if self.manager.disable >= WARNING:
            return
        if self.isEnabledFor(WARNING):
            apply(self._log, (WARNING, msg, args), kwargs)

    warn = warning

    def error(self, msg, *args, **kwargs):
        if self.manager.disable >= ERROR:
            return
        if self.isEnabledFor(ERROR):
            apply(self._log, (ERROR, msg, args), kwargs)

    def exception(self, msg, *args):
        apply(self.error, (msg,) + args, {'exc_info': 1})

    def critical(self, msg, *args, **kwargs):
        if self.manager.disable >= CRITICAL:
            return
        if CRITICAL >= self.getEffectiveLevel():
            apply(self._log, (CRITICAL, msg, args), kwargs)

    fatal = critical

    def log(self, level, msg, *args, **kwargs):
        if type(level) != types.IntType:
            if raiseExceptions:
                raise TypeError, 'level must be an integer'
            else:
                return
        if self.manager.disable >= level:
            return
        if self.isEnabledFor(level):
            apply(self._log, (level, msg, args), kwargs)

    def findCaller(self):
        f = currentframe().f_back
        rv = ('(unknown file)', 0, '(unknown function)')
        while hasattr(f, 'f_code'):
            co = f.f_code
            filename = os.path.normcase(co.co_filename)
            if filename == _srcfile:
                f = f.f_back
                continue
            rv = (filename, f.f_lineno, co.co_name)
            break

        return rv

    def makeRecord(self, name, level, fn, lno, msg, args, exc_info, func = None, extra = None):
        rv = LogRecord(name, level, fn, lno, msg, args, exc_info, func)
        if extra:
            for key in extra:
                if key in ('message', 'asctime') or key in rv.__dict__:
                    raise KeyError('Attempt to overwrite %r in LogRecord' % key)
                rv.__dict__[key] = extra[key]

        return rv

    def _log(self, level, msg, args, exc_info = None, extra = None):
        if _srcfile:
            fn, lno, func = self.findCaller()
        else:
            fn, lno, func = ('(unknown file)', 0, '(unknown function)')
        if exc_info:
            if type(exc_info) != types.TupleType:
                exc_info = sys.exc_info()
        record = self.makeRecord(self.name, level, fn, lno, msg, args, exc_info, func, extra)
        self.handle(record)

    def handle(self, record):
        if not self.disabled and self.filter(record):
            self.callHandlers(record)

    def addHandler(self, hdlr):
        if hdlr not in self.handlers:
            self.handlers.append(hdlr)

    def removeHandler(self, hdlr):
        if hdlr in self.handlers:
            hdlr.acquire()
            try:
                self.handlers.remove(hdlr)
            finally:
                hdlr.release()

    def callHandlers(self, record):
        c = self
        found = 0
        while c:
            for hdlr in c.handlers:
                found = found + 1
                if record.levelno >= hdlr.level:
                    hdlr.handle(record)

            if not c.propagate:
                c = None
            else:
                c = c.parent

        if found == 0 and raiseExceptions and not self.manager.emittedNoHandlerWarning:
            sys.stderr.write('No handlers could be found for logger "%s"\n' % self.name)
            self.manager.emittedNoHandlerWarning = 1
        return

    def getEffectiveLevel(self):
        logger = self
        while logger:
            if logger.level:
                return logger.level
            logger = logger.parent

        return NOTSET

    def isEnabledFor(self, level):
        if self.manager.disable >= level:
            return 0
        return level >= self.getEffectiveLevel()


class RootLogger(Logger):

    def __init__(self, level):
        Logger.__init__(self, 'root', level)


_loggerClass = Logger
root = RootLogger(WARNING)
Logger.root = root
Logger.manager = Manager(Logger.root)
BASIC_FORMAT = '%(levelname)s:%(name)s:%(message)s'

def basicConfig(**kwargs):
    if len(root.handlers) == 0:
        filename = kwargs.get('filename')
        if filename:
            mode = kwargs.get('filemode', 'a')
            hdlr = FileHandler(filename, mode)
        else:
            stream = kwargs.get('stream')
            hdlr = StreamHandler(stream)
        fs = kwargs.get('format', BASIC_FORMAT)
        dfs = kwargs.get('datefmt', None)
        fmt = Formatter(fs, dfs)
        hdlr.setFormatter(fmt)
        root.addHandler(hdlr)
        level = kwargs.get('level')
        if level is not None:
            root.setLevel(level)
    return


def getLogger(name = None):
    if name:
        return Logger.manager.getLogger(name)
    else:
        return root


def critical(msg, *args, **kwargs):
    if len(root.handlers) == 0:
        basicConfig()
    apply(root.critical, (msg,) + args, kwargs)


fatal = critical

def error(msg, *args, **kwargs):
    if len(root.handlers) == 0:
        basicConfig()
    apply(root.error, (msg,) + args, kwargs)


def exception(msg, *args):
    apply(error, (msg,) + args, {'exc_info': 1})


def warning(msg, *args, **kwargs):
    if len(root.handlers) == 0:
        basicConfig()
    apply(root.warning, (msg,) + args, kwargs)


warn = warning

def info(msg, *args, **kwargs):
    if len(root.handlers) == 0:
        basicConfig()
    apply(root.info, (msg,) + args, kwargs)


def debug(msg, *args, **kwargs):
    if len(root.handlers) == 0:
        basicConfig()
    apply(root.debug, (msg,) + args, kwargs)


def log(level, msg, *args, **kwargs):
    if len(root.handlers) == 0:
        basicConfig()
    apply(root.log, (level, msg) + args, kwargs)


def disable(level):
    root.manager.disable = level


def shutdown(handlerList = _handlerList):
    for h in handlerList[:]:
        try:
            h.flush()
            h.close()
        except:
            if raiseExceptions:
                raise


try:
    import atexit
    atexit.register(shutdown)
except ImportError:

    def exithook(status, old_exit = sys.exit):
        try:
            shutdown()
        finally:
            old_exit(status)


    sys.exit = exithook