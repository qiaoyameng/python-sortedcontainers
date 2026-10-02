import random
from bisect import bisect_left, bisect_right
from sortedcontainers import SortedKeyList, SortedList, SortedListWithKey
from itertools import chain
import pytest


def negate(val):
    return -val


def test_alias():
    assert SortedKeyList is SortedListWithKey


def test_identity():
    slt = SortedKeyList(range(100))
    slt._reset(7)
    slt._check()


def test_init():
    slt = SortedKeyList(key=negate)
    slt._check()

    slt = SortedKeyList(key=negate)
    slt._reset(10000)
    assert slt._load == 10000
    slt._check()

    slt = SortedKeyList(range(10000), key=negate)
    assert all(tup[0] == tup[1] for tup in zip(slt, reversed(range(10000))))

    slt.clear()
    assert slt._len == 0
    assert slt._maxes == []
    assert slt._lists == []
    slt._check()


def test_key():
    slt = SortedKeyList(range(10000), key=lambda val: val % 10)
    slt._check()

    values = sorted(range(10000), key=lambda val: (val % 10, val))
    assert slt == values
    assert all(val in slt for val in range(10000))


def test_add():
    random.seed(0)
    slt = SortedKeyList(key=negate)
    for val in range(1000):
        slt.add(val)
        slt._check()

    slt = SortedKeyList(key=negate)
    for val in range(1000, 0, -1):
        slt.add(val)
        slt._check()

    slt = SortedKeyList(key=negate)
    for val in range(1000):
        slt.add(random.random())
        slt._check()


def test_update():
    slt = SortedKeyList(key=negate)

    slt.update(range(1000))
    assert len(slt) == 1000
    slt._check()

    slt.update(range(100))
    assert len(slt) == 1100
    slt._check()

    slt.update(range(10000))
    assert len(slt) == 11100
    slt._check()

    values = sorted(
        (val for val in chain(range(100), range(1000), range(10000))), key=negate
    )
    assert all(tup[0] == tup[1] for tup in zip(slt, values))


def test_contains():
    slt = SortedKeyList(key=negate)
    assert 0 not in slt

    slt.update(range(10000))

    for val in range(10000):
        assert val in slt

    assert 10000 not in slt
    assert -1 not in slt

    slt._check()


def test_discard():
    slt = SortedKeyList(key=negate)

    assert slt.discard(0) == None
    assert len(slt) == 0
    slt._check()

    slt = SortedKeyList([1, 2, 2, 2, 3, 3, 5], key=negate)
    slt._reset(4)

    slt.discard(6)
    slt._check()
    slt.discard(4)
    slt._check()
    slt.discard(2)
    slt._check()

    assert all(tup[0] == tup[1] for tup in zip(slt, reversed([1, 2, 2, 3, 3, 5])))


def test_remove():
    slt = SortedKeyList(key=negate)

    assert slt.discard(0) == None
    assert len(slt) == 0
    slt._check()

    slt = SortedKeyList([1, 2, 2, 2, 3, 3, 5], key=negate)
    slt._reset(4)

    slt.remove(2)
    slt._check()

    assert all(tup[0] == tup[1] for tup in zip(slt, reversed([1, 2, 2, 3, 3, 5])))


def test_remove_valueerror1():
    slt = SortedKeyList(key=negate)
    with pytest.raises(ValueError):
        slt.remove(0)


def test_remove_valueerror2():
    slt = SortedKeyList(range(100), key=negate)
    slt._reset(10)
    with pytest.raises(ValueError):
        slt.remove(100)


def test_remove_valueerror3():
    slt = SortedKeyList([1, 2, 2, 2, 3, 3, 5], key=negate)
    with pytest.raises(ValueError):
        slt.remove(4)


def test_delete():
    slt = SortedKeyList(range(20), key=negate)
    slt._reset(4)
    slt._check()
    for val in range(20):
        slt.remove(val)
        slt._check()
    assert len(slt) == 0
    assert slt._maxes == []
    assert slt._lists == []


def test_getitem():
    random.seed(0)
    slt = SortedKeyList(key=negate)
    slt._reset(17)

    slt.add(5)
    assert slt[0] == 5
    slt.clear()

    lst = list()

    for rpt in range(100):
        val = random.random()
        slt.add(val)
        lst.append(val)

    lst.sort(reverse=True)

    assert all(slt[idx] == lst[idx] for idx in range(100))
    assert all(slt[idx - 99] == lst[idx - 99] for idx in range(100))


