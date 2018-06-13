# Embedded file name: jsonrpc\serviceHandler.pyo
from jsonrpc import loads, dumps, JSONEncodeException

def ServiceMethod(fn):
    fn.IsServiceMethod = True
    return fn


class ServiceException(Exception):
    pass


class ServiceRequestNotTranslatable(ServiceException):
    pass


class BadServiceRequest(ServiceException):
    pass


class ServiceMethodNotFound(ServiceException):

    def __init__(self, name):
        self.methodName = name


class ServiceHandler(object):

    def __init__(self, service):
        self.service = service

    def handleRequest(self, json):
        err = None
        result = None
        id_ = ''
        try:
            req = self.translateRequest(json)
        except ServiceRequestNotTranslatable, e:
            err = e
            req = {'id': id_}

        if err == None:
            try:
                id_ = req['id']
                methName = req['method']
                args = req['params']
            except:
                err = BadServiceRequest(json)

        if err == None:
            try:
                meth = self.findServiceEndpoint(methName)
            except Exception, e:
                err = e

        if err == None:
            try:
                result = self.invokeServiceEndpoint(meth, args)
            except Exception, e:
                err = e

        resultdata = self.translateResult(result, err, id_)
        return resultdata

    def translateRequest(self, data):
        try:
            req = loads(data)
        except:
            raise ServiceRequestNotTranslatable(data)

        return req

    def findServiceEndpoint(self, name):
        try:
            meth = getattr(self.service, name)
            if getattr(meth, 'IsServiceMethod'):
                return meth
            else:
                raise ServiceMethodNotFound(name)
        except AttributeError:
            raise ServiceMethodNotFound(name)

    def invokeServiceEndpoint(self, meth, args):
        return meth(*args)

    def translateResult(self, rslt, err, id_):
        if err != None:
            message = '(no details available)'
            if hasattr(err, 'message'):
                message = err.message
            err = {'name': err.__class__.__name__,
             'message': message}
            rslt = None
        try:
            data = dumps({'result': rslt,
             'id': id_,
             'error': err})
        except JSONEncodeException, e:
            err = {'name': 'JSONEncodeException',
             'message': 'Result Object Not Serializable'}
            data = dumps({'result': None,
             'id': id_,
             'error': err})

        return data