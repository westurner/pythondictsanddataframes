# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light,md
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.5.2
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# # Dicts and DataFrames

# ## Question / Problem / Challenge
# Question: Now that dicts are insertion-ordered (since Python 3.6), can we lookup items by integer-location?
# - As of CPython 3.10: No; the public Python `dict` API neither:
#   - (1) offers any method to access keys, values, or items by integer-location; nor
#   - (2) exposes anything from the underlying C code like `dict._array` which could be used for such a method. `dict._array` would be considered an implementation detail that could be different in Python versions and implementations
#
# How could lookup of `dict` keys, values, and items *by integer-location* be implemented?
#     - This is the subject of this document.

# ## Background
# - The CPython dict is an insertion-ordered Hashmap:  
#   https://docs.python.org/3/library/stdtypes.html#mapping-types-dict
#   - https://github.com/python/cpython/blob/master/Objects/dictobject.c
#   - https://github.com/python/cpython/blob/master/Objects/odictobject.c
# - The Pandas Series and DataFrames are insertion-ordered columnar data structures  
#   - https://pandas.pydata.org/pandas-docs/stable/reference/series.html  
#     - https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.Series.html#pandas.Series 
#     - https://github.com/pandas-dev/pandas/blob/master/pandas/core/series.py
#   - https://pandas.pydata.org/pandas-docs/stable/reference/frame.html  
#     - https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.html  
#     - https://github.com/pandas-dev/pandas/blob/master/pandas/core/frame.py

import itertools
import pandas as pd
import pytest
import random
try:
    display  # IPython
except NameError:
    def display(*args): print(args)
pd.set_option('display.notebook_repr_html', False)

# ### CPython dict basics

odict = {'a':'A', 'b':'B', 'c':'C', 'd': 'D'}
odict = dict(a='A', b='B', c='C', d='D')
odict = dict((x, x.upper()) for x in 'abcd')  # list comprehension
odict = {x:x.upper() for x in 'abcd'}         # dict comprehension
odict = dict.fromkeys('abcd')
[odict.__setitem__(x, x.upper()) for x in 'abcd']
display(odict)
assert list(odict.keys()) == list('abcd') == ['a', 'b', 'c', 'd']
assert random.seed(1) or list(odict.keys()) == random.seed(2**10) or list(odict.keys())
assert list(odict.values()) == list('ABCD')
assert list(odict.items()) == [('a', 'A'), ('b', 'B'), ('c', 'C'), ('d', 'D')]

# `itertools.islice(dict.items())` is suboptimal for a number of cases because we don't need to iterate through the items at the beginning: we could directly address the underlying array.

# +

# This would not call next() unnecessarily:
with pytest.raises(AttributeError): # 'dict' object has no attribute '_array'
    odict._array[3]   # _array[3]
# -

# ## Possible Solutions

# ### No changes to CPython

# #### Make an unnecessary copy of the whole dict in order to only take(3)

assert list(odict.items())[3] == ('d', 'D')

# #### Call `itertools.islice(dict.items())`
# - Does this call `next()`, `next()`, `next()`, `next()` unnecessarily?
# - `itertools.islice(dict.items())` is suboptimal for a number of cases because we don't need to iterate through the items at the beginning. Directly addressing the underlying array would be much faster but unlikely to happen because the underlying array is an implementation detail.

list(itertools.islice(odict.items(), 0))

list(itertools.islice(odict.items(), 3))

list(itertools.islice(odict.items(), 3, 3+1))

# ### Change CPython

# #### Expose something like `dict._array`
# - Again, the underlying array is a \[CPython,] implementation detail
# - So, there must be methods that provide access to the [(key, item),] data that hide the implementation details.

# #### Overload `dict.__getitem__` (`dict[]`)
#
# `dict[]` (`dict.__getitem__`) is already used for lookup by key value, so `dict[3]` could either be lookup by value or lookup by integer-location: which would be dangerously abiguous at runtime and frustratingly vague to review. (See also the note below regarding the fate of the Pandas `.ix.__getitem__` method).

# #### Make all iterators subscriptable: define `iterator.__getitem__`
#
# `dict.items()[3]` fails with a `TypeError: 'dict_items' object is not subscriptable`:`dict.items()` returns a view (instead of an unnecessarily copied list like in Python 2) which is not subscriptable.
#
# Could we define `iterator.__getitem__` such that:
#
# ```python
# obj = list('abcd')
# iter(obj)[3] => islice(obj, 3, 3+1)
# iter(obj)[3:4] => islice(obj, 3, 4)
# iter(obj)[0:4:2] => islice(obj, 1, 4, 2)
# ```
#
# - This would require a change to the python grammar.
# - This would result in implicit iteration/traversal, which may be destructive and opaquely resource-prohibitive.
# - This would not break existing code.