def test_getitem_slice():
    random.seed(0)
    slt = SortedKeyList(key=negate)
    slt._reset(17)

    lst = list()

    for rpt in range(100):
        val = random.random()
        slt.add(val)
        lst.append(val)

    lst.sort(reverse=True)

    assert all(slt[start:] == lst[start:] for start in [-75, -25, 0, 25, 75])

    assert all(slt[:stop] == lst[:stop] for stop in [-75, -25, 0, 25, 75])

    assert all(slt[::step] == lst[::step] for step in [-5, -1, 1, 5])

    assert all(
        slt[start:stop] == lst[start:stop]
        for start in [-75, -25, 0, 25, 75]
        for stop in [-75, -25, 0, 25, 75]
    )

    assert all(
        slt[:stop:step] == lst[:stop:step]
        for stop in [-75, -25, 0, 25, 75]
        for step in [-5, -1, 1, 5]
    )

    assert all(
        slt[start::step] == lst[start::step]
        for start in [-75, -25, 0, 25, 75]
        for step in [-5, -1, 1, 5]
    )

    assert all(
        slt[start:stop:step] == lst[start:stop:step]
        for start in [-75, -25, 0, 25, 75]
        for stop in [-75, -25, 0, 25, 75]
        for step in [-5, -1, 1, 5]
    )


def test_getitem_slice_big():
    slt = SortedKeyList(range(4), key=negate)
    lst = list(reversed(range(4)))

    itr = (
        (start, stop, step)
        for start in [-6, -4, -2, 0, 2, 4, 6]
        for stop in [-6, -4, -2, 0, 2, 4, 6]
        for step in [-3, -2, -1, 1, 2, 3]
    )

    for start, stop, step in itr:
        assert slt[start:stop:step] == lst[start:stop:step]


def test_getitem_slicezero():
    slt = SortedKeyList(range(100), key=negate)
    slt._reset(17)
    with pytest.raises(ValueError):
        slt[::0]


def test_getitem_indexerror1():
    slt = SortedKeyList(key=negate)
    with pytest.raises(IndexError):
        slt[5]


def test_getitem_indexerror2():
    slt = SortedKeyList(range(100), key=negate)
    with pytest.raises(IndexError):
        slt[200]


def test_getitem_indexerror3():
    slt = SortedKeyList(range(100), key=negate)
    with pytest.raises(IndexError):
        slt[-101]


def test_delitem():
    random.seed(0)
    slt = SortedKeyList(range(100), key=negate)
    slt._reset(17)
    while len(slt) > 0:
        del slt[random.randrange(len(slt))]
        slt._check()


def test_delitem_slice():
    slt = SortedKeyList(range(100), key=negate)
    slt._reset(17)
    del slt[10:40:1]
    del slt[10:40:-1]
    del slt[10:40:2]
    del slt[10:40:-2]


def test_iter():
    slt = SortedKeyList(range(10000), key=negate)
    itr = iter(slt)
    assert all(tup[0] == tup[1] for tup in zip(range(9999, -1, -1), itr))


def test_reversed():
    slt = SortedKeyList(range(10000), key=negate)
    rev = reversed(slt)
    assert all(tup[0] == tup[1] for tup in zip(range(10000), rev))


def test_reverse():
    slt = SortedKeyList(range(10000), key=negate)
    with pytest.raises(NotImplementedError):
        slt.reverse()


def test_islice():
    return
    slt = SortedKeyList(key=negate)
    slt._reset(7)

    assert [] == list(slt.islice())

    values = sorted(range(53), key=negate)
    slt.update(values)

    for start in range(53):
        for stop in range(53):
            assert list(slt.islice(start, stop)) == values[start:stop]

    for start in range(53):
        for stop in range(53):
            assert (
                list(slt.islice(start, stop, reverse=True)) == values[start:stop][::-1]
            )

    for start in range(53):
        assert list(slt.islice(start=start)) == values[start:]
        assert list(slt.islice(start=start, reverse=True)) == values[start:][::-1]

    for stop in range(53):
        assert list(slt.islice(stop=stop)) == values[:stop]
        assert list(slt.islice(stop=stop, reverse=True)) == values[:stop][::-1]


