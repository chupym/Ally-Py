'''
Created on Aug 3, 2012

@package: ally core
@copyright: 2011 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides the JSON encoder processor handler.
'''

from .base import RenderBaseHandler, Content
from ally.container.ioc import injected
from ally.core.impl.index import ACTION_STREAM, ACTION_DISCARD, NAME_BLOCK, \
    ACTION_INJECT, ADJUST_STANDARD, Index, ACTION_NAME
from ally.core.spec.resources import Converter
from ally.core.spec.transform import IRender
from ally.design.processor.attribute import optional
from ally.design.processor.context import Context
from ally.indexing.spec.model import Block, Action
from ally.indexing.spec.perform import skip, feed, feedValue, feedName, \
    feedIndexed, feedContent, push, setFlag, remFlag, setFlagIfBefore, feedKey, pop, \
    pushKey, setFlagIfNotBefore
from ally.support.util import immut
from codecs import getwriter
from collections import deque
from functools import partial
from io import BytesIO
from json.encoder import encode_basestring
    
# --------------------------------------------------------------------

# The patterns to use in creating JSON specific names.
PATTERN_JSON_BLOCK_NAMED = 'JSON block %s with name'  # The JSON block pattern for blocks with name.
PATTERN_JSON_BLOCK_UNAMED = 'JSON block %s no name'  # The JSON block pattern for blocks with no name.
PSIND_ATTR_CAPTURE = 'JSON start capture %s'  # The pattern used for start indexes used in capturing attributes.
PEIND_ATTR_CAPTURE = 'JSON end capture %s'  # The pattern used for indexes used in capturing attributes.

# The names.
PATTERN_JSON_START_ADJUST = 'JSON start %s adjust'
PATTERN_JSON_END_ADJUST = 'JSON end %s adjust'

# Variables
VAR_JSON_NAME = 'JSON tag name'  # The name used for the tag name.
VAR_JSON_ATTRS = 'JSON tag attributes'  # The name used for the tag attributes.

# The JSON actions.
ACTION_JSON_ADJUST = 'adjust'  # The adjust action.
ACTION_JSON_COMMA = 'adjust_comma'  # The adjust comma action.

# The standard JSON indexes.
IND_DECL = 'JSON declarations'
SIND_ENTRY, EIND_ENTRY = 'JSON start entry', 'JSON end entry'
SIND_COMMA, EIND_COMMA = 'JSON start comma', 'JSON end comma'
SIND_VALUE, EIND_VALUE = 'JSON start value', 'JSON end value'
SIND_NAME, EIND_NAME = 'JSON start name', 'JSON end name'
SIND_ATTRS, EIND_ATTRS = 'JSON start attributes', 'JSON end attributes'
KEY_NAME = 'JSON key block name'

# The JSON flags.
FLAG_COMMA = 'comma required'
FLAG_COMMA_ATTR = 'comma attribute required'

# The escape characters for values.
ESCAPE_JSON = {'\\': '\\\\', '"': '\\"', '\n': '\\n', '\r': '\\r', '\t': '\\t'}

# The common actions for JSON block.
ACTIONS_BLOCK_JSON = (
                      Action(ACTION_JSON_COMMA,
                             skip(SIND_ENTRY), feed(SIND_COMMA), feed(EIND_COMMA, FLAG_COMMA), skip(EIND_COMMA),
                             setFlag(FLAG_COMMA),
                             final=False),
                      Action(ACTION_STREAM,
                             feed(EIND_ENTRY), remFlag(FLAG_COMMA_ATTR),
                             before=(ACTION_JSON_COMMA,)),
                      Action(ACTION_DISCARD,
                             skip(EIND_ENTRY)),
                      )

# The JSON block.
BLOCK_JSON_NAMED = Block(
                         Action(ACTION_NAME,
                                skip(SIND_NAME), feed(EIND_NAME),
                                rewind=True, final=False),
                         *ACTIONS_BLOCK_JSON
                         )
BLOCK_JSON_UNNAMED = Block(
                         Action(ACTION_NAME,
                                feedKey(KEY_NAME),
                                final=False),
                         *ACTIONS_BLOCK_JSON,
                         keys=(KEY_NAME,)
                         )

