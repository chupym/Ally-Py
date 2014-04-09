'''
Created on Mar 8, 2013

@package: ally core http
@copyright: 2012 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides the setup for the encode processors.
'''

from ally.container import ioc
from ally.core.http.impl.index import BLOCKS_HTTP
from ally.core.http.impl.processor.encoder.accessible_paths import \
    AccessiblePathEncode
from ally.core.http.impl.processor.encoder.model_path import \
    ModelPathAttributeEncode
from ally.core.http.impl.processor.encoder.path_support import \
    PathUpdaterSupportEncode, pathUpdaterSupportEncodeExport
from ally.core.http.impl.processor.encoder.property_of_model_path import \
    PropertyOfModelPathAttributeEncode, propertyOfModelPathAttributeEncodeExport
from ally.core.http.impl.processor.encoder.property_reference import \
    PropertyReferenceEncode, propertyReferenceEncodeExport
from ally.core.impl.processor.encoder.property import propertyEncodeExport
from ally.design.processor.handler import Handler

from ..ally_core.encode import assemblyModelExtraEncode, updateAssemblyEncode, \
    assemblyEncode, propertyOfModelEncode, assemblyItemEncode, \
    updateAssemblyItemEncode, assemblyPropertyEncode, updateAssemblyPropertyEncode, \
    modelPropertyEncode, modelEncode, updateAssemblyEncodeExport, \
    assemblyEncodeExport
from ..ally_core.encode import updateAssemblyPropertyPrimitiveEncode, \
    assemblyPropertyPrimitiveEncode, propertyEncode
from ..ally_core.parsing_rendering import blocksDefinitions


# --------------------------------------------------------------------
@ioc.entity
def pathUpdaterSupportEncode() -> Handler: return PathUpdaterSupportEncode()

@ioc.entity
def accessiblePathEncode(): return AccessiblePathEncode()

@ioc.entity
def modelPathAttributeEncode() -> Handler: return ModelPathAttributeEncode()

@ioc.entity
def propertyReferenceEncode() -> Handler: return PropertyReferenceEncode()

@ioc.entity
def propertyOfModelPathAttributeEncode() -> Handler: return PropertyOfModelPathAttributeEncode()

# --------------------------------------------------------------------

@ioc.after(updateAssemblyEncode)
def updateAssemblyEncodeWithPath():
    assemblyEncode().add(modelPathAttributeEncode(), before=modelPropertyEncode())
    assemblyEncode().add(pathUpdaterSupportEncode())
    
@ioc.after(updateAssemblyPropertyPrimitiveEncode)
def updateAssemblyPropertyPrimitiveReferenceEncode():
    assemblyPropertyPrimitiveEncode().add(propertyReferenceEncode(), before=propertyEncode())
    
@ioc.after(assemblyModelExtraEncode)
def updateAssemblyModelExtraEncodeWithPath():
    assemblyModelExtraEncode().add(accessiblePathEncode())
   
@ioc.after(updateAssemblyItemEncode)
def updateAssemblyItemEncodeWithPath():
    assemblyItemEncode().add(modelPathAttributeEncode(), before=modelPropertyEncode())
    # TODO: Gabriel: This is a temporary fix to get the same rendering as before until we refactor the plugins
    # to return only ids.
    assemblyItemEncode().add(modelPathAttributeEncode(), before=modelEncode())
    assemblyItemEncode().add(pathUpdaterSupportEncode())

@ioc.after(updateAssemblyPropertyEncode)
def updateAssemblyPropertyEncodeWithPath():
    assemblyPropertyEncode().add(propertyReferenceEncode(), propertyOfModelPathAttributeEncode(),
                                 before=propertyOfModelEncode())

@ioc.after(updateAssemblyEncodeExport)
def updateAssemblyEncodeExportForPath():
    assemblyEncodeExport().add(propertyEncodeExport, pathUpdaterSupportEncodeExport, propertyReferenceEncodeExport,
                               propertyOfModelPathAttributeEncodeExport)


# --------------------------------------------------------------------

@ioc.before(blocksDefinitions)
def updateBlocksDefinitionsForURL():
    blocksDefinitions().update(BLOCKS_HTTP)
