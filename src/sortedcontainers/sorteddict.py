"""Sorted Dict
==============

:doc:`Sorted Containers<index>` is an Apache2 licensed Python sorted
collections library, written in pure-Python, and fast as C-extensions. The
:doc:`introduction<introduction>` is the best way to get started.

Sorted dict implementations:

.. currentmodule:: sortedcontainers

* :class:`SortedDict`
* :class:`SortedKeysView`
* :class:`SortedItemsView`
* :class:`SortedValuesView`

"""

import warnings
from collections.abc import ItemsView, KeysView, Mapping, Sequence, ValuesView
from itertools import chain

from .sortedlist import SortedList, recursive_repr
from .sortedset import SortedSet


class SortedDict(dict):
    """Sorted dict is a sorted mutable mapping.

    Sorted dict keys are maintained in sorted order. The design of sorted dict
    is simple: sorted dict inherits from dict to store items and maintains a
    sorted list of keys.

    Sorted dict keys must be hashable and comparable. The hash and total
    ordering of keys must not change while they are stored in the sorted dict.

    Mutable mapping methods:

    * :func:`SortedDict.__getitem__` (inherited from dict)
    * :func:`SortedDict.__setitem__`
    * :func:`SortedDict.__delitem__`
    * :func:`SortedDict.__iter__`
    * :func:`SortedDict.__len__` (inherited from dict)

    Methods for adding items:

    * :func:`SortedDict.setdefault`
    * :func:`SortedDict.update`

    Methods for batch editing:

    * :func:`SortedDict.batch_update`

    Methods for removing items:

    * :func:`SortedDict.clear`
    * :func:`SortedDict.pop`
    * :func:`SortedDict.popitem`

    Methods for looking up items:

    * :func:`SortedDict.__contains__` (inherited from dict)
    * :func:`SortedDict.get` (inherited from dict)
    * :func:`SortedDict.peekitem`

    Methods for views:

    * :func:`SortedDict.keys`
    * :func:`SortedDict.items`
    * :func:`SortedDict.values`

    Methods for miscellany:

    * :func:`SortedDict.copy`
    * :func:`SortedDict.fromkeys`
    * :func:`SortedDict.__reversed__`
    * :func:`SortedDict.__eq__` (inherited from dict)
    * :func:`SortedDict.__ne__` (inherited from dict)
    * :func:`SortedDict.__repr__`
    * :func:`SortedDict._check`

    Sorted list methods available (applies to keys):

    * :func:`SortedList.bisect_left`
    * :func:`SortedList.bisect_right`
    * :func:`SortedList.index`
    * :func:`SortedList.irange`
    * :func:`SortedList.islice`
    * :func:`SortedList._reset`

    Additional sorted list methods available, if key-function used:

    * :func:`SortedKeyList.bisect_key_left`
    * :func:`SortedKeyList.bisect_key_right`
    * :func:`SortedKeyList.irange_key`

    Sorted dicts may only be compared for equality and inequality.

    """

    def __init__(self, *args, **kwargs):
        """Initialize sorted dict instance.

        Optional key-function argument defines a callable that, like the `key`
        argument to the built-in `sorted` function, extracts a comparison key
        from each dictionary key. If no function is specified, the default
        compares the dictionary keys directly. The key-function argument must
        be provided as a positional argument and must come before all other
        arguments.

        Optional iterable argument provides an initial sequence of pairs to
        initialize the sorted dict. Each pair in the sequence defines the key
        and corresponding value. If a key is seen more than once, the last
        value associated with it is stored in the new sorted dict.

        Optional mapping argument provides an initial mapping of items to
        initialize the sorted dict.

        If keyword arguments are given, the keywords themselves, with their
        associated values, are added as items to the dictionary. If a key is
        specified both in the positional argument and as a keyword argument,
        the value associated with the keyword is stored in the
        sorted dict.

        Sorted dict keys must be hashable, per the requirement for Python's
        dictionaries. Keys (or the result of the key-function) must also be
        comparable, per the requirement for sorted lists.

        >>> d = {'alpha': 1, 'beta': 2}
        >>> SortedDict([('alpha', 1), ('beta', 2)]) == d
        True
        >>> SortedDict({'alpha': 1, 'beta': 2}) == d
        True
        >>> SortedDict(alpha=1, beta=2) == d
        True

        """
        if args and (args[0] is None or callable(args[0])):
            _key = self._key = args[0]
            args = args[1:]
        else:
            _key = self._key = None

        # Reaching through ``self._list`` repeatedly adds unnecessary overhead
        # so cache references to sorted list methods. Some sorted list
        # methods are also exposed publicly.

        self._set_list(SortedList(key=_key))

        self._update(*args, **kwargs)

    def _set_list(self, _list):
        """Swap the sorted key list and re-cache its bound methods.

        Used by :func:`SortedDict.__init__` and :func:`SortedDict.batch_update`
        to install a fully-built sorted key list.

        :param _list: sorted list of keys

        """
        self._list = _list
        self._list_add = _list.add
        self._list_clear = _list.clear
        self._list_iter = _list.__iter__
        self._list_reversed = _list.__reversed__
        self._list_pop = _list.pop
        self._list_remove = _list.remove
        self._list_update = _list.update

        # Expose some sorted list methods publicly.

        self.bisect_left = _list.bisect_left
        self.bisect = _list.bisect_right
        self.bisect_right = _list.bisect_right
        self.index = _list.index
        self.irange = _list.irange
        self.islice = _list.islice
        self._reset = _list._reset

        if self._key is not None:
            self.bisect_key_left = _list.bisect_key_left
            self.bisect_key_right = _list.bisect_key_right
            self.bisect_key = _list.bisect_key
            self.irange_key = _list.irange_key

    @property
    def key(self):
        """Function used to extract comparison key from keys.

        Sorted dict compares keys directly when the key function is none.

        """
        return self._key

    @property
    def iloc(self):
        """Cached reference of sorted keys view.

        Deprecated in version 2 of Sorted Containers. Use
        :func:`SortedDict.keys` instead.

        """
        # pylint: disable=attribute-defined-outside-init
        try:
            return self._iloc
        except AttributeError:
            warnings.warn(
                'sorted_dict.iloc is deprecated.' ' Use SortedDict.keys() instead.',
                DeprecationWarning,
                stacklevel=2,
            )
            _iloc = self._iloc = SortedKeysView(self)
            return _iloc

    def clear(self):
        """Remove all items from sorted dict.

        Runtime complexity: `O(n)`

        """
        dict.clear(self)
        self._list_clear()

    def __delitem__(self, key):
        """Remove item from sorted dict identified by `key`.

        ``sd.__delitem__(key)`` <==> ``del sd[key]``

        Runtime complexity: `O(log(n))` -- approximate.

        >>> sd = SortedDict({'a': 1, 'b': 2, 'c': 3})
        >>> del sd['b']
        >>> sd
        SortedDict({'a': 1, 'c': 3})
        >>> del sd['z']
        Traceback (most recent call last):
          ...
        KeyError: 'z'

        :param key: `key` for item lookup
        :raises KeyError: if key not found

        """
        dict.__delitem__(self, key)
        self._list_remove(key)

    def __iter__(self):
        """Return an iterator over the keys of the sorted dict.

        ``sd.__iter__()`` <==> ``iter(sd)``

        Iterating the sorted dict while adding or deleting items may raise a
        :exc:`RuntimeError` or fail to iterate over all keys.

        """
        return self._list_iter()

    def __reversed__(self):
        """Return a reverse iterator over the keys of the sorted dict.

        ``sd.__reversed__()`` <==> ``reversed(sd)``

        Iterating the sorted dict while adding or deleting items may raise a
        :exc:`RuntimeError` or fail to iterate over all keys.

        """
        return self._list_reversed()

    def __setitem__(self, key, value):
        """Store item in sorted dict with `key` and corresponding `value`.

        ``sd.__setitem__(key, value)`` <==> ``sd[key] = value``

        Runtime complexity: `O(log(n))` -- approximate.

        >>> sd = SortedDict()
        >>> sd['c'] = 3
        >>> sd['a'] = 1
        >>> sd['b'] = 2
        >>> sd
        SortedDict({'a': 1, 'b': 2, 'c': 3})

        :param key: key for item
        :param value: value for item

        """
        if key not in self:
            self._list_add(key)
        dict.__setitem__(self, key, value)

    _setitem = __setitem__

    def __or__(self, other):
        if not isinstance(other, Mapping):
            return NotImplemented
        items = chain(self.items(), other.items())
        return self.__class__(self._key, items)

    def __ror__(self, other):
        if not isinstance(other, Mapping):
            return NotImplemented
        items = chain(other.items(), self.items())
        return self.__class__(self._key, items)

    def __ior__(self, other):
        self._update(other)
        return self

    def copy(self):
        """Return a shallow copy of the sorted dict.

        Runtime complexity: `O(n)`

        :return: new sorted dict

        """
        return self.__class__(self._key, self.items())

    __copy__ = copy

    @classmethod
    def fromkeys(cls, iterable, value=None):
        """Return a new sorted dict initailized from `iterable` and `value`.

        Items in the sorted dict have keys from `iterable` and values equal to
        `value`.

        Runtime complexity: `O(n*log(n))`

        :return: new sorted dict

        """
        return cls((key, value) for key in iterable)

    def keys(self):
        """Return new sorted keys view of the sorted dict's keys.

        See :class:`SortedKeysView` for details.

        :return: new sorted keys view

        """
        return SortedKeysView(self)

    def items(self):
        """Return new sorted items view of the sorted dict's items.

        See :class:`SortedItemsView` for details.

        :return: new sorted items view

        """
        return SortedItemsView(self)

    def values(self):
        """Return new sorted values view of the sorted dict's values.

        Note that the values view is sorted by key.

        See :class:`SortedValuesView` for details.

        :return: new sorted values view

        """
        return SortedValuesView(self)

    class _NotGiven:
        # pylint: disable=too-few-public-methods
        def __repr__(self):
            return '<not-given>'

    __not_given = _NotGiven()

    def pop(self, key, default=__not_given):
        """Remove and return value for item identified by `key`.

        If the `key` is not found then return `default` if given. If `default`
        is not given then raise :exc:`KeyError`.

        Runtime complexity: `O(log(n))` -- approximate.

        >>> sd = SortedDict({'a': 1, 'b': 2, 'c': 3})
        >>> sd.pop('c')
        3
        >>> sd.pop('z', 26)
        26
        >>> sd.pop('y')
        Traceback (most recent call last):
          ...
        KeyError: 'y'

        :param key: `key` for item
        :param default: `default` value if key not found (optional)
        :return: value for item
        :raises KeyError: if `key` not found and `default` not given

        """
        if key in self:
            self._list_remove(key)
            return dict.pop(self, key)
        else:
            if default is self.__not_given:
                raise KeyError(key)
            return default

    def popitem(self, index=-1):
        """Remove and return ``(key, value)`` pair at `index` from sorted dict.

        Optional argument `index` defaults to -1, the last item in the sorted
        dict. Specify ``index=0`` for the first item in the sorted dict.

        If the sorted dict is empty, raises :exc:`KeyError`.

        If the `index` is out of range, raises :exc:`IndexError`.

        Runtime complexity: `O(log(n))`

        >>> sd = SortedDict({'a': 1, 'b': 2, 'c': 3})
        >>> sd.popitem()
        ('c', 3)
        >>> sd.popitem(0)
        ('a', 1)
        >>> sd.popitem(100)
        Traceback (most recent call last):
          ...
        IndexError: list index out of range

        :param int index: `index` of item (default -1)
        :return: key and value pair
        :raises KeyError: if sorted dict is empty
        :raises IndexError: if `index` out of range

        """
        if not self:
            raise KeyError('popitem(): dictionary is empty')

        key = self._list_pop(index)
        value = dict.pop(self, key)
        return (key, value)

    def peekitem(self, index=-1):
        """Return ``(key, value)`` pair at `index` in sorted dict.

        Optional argument `index` defaults to -1, the last item in the sorted
        dict. Specify ``index=0`` for the first item in the sorted dict.

        Unlike :func:`SortedDict.popitem`, the sorted dict is not modified.

        If the `index` is out of range, raises :exc:`IndexError`.

        Runtime complexity: `O(log(n))`

        >>> sd = SortedDict({'a': 1, 'b': 2, 'c': 3})
        >>> sd.peekitem()
        ('c', 3)
        >>> sd.peekitem(0)
        ('a', 1)
        >>> sd.peekitem(100)
        Traceback (most recent call last):
          ...
        IndexError: list index out of range

        :param int index: index of item (default -1)
        :return: key and value pair
        :raises IndexError: if `index` out of range

        """
        key = self._list[index]
        return key, self[key]

    def setdefault(self, key, default=None):
        """Return value for item identified by `key` in sorted dict.

        If `key` is in the sorted dict then return its value. If `key` is not
        in the sorted dict then insert `key` with value `default` and return
        `default`.

        Optional argument `default` defaults to none.

        Runtime complexity: `O(log(n))` -- approximate.

        >>> sd = SortedDict()
        >>> sd.setdefault('a', 1)
        1
        >>> sd.setdefault('a', 10)
        1
        >>> sd
        SortedDict({'a': 1})

        :param key: key for item
        :param default: value for item (default None)
        :return: value for item identified by `key`

        """
        if key in self:
            return self[key]
        dict.__setitem__(self, key, default)
        self._list_add(key)
        return default

    def update(self, *args, **kwargs):
        """Update sorted dict with items from `args` and `kwargs`.

        Overwrites existing items.

        Optional arguments `args` and `kwargs` may be a mapping, an iterable of
        pairs or keyword arguments. See :func:`SortedDict.__init__` for
        details.

        :param args: mapping or iterable of pairs
        :param kwargs: keyword arguments mapping

        """
        if not self:
            dict.update(self, *args, **kwargs)
            self._list_update(dict.__iter__(self))
            return

        if not kwargs and len(args) == 1 and isinstance(args[0], dict):
            pairs = args[0]
        else:
            pairs = dict(*args, **kwargs)

        if (10 * len(pairs)) > len(self):
            dict.update(self, pairs)
            self._list_clear()
            self._list_update(dict.__iter__(self))
        else:
            for key in pairs:
                self._setitem(key, pairs[key])

    _update = update

    def batch_update(self, operations):
        """Apply a batch of edits to the sorted dict atomically.

        The `operations` argument is an iterable of operation tuples which
        are applied in order:

        * ``('add', key, value)`` -- insert item; an existing item with the
          same key is overwritten
        * ``('replace', key, value)`` -- synonym for ``'add'``; a missing
          key is inserted
        * ``('remove', key)`` -- remove item with `key`; removing a key
          that is not present is a no-op

        Edge-case semantics:

        * Duplicate operations on the same key are applied in order and the
          last operation wins: ``('add', 'a', 1)`` followed by
          ``('remove', 'a')`` deletes the key, while the reverse order
          stores ``('a', 1)``.
        * Overwriting an existing key with ``'add'`` or ``'replace'`` keeps
          its sorted position; only the stored value changes.
        * Removing a missing key is silently ignored, like
          :func:`SortedList.discard`.

        The batch is all-or-nothing. All key-function calls and comparisons
        run while the new sorted key list and item table are built on the
        side. If any operation raises -- for example a comparison or the
        key-function fails, or an operation tuple is malformed -- then the
        exception propagates and the sorted dict is left exactly as it was:
        the dict items, the sorted key list blocks (``_lists``), the maxes
        index (``_maxes``) and the positional index (``_index``) are all
        untouched.

        On success the new structure is committed in one step: the internal
        sorted key list is swapped for the fully-built replacement and the
        dict items are replaced. The commit runs no user code: no key
        function, comparison, or hash is invoked while committing.

        The batch is *not* thread-safe: no lock is held and concurrent
        readers may observe the commit in progress. Use external
        synchronization to serialize batches against readers.

        Views returned by :func:`SortedDict.keys`, :func:`SortedDict.items`
        and :func:`SortedDict.values` are live: after a successful commit
        they reflect the new items. Iterators created before the commit
        keep iterating the previous key list and do not observe the batch.
        Do not run a batch concurrently with iteration from another thread.

        Runtime complexity: `O(n + k*log(n))` -- approximate, for `k`
        operations on a sorted dict of size `n`.

        >>> sd = SortedDict({'a': 1, 'b': 2, 'c': 3})
        >>> sd.batch_update([('remove', 'a'), ('add', 'd', 4), ('replace', 'b', 20)])
        >>> sd
        SortedDict({'b': 20, 'c': 3, 'd': 4})
        >>> sd.batch_update([('remove', 'zz'), ('add', 'b', -1)])
        >>> sd
        SortedDict({'b': -1, 'c': 3, 'd': 4})
        >>> sd.batch_update([('add', 'e', 5), ('frobnicate', 'x')])
        Traceback (most recent call last):
          ...
        ValueError: unknown batch update operation: 'frobnicate'
        >>> sd
        SortedDict({'b': -1, 'c': 3, 'd': 4})

        :param operations: iterable of operation tuples
        :raises ValueError: if an operation is unknown or malformed

        """
        keys = self._list.copy()
        items = dict.copy(self)

        for operation in operations:
            kind = operation[0]
            if kind == 'remove':
                _, key = operation
                if key in items:
                    del items[key]
                    keys.remove(key)
            elif kind == 'add' or kind == 'replace':
                _, key, value = operation
                if key not in items:
                    keys.add(key)
                items[key] = value
            else:
                raise ValueError(f'unknown batch update operation: {kind!r}')

        # Commit: swap in the fully-built structures. No user code runs
        # below, so the commit cannot fail partway through.

        self._set_list(keys)
        dict.clear(self)
        dict.update(self, items)

    def __reduce__(self):
        """Support for pickle.

        The tricks played with caching references in
        :func:`SortedDict.__init__` confuse pickle so customize the reducer.

        """
        items = dict.copy(self)
        return (type(self), (self._key, items))

    @recursive_repr()
    def __repr__(self):
        """Return string representation of sorted dict.

        ``sd.__repr__()`` <==> ``repr(sd)``

        :return: string representation

        """
        _key = self._key
        type_name = type(self).__name__
        key_arg = '' if _key is None else f'{_key!r}, '
        item_format = '{!r}: {!r}'.format
        items = ', '.join(item_format(key, self[key]) for key in self._list)
        return f'{type_name}({key_arg}{{{items}}})'

    def _check(self):
        """Check invariants of sorted dict.

        Runtime complexity: `O(n)`

        """
        _list = self._list
        _list._check()
        assert len(self) == len(_list)
        assert all(key in self for key in _list)


