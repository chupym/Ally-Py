'''
Created on Jan 12, 2012

@package: ally core plugin
@copyright: 2012 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides the setup registry for the plugins.
'''

from ..cdm.local_cdm import contentDeliveryManager
from ally.container import ioc
from ally.container.proxy import proxyWrapFor
from cdm.spec import ICDM
from functools import partial

# --------------------------------------------------------------------

def registerService(service, binders=None):
    '''
    A listener to register the service.
    
    @param service: object
        The service to be registered.
    @param binders: list[Callable]|tuple(Callable)
        The binders used for the registered services.
    '''
    proxy = proxyWrapFor(service)
    if binders:
        for binder in binders: binder(proxy)
    services().append(proxy)

def addService(*binders):
    '''
    Create listener to register the service with the provided binders.
    
    @param binders: arguments[Callable]
        The binders used for the registered services.
    '''
    return partial(registerService, binders=binders)

# --------------------------------------------------------------------

@ioc.entity
def cdmGUI() -> ICDM:
    '''
    The content delivery manager (CDM) for the plugin's static resources
    '''
    return contentDeliveryManager()

@ioc.entity
def services():
    '''
    The plugins services that will be registered automatically.
    '''
    return []
