"""Aggregating Sorted Dict
==========================

An optional :class:`AggregatingSortedDict` maintains a running summary for
every sublist (block) of the underlying sorted keys. The summary of any key
range is then computed by combining cached block summaries: interior blocks
contribute their cache directly and only the two boundary blocks are expanded.

The aggregate is described by three callables provided by the caller:

* ``identity`` -- the neutral aggregate value, or a zero-argument callable
  returning one. A callable may be used when the aggregate is a mutable object
  so that every empty range receives a fresh identity.
* ``combine(left, right)`` -- an associative (but not necessarily commutative)
  binary operation. No inverse is ever required.
* ``get_value(value)`` -- extracts the per-item aggregate from a stored value
  (defaults to the identity function).

Because subtraction or any inverse operation is never used, non-commutative
operations such as ordered string concatenation are supported.

Summary updates are kept consistent with every mutation. The list primitives
(:meth:`add`, :meth:`_delete`, :meth:`update`, :meth:`clear` and
:meth:`_reset`) snapshot the affected blocks before mutating; if a user
supplied callable raises while a block summary is rebuilt, the structure and
the summaries are both rolled back. The mapping layer coordinates with those
primitives so that a failed operation never leaves key/value changes without a
matching summary update.
"""

from bisect import bisect_right

from .sortedlist import SortedKeyList, SortedList
from .sorteddict import SortedDict, SortedItemsView, SortedKeysView, SortedValuesView


def _identity_value(value):
    """Default per-item aggregate: return the stored value unchanged."""
    return value


class _NotGiven:
    """Sentinel for ``pop``'s missing default argument."""


_NOT_GIVEN = _NotGiven()


class _SummaryMixin:
    """Per-block aggregate summaries for a sorted list.

    ``self._summaries`` is a list aligned with ``self._lists``: entry *i*
    caches the aggregate of the keys stored in block *i*. ``_keys`` is
    ``None`` for plain sorted lists and a parallel list of blocks for
    sorted-key lists (the attribute is also mirrored on the mixin so the
    generic snapshot code can refer to it).
    """

    _aggregate_mapping = None
    _keys = None

    def _summary_init(self):
        self._summaries = []

    def _fresh_identity(self):
        identity = self._agg_identity
        return identity() if callable(identity) else identity

    def _element(self, key):
        return self._agg_get_value(self._aggregate_mapping[key])

    def _fold_elements(self, keys):
        """Left-fold the aggregate over the stored items for ``keys``."""
        iterator = iter(keys)
        try:
            result = self._element(next(iterator))
        except StopIteration:
            return self._fresh_identity()
        combine = self._agg_combine
        for key in iterator:
            result = combine(result, self._element(key))
        return result

    def _recompute_block(self, pos):
        self._summaries[pos] = self._fold_elements(self._lists[pos])

    def _snap(self, lo, hi):
        snap = {
            'lo': lo,
            'hi': hi,
            'len': self._len,
            'total': len(self._lists),
            'lists': [list(block) for block in self._lists[lo:hi]],
            'maxes': list(self._maxes[lo:hi]),
            'summaries': list(self._summaries[lo:hi]),
        }
        if self._keys is not None:
            snap['keys'] = [list(block) for block in self._keys[lo:hi]]
        return snap

    def _restore(self, snap):
        lo = snap['lo']
        hi = snap['hi']
        tail = snap['total'] - hi

        self._lists[:] = (
            self._lists[:lo] + snap['lists'] + self._lists[len(self._lists) - tail:]
        )
        self._maxes[:] = (
            self._maxes[:lo] + snap['maxes'] + self._maxes[len(self._maxes) - tail:]
        )
        self._summaries[:] = (
            self._summaries[:lo]
            + snap['summaries']
            + self._summaries[len(self._summaries) - tail:]
        )
        if self._keys is not None:
            self._keys[:] = (
                self._keys[:lo]
                + snap['keys']
                + self._keys[len(self._keys) - tail:]
            )
        self._len = snap['len']
        del self._index[:]

    def _snap_all(self):
        return self._snap(0, len(self._lists))

    def _sort_key(self, value):
        return value

    def add(self, value):
        _maxes = self._maxes
        if not _maxes:
            pos = 0
        else:
            pos = bisect_right(_maxes, self._sort_key(value))
            if pos == len(_maxes):
                pos -= 1
        snap = self._snap(pos, pos + 1)
        try:
            super().add(value)
            if len(self._summaries) == len(self._lists):
                self._recompute_block(pos)
            elif len(self._summaries) == pos:
                self._summaries.append(self._fold_elements(self._lists[pos]))
            else:
                self._recompute_block(pos)
                self._summaries.insert(
                    pos + 1, self._fold_elements(self._lists[pos + 1])
                )
        except BaseException:
            self._restore(snap)
            raise

    def _delete(self, pos, idx):
        lo = 0 if pos == 0 else pos - 1
        hi = min(len(self._lists), pos + 2)
        snap = self._snap(lo, hi)
        try:
            super()._delete(pos, idx)
            if len(self._lists) == len(self._summaries):
                for index in range(lo, min(hi, len(self._lists))):
                    self._recompute_block(index)
            else:
                del self._summaries[pos]
                for index in range(lo, min(hi - 1, len(self._lists))):
                    self._recompute_block(index)
        except BaseException:
            self._restore(snap)
            raise

    def __delitem__(self, index):
        if isinstance(index, slice):
            snap = self._snap_all()
            try:
                super().__delitem__(index)
            except BaseException:
                self._restore(snap)
                raise
        else:
            super().__delitem__(index)

    def update(self, iterable):
        snap = self._snap_all()
        try:
            super().update(iterable)
            self._summaries[:] = [
                self._fold_elements(block) for block in self._lists
            ]
        except BaseException:
            self._restore(snap)
            raise

    def clear(self):
        super().clear()
        del self._summaries[:]

    def _reset(self, load):
        snap = self._snap_all()
        try:
            super()._reset(load)
            self._summaries[:] = [
                self._fold_elements(block) for block in self._lists
            ]
        except BaseException:
            self._restore(snap)
            raise

    def rebuild(self, keys):
        """Clear and load ``keys``, recomputing summaries atomically.

        Used by the mapping's batch-update path so that clearing and loading
        share one snapshot and roll back together.
        """
        snap = self._snap_all()
        try:
            super().clear()
            del self._summaries[:]
            super().update(keys)
            self._summaries[:] = [
                self._fold_elements(block) for block in self._lists
            ]
        except BaseException:
            self._restore(snap)
            raise

    _update = update
    _clear = clear