# Provides the JSON standard block definitions.
BLOCKS_JSON = {
               PATTERN_JSON_START_ADJUST % ADJUST_STANDARD:
               Block(
                     Action(ACTION_JSON_ADJUST,
                            feed(SIND_ATTRS),
                            setFlagIfBefore(EIND_ATTRS, FLAG_COMMA_ATTR),
                            setFlagIfNotBefore(EIND_ATTRS, 'comma attribute required after'), feed(EIND_ATTRS),
                            feedValue(',', FLAG_COMMA_ATTR), feedName(VAR_JSON_ATTRS),
                            feedValue(',', 'comma attribute required after'), remFlag('comma attribute required after'),
                            feed(SIND_NAME), setFlagIfBefore(EIND_NAME, 'name required'),
                            skip(EIND_NAME), feedName(VAR_JSON_NAME, 'name required'), remFlag('name required'),
                            feed(IND_DECL)),
                     Action(ACTION_STREAM,
                            feed(IND_DECL)),
                     ),
              
              PATTERN_JSON_BLOCK_NAMED % NAME_BLOCK: BLOCK_JSON_NAMED,
              
              PATTERN_JSON_BLOCK_UNAMED % NAME_BLOCK: BLOCK_JSON_UNNAMED,
              
              PATTERN_JSON_END_ADJUST % ADJUST_STANDARD:
              Block(
                    Action(ACTION_JSON_ADJUST,
                           feed(EIND_ENTRY)),
                    Action(ACTION_STREAM,
                           feed(EIND_ENTRY)),
                    ),
              }

def createJSONAttributesActions(injectAttributes=None, captureAttributes=None):
    '''
    Create the actions associated with the provided attributes.
    
    @param injectAttributes: dictionary{string: string}
        The attributes to be injected dictionary, as a key the action to be associated with the attribute injection and
        as a value the attribute name to be injected.
    @param captureAttributes: dictionary{string: string}
        The attributes to be captured dictionary, as a key the action to be associated with the attribute capture and
        as a value the name to be used latter on as a reference for the attribute capture.
    @return: list[Action]
        The created list of actions for the attributes.
    '''
    actions = []
    if injectAttributes:
        assert isinstance(injectAttributes, dict), 'Invalid inject attributes %s' % injectAttributes
        for action, nameAttr in injectAttributes.items():
            actions.append(Action(action,
                                  feed(SIND_ATTRS),
                                  setFlagIfBefore(EIND_ATTRS, FLAG_COMMA_ATTR), feed(EIND_ATTRS),
                                  feedValue(',', FLAG_COMMA_ATTR),
                                  feedValue('"%s":"' % nameAttr), feedContent(escapes=ESCAPE_JSON), feedValue('"'),
                                  setFlag(FLAG_COMMA_ATTR),
                                  final=False, before=(ACTION_JSON_COMMA,)))
    
    if captureAttributes:
        assert isinstance(captureAttributes, dict), 'Invalid capture attributes %s' % captureAttributes
        for action, name in captureAttributes.items():
            actions.append(Action(action,
                                  skip(PSIND_ATTR_CAPTURE % name),
                                  feed(PEIND_ATTR_CAPTURE % name),
                                  rewind=True, final=False))
    return actions

def createJSONBlockForIndexed(name, *actions, injectAttributes=None, captureAttributes=None):
    '''
    Create a new JSON block that can be used for injecting indexed content.
    
    @param name: string
        The name that can be latter on used as a reference for the block.
    @param actions: arguments[Action]
        Additional actions to be registered with the created block.
    @see: createJSONAttributesActions
    '''
    actions = list(actions)
    actions.extend(createJSONAttributesActions(injectAttributes, captureAttributes))
    
    actionsNamed = list(actions)
    actionsNamed.extend(BLOCK_JSON_NAMED.actions)
    actionsNamed.append(Action(ACTION_INJECT,
                               feed(SIND_NAME), push(VAR_JSON_NAME, EIND_NAME), feedName(VAR_JSON_NAME),
                               feed(SIND_VALUE),
                               skip(SIND_ATTRS), push(VAR_JSON_ATTRS, EIND_ATTRS),
                               skip(EIND_VALUE),
                               feedIndexed(actions=(ACTION_JSON_ADJUST,)),
                               feed(EIND_ENTRY),
                               pop(VAR_JSON_NAME), pop(VAR_JSON_ATTRS),
                               before=(ACTION_JSON_COMMA,))
                        )
    
    actionsUnamed = list(actions)
    actionsUnamed.extend(BLOCK_JSON_UNNAMED.actions)
    actionsUnamed.append(Action(ACTION_INJECT,
                                pushKey(VAR_JSON_NAME, KEY_NAME),
                                feed(SIND_VALUE),
                                skip(SIND_ATTRS), push(VAR_JSON_ATTRS, EIND_ATTRS),
                                skip(EIND_VALUE),
                                feedIndexed(actions=(ACTION_JSON_ADJUST,)),
                                feed(EIND_ENTRY),
                                pop(VAR_JSON_NAME), pop(VAR_JSON_ATTRS),
                                before=(ACTION_JSON_COMMA,))
                         )
    
    return {PATTERN_JSON_BLOCK_NAMED % name: Block(*actionsNamed),
            PATTERN_JSON_BLOCK_UNAMED % name: Block(*actionsUnamed, keys=(KEY_NAME,))}
    
