'''
Created on Jan 28, 2013

@package: gateway
@copyright: 2012 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Implementation for the default anonymous gateway data.
'''

from ..api.gateway import IGatewayService, Gateway, Identifier, Custom
from ..meta.gateway import GatewayData
from ally.api.error import InputError, IdError
from ally.container import wire
from ally.container.ioc import injected
from ally.container.support import setup
from ally.design.processor.assembly import Assembly
from ally.design.processor.attribute import requires
from ally.design.processor.context import Context
from ally.design.processor.execution import Processing, FILL_ALL
from ally.internationalization import _
from ally.support.api.util_service import namesFor, copyContainer
from collections import Iterable
from sql_alchemy.support.util_service import SessionSupport, iterateCollection
from hashlib import sha512
import json
import re
from ally.api.validate import validate, Mandatory

# --------------------------------------------------------------------

class Solicit(Context):
    '''
    The solicit context.
    '''
    # ---------------------------------------------------------------- Required
    gateways = requires(Iterable)
    
# --------------------------------------------------------------------

@injected
@setup(IGatewayService, name='gatewayService')
@validate(Mandatory(Custom.Name))
class GatewayServiceAlchemy(IGatewayService, SessionSupport):
    '''
    Implementation for @see: IGatewayService that provides the default anonymous gateway data.
    '''
    
    assemblyAnonymousGateways = Assembly; wire.entity('assemblyAnonymousGateways')
    # The assembly to be used for generating gateways
    
    def __init__(self):
        assert isinstance(self.assemblyAnonymousGateways, Assembly), \
        'Invalid assembly gateways %s' % self.assemblyAnonymousGateways
        
        self._processing = self.assemblyAnonymousGateways.create(solicit=Solicit)
         
    def getAnonymous(self):
        '''
        @see: IGatewayService.getAnonymous
        '''
        proc = self._processing
        assert isinstance(proc, Processing), 'Invalid processing %s' % proc
        
        solicit = proc.execute(FILL_ALL).solicit
        assert isinstance(solicit, Solicit), 'Invalid solicit %s' % solicit
        return solicit.gateways or ()

    # ----------------------------------------------------------------
    
    def getById(self, name):
        '''
        @see: IGatewayService.getById
        '''
        assert isinstance(name, str), 'Invalid gateway name %s' % name
        data = self.session().query(GatewayData).get(name)
        if data is None: raise IdError()
        assert isinstance(data, GatewayData), 'Invalid data %s' % data
        
        gatewayData = json.loads(str(data.identifier, 'utf8'))
        gatewayData.update(json.loads(str(data.navigate, 'utf8')))
        gateway = copyContainer(gatewayData, Custom())
        gateway.Name = name
        return gateway
    
    def getAll(self, **options):
        '''
        @see: IGatewayService.getAll
        '''
        return iterateCollection(self.session().query(GatewayData.name), **options)
    
    def insert(self, gateway):
        '''
        @see: IGatewayService.insert
        '''
        assert isinstance(gateway, Custom), 'Invalid gateway %s' % gateway
        assert isinstance(gateway.Name, str), 'Invalid name %s' % gateway.Name
        if gateway.Clients:
            for pattern in gateway.Clients:
                try: re.compile(pattern)
                except: raise RegexError(Gateway.Clients)
        if gateway.Pattern:
            try: re.compile(gateway.Pattern)
            except: raise RegexError(Gateway.Pattern)
        if gateway.Headers:
            for pattern in gateway.Headers:
                try: re.compile(pattern)
                except: raise RegexError(Gateway.Headers)
        
        identifier, navigate = self.dataFor(gateway)

        data = GatewayData()
        data.name = gateway.Name
        data.priority = gateway.Priority
        data.identifier, data.navigate = identifier.encode(), navigate.encode()
        data.hash = sha512(data.identifier).hexdigest()
        
        self.session().add(data)
        return gateway.Name
    
    def update(self, gateway):
        '''
        @see: IGatewayService.update
        '''
        assert isinstance(gateway, Custom), 'Invalid gateway %s' % gateway

        data = self.session().query(GatewayData).get(gateway.Name)
        if data is None: raise IdError()
        assert isinstance(data, GatewayData), 'Invalid data %s' % data
        data.navigate = self.dataFor(gateway, onlyNavigate=True).encode()
        if Custom.Priority in gateway: data.priority = gateway.Priority
        
    def delete(self, name):
        '''
        @see: IGatewayService.delete
        '''
        assert isinstance(name, str), 'Invalid gateway name %s' % name
        return self.session().query(GatewayData).filter(GatewayData.name == name).delete() > 0

    # ----------------------------------------------------------------
    
    def dataFor(self, gateway, onlyNavigate=False):
        '''
        Provides the json serialized data for the gateway.
        '''
        assert isinstance(gateway, Gateway), 'Invalid gateway %s' % gateway
        
        navigateData, namesIdentifier = {}, set(namesFor(Identifier))
        if not onlyNavigate: identifierData = {}
        for name in namesFor(Gateway):
            if onlyNavigate and name in namesIdentifier: continue
            
            value = getattr(gateway, name)
            if isinstance(value, list): value = sorted(value)
            if name in namesIdentifier: identifierData[name] = value
            else: navigateData[name] = value
        
        navigate = json.dumps(navigateData, sort_keys=True)
        if onlyNavigate: return navigate
        
        identifier = json.dumps(identifierData, sort_keys=True)
        return identifier, navigate

# --------------------------------------------------------------------

class RegexError(InputError):
    '''
    Raised for invalid regex pattern.
    '''    
    
    def __init__(self, prop):
        super().__init__(_('Invalid regex pattern'), prop)
