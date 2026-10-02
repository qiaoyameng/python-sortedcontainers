"""Priority Queue
================

A priority queue backed by :class:`SortedKeyList` with support for members
whose priority changes while they remain in the queue.

In a plain :class:`SortedKeyList` the sort key of every value is cached in
``_keys``.  Mutating a member in place does *not* update that cached key, so
the list order becomes stale.  Two opt-in mechanisms are provided:

* :class:`PriorityQueue` constructed with ``managed=True`` keeps an identity
  index of every member and its cached key so that a member is always located
  by *who it is*, never by its (possibly new) key.

* :meth:`PriorityQueue.refresh` recomputes the key of one member and moves
  only that member's entries to the correct position -- the whole queue is
  never re-sorted and no ``__setattr__`` interception is required.

"""

from collections.abc import Iterator

from .sortedlist import identity, SortedKeyList


class _Entry:
    """A managed member together with the key cached at insertion time.

    ``_Entry`` deliberately does not forward comparison to the member.  The
    backing :class:`SortedKeyList` compares ``_Entry`` objects through its key
    function (``entry.key``), so members are never required to be mutually
    comparable and two members that compare equal but are distinct objects
    remain distinct entries.

    """

    __slots__ = ('member', 'key')

    def __init__(self, member, key):
        self.member = member
        self.key = key

    def __repr__(self):
        return f'_Entry(member={self.member!r}, key={self.key!r})'


def _entry_key(entry):
    "Return the cached key of a managed entry."
    return entry.key


