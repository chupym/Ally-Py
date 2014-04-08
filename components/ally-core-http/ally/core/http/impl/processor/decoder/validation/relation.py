'''
Created on Oct 30, 2013

@package: ally core
@copyright: 2011 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides the relation validation.
'''

import logging

from ally.api.error import InputError
from ally.api.operator.type import TypeProperty, TypePropertyContainer, \
    TypeModel
from ally.api.validate import Relation
from ally.container.ioc import injected
from ally.core.impl.processor.decoder.base import ExportingTarget
from ally.core.spec.resources import Converter
from ally.design.processor.assembly import Assembly
from ally.design.processor.attribute import requires, definesIf, defines
from ally.design.processor.branch import Branch
from ally.design.processor.context import Context
from ally.design.processor.execution import Processing
from ally.design.processor.handler import HandlerBranching
from ally.http.spec.server import HTTP_GET
from ally.support.util_spec import IDo
from ally.core.impl.processor.decoder.base import addError
from ally.internationalization import _
from ally.api.config import UPDATE

# --------------------------------------------------------------------
log = logging.getLogger(__name__)

# --------------------------------------------------------------------

class Invoker(Context):
    '''
    The invoker context.
    '''
    # ---------------------------------------------------------------- Required
    method = requires(int)
    node = requires(Context)
    doInvoke = requires(IDo)
    location = requires(str)

class Node(Context):
    '''
    The node context.
    '''
    # ---------------------------------------------------------------- Defined
    parent = requires(Context)
    invokersGet = requires(dict)
    
class Decoding(Context):
    '''
    The model decoding context.
    '''
    # ---------------------------------------------------------------- Defined
    relation = definesIf(Context, doc='''
    @rtype: Invoker
    The invoker that the decoding is in relation with.
    ''')
    # ---------------------------------------------------------------- Required
    validations = requires(list)
    property = requires(TypeProperty)
    doSet = requires(IDo)

class Target(Context):
    '''
    The target context.
    '''
    # ---------------------------------------------------------------- Required
    arg = requires(object)
    
class RequestTarget(Context):
    '''
    The request context.
    '''
    # ---------------------------------------------------------------- Required
    nodesValues = requires(dict)
    converterPath = requires(Converter)

class Request(Context):
    '''
    The request context.
    '''
    # ---------------------------------------------------------------- Defined
    scheme = defines(str)
    node = defines(Context)
    nodesValues = defines(dict)
    converterPath = defines(Converter)
    method = defines(str)
    
class Response(Context):
    '''
    The response context.
    '''
    # ---------------------------------------------------------------- Required
    obj = requires(object)
    errorInput = requires(InputError)
        
# --------------------------------------------------------------------

validateRelationExport = ExportingTarget(Target, request=RequestTarget)
# Context export for dictionary item decode.

@injected
class ValidateRelation(HandlerBranching):
    '''
    Implementation for a handler that provides the relation validation.
    '''
    
    assemblyInvoking = Assembly
    # The assembly used for invoking in order to validate the relation.
    
    def __init__(self):
        assert isinstance(self.assemblyInvoking, Assembly), 'Invalid assembly %s' % self.assemblyInvoking
        super().__init__(Branch(self.assemblyInvoking).using(request=Request, response=Response), Node=Node)
    
    def process(self, chain, processing, invoker:Invoker, decoding:Decoding, **keyargs):
        '''
        @see: HandlerProcessor.process
        
        Process the maximum length validation.
        '''
        assert isinstance(invoker, Invoker), 'Invalid invoker %s' % invoker
        assert isinstance(decoding, Decoding), 'Invalid decoding %s' % decoding
        if not invoker.node: return
        
        model, forSelfId = None, False
        if decoding.validations: 
            model, validations = None, []
            for validation in decoding.validations:
                if isinstance(validation, Relation):
                    assert isinstance(validation, Relation)
                    assert isinstance(validation.property, TypePropertyContainer), 'Invalid property %s' % property
                    if model is None: model = validation.property.container
                    elif model != validation.property.container:
                        log.warn('Incompatible relation model %s and model %s', model, validation.property.container)
                else: validations.append(validation)
            
            decoding.validations = validations
            
        if model is None and decoding.property and invoker.method == UPDATE:
            assert isinstance(decoding.property, TypeProperty)
            if decoding.property.parent.propertyId == decoding.property:
                # Validating the existance of his own id.
                model = decoding.property.parent
                forSelfId = True

        if model is not None:
            assert isinstance(model, TypeModel), 'Invalid model %s' % model
            assert isinstance(model.propertyId, TypeProperty), 'Invalid model id %s' % model.propertyId
            assert isinstance(invoker.node, Node), 'Invalid node %s' % invoker.node
            
            relation = None
            if invoker.node.invokersGet: relation = invoker.node.invokersGet.get(model.propertyId)
            if relation is None:
                if not forSelfId:
                    log.warn('Cannot a get invoker for %s, at:%s', model.propertyId, invoker.location)
            else:
                if Decoding.relation in decoding: decoding.relation = relation
                decoding.doSet = self.createSet(decoding.doSet, decoding.property,
                                                processing, relation, forSelfId)

    # ----------------------------------------------------------------
    
    def createSet(self, wrapped, prop, processing, relation, forSelfId):
        '''
        Create the do set to use with validation.
        '''
        assert callable(wrapped), 'Invalid wrapped set %s' % wrapped
        assert isinstance(prop, TypeProperty), 'Invalid property %s' % prop
        def doSet(target, value):
            assert isinstance(processing, Processing), 'Invalid processing %s' % processing
            assert isinstance(relation, Invoker), 'Invalid invoker %s' % relation
            assert isinstance(target, Target), 'Invalid target %s' % target
            assert isinstance(target.arg.request, RequestTarget), 'Invalid request %s' % target.arg.request
            
            arg = dict(target.arg.__dict__)
            request = processing.ctx.request()
            assert isinstance(request, Request)
            request.scheme = target.arg.request.scheme
            request.node = relation.node
            request.converterPath = target.arg.request.converterPath
            request.method = HTTP_GET
            if target.arg.request.nodesValues:
                request.nodesValues = dict(target.arg.request.nodesValues)
            else: request.nodesValues = {}
            assert isinstance(request.converterPath, Converter)
            request.nodesValues[relation.node.parent] = request.converterPath.asString(value, prop)
            
            arg['request'] = request
            arg['response'] = processing.ctx.response()
            
            arg = processing.execute(**arg)
            assert isinstance(arg.response, Response), 'Invalid response %s' % arg.response
            
            if arg.response.errorInput or arg.response.obj is None:
                if forSelfId: addError(target, 'other', prop, _('Unknown value'))
                else: addError(target, 'missing', prop, _('Relation constraint failed'))
            wrapped(target, value)
        return doSet