# #### Add `dict.getkey(index)` and `dict.getitem(index)`
# ```python
# def getkey(self: dict, index: int):
#     pass
#
# def getitem(self: dict, index: int):
#     pass
# ```
#
# - This does not support slices
# - This still has to unnecessarily iterate with `islice` without something like `dict._array`

# #### Make `dict.keys()`, `dict.values()`, and `dict.items()` subscriptable
#
# ```python
# obj = dict.fromkeys('abcd')
# obj.keys()[3] => next(islice(obj, 3))
# ```
#
# - This would require a change to the python grammar.
# - This would be a special case; and then we'd all be asking for subscriptable iterators, too.
# - This would not break existing code.

# iterator[3] does not call islice(iterator, 3):
with pytest.raises(TypeError): # 'dict_keys' object is not subscriptable
    odict.keys()[3]
with pytest.raises(TypeError): # 'dict_values' object is not subscriptable
    odict.values()[3]
with pytest.raises(TypeError): # 'dict_items' object is not subscriptable
    odict.items()[3]


# #### Define `dict.keys.__getitem__` and handle slices
#
# ```python
# obj = dict.fromkeys('abcd')
# obj.keys[3] => obj._array[3]
# ```
#
# - This would (edit: not) be backward incompatible; though everyone is used to `dict.keys()` being a method and not a property, so it would look weird in reviews for awhile (and visually-indiscernable)
#   To not break all existing code, it would have to be:
#   ```python
#   obj = dict.fromkeys('abcd')
#   obj.keys()[3] => obj._array[3]
#   ```
#   
#   Which brings us back to the previous question.
# - Would this be confusing to newcomers? Why don't other iterators work that way?

# #### Copy the Pandas Series / DataFrame `.iloc` API?

# ##### How is the Pandas DataFrame API at all relevant to dicts?
# - Pandas DataFrames (and Series, which have an index and one column; more like dicts) support key/value lookup just like dicts
# - IIUC, OP is asking for lookup by integer-location; which is supported by `DataFrame.iloc` (and `Series.iloc`)
# - Pandas already handles the presented use cases with an `.iloc` method that handles slices and tuples (and callables).
#   - Pandas [used to have `.ix`](https://pandas.pydata.org/pandas-docs/version/0.23.4/generated/pandas.DataFrame.ix.html), which was:
#     > A primarily label-location based indexer, with integer position fallback.
#     > 
#     > Warning: Starting in 0.20.0, the .ix indexer is deprecated, in favor of the more strict .iloc and .loc indexers.
# - The Pandas API is now also implemented by Dask, Modin, CuDF.
#   It may be the most widely-used DataFrame API.
# - Granted, a DataFrame is not the same as an OrderedHashmap; because we often find that data is multi-columnar and we usually don't want to have to `lookup`/`seek()` to the n-th field of each hashmap value.
#   But we do want indexed data with fast sequential reads and the option to return one or more items by integer-location.

# ##### Add an `.iloc` property with a `__getitem__` to `dict` that returns just the key (slice) or the `(key, item)` (slice)
# ```python
# obj = dict.fromkeys('abcd')
# obj.iloc[3] => obj._array[3][0]  # key-only? or
# obj.iloc[3] => obj._array[3]     # (key, item)?
# ```

# ##### Add an `.iloc` property to the `.keys`, `.values`, and `.items` methods?
#
# ```python
# obj.keys.iloc[3] => obj._array[3][0]
# obj.values.iloc[3] => obj._array[3][1]
# obj.items.iloc[3] => obj._array[3]
# ```
#
# - Is there any precedent for adding a property to a method in the CPython standard library?
# - It can be done with *slow* init-time binding and/or metaclassery.
#   - See: `IlocIndexer` below

# #### Add `.keys_iloc()`, `.values_iloc()`, and `.items_iloc()` to `dict`
#
# - Does not require binding `IlocIndexer` to `.keys.iloc`, `.values.iloc`, and `.items.iloc` at `dict.__init__` time or metaclassery.
# - Supports slices

# +
def _dict_view_islice(iterable, start: int=None, stop: int=None, step: int=None):
    # This implementation calls islice()
    # which, AFAIU, calls next() a bunch of times unnecessarily
    _slice = slice(start, stop, step) if not isinstance(start, slice) else start
    return itertools.islice(iterable, _slice.start, _slice.stop, _slice.step)
    
