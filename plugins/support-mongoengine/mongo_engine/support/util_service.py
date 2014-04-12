'''
Created on Jan 5, 2012

@package: support mongoengine
@copyright: 2012 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides utility methods for Mongo engine service implementations.
'''

from itertools import chain
from mongoengine.base.fields import BaseField

from ally.api.criteria import AsLike, AsOrdered, AsBoolean, AsEqual, AsDate, \
    AsTime, AsDateTime, AsRange, AsRangeInt
from ally.api.extension import IterSlice
from ally.api.operator.type import TypeProperty, TypeCriteria, TypeModel
from ally.api.type import typeFor
from ally.support.api.util_service import namesFor, likeAsRegex, modelId
from ally.support.util import modifyFirst
from inspect import isclass
from mongoengine.document import Document, EmbeddedDocument
from ally.api.error import IdError, InputError
from ally.internationalization import _


# --------------------------------------------------------------------
def buildLimits(objects, offset=None, limit=None):
    '''
    Builds limiting on the mongo engine objects.

    @param objects: QuerySetManager
        The objects query to use for limits.
    @param offset: integer|None
        The offset to fetch elements from.
    @param limit: integer|None
        The limit of elements to get.
    @return: QuerySetManager
        The limited query objects.
    '''
    if offset is not None: objects = objects.skip(offset)
    if limit is not None: objects = objects.limit(limit)
    return objects

def buildQuery(objects, query, Mapped, only=None, exclude=None, orderBy=None, **mapping):
    '''
    Builds the query on the SQL alchemy query.
 
    @param objects: QuerySetManager
        The objects query to use.
    @param query: query
        The REST query object to provide filtering on.
    @param Mapped: class
        The mapped model class to use the query on.
    @param only: tuple(string|TypeCriteriaEntry)|string|TypeCriteriaEntry|None
        The criteria names or references to build the query for, if no criteria is provided then all the query criteria
        are considered.
    @param exclude: tuple(string|TypeCriteriaEntry)|string|TypeCriteriaEntry|None
        The criteria names or references to be excluded when processing the query. If you provided a only parameter you cannot
        provide an exclude.
    @param orderBy: field or string
        The default order by if none has been provided.
    @param mapping: key arguments of fields, string or callable(objects, criteria) -> objects
        The field or objects build callable mappings provided for criteria name.
    '''
    assert query is not None, 'A query object is required'
    
    fields = {}
    for name in namesFor(Mapped):
        field = getattr(Mapped, name)
        # If no API type is detected it means that the API property is mapped
        if isinstance(field, BaseField): fields[modifyFirst(name, False)] = field.name
    fields = {name:fields.get(name) for name in namesFor(query)}
 
    if only:
        if not isinstance(only, tuple): only = (only,)
        assert not exclude, 'Cannot have only \'%s\' and exclude \'%s\' criteria at the same time' % (only, exclude)
        onlyFields = {}
        for criteria in only:
            if isinstance(criteria, str):
                field = fields.get(criteria)
                assert field is not None, 'Invalid only criteria name \'%s\' for query %s' % (criteria, query)
                onlyFields[criteria] = field
            else:
                typ = typeFor(criteria)
                assert isinstance(typ, TypeProperty), 'Invalid only criteria %s' % criteria
                assert isinstance(typ.type, TypeCriteria), 'Invalid only criteria %s' % criteria
                field = fields.get(typ.name)
                assert field is not None, 'Invalid only criteria \'%s\' for query %s' % (criteria, query)
                onlyFields[typ.name] = field
        fields = onlyFields
    elif exclude:
        if not isinstance(exclude, tuple): exclude = (exclude,)
        for criteria in exclude:
            if isinstance(criteria, str):
                field = fields.pop(criteria, None)
                assert field is not None, 'Invalid exclude criteria name \'%s\' for query %s' % (criteria, query)
            else:
                typ = typeFor(criteria)
                assert isinstance(typ, TypeProperty), 'Invalid exclude criteria %s' % criteria
                assert isinstance(typ.type, TypeCriteria), 'Invalid only criteria %s' % criteria
                field = fields.pop(typ.name, None)
                assert field is not None, 'Invalid exclude criteria \'%s\' for query %s' % (criteria, query)
  
    ordered, unordered, filters = [], [], {}
    for criteria, field in fields.items():
        if getattr(query.__class__, criteria) not in query: continue
         
        mapped = mapping.get(criteria)
        if mapped is not None:
            if isinstance(mapped, str): field = mapped
            elif isinstance(mapped, BaseField): field = mapped.name
            else:
                assert callable(mapped), 'Invalid criteria \'%s\' mapping' % criteria
                objects = mapped(objects, getattr(query, criteria))
                continue
         
        if field is None: continue
 
        crt = getattr(query, criteria)
        if isinstance(crt, AsBoolean):
            assert isinstance(crt, AsBoolean)
            if AsBoolean.value in crt:
                filters[field] = crt.value
        elif isinstance(crt, AsLike):
            assert isinstance(crt, AsLike)
            if AsLike.like in crt: filters[field] = likeAsRegex(crt.like, False)
            elif AsLike.ilike in crt: filters[field] = likeAsRegex(crt.ilike, True)
        elif isinstance(crt, AsEqual):
            assert isinstance(crt, AsEqual)
            if AsEqual.equal in crt:
                filters[field] = crt.equal
        elif isinstance(crt, (AsDate, AsTime, AsDateTime, AsRange, AsRangeInt)):
            if crt.__class__.start in crt: filters['%s__gte' % field] = crt.start
            elif crt.__class__.until in crt: filters['%s__lt' % field] = crt.until
            if crt.__class__.end in crt: filters['%s__lte' % field] = crt.end
            elif crt.__class__.since in crt: filters['%s__gt' % field] = crt.since
 
        if isinstance(crt, AsOrdered):
            assert isinstance(crt, AsOrdered)
            if AsOrdered.ascending in crt:
                if AsOrdered.priority in crt and crt.priority:
                    ordered.append((field, crt.ascending, crt.priority))
                else:
                    unordered.append((field, crt.ascending, None))
 
    if filters: objects = objects.filter(**filters)
    
    if ordered or unordered:
        if ordered: ordered.sort(key=lambda pack: pack[2])
        objects = objects.order_by(*(field if asc else '-%s' % field
                                     for field, asc, _priority in chain(ordered, unordered)))
    elif orderBy is not None:
        if isinstance(orderBy, BaseField): orderBy = orderBy.name
        objects = objects.order_by(orderBy)
    
    return objects
 