def test_irange():
    slt = SortedKeyList(key=negate)
    slt._reset(7)

    assert [] == list(slt.irange())

    values = list(range(53))
    slt.update(values)

    for start in range(53):
        for end in range(start, 53):
            assert list(slt.irange(end, start)) == values[start : (end + 1)][::-1]
            assert (
                list(slt.irange(end, start, reverse=True)) == values[start : (end + 1)]
            )

    for start in range(53):
        for end in range(start, 53):
            assert (
                list(slt.irange(end, start, (True, False)))
                == values[(start + 1) : (end + 1)][::-1]
            )

    for start in range(53):
        for end in range(start, 53):
            assert (
                list(slt.irange(end, start, (False, True))) == values[start:end][::-1]
            )

    for start in range(53):
        for end in range(start, 53):
            assert (
                list(slt.irange(end, start, (False, False)))
                == values[(start + 1) : end][::-1]
            )

    for start in range(53):
        assert list(slt.irange(start)) == values[: (start + 1)][::-1]

    for end in range(53):
        assert list(slt.irange(None, end, (True, False))) == values[(end + 1) :][::-1]

    assert list(slt.irange(inclusive=(False, False))) == values[::-1]

    assert list(slt.irange(-1)) == []
    assert list(slt.irange(None, -1, (True, False))) == values[::-1]


def test_len():
    slt = SortedKeyList(key=negate)

    for val in range(10000):
        slt.add(val)
        assert len(slt) == (val + 1)


def test_bisect_left():
    slt = SortedKeyList(key=negate)
    assert slt.bisect_left(0) == 0
    slt = SortedKeyList(range(100), key=negate)
    slt._reset(17)
    slt.update(range(100))
    slt._check()
    assert slt.bisect_left(50) == 98
    assert slt.bisect_left(0) == 198
    assert slt.bisect_left(-1) == 200


def test_bisect():
    slt = SortedKeyList(key=negate)
    assert slt.bisect(10) == 0
    slt = SortedKeyList(range(100), key=negate)
    slt._reset(17)
    slt.update(range(100))
    slt._check()
    assert slt.bisect(10) == 180
    assert slt.bisect(0) == 200


def test_bisect_right():
    slt = SortedKeyList(key=negate)
    assert slt.bisect_right(10) == 0
    slt = SortedKeyList(range(100), key=negate)
    slt._reset(17)
    slt.update(range(100))
    slt._check()
    assert slt.bisect_right(10) == 180
    assert slt.bisect_right(0) == 200


def test_copy():
    slt = SortedKeyList(range(100), key=negate)
    slt._reset(7)
    two = slt.copy()
    slt.add(100)
    assert len(slt) == 101
    assert len(two) == 100


def test_copy_copy():
    import copy

    slt = SortedKeyList(range(100), key=negate)
    slt._reset(7)
    two = copy.copy(slt)
    slt.add(100)
    assert len(slt) == 101
    assert len(two) == 100


def test_count():
    slt = SortedKeyList(key=negate)
    slt._reset(7)

    assert slt.count(0) == 0

    for iii in range(100):
        for jjj in range(iii):
            slt.add(iii)
        slt._check()

    for iii in range(100):
        assert slt.count(iii) == iii


def test_pop():
    slt = SortedKeyList(range(10), key=negate)
    slt._reset(4)
    slt._check()
    assert slt.pop() == 0
    slt._check()
    assert slt.pop(0) == 9
    slt._check()
    assert slt.pop(-2) == 2
    slt._check()
    assert slt.pop(4) == 4
    slt._check()


def test_pop_indexerror1():
    slt = SortedKeyList(range(10), key=negate)
    slt._reset(4)
    with pytest.raises(IndexError):
        slt.pop(-11)


def test_pop_indexerror2():
    slt = SortedKeyList(range(10), key=negate)
    slt._reset(4)
    with pytest.raises(IndexError):
        slt.pop(10)


def test_index():
    slt = SortedKeyList(range(100), key=negate)
    slt._reset(17)

    for pos, val in enumerate(range(99, -1, -1)):
        assert val == slt.index(pos)

    assert slt.index(99, 0, 1000) == 0

    slt = SortedKeyList((0 for rpt in range(100)), key=negate)
    slt._reset(17)

    for start in range(100):
        for stop in range(start, 100):
            assert slt.index(0, start, stop + 1) == start

    for start in range(100):
        assert slt.index(0, -(100 - start)) == start

    assert slt.index(0, -1000) == 0


