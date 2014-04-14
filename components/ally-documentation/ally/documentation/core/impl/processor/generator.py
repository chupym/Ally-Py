'''
Created on Oct 9, 2013

@package: ally documentation
@copyright: 2011 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Processor that generates the documentation based on jinja2 templates.
'''

from collections import deque
import logging
import os
import re

from jinja2.environment import Environment
from jinja2.exceptions import TemplateNotFound
from jinja2.loaders import BaseLoader

from ally.container.ioc import injected
from ally.design.processor.attribute import requires
from ally.design.processor.context import Context
from ally.design.processor.handler import HandlerProcessor
from ally.support.util import modifyFirst, TextTable


# --------------------------------------------------------------------
log = logging.getLogger(__name__)

# --------------------------------------------------------------------

class Document(Context):
    '''
    The document context.
    '''
    # ---------------------------------------------------------------- Required
    loader = requires(BaseLoader)
    data = requires(dict)
      
# --------------------------------------------------------------------

@injected
class GeneratorHandler(HandlerProcessor):
    '''
    Handler that generates the documentation based on jinja2 templates.
    '''
    
    pathDocumentation = str
    # The folder where the documentation will be placed.
    patternGenerate = str
    # The pattern used for identify the template paths that need to be generated.
    
    def __init__(self):
        assert isinstance(self.pathDocumentation, str), 'Invalid documentation path %s' % self.pathDocumentation
        assert isinstance(self.patternGenerate, str), 'Invalid generate pattern %s' % self.patternGenerate
        super().__init__()
        
        self._rPatternGenerate = re.compile(self.patternGenerate)
        
    def process(self, chain, document:Document, **keyargs):
        '''
        @see: HandlerProcessor.process
        
        Generate the jinja templates.
        '''
        assert isinstance(document, Document), 'Invalid document %s' % document
        if not document.loader: return  # No loader available.
        
        doRender = self.createRenderer(document.loader)
        for path in document.loader.list_templates():
            if self._rPatternGenerate.match(path): doRender(path, path, data=document.data)

    # ----------------------------------------------------------------
    
    def createRenderer(self, loader):
        '''
        Construct the template renderer.
        
        @param loader: BaseLoader
            The loader to extract the templates from.
        '''
        assert isinstance(loader, BaseLoader), 'Invalid loader %s' % loader
        environment = Environment(loader=loader, extensions=['jinja2.ext.do'])
        
        def doRender(tpath, path, **data):
            '''
            Render the template into the provided path.
            '''
            try: template = environment.get_template(tpath)
            except TemplateNotFound:
                log.info('Template \'%s\' is missing', tpath)
                return False
            except:
                log.exception('Template \'%s\' has a problem', tpath)
                return False

            content = template.render(**data)
            
            try: folder = path[:path.index('/')]
            except ValueError: folder = self.pathDocumentation
            else: folder = os.path.join(self.pathDocumentation, folder.replace('/', os.sep))
            
            if not os.path.exists(folder): os.makedirs(folder)
            file = os.path.join(self.pathDocumentation, path.replace('/', os.sep))
            
            with open(file, 'w') as dest: dest.write(content)
            return True

        environment.globals['render'] = doRender
        environment.globals['isColl'] = lambda value: isinstance(value, (list, tuple, deque))
        environment.globals['isDict'] = lambda value: isinstance(value, dict)
        environment.globals['upperFirst'] = lambda value: modifyFirst(value, True)
        environment.globals['transform'] = lambda coll, format: [format % item for item in coll]
        environment.globals['TextTable'] = TextTable
        environment.globals['ident'] = self.ident
        
        return doRender
    
    def ident(self, text, ident='   '):
        ''' Escapes a restructured text.'''
        if isinstance(text, str):
            return ident + text.replace('\n', '\n%s' % ident)
        return ident