def iterateObjectCollection(objects, offset=None, limit=None, withTotal=False, _factorySlice=IterSlice):
    '''
    Iterates the collection of objects from a mongo engine query based on the provided parameters.
     
    @param objects: QuerySetManager
        The objects query to iterate the collection from.
         
    ... the options
     
    @return: Iterable(object)
        The obtained collection of objects.
    '''
    if withTotal:
        if limit <= 0: return _factorySlice((), objects.count())
        objectsLimit = buildLimits(objects, offset, limit)
        return _factorySlice(objectsLimit, objects.count(), offset, limit)
    return objects
 
def iterateCollection(objects, field, offset=None, limit=None, withTotal=False, _factorySlice=IterSlice):
    '''
    Iterates the collection of value from the sql query based on the provided parameters.
     
    @param objects: QuerySetManager
        The objects query to iterate the collection from.
    @param field: field or string
        The field or field name to iterate the collection for.
         
    ... the options
     
    @return: Iterable(object)
        The obtained collection of values.
    '''
    if isinstance(field, BaseField): field = field.name
    objects = objects.only(field)
    if withTotal:
        if limit == 0: return _factorySlice((), objects.count())
        objectsLimit = buildLimits(objects, offset, limit)
        return _factorySlice((getattr(item, field) for item in objectsLimit), objects.count(), offset, limit)
    return (getattr(item, field) for item in objects)

# --------------------------------------------------------------------

def copyModel(Mapped, src, dst=None):
    '''
    Copy the source model into the destination mapped model. If dst is None
    it creates a new model.
    
    @param src: object
        The source model from which to copy.
    @param dst: object
        The destination mapped model to which to copy.
    @return: object
        The database model that has been inserted.
    '''
    assert isclass(Mapped), 'Invalid class %s' % Mapped
    assert issubclass(Mapped, Document) or issubclass(Mapped, EmbeddedDocument), 'Invalid mapped class %s' % Mapped
    assert dst is None or isinstance(dst, Mapped), 'Invalid mapped model %s' % dst
    
    typ = typeFor(Mapped)
    assert isinstance(typ, TypeModel), 'Invalid model class %s' % Mapped
    
    if dst is None:
        dst = Mapped()
    for name, prop in typ.properties.items():
        if not isinstance(getattr(Mapped, name), BaseField): continue
        if not isinstance(src, Mapped) and prop in src or name in src:
            setattr(dst, name, getattr(src, name))
    return dst

def insertModel(Mapped, model, **data):
    '''
    Inserts the provided model entity.
    
    @param Mapped: class
        The mapped class to insert the model for.
    @param model: object
        The model to insert.
    @param data: key arguments
        Additional data to place on the inserted model.
    @return: object
        The database model that has been inserted.
    '''
    assert isclass(Mapped), 'Invalid class %s' % Mapped
    assert issubclass(Mapped, Document), 'Invalid mapped class %s' % Mapped
    
    typ = typeFor(Mapped)
    assert isinstance(typ, TypeModel), 'Invalid model class %s' % Mapped
    
    if isinstance(model, Mapped): dbModel = model
    else:
        dbModel = Mapped()
        for name, prop in typ.properties.items():
            if name in data or not isinstance(getattr(Mapped, name), BaseField): continue
            if prop in model: setattr(dbModel, name, getattr(model, name))
        
        for name, value in data.items(): setattr(dbModel, name, value)
    
    if typ.propertyId:
        if Mapped.objects(**{typ.propertyId.name: modelId(dbModel)}).count() > 0:
            raise InputError(typ.propertyId, _('There is already an entity with this identifier'))
    
    dbModel.save()
    return dbModel

def updateModel(Mapped, model, **data):
    '''
    Updates the provided model entity using the current session.

    @param Mapped: class
        The mapped class to update the model for, the model type is required to have a property id.
    @param model: object
        The model to be updated.
    @param data: key arguments
        Additional data to place on the updated model.
    @return: object
        The database model that has been updated.
    '''
    assert isclass(Mapped), 'Invalid class %s' % Mapped
    assert issubclass(Mapped, Document), 'Invalid mapped class %s' % Mapped
    if isinstance(model, Mapped): dbModel = model
    else:
        typ = typeFor(Mapped)
        assert isinstance(typ, TypeModel), 'Invalid model class %s' % Mapped
        assert typ.isValid(model), 'Invalid model %s for %s' % (model, typ)
        assert isinstance(typ.propertyId, TypeProperty), 'Invalid property id of %s' % typ

        dbModel = Mapped.objects(**{typ.propertyId.name: getattr(model, typ.propertyId.name)}).first()
        if not dbModel: raise IdError(typ.propertyId)
        for name, prop in typ.properties.items():
            if name in data or not isinstance(getattr(Mapped, name), BaseField): continue
            if prop in model: setattr(dbModel, name, getattr(model, name))
            
        for name, value in data.items(): setattr(dbModel, name, value)
    
    dbModel.save()
    return dbModel
