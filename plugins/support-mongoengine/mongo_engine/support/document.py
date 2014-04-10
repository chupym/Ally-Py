'''
Created on Jan 5, 2012

@package: support mongoengine
@copyright: 2012 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides support for mongo engine document handling.
'''

from mongoengine.queryset.manager import QuerySetManager
from mongoengine.document import Document, EmbeddedDocument

# --------------------------------------------------------------------

class Base(Document):
    '''
    Provides the base for Document mapping.
    '''
    objects = QuerySetManager()  # Just to have type hinting no real value.
    meta = {'allow_inheritance': True, 'abstract': True}

class BaseEmbedded(EmbeddedDocument):
    '''
    Provides the base for EmbeddedDocument mapping.
    '''
    objects = QuerySetManager()  # Just to have type hinting no real value.
    meta = {'allow_inheritance': True, 'abstract': True}