class PriorityQueue:
    """A priority queue whose members may change priority.

    Members are ordered by the result of the ``key`` function applied to each
    member, from lowest key to highest key (the member with the lowest key is
    returned first by :meth:`pop`).  This matches the convention of
    :mod:`heapq`.

    By default the queue is *unmanaged*: members are stored directly in a
    :class:`SortedKeyList` exactly like ``SortedKeyList(key=key)``.  Because
    members are found by value in that mode, a member whose key changed can no
    longer be located reliably.  Construct the queue with ``managed=True`` to
    opt in to the managed-member mode:

    * members are tracked by identity (``is``) in an internal index;
    * the *same* instance may be enqueued more than once -- every
      :meth:`put` inserts one entry and :meth:`refresh` moves every entry of
      that instance;
    * members that compare equal (``==``) but are distinct instances
      (``is not``) are independent;
    * members never need to support comparison (only their keys do);
    * :meth:`refresh` is available.

    :param iterable: optional iterable of initial members
    :param key: callable returning the priority key of a member (default
        identity)
    :param managed: when true, enable the managed-member mode (default false)

    """

    def __init__(self, iterable=None, key=identity, managed=False):
        self._key = key
        self._managed = bool(managed)

        if managed:
            # Mapping: id(member) -> [member, cached_key, multiplicity].
            self._index = {}
            self._list = SortedKeyList(key=_entry_key)
        else:
            self._index = None
            self._list = SortedKeyList(key=key)

        if iterable is not None:
            for member in iterable:
                self.put(member)

    @property
    def key(self):
        "Function used to extract the priority key from members."
        return self._key

    @property
    def managed(self):
        "Whether the queue tracks members by identity (managed-member mode)."
        return self._managed

    def __len__(self):
        return len(self._list)

    def __iter__(self) -> Iterator:
        "Iterate members in priority order."
        if self._managed:
            for entry in self._list:
                yield entry.member
        else:
            yield from self._list

    def __reversed__(self) -> Iterator:
        "Iterate members in reverse priority order."
        if self._managed:
            for entry in reversed(self._list):
                yield entry.member
        else:
            yield from reversed(self._list)

    def __contains__(self, member):
        if self._managed:
            return id(member) in self._index
        return member in self._list

    def __repr__(self):
        members = list(self)
        if self._managed:
            return f'PriorityQueue({members!r}, key={self._key!r}, managed=True)'
        return f'PriorityQueue({members!r}, key={self._key!r})'

    def put(self, member):
        """Add one entry for `member` to the queue.

        The key is computed before the data structure is touched, so if the
        key function raises, nothing is inserted and the queue is unchanged.

        In managed mode the same instance may be put more than once; every
        call adds a distinct entry.  Members that compare equal but are not
        the same object are always independent.

        Runtime complexity: `O(log(n))`

        """
        key = self._key(member)

        if self._managed:
            index = self._index
            record = index.get(id(member))
            if record is None:
                index[id(member)] = [member, key, 1]
            else:
                # The first cached key remains authoritative; refresh() moves
                # all entries together so their keys can never diverge.
                record[2] += 1
            self._list.add(_Entry(member, key))
        else:
            self._list.add(member)

    add = put
    enqueue = put

    def pop(self, index=0):
        """Remove and return the member at `index`.

        With the default `index` of zero the lowest-key (highest priority)
        member is returned.

        :raises IndexError: if the queue is empty or `index` is out of range

        """
        item = self._list.pop(index)

        if self._managed:
            member = item.member
            record = self._index[id(member)]
            if record[2] == 1:
                del self._index[id(member)]
            else:
                record[2] -= 1
            return member

        return item

    def peek(self, index=0):
        """Return the member at `index` without removing it."""
        item = self._list[index]
        if self._managed:
            return item.member
        return item

    def discard(self, member):
        """Remove one entry for `member` if present.

        In managed mode the member is matched by identity.  In unmanaged mode
        the member is matched by value exactly like
        :meth:`SortedKeyList.discard`.

        """
        if self._managed:
            record = self._index.get(id(member))
            if record is None:
                return
            self._discard_one_managed(member)
        else:
            self._list.discard(member)

    def remove(self, member):
        """Remove one entry for `member`.

        In managed mode the member is matched by identity.

        :raises ValueError: if the member is not in the queue

        """
        if self._managed:
            if id(member) not in self._index:
                raise ValueError(f'{member!r} not in priority queue')
            self._discard_one_managed(member)
        else:
            self._list.remove(member)

    def _discard_one_managed(self, member):
        # Locate the member within its cached-key run by identity, not by the
        # possibly-new current key.
        record = self._index[id(member)]
        cached_key = record[1]
        start = self._list.bisect_key_left(cached_key)
        stop = self._list.bisect_key_right(cached_key)
        for pos in range(start, stop):
            entry = self._list[pos]
            if entry.member is member:
                self._list.pop(pos)
                if record[2] == 1:
                    del self._index[id(member)]
                else:
                    record[2] -= 1
                return

    def count(self, member):
        """Return the number of entries of `member` in the queue.

        In managed mode counting is by identity; in unmanaged mode counting is
        by value.

        """
        if self._managed:
            record = self._index.get(id(member))
            return 0 if record is None else record[2]
        return self._list.count(member)

    def refresh(self, member):
        """Recompute the key of `member` and reposition its entries.

        The member is located by identity using its *cached* key, so a member
        whose priority just changed is always found even though its new key
        may sort elsewhere.  Only the entries of that single member are
        moved; the rest of the queue is untouched.

        If the key returns the same value the entries already occupy the right
        region and nothing moves (refreshing into an equal-key run is a
        no-op).  If the key function raises, or the new key cannot be compared
        with the existing keys, the member's entries are left exactly where
        they were and the exception propagates: the backing list and the
        identity index stay mutually consistent.

        :raises RuntimeError: if the queue is not managed
        :raises ValueError: if `member` is not in the queue

        """
        if not self._managed:
            raise RuntimeError(
                'refresh() requires a managed PriorityQueue; construct with '
                'managed=True'
            )

        record = self._index.get(id(member))
        if record is None:
            raise ValueError(f'{member!r} not in priority queue')

        # Compute the new key *before* touching anything: a failing key
        # function must leave the structure unchanged.
        new_key = self._key(member)
        old_key = record[1]

        if new_key == old_key:
            # Already in the right key region.
            return

        # Validate that the new key sorts against the existing keys.  This
        # runs before any mutation so a comparison failure cannot leave
        # partially deleted entries behind.  Recomputing it after the removals
        # is redundant.
        self._list.bisect_key_right(new_key)

        # Find every entry belonging to this member by scanning its
        # cached-key run and matching identity (never by the new key).
        start = self._list.bisect_key_left(old_key)
        stop = self._list.bisect_key_right(old_key)
        positions = [
            pos
            for pos in range(start, stop)
            if self._list[pos].member is member
        ]

        # Remove from the highest position so earlier indices stay valid.
        for pos in reversed(positions):
            self._list.pop(pos)

        # Re-insert one entry per occurrence.  add() places each at the right
        # end of the equal-new-key run, preserving occurrence order, and
        # handles sublist splitting and the index itself.
        for _ in positions:
            self._list.add(_Entry(member, new_key))

        record[1] = new_key

    def clear(self):
        "Remove every member from the queue."
        self._list.clear()
        if self._managed:
            self._index.clear()

    def _check(self):
        """Check internal invariants of the queue.

        Runs :meth:`SortedKeyList._check` on the backing list and, in managed
        mode, verifies that the identity index agrees with the stored entries
        (multiplicity and cached keys).

        Runtime complexity: `O(n)`

        """
        self._list._check()

        if self._managed:
            index = self._index

            # Reconstruct the identity bookkeeping from the actual entries.
            seen = {}
            for entry in self._list:
                member_id = id(entry.member)
                if member_id not in seen:
                    seen[member_id] = [entry.member, entry.key, 1]
                else:
                    assert seen[member_id][1] == entry.key
                    seen[member_id][2] += 1

            assert set(seen) == set(index)
            for member_id, (member, key, count) in seen.items():
                record = index[member_id]
                assert record[0] is member
                assert record[1] == key
                assert record[2] == count
