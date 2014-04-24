'''
Created on Aug 14, 2013

@package: gateway
@copyright: 2012 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Processor that adds Gateway objects based on database GatewayData.
'''

from ally.container import wire
from ally.container.ioc import injected
from ally.container.support import setup
from ally.design.processor.attribute import defines
from ally.design.processor.context import Context
from ally.design.processor.handler import HandlerProcessor, Handler
from ally.support.api.util_service import copyContainer
from collections import Iterable
from gateway.api.gateway import Gateway
from gateway.meta.gateway import GatewayData
from sql_alchemy.support.util_service import SessionSupport
import itertools
import json

# --------------------------------------------------------------------

@setup(name='databaseGatewayProvider')
class DatabaseGatewayProviderAlchemy(SessionSupport):
    '''
    The SQL alchemy database gateways provider.
    '''
    
    def iterateGateways(self):
        '''
        Iterates all the custom database gateways.
        
        @return: Iterable(Gateway)
            The gateways for the custom database gateways.
        '''
        gateways = []
        for data in self.session().query(GatewayData).order_by(GatewayData.priority).all():
            assert isinstance(data, GatewayData), 'Invalid data %s' % data

            gatewayData = json.loads(str(data.identifier, 'utf8'))
            gatewayData.update(json.loads(str(data.navigate, 'utf8')))
            gateways.append(copyContainer(gatewayData, Gateway()))

        return gateways

# --------------------------------------------------------------------

class Solicit(Context):
    '''
    The solicit context.
    '''
    # ---------------------------------------------------------------- Defined
    gateways = defines(Iterable, doc='''
    @rtype: Iterable(Gateway)
    The default gateways.
    ''')

# --------------------------------------------------------------------

@injected
@setup(Handler, name='registerDatabaseGateway')
class RegisterDatabaseGatewayHandler(HandlerProcessor):
    '''
    Provides the handler that populates Gateway objects based on database GatewayData.
    '''
    
    databaseGatewayProvider = DatabaseGatewayProviderAlchemy; wire.entity('databaseGatewayProvider')
    
    def __init__(self):
        assert isinstance(self.databaseGatewayProvider, DatabaseGatewayProviderAlchemy), \
        'Invalid database gateway provider %s' % self.databaseGatewayProvider
        super().__init__()
    
    def process(self, chain, solicit:Solicit, **keyargs):
        '''
        @see: HandlerProcessor.process
        
        Adds the databse gateways.
        '''
        assert isinstance(solicit, Solicit), 'Invalid solicit %s' % solicit
        
        gateways = self.databaseGatewayProvider.iterateGateways()
        if solicit.gateways is not None: solicit.gateways = itertools.chain(solicit.gateways, gateways)
        else: solicit.gateways = gateways
