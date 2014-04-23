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

@ioc.config
def elasticsearch_host():
    ''' The host for elastic search.
        Defaults to localhost:9200
    '''
    return 'localhost:9200'

@ioc.before(defaultGateways)
def updateGatewayWithElasticsearchProxy():
    defaultGateways().extend([
        {
            'Name': 'get_content_item_elastic',
            'Pattern': '^api/Elastic[\/](.*)',
            'Methods': [HTTP_GET],
            'Host': elasticsearch_host(),
            'Navigate': '/content/{1}/_search'
            }
        ])