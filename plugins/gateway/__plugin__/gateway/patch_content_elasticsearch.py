'''
Created on April 16, 2014

@package: gateway
@copyright: 2014 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Adrian Magdas

Provides the elastic search proxy for content.
'''

from .service import asPattern, defaultGateways
from ally.container import ioc
import logging
from ally.http.spec.server import HTTP_GET

log = logging.getLogger(__name__)

#/Content/Item/Id - works 
#/Content/_search - retrieve all content
#/Content/Item/_search - retrieve all items

@ioc.before(defaultGateways)
def updateGatewayWithElasticsearchProxy():
    print('Extending gateways with elastic search ones')
    defaultGateways().extend([
        {
            'Name': 'get_content_item_elastic',
            'Pattern': '^api/Content/Item[\/]',
            'Methods': [HTTP_GET],
            #'Host': 'localhost:9200',
            'Navigate': 'localhost:9200/content/item/_search'
            },
        {
            'Name': 'get_content_elastic',
            'Pattern': '^api/Content[\/]',
            'Methods': [HTTP_GET],
            #'Host': 'localhost:9200',
            'Navigate': 'localhost:9200/content/_search',
            },
        ])
