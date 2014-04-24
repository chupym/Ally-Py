'''
Created on Jan 9, 2012

@package: gateway
@copyright: 2012 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Contains the services for gateway.
'''
    
from ..plugin.registry import registerService
from .database import binders
from ally.container import support, ioc, bind, app
from ally.container.support import entityFor
from ally.design.processor.assembly import Assembly
from ally.support.api.util_service import copyContainer
from gateway.api.gateway import IGatewayService, Custom
import logging
import re

# --------------------------------------------------------------------

log = logging.getLogger(__name__)

asPattern = lambda rootURI: '^%s(?:/|(?=\\.)|$)(.*)' % re.escape(rootURI) if rootURI else '(.*)'
# Make the root URI into a gateway pattern.

# --------------------------------------------------------------------

registerDatabaseGateway = gatewayMethodMerge = registerMethodOverride = support.notCreated  # Just to avoid errors

SERVICES = 'gateway.api.**.I*Service'

bind.bindToEntities('gateway.impl.**.*Alchemy', 'gateway.core.impl.**.*Alchemy', binders=binders)
support.createEntitySetup('gateway.impl.**.*', 'gateway.core.impl.**.*')
support.listenToEntities(SERVICES, listeners=registerService)
support.loadAllEntities(SERVICES)

# --------------------------------------------------------------------

@ioc.entity
def assemblyAnonymousGateways() -> Assembly:
    ''' The assembly used for generating anonymous gateways'''
    return Assembly('Anonymous gateways')

# --------------------------------------------------------------------

@ioc.entity
def defaultGateways() -> list: return []

# --------------------------------------------------------------------

@ioc.before(assemblyAnonymousGateways)
def updateAssemblyAnonymousGateways():
    assemblyAnonymousGateways().add(registerDatabaseGateway(), gatewayMethodMerge(), registerMethodOverride())

@app.populate(app.DEVEL)
def populateDefaulyGateways():
    serviceGateway = entityFor(IGatewayService)
    assert isinstance(serviceGateway, IGatewayService)
    
    for priority, data in enumerate(defaultGateways()):
        custom = copyContainer(data, Custom())
        assert isinstance(custom, Custom)
        custom.Priority = priority
        serviceGateway.delete(custom.Name)
        serviceGateway.insert(custom)
