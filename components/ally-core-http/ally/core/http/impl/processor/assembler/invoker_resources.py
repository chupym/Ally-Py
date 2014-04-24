'''
Created on Mar 18, 2013

@package: ally core http
@copyright: 2011 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides the resource paths encoding.
'''
# TODO: Gabrile: Move to encoders when they are refactored
from ally.container.ioc import injected
from ally.core.http.impl.index import NAME_BLOCK_REST, ACTION_REFERENCE
from ally.core.spec.transform import ITransfrom, IRender
from ally.design.processor.attribute import requires, defines
from ally.design.processor.context import Context
from ally.design.processor.handler import HandlerProcessor
from ally.http.spec.server import HTTP_GET
from ally.support.util import firstOf
from ally.support.util_spec import IDo
from ally.support.util_sys import locationStack
from collections import deque
from ally.api.operator.type import TypeModel
from itertools import chain

# --------------------------------------------------------------------

class Register(Context):
    '''
    The register context.
    '''
    # ---------------------------------------------------------------- Defined
    invokers = defines(list)
    # ---------------------------------------------------------------- Required
    exclude = requires(set)

class Node(Context):
    '''
    The node context.
    '''
    # ---------------------------------------------------------------- Required
    invokers = requires(dict)
    invokersAccessible = requires(dict)
    childByName = requires(dict)

class InvokerResources(Context):
    '''
    The invoker context.
    '''
    # ---------------------------------------------------------------- Defined
    id = defines(str)
    location = defines(str)
    methodHTTP = defines(str)
    path = defines(list)
    encoder = defines(ITransfrom, doc='''
    @rtype: ITransfrom
    The encoder to be used for rendering the response object.
    ''')
    # ---------------------------------------------------------------- Required
    node = requires(Context)
    target = requires(TypeModel)
    doEncodePath = requires(IDo)
    
# --------------------------------------------------------------------

@injected
class InvokerResourcesHandler(HandlerProcessor):
    '''
    Implementation for a handler that provides the resources encoding.
    '''

    nameResources = 'Resources'
    # The name used for resources paths.
    nameRef = 'href'
    # The reference attribute name.
    nameRel = 'rel'
    # The relation attribute name.
    additional = None
    # Additional resources links to be pushed in the main resources.
    
    def __init__(self):
        assert isinstance(self.nameResources, str), 'Invalid resources name %s' % self.nameResources
        assert isinstance(self.nameRef, str), 'Invalid reference name %s' % self.nameRef
        assert self.additional is None or isinstance(self.additional, dict), \
        'Invalid additional resources %s' % self.additional
        super().__init__(Node=Node)
        
    def process(self, chain, register:Register, Invoker:InvokerResources, **keyargs):
        '''
        @see: HandlerProcessor.process
        
        Create the collection encoder.
        '''
        assert isinstance(register, Register), 'Invalid register %s' % register
        assert issubclass(Invoker, InvokerResources), 'Invalid invoker class %s' % Invoker
        
        if self.nameResources in register.exclude: return
        if register.invokers is None: register.invokers = []
        
        invoker = Invoker()
        register.invokers.append(invoker)
        assert isinstance(invoker, InvokerResources), 'Invalid invoker %s' % invoker
        invoker.id = self.nameResources
        invoker.location = locationStack(self.__class__)
        invoker.methodHTTP = HTTP_GET
        invoker.path = []
        invoker.encoder = EncoderResources(self.nameResources, self.nameRef,
                                           self.nameRel, invoker, self.additional)

# --------------------------------------------------------------------

class EncoderResources(ITransfrom):
    '''
    Implementation for a @see: ITransfrom for resources.
    '''
    
    def __init__(self, nameResources, nameRef, nameRel, invoker, additional):
        '''
        Construct the resources encoder.
        '''
        assert isinstance(nameResources, str), 'Invalid resources name %s' % nameResources
        assert isinstance(nameRef, str), 'Invalid reference name %s' % nameRef
        assert isinstance(invoker, InvokerResources), 'Invalid invoker %s' % invoker
        assert additional is None or isinstance(additional, dict), \
        'Invalid additional resources %s' % additional
        
        self.nameResources = nameResources
        self.nameRef = nameRef
        self.nameRel = nameRel
        self.invoker = invoker
        self.additional = additional
        
    def transform(self, value, target, support):
        '''
        @see: ITransfrom.transform
        '''
        assert isinstance(target, IRender), 'Invalid target %s' % target
        
        target.beginCollection(self.nameResources)
        if self.invoker.node:
            accessible, stack = [], deque()
            stack.append(([], self.invoker.node))
            while stack:
                names, node = stack.popleft()
                assert isinstance(node, Node)
                if node.invokers and HTTP_GET in node.invokers and names:
                    accessible.append((names, node.invokers[HTTP_GET]))
                if node.childByName:
                    stack.extend((list(chain(names, (cname,))), cnode) for cname, cnode in node.childByName.items())
            
            indexes = dict(indexBlock=NAME_BLOCK_REST, indexAttributesCapture={self.nameRef: ACTION_REFERENCE})
            for names, invoker in sorted(accessible, key=firstOf):
                assert isinstance(invoker, InvokerResources), 'Invalid invoker %s' % invoker
                assert isinstance(invoker.doEncodePath, IDo), 'Invalid path encode %s' % invoker.doEncodePath
                target.beginObject(''.join(names), attributes={self.nameRef: invoker.doEncodePath(support),
                                                               self.nameRel: '/'.join(names)}, **indexes).end()
        
            if self.additional:
                assert isinstance(support.doEncodePath, IDo), 'Invalid path encode %s' % support.doEncodePath
                for name in sorted(self.additional):
                    path, rel = self.additional[name]
                    target.beginObject(name, attributes=
                                       {self.nameRef: support.doEncodePath(path), self.nameRel: rel}).end()
                
        target.end()