def _view_delitem(self, index):
    """Remove item at `index` from sorted dict.

    ``view.__delitem__(index)`` <==> ``del view[index]``

    Supports slicing.

    Runtime complexity: `O(log(n))` -- approximate.

    >>> sd = SortedDict({'a': 1, 'b': 2, 'c': 3})
    >>> view = sd.keys()
    >>> del view[0]
    >>> sd
    SortedDict({'b': 2, 'c': 3})
    >>> del view[-1]
    >>> sd
    SortedDict({'b': 2})
    >>> del view[:]
    >>> sd
    SortedDict({})

    :param index: integer or slice for indexing
    :raises IndexError: if index out of range

    """
    _mapping = self._mapping
    _list = _mapping._list
    dict_delitem = dict.__delitem__
    if isinstance(index, slice):
        keys = _list[index]
        del _list[index]
        for key in keys:
            dict_delitem(_mapping, key)
    else:
        key = _list.pop(index)
        dict_delitem(_mapping, key)


class SortedKeysView(KeysView, Sequence):
    """Sorted keys view is a dynamic view of the sorted dict's keys.

    When the sorted dict's keys change, the view reflects those changes.

    The keys view implements the set and sequence abstract base classes.

    """

    __slots__ = ()

    @classmethod
    def _from_iterable(cls, it):
        return SortedSet(it)

    def __getitem__(self, index):
        """Lookup key at `index` in sorted keys views.

        ``skv.__getitem__(index)`` <==> ``skv[index]``

        Supports slicing.

        Runtime complexity: `O(log(n))` -- approximate.

        >>> sd = SortedDict({'a': 1, 'b': 2, 'c': 3})
        >>> skv = sd.keys()
        >>> skv[0]
        'a'
        >>> skv[-1]
        'c'
        >>> skv[:]
        ['a', 'b', 'c']
        >>> skv[100]
        Traceback (most recent call last):
          ...
        IndexError: list index out of range

        :param index: integer or slice for indexing
        :return: key or list of keys
        :raises IndexError: if index out of range

        """
        return self._mapping._list[index]

    __delitem__ = _view_delitem


