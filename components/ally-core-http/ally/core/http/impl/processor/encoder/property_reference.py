'''
Created on Mar 18, 2013

@package: ally core http
@copyright: 2011 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides the reference types encoding.
'''

from ally.api.operator.type import TypeProperty
from ally.api.type import TypeReference, Type
from ally.container.ioc import injected
from ally.core.http.impl.index import NAME_BLOCK_CLOB, ACTION_REFERENCE
from ally.core.spec.transform import ITransfrom, IRender
from ally.design.processor.attribute import requires, defines, optional
from ally.design.processor.context import Context
from ally.design.processor.handler import HandlerProcessor
from ally.support.util_spec import IDo
from ally.core.impl.processor.encoder.base import ExportingSupport

# --------------------------------------------------------------------

class Create(Context):
    '''
    The create encoder context.
    '''
    # ---------------------------------------------------------------- Defined
    encoder = defines(ITransfrom, doc='''
    @rtype: IEncoder
    The encoder for the reference.
    ''')
    # ---------------------------------------------------------------- Required
    name = optional(str)
    # ---------------------------------------------------------------- Required
    objType = requires(Type)

class Support(Context):
    '''
    The encoder support context.
    '''
    # ---------------------------------------------------------------- Required
    doEncodePath = requires(IDo)
    
# --------------------------------------------------------------------

propertyReferenceEncodeExport = ExportingSupport(Support)
# The property reference support export.

@injected
class PropertyReferenceEncode(HandlerProcessor):
    '''
    Implementation for a handler that provides the references types encoding.
    '''
    
    nameRef = 'href'
    # The reference attribute name.
    
    def __init__(self):
        assert isinstance(self.nameRef, str), 'Invalid reference name %s' % self.nameRef
        super().__init__()
        
    def process(self, chain, create:Create, **keyargs):
        '''
        @see: HandlerProcessor.process
        
        Create the collection encoder.
        '''
        assert isinstance(create, Create), 'Invalid create %s' % create
        
        if create.encoder is not None: return 
        # There is already an encoder, nothing to do.
        if not isinstance(create.objType, TypeProperty): return 
        # The type is not for a property, nothing to do, just move along
        assert isinstance(create.objType, TypeProperty)
        if not isinstance(create.objType.type, TypeReference): return 
        # The type is not a reference, just move along
        
        if Create.name in create and create.name: name = create.name
        else: name = create.objType.name
        assert isinstance(name, str), 'Invalid name %s' % name
        create.encoder = EncoderReference(name, self.nameRef)

# --------------------------------------------------------------------

class EncoderReference(ITransfrom):
    '''
    Implementation for a @see: ITransfrom for references types.
    '''
    
    def __init__(self, name, nameRef):
        '''
        Construct the reference encoder.
        '''
        assert isinstance(name, str), 'Invalid name %s' % name
        assert isinstance(nameRef, str), 'Invalid reference name %s' % nameRef
        
        self.name = name
        self.nameRef = nameRef
        
    def transform(self, value, target, support):
        '''
        @see: ITransfrom.transform
        '''
        assert isinstance(target, IRender), 'Invalid target %s' % target
        assert isinstance(support, Support), 'Invalid support %s' % support
        assert isinstance(support.doEncodePath, IDo), 'Invalid path encoder %s' % support.doEncodePath
        
        target.beginObject(self.name, attributes={self.nameRef: support.doEncodePath(value)},
                           indexBlock=NAME_BLOCK_CLOB, indexAttributesCapture={self.nameRef: ACTION_REFERENCE}).end()