def keys_iloc(self: dict, start: int=None, stop: int=None, step: int=None):
    return _dict_view_islice(self, start, stop, step)

def values_iloc(self: dict, start: int=None, stop: int=None, step: int=None):
    return _dict_view_islice(self.values(), start, stop, step)

def items_iloc(self: dict, start: int=None, stop: int=None, step: int=None):
    return _dict_view_islice(self.items(), start, stop, step)

assert next(keys_iloc(odict, 3)) == 'd'
assert next(values_iloc(odict, 3)) == 'D'
assert next(items_iloc(odict, 3)) == ('d', 'D')
assert list(items_iloc(odict, 0, 4, 2)) == [('a', 'A'), ('c', 'C')]
assert list(items_iloc(odict, slice(0, 4, 2))) == [('a', 'A'), ('c', 'C')]

# ...

def _dict_view_ilookup(obj: dict, start: int=None, stop: int=None, step: int=None):
    # This implementation would access the underlying dict array values directly
    # (without calling iter() and next() on dict views)
    _slice = slice(start, stop, step) if not isinstance(start, slice) else start
    return obj._array[_slice]


# -

# ### Support passing slices to methods so that `.keys(1:2)` or `.keys_iloc(1:2)` works
#
# - AFAIU, this would require a change to the Python grammar.

# ### Add `start`, `stop`, and `step` arguments to `.keys()`, were `start` can optionally be a `slice()`
#
# - This would not be break any existing code, but alone would not support normal slice syntax.

# +
class IlocIndexer:
    def __init__(self, obj):
        self.obj = obj

    def __getitem__(self, obj):
        if isinstance(obj, int):
            _slice = slice(obj, obj+1)
        elif isinstance(obj, slice):
            _slice = obj
        else:
            _slice = slice(obj)
        return itertools.islice(self.obj(), _slice.start, _slice.stop, _slice.step)
        # return self.obj._array[_slice]


class Dict(dict):
    def keys(self):
        return super().keys()

    def values(self):
        return super().values()
    
    def items(self):
        return super().items()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.keys.__func__.iloc = IlocIndexer(self.keys)
        self.values.__func__.iloc = IlocIndexer(self.values)
        self.items.__func__.iloc = IlocIndexer(self.items)

d = Dict.fromkeys('abcd')
d = Dict(odict)
assert list(d.keys()) == list('abcd')
assert list(d.keys.iloc[0]) == list('a')
assert list(d.keys.iloc[2:4]) == list('cd')
assert list(d.values()) == list('ABCD')
assert list(d.values.iloc[0]) == list('A')
assert list(d.values.iloc[2:4]) == list('CD')
assert list(d.items()) == [(x,x.upper()) for x in 'abcd']
assert list(d.items.iloc[0]) == [('a', 'A')]
assert list(d.items.iloc[2:4]) == [('c', 'C'), ('d', 'D')]
# -

# ## If you give a mouse a cookie
# **Once we've added the ability to lookup from (now ordered) dicts by integer-location, what else will people ask for?**
#
# Probably features from `pandas.Series`, `pandas.DataFrame`, `pandas.MultiIndex`.
# - Slices
# - Multidimensional lookup
# - Lookup of integer-locations

# ### Slices

df = pd.DataFrame.from_dict(odict, orient='index')
display(df)
df.columns = [0]
assert list(df.iloc[2:4]) == [0]
df.columns = ['letter']
assert list(df.iloc[2:4]) == ['letter']

# ### Multidimensional lookup: `.iloc[0, 1, 0]`

# +
df = pd.DataFrame.from_dict(odict, orient='index')
df.columns = ['letter']
display(df)
assert df.iloc[2, 0] == 'C'
assert df.iloc[3, 0] == 'D'
assert list(df.iloc[2:4, 0]) == ['C', 'D']

df = df.T
display(df)
assert list(df.iloc[0, 2:4]) == ['C', 'D']
# -

# ### Lookup of integer-locations

# #### Python `list.index(value)`

alist = list('abcd')
assert alist.index('d') == 3

# #### Python `dict.get(key, default=None)`

assert odict.get('d') == 'D' 

# Something like this would sort next to `.get()` when tab-completing:
# ```python
# assert odict.getkeypos('d') == 3
# ```

# #### Pandas 

# +
df = pd.DataFrame.from_dict(odict, orient='index')
display(df)

