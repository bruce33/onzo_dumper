# Embedded file name: jsonrpc\proxy.pyo
import urllib2
from jsonrpc.json import dumps, loads, JSONDecodeException

class JSONRPCException(Exception):

    def __init__(self, rpcError):
        Exception.__init__(self)
        self.error = rpcError

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__, repr(self.error))


class ServiceProxy(object):

    def __init__(self, serviceURL, serviceName = None):
        self.__serviceURL = serviceURL
        self.__serviceName = serviceName

    def __getattr__(self, name):
        if self.__serviceName != None:
            name = '%s.%s' % (self.__serviceName, name)
        return ServiceProxy(self.__serviceURL, name)

    def __call__(self, *args):
        postdata = dumps({'method': self.__serviceName,
         'params': args,
         'id': 'jsonrpc'})
        request = urllib2.Request(self.__serviceURL, postdata, {'Content-type': 'application/json'})
        respdata = urllib2.urlopen(request).read()
        try:
            resp = loads(respdata)
            if resp.get('error'):
                raise JSONRPCException(resp['error'])
            else:
                return resp['result']
        except JSONDecodeException:
            raise JSONDecodeException(respdata)