def test_index_valueerror1():
    slt = SortedKeyList([0] * 10, key=negate)
    slt._reset(4)
    with pytest.raises(ValueError):
        slt.index(0, 10)


def test_index_valueerror2():
    slt = SortedKeyList([0] * 10, key=negate)
    slt._reset(4)
    with pytest.raises(ValueError):
        slt.index(0, 0, -10)


def test_index_valueerror3():
    slt = SortedKeyList([0] * 10, key=negate)
    slt._reset(4)
    with pytest.raises(ValueError):
        slt.index(0, 7, 3)


def test_index_valueerror4():
    slt = SortedKeyList([0] * 10, key=negate)
    slt._reset(4)
    with pytest.raises(ValueError):
        slt.index(1)


def test_index_valueerror5():
    slt = SortedKeyList(key=negate)
    with pytest.raises(ValueError):
        slt.index(1)


def test_index_valueerror6():
    slt = SortedKeyList(range(10), key=negate)
    slt._reset(4)
    with pytest.raises(ValueError):
        slt.index(6, 5)


def test_mul():
    this = SortedKeyList(range(10), key=negate)
    this._reset(4)
    that = this * 5
    this._check()
    that._check()
    assert this == list(reversed(range(10)))
    assert that == list(sorted(list(range(10)) * 5, reverse=True))
    assert this != that


def test_imul():
    this = SortedKeyList(range(10), key=negate)
    this._reset(4)
    this *= 5
    this._check()
    assert this == sorted(list(range(10)) * 5, reverse=True)


def test_op_add():
    this = SortedKeyList(range(10), key=negate)
    this._reset(4)
    assert (this + this + this) == (this * 3)

    that = SortedKeyList(range(10), key=negate)
    that._reset(4)
    that += that
    that += that
    assert that == (this * 4)


def test_eq():
    this = SortedKeyList(range(10), key=negate)
    this._reset(4)
    that = SortedKeyList(range(20), key=negate)
    that._reset(4)
    assert not (this == that)
    that.clear()
    that.update(range(10))
    assert this == that


def test_lt():
    this = SortedKeyList(range(10), key=negate)
    this._reset(4)
    that = SortedKeyList(range(10, 20), key=negate)
    that._reset(5)
    assert this < that
    assert not (that < this)
    that = SortedKeyList(range(1, 20), key=negate)
    that._reset(6)
    assert this < that
    that = SortedKeyList(range(1, 10), key=negate)
    that._reset(4)
    assert not (this < that)


def test_lte():
    this = SortedKeyList(range(10), key=negate)
    this._reset(4)
    that = SortedKeyList(range(10), key=negate)
    that._reset(5)
    assert this <= that
    assert that <= this
    del this[-1]
    assert this <= that
    assert not (that <= this)


def test_gt():
    this = SortedKeyList(range(10), key=negate)
    this._reset(4)
    that = SortedKeyList(range(10, 20), key=negate)
    that._reset(5)
    assert that > this
    assert not (this > that)
    that = SortedKeyList(range(1, 20), key=negate)
    that._reset(6)
    assert that > this
    that = SortedKeyList(range(1, 10), key=negate)
    that._reset(4)
    assert not (that > this)


def test_gte():
    this = SortedKeyList(range(10), key=negate)
    this._reset(4)
    that = SortedKeyList(range(10), key=negate)
    that._reset(5)
    assert this >= that
    assert that >= this
    del this[-1]
    assert that >= this
    assert not (this >= that)


def test_repr():
    this = SortedKeyList(range(10), key=negate)
    this._reset(4)
    assert repr(this).startswith(
        'SortedKeyList([9, 8, 7, 6, 5, 4, 3, 2, 1, 0], key=<function negate at '
    )


def test_pickle():
    import pickle

    alpha = SortedKeyList(range(10000), key=negate)
    alpha._reset(500)
    beta = pickle.loads(pickle.dumps(alpha))
    assert alpha == beta
    assert alpha._key == beta._key
    assert alpha._load == 500
    assert beta._load == 1000


def test_check():
    slt = SortedKeyList(range(10), key=negate)
    slt._reset(4)
    slt._len = 5
    with pytest.raises(AssertionError):
        slt._check()


