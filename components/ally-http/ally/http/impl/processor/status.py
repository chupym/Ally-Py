'''
Created on Feb 1, 2013

@package: ally core http
@copyright: 2011 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides the status and status text population based on codes.
'''

from ally.container.ioc import injected
from ally.design.processor.attribute import requires, defines
from ally.design.processor.context import Context
from ally.design.processor.handler import HandlerProcessor
from ally.api.type import Input

# --------------------------------------------------------------------

class Invoker(Context):
    '''
    The invoker context.
    '''
    # ---------------------------------------------------------------- Required
    decodingContent = requires(Context)
    inputContent = requires(Input)
    
class Request(Context):
    '''
    The request context.
    '''
    # ---------------------------------------------------------------- Required
    invoker = requires(Context)
    method = requires(str)
    
class Response(Context):
    '''
    The response context.
    '''
    # ---------------------------------------------------------------- Required
    code = requires(str)
    # ---------------------------------------------------------------- Defined
    status = defines(int)
    text = defines(str)

# --------------------------------------------------------------------

@injected
class StatusHandler(HandlerProcessor):
    '''
    Provides the code to status handler.
    '''

    codeToStatus = dict
    # A dictionary containing as a key the string code and as a value the integer status code.
    codeToText = dict
    # A dictionary containing as a key the string code and as a value the string text message for the code.

    def __init__(self):
        '''
        Construct the encoder.
        '''
        assert isinstance(self.codeToStatus, dict), 'Invalid code to status mapping %s' % self.codeToStatus
        assert isinstance(self.codeToText, dict), 'Invalid code to text mapping %s' % self.codeToText
        if __debug__:
            for code, status in self.codeToStatus.items():
                assert isinstance(code, str), 'Invalid code %s' % code
                assert isinstance(status, int) or callable(status), 'Invalid status %s' % status
            for code, text in self.codeToText.items():
                assert isinstance(code, str), 'Invalid code %s' % code
                assert isinstance(text, str) or callable(text), 'Invalid text %s' % text
        super().__init__(Invoker=Invoker)

    def process(self, chain, request:Request, response:Response, **keyargs):
        '''
        @see: HandlerProcessor.process
        
        Process the status.
        '''
        assert isinstance(request, Request), 'Invalid request %s' % request
        assert isinstance(response, Response), 'Invalid response %s' % response
        assert isinstance(response.code, str), 'Invalid response code %s' % response.code
        
        if request.invoker:
            assert isinstance(request.invoker, Invoker)
            hasContent = request.invoker.decodingContent is not None or request.invoker.inputContent is not None
        else: hasContent = False
        
        status = self.codeToStatus.get(response.code)
        if status is not None and callable(status): status = status(request.method, hasContent)
        if response.status is None:
            if status is None: ValueError('Cannot produce a status for code \'%s\'' % response.code)
            response.status = status
        elif status is not None: response.status = status
            
        text = self.codeToText.get(response.code)
        if text is not None and callable(text): text = text(request.method, hasContent)
        if text is not None:
            response.text = text
