'''
Created on Mar 7, 2013

@package: ally core
@copyright: 2011 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides the model encoder.
'''

from ally.api.operator.container import Model
from ally.api.operator.type import TypeModel, TypeProperty, TypeModelProperty
from ally.api.type import Iter, Boolean, Integer, Number, Percentage, String, \
    Time, Date, DateTime, typeFor
from ally.container.ioc import injected
from ally.core.spec.resources import Normalizer
from ally.core.spec.transform.encoder import DO_RENDER
from ally.core.spec.transform.render import IRender
from ally.design.processor.assembly import Assembly
from ally.design.processor.attribute import requires, defines, optional
from ally.design.processor.context import Context
from ally.design.processor.execution import Chain, Processing, CONSUMED
from ally.design.processor.handler import HandlerBranching
from ally.design.processor.processor import Included
from ally.exception import DevelError
from weakref import WeakKeyDictionary

# --------------------------------------------------------------------

class Support(Context):
    '''
    The encode support context.
    '''
    # ---------------------------------------------------------------- Required
    doAction = requires(int)
    normalizer = requires(Normalizer)

class EncodeModel(Context):
    '''
    The encode model context.
    '''
    # ---------------------------------------------------------------- Optional
    name = optional(str)
    attributes = optional(dict, doc='''
    @rtype: dictionary{string: string}
    The attributes to be used with the model rendering.
    ''')
    # ---------------------------------------------------------------- Required
    obj = requires(object)
    objType = requires(object)
    render = requires(IRender)
    
class EncodeProperty(Context):
    '''
    The encode property context.
    '''
    # ---------------------------------------------------------------- Defined
    name = defines(str, doc='''
    @rtype: string
    The name used to render the property with.
    ''')
    obj = defines(object, doc='''
    @rtype: object
    The value object of the property to be encoded.
    ''')
    objType = defines(object, doc='''
    @rtype: object
    The property type.
    ''')
    render = defines(IRender, doc='''
    @rtype: IRender
    The renderer to be used for output encoded data.
    ''')
    
# --------------------------------------------------------------------

@injected
class ModelEncode(HandlerBranching):
    '''
    Implementation for a handler that provides the model encoding.
    '''
    
    propertyEncodeAssembly = Assembly
    # The encode processors to be used for encoding properties.
    typeOrders = [Boolean, Integer, Number, Percentage, String, Time, Date, DateTime, Iter]
    # The type that define the order in which the properties should be rendered.
    
    def __init__(self):
        assert isinstance(self.propertyEncodeAssembly, Assembly), \
        'Invalid property encode assembly %s' % self.propertyEncodeAssembly
        assert isinstance(self.typeOrders, list), 'Invalid type orders %s' % self.typeOrders
        super().__init__(Included(self.propertyEncodeAssembly).using(encode=EncodeProperty))
        
        self.typeOrders = [typeFor(typ) for typ in self.typeOrders]
        self._cacheSort = WeakKeyDictionary()
        
    def process(self, chain, propertyProcessing, support:Support, encode:EncodeModel, **keyargs):
        '''
        @see: HandlerBranching.process
        
        Encode the model.
        '''
        assert isinstance(chain, Chain), 'Invalid chain %s' % chain
        assert isinstance(propertyProcessing, Processing), 'Invalid processing %s' % propertyProcessing
        assert isinstance(support, Support), 'Invalid support %s' % support
        assert isinstance(encode, EncodeModel), 'Invalid encode %s' % encode
        
        if not support.doAction & DO_RENDER:
            # If no rendering is required we just proceed, maybe other processors might do something
            chain.proceed()
            return
    
        if isinstance(encode.objType, TypeModel): 
            modelType = encode.objType
            propType = None
        elif isinstance(encode.objType, TypeModelProperty):
            propType = encode.objType
            assert isinstance(propType, TypeModelProperty)
            modelType = propType.parent
        else:  # The type is not for a model, nothing to do, just move along
            chain.proceed()
            return
        
        assert encode.obj is not None, 'An object is required for rendering'
        assert isinstance(modelType, TypeModel)
        assert isinstance(modelType.container, Model)
        
        assert isinstance(support.normalizer, Normalizer), 'Invalid normalizer %s' % support.normalizer
        assert isinstance(encode.render, IRender), 'Invalid render %s' % encode.render
        
        if EncodeModel.name in encode and encode.name: name = support.normalizer.normalize(encode.name)
        else: name = support.normalizer.normalize(modelType.container.name)
        if EncodeModel.attributes in encode: attributes = encode.attributes
        else: attributes = None
        
        encode.render.objectStart(name, attributes)
        if propType:
            encodeProperty = propertyProcessing.ctx.encode(render=encode.render)
            assert isinstance(encodeProperty, EncodeProperty), 'Invalid encode property %s' % encodeProperty
            encodeProperty.objType = propType
            encodeProperty.obj = encode.obj
            encodeProperty.name = propType.property
            if Chain(propertyProcessing).execute(CONSUMED, support=support, encode=encodeProperty, **keyargs):
                raise DevelError('Cannot encode %s' % propType)
        else:
            for propType in self.sortedTypes(modelType):
                if propType not in encode.obj: continue
                encodeProperty = propertyProcessing.ctx.encode(render=encode.render)
                assert isinstance(encodeProperty, EncodeProperty), 'Invalid encode property %s' % encodeProperty
                encodeProperty.objType = propType
                encodeProperty.obj = getattr(encode.obj, propType.property)
                encodeProperty.name = propType.property
                if Chain(propertyProcessing).execute(CONSUMED, support=support, encode=encodeProperty, **keyargs):
                    raise DevelError('Cannot encode %s' % propType)
        
        encode.render.objectEnd()
        
    # --------------------------------------------------------------------
    
    def sortedTypes(self, modelType):
        '''
        Provides the sorted properties type for the model type.
        '''
        sorted = self._cacheSort.get(modelType)
        if sorted is None:
            assert isinstance(modelType, TypeModel), 'Invalid type model %s' % modelType
            sorted = self._cacheSort[modelType] = list(modelType.propertyTypes())
            if modelType.hasId(): sorted.remove(modelType.propertyTypeId())
            sorted.sort(key=lambda propType: propType.property)
            sorted.sort(key=self.sortKey)
            if modelType.hasId(): sorted.insert(0, modelType.propertyTypeId())
        return sorted
    
    def sortKey(self, propType):
        '''
        Provides the sorting key for property types, used in sort functions.
        '''
        assert isinstance(propType, TypeProperty), 'Invalid property type %s' % propType

        for k, ord in enumerate(self.typeOrders):
            if propType.type == ord: break
        return k