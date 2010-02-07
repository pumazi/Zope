##############################################################################
#
# Copyright (c) 2002 Zope Corporation and Contributors. All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE
#
##############################################################################
import pdb

from Acquisition import Implicit
from Shared.DC.ZRDB.namedtuple import namedtuple

##class Record(object):
##    def __init__(self, data, parent, binit=None):
##        if parent is not None:
##            pass
##            # self=self.__of__(parent) # ???? what madness is this?
##        if binit:
##            binit(self)

class SQLAlias(object):
    # previously inherited ExtensionClass.Base
    def __init__(self, name):
        self._n=name
    def __of__(self, parent):
        return getattr(parent, self._n)

class NoBrains:
    pass


def record_cls_factory(data, fieldnames, schema, parent, brains, zbrains):
    """Return a custom 'record' class inheriting from Record, Implicit,
    brains, and zbrains).
    
    The namedtuple base class with look something like this:
    
    class TupleWithFieldnames(tuple):
        'TupleWithFieldnames(foo, bar)' 

        __slots__ = () 

        _fields = ('foo', 'bar') 

        def __new__(cls, foo, bar):
            return tuple.__new__(cls, (foo, bar)) 

        @classmethod
        def _make(cls, iterable, new=tuple.__new__, len=len):
            'Make a new TupleWithFieldnames object from a sequence or iterable'
            result = new(cls, iterable)
            if len(result) != 2:
                raise TypeError('Expected 2 arguments, got %d' % len(result))
            return result 

        def __repr__(self):
            return 'TupleWithFieldnames(foo=%r, bar=%r)' % self 

        def _asdict(t):
            'Return a new dict which maps field names to their values'
            return {'foo': t[0], 'bar': t[1]} 

        def _replace(self, **kwds):
            'Return a new TupleWithFieldnames object replacing specified fields with new values'
            result = self._make(map(kwds.pop, ('foo', 'bar'), self))
            if kwds:
                raise ValueError('Got unexpected field names: %r' % kwds.keys())
            return result 

        def __getnewargs__(self):
            return tuple(self) 

        foo = property(itemgetter(0))
        bar = property(itemgetter(1))

    """
    # to create a namedtuple, we need a space delimited list of names
    fieldnames = ' '.join(fieldnames)
    namedtuple_cls = namedtuple('TupleWithFieldnames', fieldnames) #, verbose=True)
    bases = (namedtuple_cls, brains)
    if zbrains is not brains:
        bases += (zbrains,)
    stubbase = type('stubclass', bases, {})
    class BrainyRecord(stubbase):
        __record_schema__ = schema #...why?
        aliases = {}

        def __new__(cls, data, parent=None, brains=None):
            """Override the namedtuple __new__ method to handle expected
            BrainyRecord API"""
            self = tuple.__new__(cls, data) 
            cls._parent = parent
            if hasattr(brains, '__init__'):
                binit=brains.__init__
                if hasattr(binit,'im_func'):
                    binit=binit.im_func
                binit(self)
            binit=brains.__init__
            return self

        def __of__(self, parent):
            # hack...I don't know how to properly implement Aquisition
            BrainyRecord._parent = parent
            return self

        @classmethod
        def register_alias(cls, attr_name, alias_name):
            cls.aliases[alias_name] = attr_name
        
        @classmethod
        def register_lowercase_aliases(cls):
            for name in cls._fields:
                lowercase = name.lower()
                if lowercase != name:
                    cls.register_alias(name, lowercase)

        @classmethod
        def register_uppercase_aliases(cls):
            for name in cls._fields:
                uppercase = name.upper()
                if uppercase != name:
                    cls.register_alias(name, uppercase)

        def __getitem__(self, key):
            try:
                return namedtuple_cls.__getitem__(self,key)
            except TypeError:
                return self.get_item_by_name(key)

        def get_item_by_name(self, key):
            try:
                return getattr(self, key)
            except KeyError:
                return get_item_by_alias (key)

        def get_item_by_alias(self, key):
            truename = self.aliases[key]
            return getattr(self, truename)

        def __getattr__(self, name):
            truename = self.aliases.get(name, None)
            if not truename:
                raise AttributeError, "No attribute or alias found matching:" + name
            return getattr(self, truename)

        def as_dict (self):
            return self._asdict()

        def __setattr__ (self, name, value):
            truename = self.aliases.get(name, name)
            kwargs = {truename:value}
            try:
                self._replace(**kwargs)
            except ValueError,e:
                msg = str(e)
                raise AttributeError(msg)

        def __setitem__ (self, key, value):
            truename = self.aliases.get(key, key)
            kwargs = {truename:value}
            self._replace(**kwargs)
        
        def __add__ (self, other):
            raise TypeError, "Two Records cannot be added together."
        
        def __mul__ (self, other):
            raise TypeError, "Two Records cannot be multiplied."
        
        def __delitem__ (self, index):
            raise TypeError, "Record items cannot be deleted."
        
        @property
        def aq_self (self):  #hack -- don't know how to implement Acquisition support
            return self

        @property
        def aq_parent (self):  #hack -- don't know how to implement Acquisition support
            return self._parent

    BrainyRecord.register_uppercase_aliases()
    BrainyRecord.register_lowercase_aliases()
    return BrainyRecord