def test_split():
    values = [val // 3 for val in range(30)]
    skl = SortedKeyList(values, key=negate)
    skl._reset(4)
    assert len(skl._lists) > 2
    source = list(skl)

    for index in range(-35, 36):
        left, right = skl.split(index)

        # The original is not consumed.
        assert list(skl) == source
        skl._check()

        assert isinstance(left, SortedKeyList)
        assert isinstance(right, SortedKeyList)
        assert left.key is negate
        assert right.key is negate

        cut = index + len(source) if index < 0 else index
        cut = min(max(cut, 0), len(source))
        assert len(left) == cut
        assert len(right) == len(source) - cut

        # Split is positional; duplicates keep their order on both sides.
        assert list(left) == source[:cut]
        assert list(right) == source[cut:]
        left._check()
        right._check()

        # Results share no mutable sublists with the original or each other.
        original_ids = set(map(id, skl._lists + skl._keys))
        left_ids = set(map(id, left._lists + left._keys))
        right_ids = set(map(id, right._lists + right._keys))
        assert not original_ids & left_ids
        assert not original_ids & right_ids
        assert not left_ids & right_ids

        # Positional indexing and key-bisect work on both parts.
        for pos, value in enumerate(source[:cut]):
            assert left[pos] == value
        for pos, value in enumerate(source[cut:]):
            assert right[pos] == value
        left_keys = list(map(negate, source[:cut]))
        right_keys = list(map(negate, source[cut:]))
        for value in (0, 5, 9):
            key = negate(value)
            assert left.bisect_key_left(key) == bisect_left(left_keys, key)
            assert left.bisect_key_right(key) == bisect_right(left_keys, key)
            assert right.bisect_key_left(key) == bisect_left(right_keys, key)
            assert right.bisect_key_right(key) == bisect_right(right_keys, key)

        # Parts reassemble into the whole.
        assert list(left.concat(right)) == source

        # Mutating a part affects neither the original nor the other part.
        left.add(100)
        assert list(skl) == source
        assert list(right) == source[cut:]


def test_concat():
    skl1 = SortedKeyList([val // 4 for val in range(20)], key=negate)
    skl2 = SortedKeyList([val // 4 for val in range(20, 45)], key=negate)
    skl1._reset(4)
    skl2._reset(4)
    assert len(skl1._lists) > 1
    assert len(skl2._lists) > 1

    # With the negate key, larger values sort first.
    result = skl2.concat(skl1)
    result._check()
    assert isinstance(result, SortedKeyList)
    assert result.key is negate

    combined = list(skl2) + list(skl1)
    assert list(result) == combined
    assert len(result) == len(combined)

    # Positional indexing and key-bisect work on the concatenated result.
    for pos, value in enumerate(combined):
        assert result[pos] == value
    combined_keys = list(map(negate, combined))
    for value in (0, 4, 5, 11):
        key = negate(value)
        assert result.bisect_key_left(key) == bisect_left(combined_keys, key)
        assert result.bisect_key_right(key) == bisect_right(combined_keys, key)

    # Originals are unchanged and share no mutable sublists with the result.
    assert list(skl1) == combined[len(skl2):]
    assert list(skl2) == combined[:len(skl2)]
    result_ids = set(map(id, result._lists + result._keys))
    assert not result_ids & set(map(id, skl1._lists + skl1._keys))
    assert not result_ids & set(map(id, skl2._lists + skl2._keys))
    result.add(100)
    assert list(skl1) == combined[len(skl2):]
    assert list(skl2) == combined[:len(skl2)]
    result._check()

    # Concatenating with an empty sorted-key list copies sublists.
    empty = SortedKeyList(key=negate)
    empty._reset(4)
    assert list(empty.concat(skl1)) == list(skl1)
    assert list(skl1.concat(empty)) == list(skl1)
    copied = empty.concat(skl1)
    assert not set(map(id, copied._lists)) & set(map(id, skl1._lists))


def test_concat_errors():
    skl1 = SortedKeyList(range(10), key=negate)
    skl2 = SortedKeyList(range(10, 20), key=negate)
    skl1._reset(4)
    skl2._reset(4)

    with pytest.raises(TypeError):
        skl2.concat(SortedList(range(10)))

    with pytest.raises(ValueError):
        skl1.concat(skl2)

    skl3 = SortedKeyList(range(10, 20), key=lambda val: -val)
    skl3._reset(4)
    with pytest.raises(ValueError):
        skl2.concat(skl3)

    skl4 = SortedKeyList(range(10, 20), key=negate)
    skl4._reset(5)
    with pytest.raises(ValueError):
        skl2.concat(skl4)
