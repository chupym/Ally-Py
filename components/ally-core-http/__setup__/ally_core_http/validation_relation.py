'''
Created on Nov 1, 2013

@package: ally core http
@copyright: 2012 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides the setup for the relation processors validation.
'''

from ally.container import ioc
from ally.core.http.impl.processor.decoder.validation.relation import \
    ValidateRelation, validateRelationExport
from ally.design.processor.assembly import Assembly
from ally.design.processor.handler import Handler

from ..ally_core.decode import updateAssemblyDecodeModel, assemblyDecodeModel, \
    validateLen, updateAssemblyDecodeContentExport, assemblyDecodeContentExport
from ..ally_core.processor import invoking
from .processor import methodInvoker, scheme


# --------------------------------------------------------------------
@ioc.entity
def assemblyValidationInvoking() -> Assembly:
    '''
    The assembly containing the handlers that will be used for handling an invoking.
    '''
    return Assembly('Request validation invoking')

# --------------------------------------------------------------------

@ioc.entity
def validateRelation() -> Handler:
    b = ValidateRelation()
    b.assemblyInvoking = assemblyValidationInvoking()
    return b

# --------------------------------------------------------------------

@ioc.before(assemblyValidationInvoking)
def updateAssemblyValidationInvoking():
    assemblyValidationInvoking().add(methodInvoker(), scheme(), invoking())

@ioc.after(updateAssemblyDecodeModel)
def updateAssemblyDecodeModelForValidation():
    assemblyDecodeModel().add(validateRelation(), before=validateLen())

@ioc.before(updateAssemblyDecodeContentExport)
def updateAssemblyDecodeContentExportForValidation():
    assemblyDecodeContentExport().add(validateRelationExport)