def createJSONBlockForContent(name, *actions, injectAttributes=None, captureAttributes=None):
    '''
    Create a new JSON block that can be used for injecting text content.
    
    @param name: string
        The name that can be latter on used as a reference for the block.
    @param actions: arguments[Action]
        Additional actions to be registered with the created block.
    @see: createJSONAttributesActions
    '''
    actions = list(actions)
    actions.extend(createJSONAttributesActions(injectAttributes, captureAttributes))
    
    actionsNamed = list(actions)
    actionsNamed.extend(BLOCK_JSON_NAMED.actions)
    actionsNamed.append(Action(ACTION_INJECT,
                               feed(SIND_NAME), push(VAR_JSON_NAME, EIND_NAME), feedName(VAR_JSON_NAME),
                               feed(SIND_ATTRS),
                               setFlagIfBefore(EIND_ATTRS, FLAG_COMMA_ATTR), feed(EIND_ATTRS),
                               feedValue(',', FLAG_COMMA_ATTR),
                               feedValue('"'), feedName(VAR_JSON_NAME), feedValue('":"'),
                               feedContent(escapes=ESCAPE_JSON), feedValue('"'), feed(EIND_ENTRY),
                               pop(VAR_JSON_NAME), pop(VAR_JSON_ATTRS),
                               before=(ACTION_JSON_COMMA,))
                        )
    
    actionsUnamed = list(actions)
    actionsUnamed.extend(BLOCK_JSON_UNNAMED.actions)
    actionsUnamed.append(Action(ACTION_INJECT,
                                pushKey(VAR_JSON_NAME, KEY_NAME),
                                feed(SIND_ATTRS),
                                setFlagIfBefore(EIND_ATTRS, FLAG_COMMA_ATTR), feed(EIND_ATTRS),
                                feedValue(',', FLAG_COMMA_ATTR),
                                feedValue('"'), feedName(VAR_JSON_NAME), feedValue('":"'),
                                feedContent(escapes=ESCAPE_JSON), feedValue('"'), feed(EIND_ENTRY),
                                pop(VAR_JSON_NAME), pop(VAR_JSON_ATTRS),
                                before=(ACTION_JSON_COMMA,))
                         )
    
    return {PATTERN_JSON_BLOCK_NAMED % name: Block(*actionsNamed),
            PATTERN_JSON_BLOCK_UNAMED % name: Block(*actionsUnamed, keys=(KEY_NAME,))}

# --------------------------------------------------------------------

class Request(Context):
    '''
    The request context.
    '''
    # ---------------------------------------------------------------- Optional
    converterContent = optional(Converter)

# --------------------------------------------------------------------

@injected
class RenderJSONHandler(RenderBaseHandler):
    '''
    Provides the JSON rendering.
    @see: RenderBaseHandler
    '''

    encodingError = 'backslashreplace'
    # The encoding error resolving.
    nameCollection = 'collection'
    # The collection name to be used for indexing the collection object.

    def __init__(self):
        assert isinstance(self.encodingError, str), 'Invalid string %s' % self.encodingError
        assert self.nameCollection is None or isinstance(self.nameCollection, str), \
        'Invalid string %s' % self.nameCollection
        super().__init__(request=Request)
        
    def process(self, chain, request:Context, **keyargs):
        if super().process(chain, **keyargs):
            assert isinstance(request, Request), 'Invalid request %s' % request
            if Request.converterContent in request and request.converterContent:
                request.converterContent = ConverterJSON(request.converterContent)

    def renderFactory(self, content):
        '''
        @see: RenderBaseHandler.renderFactory
        '''
        return RenderJSON(self.encodingError, content, self.nameCollection)