# Lookup ordinal integer-location by index value:
assert df.index.get_loc('d') == 3
assert df.iloc[df.index.get_loc('d')].tolist() == ['D']

# Lookup index values by column value:
assert df[df[0] == 'D'].index.tolist() == ['d']
df.columns = ['letters']
assert df[df['letters'] == 'D'].index.tolist() == ['d'] == \
    df.query('letters == "D"').index.tolist()

# Lookup ordinal integer-location(s) of value:
assert [df.index.get_loc(idxval) for idxval in df[df['letters'] == 'D'].index.tolist()] == [3]

import numpy as np
assert list(np.where(df['letters'].values == 'D')[0]) == [3]
# -

assert \
    df[df['letters'].eq('D')].index == \
    df.index[df['letters'].eq('D')] == \
    df.query('letters == "D"').index == \
    df[df['letters'] == 'D'].index == \
    df.eval('x = letters == "D"').query("x").index

# ### Why would I use Series or DataFrame here instead of dict?
# **How do and why would I refactor code to use `Series` or `DataFrame` instead of `dict`?**
# - Why:
#   - performance & scalability (Cython, profiling, dask.distributed scales the DataFrame API to multiple processes and/or multiple machines with datasets larger than can fit into RAM)
#   - Maintainability & security: nobody wants to figure out your poor-man's in-memory datastore implemented with only the standard library; months later you realize you need to optimize a query and something like `df.query` would take your team years to get partially working, so you just dump everything into a database and add SQL vulnerabilities and a whole dict/object layer, and all you needed was a join and merge that you *could* just do with coreutils join and merge (but that would lose type safety and unescaped newlines would then be as dangerous as unparametrized SQL queries). And then it's time to write docs for what we did here.
#   - De/serialization (`to_numpy`, `to_parquet`, `to_json`, `to_csv`, `to_html`, `to_markdown`)
# - How:
#   - Add a dependency on an external library that needs to be compiled or installed and kept upgraded.
#   - Load the data into a DataFrame
#   - Read the docs and use the API; which supports lookup by value, by integer-position (`.iloc`), by complex chained queries, etc.

# # Pandas DataFrame reference
# - There are many excellent Pandas tutorials.
# - There was a docs sprint.
# - `Series` have an `.index` and no `.columns` (only one column; more like `dict`)
# - `DataFrames` have an `.index` and a `.columns`
# - There are a number of ways to load a dict into a DataFrame and lookup values:

df = pd.DataFrame.from_records([odict])
display(df)
assert list(df.index) == [0]
assert list(df.columns) == list('abcd')
assert list(df.iloc[0]) == list('ABCD')
assert list(df.iloc[0].index) == list(df.columns) == list('abcd')
assert list(df.iloc[0]) == list(df.loc[0])
assert list(df.loc[0].index) == list(df.columns) == list('abcd')
assert list(df.loc[0]) == list('ABCD')
assert df.iloc[0]['a'] == 'A' == df.loc[0]['a'] == df.iloc[0, 0] == df.loc[0, 'a']

df = pd.DataFrame.from_records(list(odict.items()))
display(df)
assert list(df.index) == [0, 1, 2, 3]
assert list(df.columns) == [0, 1]
assert list(df.iloc[0]) == list(df.loc[0])
assert list(df.iloc[0]) == ['a', 'A']
assert list(df.iloc[0].index) == list(df.columns) == [0, 1]


with pytest.raises(ValueError):
    df = pd.DataFrame.from_dict(odict)

df = pd.DataFrame.from_dict(odict.items())
display(df)
assert list(df.index) == [0, 1, 2, 3]
assert list(df.columns) == [0, 1]
assert df[0][0] == 'a' == df.iloc[0].iloc[0] == df.iloc[0, 0]

df = pd.DataFrame.from_dict(odict, orient='index')
display(df)
assert list(df.index) == list('abcd')
assert list(df.columns) == [0]
assert df.loc['a'][0] == 'A' == df.iloc[0][0] == df.iloc[0, 0]

df.columns = ['letter']
display(df)
assert df.loc['a']['letter'] == 'A' == df.iloc[0][0] == df.loc['a'].iloc[0] == df.iloc[0].loc['letter'] == df.iloc[0, 0]

df.index = ['red', 'green', 'blue', 'orange']
display(df)

assert type(df.iloc[0][0]) == str
df.iloc[0][0] = dict.fromkeys('abc')
assert type(df.iloc[0][0]) == dict
display(df)