class _AggregatingSortedList(_SummaryMixin, SortedList):
    """Sorted list maintaining one summary per block."""

    _keys = None

    def __new__(cls, *args, **kwargs):
        return object.__new__(cls)

    def __init__(self, identity=None, combine=None, get_value=None,
                 iterable=None, key=None):
        assert key is None
        self._agg_identity = identity
        self._agg_combine = combine
        self._agg_get_value = (
            get_value if get_value is not None else _identity_value
        )
        self._summary_init()
        super().__init__(iterable, key)


class _AggregatingSortedKeyList(_SummaryMixin, SortedKeyList):
    """Sorted-key list maintaining one summary per block."""

    def __new__(cls, *args, **kwargs):
        return object.__new__(cls)

    def __init__(self, identity=None, combine=None, get_value=None,
                 iterable=None, key=lambda value: value):
        self._agg_identity = identity
        self._agg_combine = combine
        self._agg_get_value = (
            get_value if get_value is not None else _identity_value
        )
        self._summary_init()
        super().__init__(iterable, key)

    def _sort_key(self, value):
        return self._key(value)


def _view_delitem(self, index):
    """Delete ``index`` (integer or slice) from the sorted keys.

    The list structure and block summaries are updated first (those primitives
    roll themselves back on a user-callable failure); the backing mapping is
    changed only afterwards. On failure the mapping is restored from a
    snapshot.
    """
    mapping = self._mapping
    _list = mapping._list
    if isinstance(index, slice):
        keys = list(_list[index])
        del _list[index]
        for key in keys:
            dict.__delitem__(mapping, key)
    else:
        key = _list[index]
        _list.pop(index)
        dict.__delitem__(mapping, key)


def _reconstruct(identity, combine, get_value, key, items):
    return AggregatingSortedDict(
        identity, combine, items, get_value=get_value, key=key
    )


