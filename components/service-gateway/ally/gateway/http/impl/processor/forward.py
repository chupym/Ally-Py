'''
Created on Feb 8, 2013

@package: gateway service
@copyright: 2011 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides the forwarding processor.
'''

from ally.container.ioc import injected
from ally.design.processor.assembly import Assembly
from ally.design.processor.attribute import requires, defines
from ally.design.processor.branch import Branch
from ally.design.processor.context import Context
from ally.design.processor.execution import Processing, Chain
from ally.design.processor.handler import HandlerBranching
from ally.gateway.http.spec.gateway import IRepository
from ally.http.spec.headers import HeadersRequire
from urllib.parse import urlparse, parse_qsl
import logging

# --------------------------------------------------------------------

log = logging.getLogger(__name__)

# --------------------------------------------------------------------

class Gateway(Context):
    '''
    The gateway context.
    '''
    # ---------------------------------------------------------------- Required
    navigate = requires(str)
    putHeaders = requires(dict)
    host = requires(str)
    
class Match(Context):
    '''
    The match context.
    '''
    # ---------------------------------------------------------------- Required
    gateway = requires(Context)
    groupsURI = requires(tuple)
    
class Request(HeadersRequire):
    '''
    Context for request. 
    '''
    #----------------------------------------------------------------- Defines
    host = defines(str)
    # ---------------------------------------------------------------- Required
    uri = requires(str)
    parameters = requires(list)
    match = requires(Context)

# --------------------------------------------------------------------

@injected
class GatewayForwardHandler(HandlerBranching):
    '''
    Implementation for a handler that provides the gateway forward.
    '''
    
    assembly = Assembly
    # The assembly to be used in processing the request for the filters.
    assemblyByHost = Assembly
    
    def __init__(self):
        assert isinstance(self.assembly, Assembly), 'Invalid assembly %s' % self.assembly
        super().__init__(Branch(self.assembly).using('response', 'responseCnt').included(), 
                         Branch(self.assemblyByHost).using('response', 'responseCnt').included(),
                         Gateway=Gateway, Match=Match)

    def process(self, chain, processing, processingByHost, request:Request, **keyargs):
        '''
        @see: HandlerBranching.process
        
        Process the forward.
        '''
        assert isinstance(chain, Chain), 'Invalid chain %s' % chain
        assert isinstance(processing, Processing), 'Invalid processing %s' % processing
        assert isinstance(request, Request), 'Invalid request %s' % request
        if not request.match: return
        # No forwarding if there is no match on response
        
        assert isinstance(request.repository, IRepository), 'Invalid request repository %s' % request.repository
        match = request.match
        assert isinstance(match, Match), 'Invalid response match %s' % match
        assert isinstance(match.gateway, Gateway), 'Invalid gateway %s' % match.gateway
        
        if match.gateway.navigate:
            uri = match.gateway.navigate.replace('*', request.uri)
            try: uri = uri.format(None, *match.groupsURI)
            except IndexError:
                log.exception('Invalid navigate URI \'%s\' for groups %s' % (match.gateway.navigate, match.groupsURI))
                return
            url = urlparse(uri)
            request.uri = url.path.lstrip('/')
            parameters = parse_qsl(url.query, True, False)
            if request.parameters: parameters.extend(request.parameters)
            request.parameters = parameters
            request.host = match.gateway.host
        
        if match.gateway.putHeaders: request.headers.update(match.gateway.putHeaders)
        
        assert log.debug('Forwarding request to \'%s\'', request.uri) or True
        if match.gateway.host:
            chain.process(response=processingByHost.ctx.response(), responseCnt=processingByHost.ctx.responseCnt())
            chain.branch(processingByHost)
        else:
            chain.process(response=processing.ctx.response(), responseCnt=processing.ctx.responseCnt())
            chain.branch(processing)