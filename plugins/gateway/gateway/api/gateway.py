'''
Created on Jan 28, 2013

@package: gateway
@copyright: 2012 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

API specifications for gateway.
'''

from ally.api.config import model, service, call
from ally.api.option import SliceAndTotal  # @UnusedImport
from ally.api.type import List, Iter, Dict
from ally.support.api.entity_named import Entity, IEntityNQService

# --------------------------------------------------------------------

@model
class Identifier:
    '''
    Provides the gateway identifier.        
        Clients -   contains the client IPs or names regexes that needs to match in order to validate the gateway, if
                    none is provided then the gateway applies to all. At least one client IP needs to match to consider
                    the navigation valid.
        Pattern -   contains the regex that needs to match with the requested URI. The pattern needs to produce, if is the
                    case, capturing groups that can be used by the Filters or Navigate.
        Headers -   The headers to be filtered in order to validate the navigation. The headers are provided as regexes that
                    need to be matched. In case of headers that are paired as name and value the regex will receive the matching
                    string as 'Name:Value', the name is not allowed to contain ':'. At least one header needs to match to consider
                    the navigation valid.
        Methods -   The list of allowed methods for the request, if no method is provided then all methods are considered
                    valid. At least one method needs to match to consider the navigation valid.
        Errors -    The list of errors codes that are considered to be handled by this Gateway entry, if no error is provided
                    then it means the entry is not solving any error navigation. At least one error needs to match in order
                    to consider the navigation valid. The gateways that solve errors will receive also parameters for error
                        status - the status code of the error
                        allow - the method name(s) allowed, this will be provided in case of status 405 (Method not allowed)
    '''
    # The request identification attributes
    Clients = List(str)
    Pattern = str
    Headers = List(str)
    Methods = List(str)
    Errors = List(int)

@model
class Gateway(Identifier):
    '''
    Provides the gateway.
        Filters -   contains a list of URIs that need to be called in order to allow the gateway Navigate. The filters
                    are provided as 'group:URI' where group is a number from 1 to n where n is the number of capture 
                    groups  obtained from the Pattern, the filter URI is allowed to have place holders of form '*'
                    where the provided group value will be injected. In order to validate navigation at least one filter
                    from the each group will have to return an allowed access, also pre populated parameters are allowed
                    for filter URI.
        Host -      The host where the request needs to be resolved, if not provided the request will be delegated to the
                    default host.
        Protocol -  The protocol to be used in the communication with the server that handles the request, if not provided
                    the request will be delegated using the default protocol.
        Navigate -  A pattern like string of forms like '*', 'resources/*' or 'redirect/Model/{1}'. The pattern is allowed to
                    have place holders and also the '*' which stands for the actual called URI, also parameters are allowed
                    for navigate URI, the parameters will be appended to the actual parameters.
        PutHeaders -The headers to be put on the forwarded requests.
        Exclude -   The list of index block names to be excluded from the response.
    '''
    # The navigation attributes
    Filters = List(str)
    Host = str
    Protocol = str
    Navigate = str
    PutHeaders = Dict(str, str)
    # The response attributes
    Exclude = List(str)

@model
class Allowed:
    '''
    Defines the allowed model that is returned by filters.
    '''
    IsAllowed = bool

# --------------------------------------------------------------------
   
@model(domain='Gateway')
class Custom(Entity, Gateway):
    '''
    Provides the custom defined gateway.
        Name -      the unique name for the gateway.
    '''
    Priority = int

# --------------------------------------------------------------------

@service((Entity, Custom))
class IGatewayService(IEntityNQService):
    '''
    The gateway service that provides the anonymous gateways.
    '''

    @call
    def getAnonymous(self) -> Iter(Gateway):
        '''
        Get the gateways that apply for an anonymous access.
        '''
