'''
Created on Jan 15, 2013

@package: support acl
@copyright: 2012 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides the acl setup.
'''

from acl.right_sevice import RightService
from acl.spec import Acl, TypeAcl
from ally.container import ioc
from ally.internationalization import NC_

# --------------------------------------------------------------------

def aclRight(name, description) -> RightService:
    ''' Create an ACL general right '''
    b = RightService(name, description)
    aclType().add(b)
    return b

# --------------------------------------------------------------------

@ioc.entity
def acl() -> Acl: return Acl()

@ioc.entity
def aclType() -> TypeAcl:
    b = TypeAcl(NC_('security', 'Access control layer'), NC_('security',
    'Right type for the basic access control layer right setups'))
    acl().add(b)
    return b

# --------------------------------------------------------------------

setup = ioc.before(acl)
