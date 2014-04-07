'''
Created on Jan 5, 2012

@package: support sqlalchemy
@copyright: 2012 Sourcefabric o.p.s.
@license: http://www.gnu.org/licenses/gpl-3.0.txt
@author: Gabriel Nistor

Provides utility methods for SQL alchemy service implementations.
'''

from inspect import isclass
from itertools import chain

from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.interfaces import PropComparator

from ally.api.criteria import AsLike, AsOrdered, AsBoolean, AsEqual, AsDate, \
    AsTime, AsDateTime, AsRange, AsRangeInt
from ally.api.error import IdError
from ally.api.extension import IterSlice
from ally.api.operator.type import TypeProperty, TypeCriteria, TypeModel
from ally.api.type import typeFor
from ally.support.api.util_service import namesFor

from .mapper import MappedSupport, tableFor
from .session import openSession


# --------------------------------------------------------------------
class SessionSupport:
    '''
    Class that provides for the services that use SQLAlchemy the session support.
    All services that use SQLAlchemy have to extend this class in order to provide the sql alchemy session
    of the request, the session will be automatically handled by the session processor.
    '''

    def session(self):
        '''
        Provide or construct a session.
        '''
        return openSession()

# --------------------------------------------------------------------

def buildLimits(sql, offset=None, limit=None):
    '''
    Builds limiting on the SQL alchemy query.

    @param sql: SQL alchemy
        The sql alchemy query to use for limits.
    @param offset: integer|None
        The offset to fetch elements from.
    @param limit: integer|None
        The limit of elements to get.
    '''
    if offset is not None: sql = sql.offset(offset)
    if limit is not None: sql = sql.limit(limit)
    return sql

def buildQuery(sql, query, Mapped, only=None, exclude=None, orderBy=None, autoJoin=False, **mapping):
    '''
    Builds the query on the SQL alchemy query.

    @param sql: SQL alchemy
        The sql alchemy query to use.
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
    @param orderBy: object
        The default order by if none has been provided.
    @param autoJoin: boolean
        If True then it means that the query should auto join the tables that are for other columns then the mapped table.
    @param mapping: key arguments of columns or callable(sql, criteria) -> sql
        The column or sql build callable mappings provided for criteria name, the mapping columns will be automatically joined.
    '''
    assert query is not None, 'A query object is required'
    assert isinstance(autoJoin, bool), 'Invalid auto join flag %s' % autoJoin
    if autoJoin: table = tableFor(Mapped)
    
    columns = {}
    for name in namesFor(Mapped):
        cp = getattr(Mapped, name)
        # If no API type is detected it means that the API property is mapped
        for k in range(0, len(name)):
            if not name[k].isupper(): break
        name = name[:k + 1].lower() + name[k + 1:]
        if typeFor(cp) is None: columns[name] = cp
    columns = {name:columns.get(name) for name in namesFor(query)}

    if only:
        if not isinstance(only, tuple): only = (only,)
        assert not exclude, 'Cannot have only \'%s\' and exclude \'%s\' criteria at the same time' % (only, exclude)
        onlyColumns = {}
        for criteria in only:
            if isinstance(criteria, str):
                column = columns.get(criteria)
                assert column is not None, 'Invalid only criteria name \'%s\' for query %s' % (criteria, query)
                onlyColumns[criteria] = column
            else:
                typ = typeFor(criteria)
                assert isinstance(typ, TypeProperty), 'Invalid only criteria %s' % criteria
                assert isinstance(typ.type, TypeCriteria), 'Invalid only criteria %s' % criteria
                column = columns.get(typ.name)
                assert column is not None, 'Invalid only criteria \'%s\' for query %s' % (criteria, query)
                onlyColumns[typ.name] = column
        columns = onlyColumns
    elif exclude:
        if not isinstance(exclude, tuple): exclude = (exclude,)
        for criteria in exclude:
            if isinstance(criteria, str):
                column = columns.pop(criteria, None)
                assert column is not None, 'Invalid exclude criteria name \'%s\' for query %s' % (criteria, query)
            else:
                typ = typeFor(criteria)
                assert isinstance(typ, TypeProperty), 'Invalid exclude criteria %s' % criteria
                assert isinstance(typ.type, TypeCriteria), 'Invalid only criteria %s' % criteria
                column = columns.pop(typ.name, None)
                assert column is not None, 'Invalid exclude criteria \'%s\' for query %s' % (criteria, query)
 
    ordered, unordered = [], []
    for criteria, column in columns.items():
        if getattr(query.__class__, criteria) not in query: continue
        
        mapped = mapping.get(criteria)
        if mapped is not None:
            if isinstance(mapped, PropComparator): column = mapped
            else:
                assert callable(mapped), 'Invalid criteria \'%s\' mapping' % criteria
                sql = mapped(sql, getattr(query, criteria))
                continue
        
        if column is None: continue
        if autoJoin:
            ctable = None
            if isinstance(mapped, InstrumentedAttribute) and len(mapped.property.columns) == 1:
                ctable = mapped.property.columns[0].table
            elif isinstance(column, InstrumentedAttribute) and len(column.property.columns) == 1:
                ctable = column.property.columns[0].table
            # TODO: Gabriel: Fix this quick hack
            if ctable is not None and ctable != table and ctable.name not in str(sql): sql = sql.join(ctable)

        crt = getattr(query, criteria)
        if isinstance(crt, AsBoolean):
            assert isinstance(crt, AsBoolean)
            if AsBoolean.value in crt:
                sql = sql.filter(column == crt.value)
        elif isinstance(crt, AsLike):
            assert isinstance(crt, AsLike)
            if AsLike.like in crt: sql = sql.filter(column.like(crt.like))
            elif AsLike.ilike in crt: sql = sql.filter(column.ilike(crt.ilike))
        elif isinstance(crt, AsEqual):
            assert isinstance(crt, AsEqual)
            if AsEqual.equal in crt:
                sql = sql.filter(column == crt.equal)
        elif isinstance(crt, (AsDate, AsTime, AsDateTime, AsRange, AsRangeInt)):
            if crt.__class__.start in crt: sql = sql.filter(column >= crt.start)
            elif crt.__class__.until in crt: sql = sql.filter(column < crt.until)
            if crt.__class__.end in crt: sql = sql.filter(column <= crt.end)
            elif crt.__class__.since in crt: sql = sql.filter(column > crt.since)

        if isinstance(crt, AsOrdered):
            assert isinstance(crt, AsOrdered)
            if AsOrdered.ascending in crt:
                if AsOrdered.priority in crt and crt.priority:
                    ordered.append((column, crt.ascending, crt.priority))
                else:
                    unordered.append((column, crt.ascending, None))

    if ordered or unordered:
        if ordered: ordered.sort(key=lambda pack: pack[2])
        for column, asc, _priority in chain(ordered, unordered):
            if asc: sql = sql.order_by(column)
            else: sql = sql.order_by(column.desc())
    elif orderBy is not None: sql.order_by(orderBy)

    return sql