class Results:
    """Class for providing a nice interface to DBI result data
    """
    _index=None

    # We need to allow access to not-explicitly-protected
    # individual record objects contained in the result.
    __allow_access_to_unprotected_subobjects__=1

    def __init__(self,(items,data),brains=NoBrains, parent=None,
                 zbrains=None):

        self._data=data
        self.__items__=items
        self._parent=parent
        self._names=names=[]
        self._schema=schema={}
        self._data_dictionary=dd={}
        aliases=[]
        if zbrains is None:
            zbrains=NoBrains

        for i,item in enumerate(items):
            name=item['name']
            name=name.strip()
            if not name:
                raise ValueError, 'Empty column name, %s' % name
            if schema.has_key(name):
                raise ValueError, 'Duplicate column name, %s' % name
            schema[name]=i
            dd[name]=item
            names.append(name)

        self._nv=nv=len(names)

        # Create a record class to hold the records.
        names=tuple(names)

        self._record_cls = record_cls_factory (data, names, schema, parent, brains,
                                          zbrains)

        # OK, we've read meta data, now get line indexes

    def _searchable_result_columns(self):
        return self.__items__
    def names(self):
        return self._names
    def data_dictionary(self):
        return self._data_dictionary

    def __len__(self): return len(self._data)

    def __getitem__(self,index):
        if index==self._index: return self._row
        parent = self._parent
        rec = self._record_cls(self._data[index], parent)
        if parent is not None: 
            rec = rec.__of__(parent)
        self._index = index
        self._row = rec
        return rec

    def tuples(self):
        return map(tuple, self)

    def dictionaries(self):
        """Return a list of dicts, one for each data record.
        """
        return [rec.as_dict() for rec in self]

    def asRDB(self): # Waaaaa
        r=[]
        append=r.append
        strings=[]
        nstrings=[]
        items=self.__items__
        indexes=range(len(items))
        for i in indexes:
            item=items[i]
            t=item['type'].lower()
            if t=='s' or t=='t':
                t=='t'
                strings.append(i)
            else: nstrings.append(i)
            if item.has_key('width'): append('%s%s' % (item['width'], t))
            else: r.append(t)


        r=['\t'.join(self._names), '\t'.join(r)]
        append=r.append
        row=['']*len(items)
        tostr=str
        for d in self._data:
            for i in strings:
                v=tostr(d[i])
                if v:
                    if v.find('\\') > 0: v='\\\\'.join(v.split('\\'))
                    if v.find('\t') > 0: v='\\t'.join(v.split('\t'))
                    if v.find('\n') > 0: v='\\n'.join(v.split('\n'))
                row[i]=v
            for i in nstrings:
                row[i]=tostr(d[i])
            append('\t'.join(row))
        append('')

        return '\n'.join(r)