# --------------------------------------------------------------------

class ConverterJSON(Converter):
    '''
    JSON specific content converter.
    '''
    __slots__ = ('wrapped',)
    
    def __init__(self, wrapped):
        assert isinstance(wrapped, Converter), 'Invalid wrapped converter %s' % wrapped
        self.wrapped = wrapped
    
    def asString(self, value, type):
        '''
        @see: Converter.asString
        '''
        # If the value is integer float or boolean then no conversion will occur.
        if type.isOf(int) or type.isOf(float) or type.isOf(bool): return value
        return self.wrapped.asString(value, type)
    
    def asValue(self, value, type):
        '''
        @see: Converter.asValue
        '''
        if isinstance(value, str): return self.wrapped.asValue(value, type)
        if type.isOf(int):
            if isinstance(value, int): return value
        if type.isOf(float):
            if isinstance(value, float): return value
        if type.isOf(bool):
            if isinstance(value, bool): return value
        raise ValueError('Invalid value \'%s\' for type %s' % (value, type))

# --------------------------------------------------------------------

OF_PROPERTY = 1
OF_OBJECT = 2
OF_COLLECTION = 3

class RenderJSON(IRender):
    '''
    Renderer for JSON.
    '''
    __slots__ = ('nameCollection', '_content', '_outb', '_out', '_stack', '_first', '_adjust', '_block', '_indexes')
    
    def __init__(self, encodingError, content, nameCollection=None):
        '''
        Construct the JSON object renderer.
        
        @param nameCollection: string
            THe collection name to use, if None the declared collection name is used.
        @param encodingError: string
            The encoding error resolving.
        @param content: Content
            The content to render in.
        '''
        assert nameCollection is None or isinstance(nameCollection, str), 'Invalid string %s' % nameCollection
        assert isinstance(content, Content), 'Invalid content %s' % content
        assert isinstance(content.charSet, str), 'Invalid content char set %s' % content.charSet
        
        self.nameCollection = nameCollection
        self._content = content
        self._outb = BytesIO()
        self._out = getwriter(content.charSet)(self._outb, encodingError)
        
        self._stack = deque()
        self._first = True
        
        self._adjust = True
        self._block = False
        self._indexes = []

    def property(self, name, value, indexBlock=None):
        '''
        @see: IRender.property
        
        @param indexBlock: string
            Index the object with the provided index.
        '''
        assert isinstance(name, str), 'Invalid name %s' % name
        assert self._stack and self._stack[0][0] == OF_OBJECT, 'No object for property'
        if indexBlock is None and not self._block: indexBlock = NAME_BLOCK
        
        self.begin(name, OF_PROPERTY, indexBlock=indexBlock)
        if isinstance(value, list):
            value = '[%s]' % ','.join(encode(item) for item in value)
        elif isinstance(value, dict):
            value = ','.join('%s:%s' % (encode(key), encode(item)) for key, item in value.items())
            value = '{%s}' % value
        else:
            value = encode(value)
            
        self._out.write(value)
        self.end()

    def beginObject(self, name, **specifications):
        '''
        @see: IRender.beginObject
        '''
        self.begin(name, OF_OBJECT, **specifications)
        return self

    def beginCollection(self, name, **specifications):
        '''
        @see: IRender.beginCollection
        '''
        self.begin(name if self.nameCollection is None else self.nameCollection, OF_COLLECTION, **specifications)
        return self

    def end(self):
        '''
        @see: IRender.collectionEnd
        '''
        assert self._stack, 'No collection to end'
        of, index, adjust = self._stack.popleft()
        
        if adjust: index = self._index(PATTERN_JSON_END_ADJUST % adjust)
        if of == OF_COLLECTION: self._out.write(']}')
        elif of == OF_OBJECT: self._out.write('}')
        if index:
            index(EIND_VALUE, EIND_ENTRY)
            self._block = False
        
        if not self._stack:
            content = self._content
            assert isinstance(content, Content), 'Invalid content %s' % content
            content.length = self._outb.tell()
            self._outb.seek(0)
            content.source = self._outb
            if Content.indexes in content: content.indexes = self._indexes
        
    # ----------------------------------------------------------------

    def begin(self, name, of, attributes=None, indexBlock=None, adjust=ADJUST_STANDARD, indexAttributesCapture=immut()):
        '''
        Used to open a JSON object.
        
        @param attributes: dictionary{string: string}
            The attributes to associate with the object.
        @param indexBlock: string
            Index the object with the provided index.
        @param indexAttributesCapture: dictionary{string: string}
            The dictionary containing as a key the attribute name and as a value the key name as registered
            to associate with the attribute capture.
        '''
        hasNameProp = self._stack and self._stack[0][0] == OF_OBJECT
        isAdjust, hasName = False, of == OF_COLLECTION or hasNameProp
        if self._adjust:
            if indexBlock is None:
                assert not indexAttributesCapture, 'No attributes capture expected, but got %s' % indexAttributesCapture
                assert of in (OF_OBJECT, OF_COLLECTION), 'Invalid adjusting for of %s action' % of
                index = self._index(PATTERN_JSON_START_ADJUST % adjust)
                isAdjust = True
            self._adjust = False
        if not isAdjust:
            if self._block:
                indexBlock = None
                indexAttributesCapture = immut()
                index = None
            elif indexBlock:
                assert isinstance(indexBlock, str), 'Invalid index block %s' % indexBlock
                assert isinstance(indexAttributesCapture, dict), 'Invalid index attributes capture %s' % indexAttributesCapture
                if hasName: index = self._index(PATTERN_JSON_BLOCK_NAMED % indexBlock)
                else: index = self._index(PATTERN_JSON_BLOCK_UNAMED % indexBlock, {KEY_NAME: name})
                self._block = True
            else: index = None

        if index: index(SIND_ENTRY, SIND_COMMA)
        if not self._first:
            self._out.write(',')
        if of == OF_PROPERTY: self._first = False
        else: self._first = True
        if index: index(EIND_COMMA)
            
        if hasNameProp:
            if index: index(SIND_NAME, offset=1)  # offset +1 for the comma
            self._out.write('"%s"' % name)
            if index: index(EIND_NAME, offset=-1)  # offset -1 for the comma
            self._out.write(':')
        elif index: index(SIND_NAME, EIND_NAME)
        
        self._stack.appendleft((of, index, adjust if isAdjust else None))
        if of == OF_PROPERTY: return
        
        if index: index(SIND_VALUE)
        self._out.write('{')
        
        if index: index(SIND_ATTRS)
        if attributes:
            assert isinstance(attributes, dict), 'Invalid attributes %s' % attributes
            for nameAttr, valueAttr in attributes.items():
                assert isinstance(nameAttr, str), 'Invalid attribute name %s' % nameAttr
                
                if self._first: self._first = False
                else: self._out.write(',')
                self._out.write('"%s"' % nameAttr)
                self._out.write(':')

                iname = indexAttributesCapture.get(nameAttr)
                if iname:
                    offset = 1 if isinstance(valueAttr, str) else 0
                    index(PSIND_ATTR_CAPTURE % iname, offset=offset)  # offset +1 for the comma
                    self._out.write(encode(valueAttr))
                    index(PEIND_ATTR_CAPTURE % iname, offset=-offset)  # offset -1 for the comma
                else: self._out.write(encode(valueAttr))
        if index: index(EIND_ATTRS)
        
        if of == OF_COLLECTION:
            if not self._first:
                self._out.write(',')
                self._first = True
                
            if index: index(SIND_NAME, offset=1)  # offset +1 for the comma
            self._out.write('"%s"' % name)
            if index: index(EIND_NAME, offset=-1)  # offset -1 for the comma
            self._out.write(':[')
        
        if isAdjust: index(IND_DECL)
    
    # ----------------------------------------------------------------
    
    def _index(self, block, values=None):
        '''
        Create a new index.
        '''
        index = Index(block, values)
        self._indexes.append(index)
        return partial(self._put, index)
    
    def _put(self, index, *names, offset=0):
        '''
        Puts on the index the provided index names at the current offset. 
        '''
        assert isinstance(index, Index), 'Invalid index %s' % index
        offset = self._outb.tell() + offset
        for name in names:
            assert isinstance(name, str), 'Invalid name %s' % name
            index.values[name] = offset

# --------------------------------------------------------------------

def encode(value):
    '''
    Encodes the value as a JSON value.
    '''
    if isinstance(value, str): return encode_basestring(value)
    if value is True: return 'true'
    if value is False: return 'false'
    if isinstance(value, float): return repr(value)
    assert isinstance(value, int), 'Invalid value %s' % value
    return str(value)
