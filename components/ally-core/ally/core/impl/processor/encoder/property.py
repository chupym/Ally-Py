'''
Created on Mar 8, 2013

@package: ally core
@copyright: 2011 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides the primitive properties encoder.
'''

from ally.api.operator.type import TypeProperty
from ally.api.type import Iter, Type, Dict
from ally.container.ioc import injected
from ally.core.spec.resources import Converter
from ally.core.spec.transform.encdec import IEncoder, IRender
from ally.design.processor.attribute import requires, defines
from ally.design.processor.context import Context
from ally.design.processor.handler import HandlerProcessor
from collections import Iterable

# --------------------------------------------------------------------

class Create(Context):
    '''
    The create encoder context.
    '''
    # ---------------------------------------------------------------- Defined
    encoder = defines(IEncoder, doc='''
    @rtype: IEncoder
    The encoder for the property.
    ''')    
    # ---------------------------------------------------------------- Required
    name = requires(str)
    objType = requires(object)

class Support(Context):
    '''
    The encoder support context.
    '''
    # ---------------------------------------------------------------- Required
    converterContent = requires(Converter)
    
# --------------------------------------------------------------------

@injected
class PropertyEncode(HandlerProcessor):
    '''
    Implementation for a handler that provides the primitive properties values encoding.
    '''
    
    def __init__(self):
        super().__init__(Support=Support)
        
    def process(self, chain, create:Create, **keyargs):
        '''
        @see: HandlerProcessor.process
        
        Create the property encoder.
        '''
        assert isinstance(create, Create), 'Invalid create %s' % create
        
        if create.encoder is not None: return 
        # There is already an encoder, nothing to do.
        if not isinstance(create.objType, TypeProperty): return 
        # The type is not for a property, nothing to do, just move along
        
        valueType = create.objType.type
        assert isinstance(create.name, str), 'Invalid property name %s' % create.name
        create.encoder = EncoderProperty(create.name, valueType)

# --------------------------------------------------------------------

class EncoderProperty(IEncoder):
    '''
    Implementation for a @see: IEncoder for properties.
    '''
    
    def __init__(self, name, valueType):
        '''
        Construct the property encoder.
        '''
        assert isinstance(name, str), 'Invalid property name %s' % name
        assert isinstance(valueType, Type), 'Invalid value type %s' % valueType
        self.name = name
        self.valueType = valueType
        
    def encode(self, obj, target, support):
        '''
        @see: IEncoder.encode
        '''
        assert isinstance(target, IRender), 'Invalid target %s' % target
        assert isinstance(support, Support), 'Invalid support %s' % support
        assert isinstance(support.converterContent, Converter), 'Invalid converter %s' % support.converterContent
        
        if isinstance(self.valueType, Iter):
            assert isinstance(obj, Iterable), 'Invalid object %s' % obj
            itemType = self.valueType.itemType
            value = [support.converterContent.asString(item, itemType) for item in obj]
        elif isinstance(self.valueType, Dict):
            assert isinstance(obj, dict), 'Invalid object %s' % obj
            keyType = self.valueType.keyType
            valueType = self.valueType.valueType
            value = {support.converterContent.asString(key, keyType): support.converterContent.asString(item, valueType)
                     for key, item in obj.items()}
        else:
            value = support.converterContent.asString(obj, self.valueType)
        target.property(self.name, value)
        