class AggregatingSortedDict(SortedDict):
    """Sorted dict with fast associative range aggregation.

    Keys are maintained in sorted order exactly like :class:`SortedDict`.
    Additionally each block of the underlying sorted list caches an aggregate
    of the items it contains, so :meth:`aggregate` over a key range combines
    cached summaries of interior blocks and only expands the two boundary
    blocks.

    The aggregation contract:

    * ``identity`` is the neutral element of ``combine``. It may be a value or
      a zero-argument callable returning the identity; the latter is useful
      for mutable aggregates. The aggregate of an empty range is the identity.
    * ``combine(left, right)`` must be associative. It need not be
      commutative; summaries are always combined in ascending key order.
    * ``get_value(value)`` maps a stored value to the per-item aggregate. It
      defaults to the identity function.

    No inverse or subtraction operation is used, so aggregates such as ordered
    string concatenation are supported.

    >>> sd = AggregatingSortedDict(0, lambda a, b: a + b,
    ...                            {'a': 1, 'b': 2, 'c': 3})
    >>> sd.aggregate('a', 'c')
    6
    >>> sd.aggregate('b', 'z')
    5
    >>> sd.aggregate('y', 'z')
    0

    """

    def __init__(self, identity, combine, *args, get_value=None, key=None, **kwargs):
        """Initialize an aggregating sorted dict.

        ``identity`` and ``combine`` define the associative aggregate.
        ``get_value`` optionally extracts the per-item aggregate from a stored
        value and defaults to returning the value unchanged.

        Optional ``key`` function and ``args``/``kwargs`` behave as in
        :class:`SortedDict`.

        """
        self._key = key
        get_value_arg = get_value if get_value is not None else _identity_value

        if key is None:
            self._list = _AggregatingSortedList(identity, combine, get_value_arg)
        else:
            self._list = _AggregatingSortedKeyList(
                identity, combine, get_value_arg, key=key
            )
        self._list._aggregate_mapping = self

        _list = self._list
        self._list_add = _list.add
        self._list_clear = _list.clear
        self._list_iter = _list.__iter__
        self._list_reversed = _list.__reversed__
        self._list_pop = _list.pop
        self._list_remove = _list.remove
        self._list_update = _list.update

        self.bisect_left = _list.bisect_left
        self.bisect = _list.bisect_right
        self.bisect_right = _list.bisect_right
        self.index = _list.index
        self.irange = _list.irange
        self.islice = _list.islice
        self._reset = _list._reset

        if key is not None:
            self.bisect_key_left = _list.bisect_key_left
            self.bisect_key_right = _list.bisect_key_right
            self.bisect_key = _list.bisect_key
            self.irange_key = _list.irange_key

        self._update(*args, **kwargs)

    def _new_identity(self):
        return self._list._fresh_identity()

    def keys(self):
        return _AggregatingKeysView(self)

    def items(self):
        return _AggregatingItemsView(self)

    def values(self):
        return _AggregatingValuesView(self)

    def clear(self):
        """Remove all items and cached summaries."""
        self._list_clear()
        dict.clear(self)

    def __setitem__(self, key, value):
        """Store ``key``/``value``, keeping the block summary consistent.

        If a user callable raises while the affected block summary is rebuilt,
        the operation is undone and the exception propagates.
        """
        if key in self:
            old_value = dict.__getitem__(self, key)
            dict.__setitem__(self, key, value)
            pos = self._list_bisect_left_key(key)
            try:
                self._list._recompute_block(pos)
            except BaseException:
                dict.__setitem__(self, key, old_value)
                raise
        else:
            dict.__setitem__(self, key, value)
            try:
                self._list_add(key)
            except BaseException:
                dict.__delitem__(self, key)
                raise

    _setitem = __setitem__

    def _list_bisect_left_key(self, key):
        """Return the block index that contains (or would contain) ``key``."""
        _list = self._list
        if self._key is None:
            index = _list.bisect_left(key)
        else:
            index = _list.bisect_key_left(self._key(key))
        if index >= len(_list):
            return len(_list) - 1
        pos, _idx = _list._pos(index)
        return pos

    def __delitem__(self, key):
        """Remove ``key``; roll back if the summary rebuild raises."""
        if key not in self:
            raise KeyError(key)
        old_value = dict.pop(self, key)
        try:
            self._list_remove(key)
        except BaseException:
            dict.__setitem__(self, key, old_value)
            raise

    def pop(self, key, default=_NOT_GIVEN):
        """Remove and return the value for ``key`` with rollback on failure."""
        if key in self:
            old_value = dict.pop(self, key)
            try:
                self._list_remove(key)
            except BaseException:
                dict.__setitem__(self, key, old_value)
                raise
            return old_value
        if default is _NOT_GIVEN:
            raise KeyError(key)
        return default

    def popitem(self, index=-1):
        """Remove and return ``(key, value)`` at sorted ``index``."""
        if not self:
            raise KeyError('popitem(): dictionary is empty')
        key = self._list[index]
        old_value = dict.pop(self, key)
        try:
            self._list_pop(index)
        except BaseException:
            dict.__setitem__(self, key, old_value)
            raise
        return key, old_value

    def setdefault(self, key, default=None):
        """Insert ``key`` with ``default`` only when absent, atomically."""
        if key in self:
            return self[key]
        dict.__setitem__(self, key, default)
        try:
            self._list_add(key)
        except BaseException:
            dict.__delitem__(self, key)
            raise
        return default

    def update(self, *args, **kwargs):
        """Update with pairs; large updates rebuild and stay consistent.

        If a user callable raises while rebuilding the block summaries, the
        mapping and the sorted keys are restored to their previous state.
        """
        if not kwargs and len(args) == 1 and isinstance(args[0], dict):
            pairs = args[0]
        else:
            pairs = dict(*args, **kwargs)

        if not pairs:
            return

        if not self or (10 * len(pairs)) > len(self):
            snapshot = dict(self)
            dict.update(self, pairs)
            try:
                self._list.rebuild(dict.__iter__(self))
            except BaseException:
                dict.clear(self)
                dict.update(self, snapshot)
                raise
            return

        for key, value in pairs.items():
            self._setitem(key, value)

    _update = update

    def copy(self):
        """Return a shallow copy with independent block summaries."""
        return self.__class__(
            self._list._agg_identity,
            self._list._agg_combine,
            self.items(),
            get_value=self._list._agg_get_value,
            key=self._key,
        )

    __copy__ = copy

    def __or__(self, other):
        from collections.abc import Mapping as _Mapping

        if not isinstance(other, _Mapping):
            return NotImplemented
        return self.__class__(
            self._list._agg_identity,
            self._list._agg_combine,
            list(self.items()) + list(other.items()),
            get_value=self._list._agg_get_value,
            key=self._key,
        )

    def __ror__(self, other):
        from collections.abc import Mapping as _Mapping

        if not isinstance(other, _Mapping):
            return NotImplemented
        return self.__class__(
            self._list._agg_identity,
            self._list._agg_combine,
            list(other.items()) + list(self.items()),
            get_value=self._list._agg_get_value,
            key=self._key,
        )

    @property
    def total(self):
        """Aggregate of every item, left-folded in ascending key order."""
        if not self._list._summaries:
            return self._new_identity()
        result = self._list._summaries[0]
        combine = self._list._agg_combine
        for summary in self._list._summaries[1:]:
            result = combine(result, summary)
        return result

    def aggregate(
        self, minimum=None, maximum=None, inclusive=(True, True)
    ):
        """Aggregate values whose keys fall within a range.

        ``minimum`` and ``maximum`` default to ``None`` meaning unbounded on
        that side. ``inclusive`` is a ``(min_included, max_included)`` pair of
        booleans. Interior blocks contribute their cached summary; only the
        boundary blocks are expanded. An empty range returns the identity.

        Runtime complexity: `O(log(n) + b + l)` approximate, where *b* is the
        number of interior blocks and *l* the total length of the two boundary
        blocks.
        """
        _list = self._list
        if not _list._lists:
            return self._new_identity()

        if minimum is None:
            start = 0
        elif inclusive[0]:
            start = _list.bisect_left(minimum)
        else:
            start = _list.bisect_right(minimum)

        if maximum is None:
            stop = len(_list)
        elif inclusive[1]:
            stop = _list.bisect_right(maximum)
        else:
            stop = _list.bisect_left(maximum)

        if start >= stop:
            return self._new_identity()

        start_pos, start_idx = _list._pos(start)
        if stop == len(_list):
            stop_pos = len(_list._lists) - 1
            stop_idx = len(_list._lists[stop_pos])
        else:
            stop_pos, stop_idx = _list._pos(stop)

        combine = _list._agg_combine
        element = _list._fold_elements

        if start_pos == stop_pos:
            return element(_list._lists[start_pos][start_idx:stop_idx])

        result = element(_list._lists[start_pos][start_idx:])
        for pos in range(start_pos + 1, stop_pos):
            result = combine(result, _list._summaries[pos])
        result = combine(
            result, element(_list._lists[stop_pos][:stop_idx])
        )
        return result

    def __reduce__(self):
        items = dict.copy(self)
        return (
            _reconstruct,
            (
                self._list._agg_identity,
                self._list._agg_combine,
                self._list._agg_get_value,
                self._key,
                items,
            ),
        )

    def __repr__(self):
        type_name = type(self).__name__
        item_format = '{!r}: {!r}'.format
        items = ', '.join(
            item_format(key, self[key]) for key in self._list
        )
        return f'{type_name}({self._list._agg_identity!r}, {self._list._agg_combine!r}, {{{items}}})'

    def _check(self):
        """Check block-summary invariants. Runtime complexity: `O(n)`."""
        super()._check()
        _list = self._list
        assert len(_list._summaries) == len(_list._lists)
        for pos, block in enumerate(_list._lists):
            assert _list._summaries[pos] == _list._fold_elements(block)


class _AggregatingKeysView(SortedKeysView):
    __slots__ = ()
    __delitem__ = _view_delitem


class _AggregatingItemsView(SortedItemsView):
    __slots__ = ()
    __delitem__ = _view_delitem


class _AggregatingValuesView(SortedValuesView):
    __slots__ = ()
    __delitem__ = _view_delitem