def iterateObjectCollection(sql, offset=None, limit=None, withTotal=False, _factorySlice=IterSlice):
    '''
    Iterates the collection of objects from the sql query based on the provided parameters.
    
    @param sql: SQL alchemy
        The sql alchemy query to iterate the collection from.
        
    ... the options
    
    @return: Iterable(object)
        The obtained collection of objects.
    '''
    if withTotal:
        if limit <= 0: return _factorySlice((), sql.count())
        sqlLimit = buildLimits(sql, offset, limit)
        return _factorySlice(sqlLimit.yield_per(10), sql.count(), offset, limit)
    return sql.yield_per(10)

def iterateCollection(sql, offset=None, limit=None, withTotal=False, _factorySlice=IterSlice):
    '''
    Iterates the collection of value from the sql query based on the provided parameters.
    
    @param sql: SQL alchemy
        The sql alchemy query to iterate the collection from.
        
    ... the options
    
    @return: Iterable(object)
        The obtained collection of values.
    '''
    if withTotal:
        if limit == 0: return _factorySlice((), sql.count())
        sqlLimit = buildLimits(sql, offset, limit)
        return _factorySlice((value for value, in sqlLimit.all()), sql.count(), offset, limit)
    return (value for value, in sql.all())

# --------------------------------------------------------------------

def insertModel(Mapped, model, **data):
    '''
    Inserts the provided model entity using the current session.

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
    assert isinstance(Mapped, MappedSupport), 'Invalid mapped class %s' % Mapped
    if isinstance(model, Mapped): dbModel = model
    else:
        typ = typeFor(Mapped)
        assert isinstance(typ, TypeModel), 'Invalid model class %s' % Mapped
        
        dbModel = Mapped()
        for name, prop in typ.properties.items():
            if name in data or not isinstance(getattr(Mapped, name), InstrumentedAttribute): continue
            if prop in model: setattr(dbModel, name, getattr(model, name))
            
        for name, value in data.items(): setattr(dbModel, name, value)
    
    openSession().add(dbModel)
    openSession().flush((dbModel,))
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
    assert isinstance(Mapped, MappedSupport), 'Invalid mapped class %s' % Mapped
    if isinstance(model, Mapped):
        dbModel = model
        openSession().merge(dbModel)
    else:
        typ = typeFor(Mapped)
        assert isinstance(typ, TypeModel), 'Invalid model class %s' % Mapped
        assert typ.isValid(model), 'Invalid model %s for %s' % (model, typ)
        assert isinstance(typ.propertyId, TypeProperty), 'Invalid property id of %s' % typ

        idName = typ.propertyId.name
        dbModel = openSession().query(Mapped).filter(getattr(Mapped, idName) == getattr(model, idName)).one()
        if not dbModel: raise IdError(typ.propertyId)
        for name, prop in typ.properties.items():
            if name in data or not isinstance(getattr(Mapped, name), InstrumentedAttribute): continue
            if prop in model: setattr(dbModel, name, getattr(model, name))
            
        for name, value in data.items(): setattr(dbModel, name, value)
    
    openSession().flush((dbModel,))
    return dbModel

def deleteModel(Mapped, identifier):
    '''
    Delete the provided model based on the provided identifier using the current session.

    @param Mapped: class
        The mapped class to update the model for, the model type is required to have a property id.
    @param identifier: object
        The identifier to delete for.
    @return: boolean
        True if any entry was deleted, False otherwise.
    '''
    assert isclass(Mapped), 'Invalid class %s' % Mapped
    assert isinstance(Mapped, MappedSupport), 'Invalid mapped class %s' % Mapped
    typ = typeFor(Mapped)
    assert isinstance(typ, TypeModel), 'Invalid model class %s' % Mapped
    assert isinstance(typ.propertyId, TypeProperty), 'Invalid property id of %s' % typ
    assert typ.propertyId.isValid(identifier), 'Invalid identifier %s for %s' % (identifier, typ.propertyId)
    
    try: model = openSession().query(Mapped).filter(getattr(Mapped, typ.propertyId.name) == identifier).one()
    except NoResultFound: return False
    openSession().delete(model)
    return True
