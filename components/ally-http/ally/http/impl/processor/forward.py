'''
Created on Feb 13, 2013

@package: ally http
@copyright: 2012 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Forwards the requests to an external server.
'''

from ally.container.ioc import injected
from ally.design.processor.attribute import requires, defines, optional
from ally.design.processor.context import Context
from ally.design.processor.handler import HandlerProcessor
from ally.http.spec.codes import SERVICE_UNAVAILABLE, CodedHTTP, PATH_NOT_FOUND
from ally.http.spec.headers import remove, CONNECTION, CONNECTION_KEEP
from ally.http.spec.server import HTTP
from ally.support.util_io import IInputStream, IInputStreamClosable
from http.client import HTTPConnection, BadStatusLine
from urllib.parse import urlencode, urlunsplit
import logging
import socket

# --------------------------------------------------------------------

log = logging.getLogger(__name__)

# --------------------------------------------------------------------

class Request(Context):
    '''
    Context for request. 
    '''
    # ---------------------------------------------------------------- Optional
    host = optional(str)
    # ---------------------------------------------------------------- Required
    scheme = requires(str)
    method = requires(str)
    uri = requires(str)
    parameters = requires(list)
    headers = requires(dict)

class RequestContent(Context):
    '''
    Context for request content. 
    '''
    # ---------------------------------------------------------------- Required
    source = requires(IInputStream)
    length = requires(int)

class Response(CodedHTTP):
    '''
    Context for response. 
    '''
    # ---------------------------------------------------------------- Defined
    headers = defines(dict)

class ResponseContent(Context):
    '''
    Context for response content. 
    '''
    # ---------------------------------------------------------------- Required
    source = defines(IInputStream)

# --------------------------------------------------------------------

@injected
class ForwardHTTPHandler(HandlerProcessor):
    '''
    Implementation for a handler that provides forwarding to external servers.
    '''
    
    externalHost = None
    # The external server host.
    externalPort = int
    # The external server port.
    maximumRetries = 10
    # The maximum number of retries.
    removeHeaders = {'Server', 'Date', 'Connection'}
    # The headers to be removed automatically from the response.
        
    def __init__(self):
        assert isinstance(self.maximumRetries, int), 'Invalid maximum retries %s' % self.maximumRetries
        assert isinstance(self.removeHeaders, set), 'Invalid remove headers %s' % self.removeHeaders
        super().__init__()
        
        self._pool = dict()
    
    def process(self, chain, request:Request, requestCnt:RequestContent, response:Response,
                responseCnt:ResponseContent, **keyargs):
        '''
        @see: HandlerProcessor.process
        
        Process the forward.
        '''
        assert isinstance(request, Request), 'Invalid request %s' % request
        assert isinstance(requestCnt, RequestContent), 'Invalid request content %s' % requestCnt
        assert isinstance(response, Response), 'Invalid response %s' % response
        assert isinstance(responseCnt, ResponseContent), 'Invalid response content %s' % responseCnt
        
        host = self.externalHost
        if self.externalHost is None:
            assert Request.host in request, 'Invalid request, host is required if default is missing'
            host = request.host
            
        if requestCnt.source is not None:
            assert isinstance(requestCnt.source, IInputStream), 'Invalid request source %s' % requestCnt.source
            body = requestCnt.source.read(requestCnt.length)
        else: body = None
        
        if request.parameters: parameters = urlencode(request.parameters)
        else: parameters = None

        if request.headers: headers = dict(request.headers)
        else: headers = {}
        CONNECTION.put(headers, CONNECTION_KEEP)

        retries, rsp = 0, None
        while retries < self.maximumRetries:
            connection = self._connection(host)
            try:
                uri = urlunsplit(('', '', '/%s' % request.uri, parameters, '')).lower()
                assert log.debug('Going to forward to uri %s' % uri) or True
                connection.putrequest(request.method, uri, skip_host=True, skip_accept_encoding=True)
                for hname, hvalue in headers.items(): connection.putheader(hname, hvalue)
                connection.endheaders(body)
            except socket.error as e:
                SERVICE_UNAVAILABLE.set(response)
                if e.errno == 111: response.text = 'Connection refused'
                else: response.text = str(e)
                return
            
            try: rsp = connection.getresponse()
            except BadStatusLine as e:
                if e.line == '':
                    retries += 1
                    continue  # We try again with a new connection, this one might be closed.
            break
        
        if rsp is None:
            PATH_NOT_FOUND.set(response)
            return
            
        response.status = rsp.status
        response.code = response.text = rsp.reason
        response.headers = dict(rsp.headers)
        
        responseCnt.source = Recycle(self._pool[host], rsp, connection)
        
        if self.removeHeaders: remove(response, self.removeHeaders)
        
    # ----------------------------------------------------------------
    
    def _connection(self, host:str):
        '''
        Provides a connection to work with.
        '''
        if host in self._pool:
            pool = self._pool[host]
            if pool:
                return pool.pop()
        else:
            self._pool[host] = []

        port = self.externalPort
        hostTokens = host.split(':')
        if len(hostTokens) > 1:
            port = int(hostTokens[1])
            host = hostTokens[0]

        return HTTPConnection(host, port)

# --------------------------------------------------------------------

class Recycle(IInputStreamClosable):
    '''
    Wrapper for @see: IInputStreamClosable that ensures the recycle of the connection on source close.
    '''
    __slots__ = ('_pool', '_stream', '_connection')
    
    def __init__(self, pool, stream, connection):
        '''
        Construct the recycle.
        '''
        self._pool = pool
        self._stream = stream
        self._connection = connection
        
    def read(self, nbytes=None):
        '''
        @see: IInputStreamClosable.read
        '''
        assert self._stream is not None, 'Stream is closed'
        return self._stream.read(nbytes)
    
    def close(self):
        if self._stream:
            self._stream.close()
            self._pool.append(self._connection)
            self._stream = None
            self._connection = None