class SortedItemsView(ItemsView, Sequence):
    """Sorted items view is a dynamic view of the sorted dict's items.

    When the sorted dict's items change, the view reflects those changes.

    The items view implements the set and sequence abstract base classes.

    """

    __slots__ = ()

    @classmethod
    def _from_iterable(cls, it):
        return SortedSet(it)

    def __getitem__(self, index):
        """Lookup item at `index` in sorted items view.

        ``siv.__getitem__(index)`` <==> ``siv[index]``

        Supports slicing.

        Runtime complexity: `O(log(n))` -- approximate.

        >>> sd = SortedDict({'a': 1, 'b': 2, 'c': 3})
        >>> siv = sd.items()
        >>> siv[0]
        ('a', 1)
        >>> siv[-1]
        ('c', 3)
        >>> siv[:]
        [('a', 1), ('b', 2), ('c', 3)]
        >>> siv[100]
        Traceback (most recent call last):
          ...
        IndexError: list index out of range

        :param index: integer or slice for indexing
        :return: item or list of items
        :raises IndexError: if index out of range

        """
        _mapping = self._mapping
        _mapping_list = _mapping._list

        if isinstance(index, slice):
            keys = _mapping_list[index]
            return [(key, _mapping[key]) for key in keys]

        key = _mapping_list[index]
        return key, _mapping[key]

    __delitem__ = _view_delitem


class SortedValuesView(ValuesView, Sequence):
    """Sorted values view is a dynamic view of the sorted dict's values.

    When the sorted dict's values change, the view reflects those changes.

    The values view implements the sequence abstract base class.

    """

    __slots__ = ()

    def __getitem__(self, index):
        """Lookup value at `index` in sorted values view.

        ``siv.__getitem__(index)`` <==> ``siv[index]``

        Supports slicing.

        Runtime complexity: `O(log(n))` -- approximate.

        >>> sd = SortedDict({'a': 2, 'b': 1, 'c': 3})
        >>> svv = sd.values()
        >>> svv[0]
        2
        >>> svv[-1]
        3
        >>> svv[:]
        [2, 1, 3]
        >>> svv[100]
        Traceback (most recent call last):
          ...
        IndexError: list index out of range

        :param index: integer or slice for indexing
        :return: value or list of values
        :raises IndexError: if index out of range

        """
        _mapping = self._mapping
        _mapping_list = _mapping._list

        if isinstance(index, slice):
            keys = _mapping_list[index]
            return [_mapping[key] for key in keys]

        key = _mapping_list[index]
        return _mapping[key]

    __delitem__ = _view_delitem
