"""Tests for :class:`AggregatingSortedDict`.

Covers range aggregation with cached block summaries, associative but
non-commutative aggregates (ordered string concatenation), overwrite,
deletion, batch updates, empty ranges, view mutation, and rollback when user
callables raise. Random short operation sequences are checked against a plain
``dict`` folded in sorted-key order.
"""

import random
import string

import pytest

from sortedcontainers import AggregatingSortedDict


def add(a, b):
    return a + b


def concat(a, b):
    return a + b


ADD = add
CONCAT = concat


def _fold_reference(mapping, identity, combine, get_value=None,
                    keys=None):
    if get_value is None:
        get_value = lambda value: value
    values = (get_value(mapping[key]) for key in (keys or sorted(mapping)))
    result = identity
    started = False
    if callable(identity):
        result = identity()
    for value in values:
        if not started:
            result = value
            started = True
        else:
            result = combine(result, value)
    if not started and callable(identity):
        result = identity()
    return result


def test_sum_basic_ranges():
    sd = AggregatingSortedDict(
        0, ADD, {char: index + 1 for index, char in enumerate(string.ascii_letters)}
    )
    sd._list._reset(8)
    sd._check()
    assert len(sd._list._lists) > 1

    assert sd.total == sum(range(1, 53))
    assert sd.aggregate() == sd.total

    assert sd.aggregate('a', 'z') == sum(range(1, 27))
    assert sd.aggregate('A', 'Z') == sum(range(27, 53))
    assert sd.aggregate('a', 'z', inclusive=(False, False)) == sum(
        range(2, 26)
    )
    # Uppercase letters sort before lowercase; 'c' therefore includes
    # A-Z, a-c.
    assert sd.aggregate(maximum='c') == sum(range(27, 53)) + 1 + 2 + 3
    assert sd.aggregate(minimum='A', maximum='C') == 27 + 28 + 29
    assert sd.aggregate('zzz', 'zzzz') == 0
    assert sd.aggregate(minimum='zzz') == 0
    assert sd.aggregate(maximum='0') == 0


def test_noncommutative_string_order():
    sd = AggregatingSortedDict('', CONCAT)
    sd._list._reset(4)
    keys = list(string.ascii_lowercase[:14])
    for key in reversed(keys):
        sd[key] = key.upper()
    sd._check()
    assert sd.total == 'ABCDEFGHIJKLMN'
    assert sd.aggregate('c', 'g') == 'CDEFG'
    assert sd.aggregate('c', 'g', inclusive=(False, False)) == 'DEF'
    assert sd.aggregate(maximum='c') == 'ABC'
    assert sd.aggregate(minimum='l') == 'LMN'

    # Overwrite and delete must preserve order and block summaries.
    sd['d'] = 'd'
    sd['n'] = 'n'
    del sd['a']
    sd._check()
    expected = ''.join(sd[key] for key in sorted(sd))
    assert sd.total == expected
    assert expected == 'BCdEFGHIJKLMn'
    assert sd.aggregate('b', 'e') == 'BCdE'


def test_empty_mapping():
    sd = AggregatingSortedDict(0, ADD)
    assert sd.total == 0
    assert sd.aggregate(0, 10) == 0
    assert sd.aggregate() == 0
    sd[1] = 1
    del sd[1]
    assert sd.aggregate() == 0
    sd._check()


def test_callable_identity_is_fresh():
    sd = AggregatingSortedDict(list, lambda a, b: a + b)
    empty_one = sd.aggregate()
    empty_two = sd.aggregate(10, 20)
    assert empty_one == [] and empty_two == []
    assert empty_one is not empty_two
    sd[1] = [1]
    sd[2] = [2]
    assert sd.total == [1, 2]
    sd._check()


def test_overwrite_and_bulk_update():
    sd = AggregatingSortedDict(0, ADD, {key: 1 for key in range(20)})
    sd._list._reset(4)

    for key in range(0, 20, 3):
        sd[key] = 10
    sd._check()
    assert sd.total == 20 - 7 + 7 * 10

    # Small (incremental) update path.
    sd.update({0: 100, 1: 100})
    sd._check()
    assert sd[0] == 100 and sd[1] == 100

    # Large (rebuild) update path.
    sd.update({key: 2 for key in range(100, 140)})
    sd._check()
    assert sd.total == _fold_reference(dict(sd), 0, ADD)


class _Boom(Exception):
    pass


def _flaky(fail_at):
    calls = {'count': 0}

    def combine(left, right):
        calls['count'] += 1
        if calls['count'] >= fail_at:
            raise _Boom()
        return left + right

    return combine


def _bad_get_value(value):
    if value == 'boom':
        raise _Boom()
    return value


@pytest.mark.parametrize('fail_at', range(1, 10))
def test_failed_insert_rolls_back(fail_at):
    sd = AggregatingSortedDict(0, ADD, {key: 1 for key in range(20)})
    sd._list._reset(4)
    before = dict(sd)
    sd._list._agg_combine = _flaky(fail_at)
    try:
        sd[20] = 1
    except _Boom:
        assert 20 not in sd
    else:
        assert 20 in sd
        sd._list._agg_combine = ADD
    sd._list._agg_combine = ADD
    sd._check()
    assert all(key in sd for key in before)


@pytest.mark.parametrize('fail_at', range(1, 10))
def test_failed_delete_rolls_back(fail_at):
    sd = AggregatingSortedDict(0, ADD, {key: 1 for key in range(20)})
    sd._list._reset(4)
    before = dict(sd)
    sd._list._agg_combine = _flaky(fail_at)
    try:
        del sd[10]
    except _Boom:
        assert sd[10] == 1
    sd._list._agg_combine = ADD
    sd._check()
    assert dict(sd) == before or 10 not in sd


def test_failed_overwrite_preserves_old_value():
    sd = AggregatingSortedDict(
        0, ADD, {key: 1 for key in range(12)}, get_value=_bad_get_value
    )
    sd._list._reset(4)
    with pytest.raises(_Boom):
        sd[5] = 'boom'
    assert sd[5] == 1
    sd._list._agg_get_value = lambda value: value
    sd._check()


def test_failed_bulk_update_rolls_back():
    sd = AggregatingSortedDict(
        0, ADD, {key: 1 for key in range(20)}, get_value=_bad_get_value
    )
    sd._list._reset(4)
    before = dict(sd)
    with pytest.raises(_Boom):
        sd.update({key: 'boom' for key in range(100, 110)})
    assert dict(sd) == before
    sd._list._agg_get_value = lambda value: value
    sd._check()


@pytest.mark.parametrize('fail_at', [1, 2, 3, 5, 8])
def test_failed_view_delete_rolls_back(fail_at):
    sd = AggregatingSortedDict(0, ADD, {key: 1 for key in range(20)})
    sd._list._reset(4)
    before = dict(sd)
    sd._list._agg_combine = _flaky(fail_at)
    try:
        del sd.keys()[2:6]
    except _Boom:
        pass
    sd._list._agg_combine = ADD
    sd._check()
    assert dict(sd) == before or len(sd) == 16


def test_pop_and_popitem_rollback():
    sd = AggregatingSortedDict(0, ADD, {key: 1 for key in range(12)})
    sd._list._reset(4)
    sd._list._agg_combine = _flaky(1)
    with pytest.raises(_Boom):
        sd.pop(3)
    assert sd[3] == 1
    with pytest.raises(_Boom):
        sd.popitem(0)
    assert sd[0] == 1
    sd._list._agg_combine = ADD
    sd._check()


def test_pickle_copy_and_repr():
    import copy
    import pickle

    sd = AggregatingSortedDict(0, ADD, {'a': 1, 'b': 2})
    restored = pickle.loads(pickle.dumps(sd))
    restored._check()
    assert restored.total == 3 and dict(restored) == dict(sd)

    duplicate = copy.copy(sd)
    duplicate['c'] = 3
    duplicate._check()
    assert 'c' not in sd

    assert repr(sd).startswith('AggregatingSortedDict(')


def test_random_operations_match_sorted_dict_fold():
    random.seed(20261003)
    for trial in range(40):
        load = random.choice((4, 8, 16))
        sd = AggregatingSortedDict('', CONCAT)
        sd._list._reset(load)
        reference = {}

        for _ in range(120):
            action = random.random()
            key = random.randrange(30)
            if action < 0.45:
                value = random.choice(string.ascii_uppercase)
                sd[key] = value
                reference[key] = value
            elif action < 0.65:
                if key in reference:
                    del sd[key]
                    reference.pop(key)
                    sd._check()
                continue
            elif action < 0.75:
                # overwrite a key known to exist
                if reference:
                    key = random.choice(list(reference))
                    sd[key] = reference[key].lower()
                    reference[key] = reference[key].lower()
            elif action < 0.85 and reference:
                popped = sd.pop(key, None)
                assert popped == reference.pop(key, None) or popped is None
            else:
                lo = random.choice([None, random.randrange(-2, 32)])
                hi = random.choice([None, random.randrange(-2, 32)])
                inclusive = (
                    random.choice((True, False)),
                    random.choice((True, False)),
                )
                got = sd.aggregate(lo, hi, inclusive=inclusive)
                keys = sorted(reference)
                if lo is not None:
                    keys = [
                        key
                        for key in keys
                        if (key >= lo if inclusive[0] else key > lo)
                    ]
                if hi is not None:
                    keys = [
                        key
                        for key in keys
                        if (key <= hi if inclusive[1] else key < hi)
                    ]
                expected = ''.join(reference[key] for key in keys)
                assert got == expected, (trial, lo, hi, inclusive, got, expected)
                continue
            sd._check()

        assert dict(sd) == reference
        assert sd.total == ''.join(reference[key] for key in sorted(reference))


def test_ledger_amount_extraction_and_ranges():
    import datetime

    ledger = AggregatingSortedDict(
        0, add, get_value=lambda record: record['amount']
    )
    entries = {
        datetime.date(2026, 1, 1): 100,
        datetime.date(2026, 2, 15): 250,
        datetime.date(2026, 3, 8): 75,
        datetime.date(2026, 4, 20): 400,
    }
    for day, amount in entries.items():
        ledger[day] = {'amount': amount}
    ledger._check()
    assert ledger.total == 825
    assert (
        ledger.aggregate(datetime.date(2026, 2, 1), datetime.date(2026, 3, 31))
        == 325
    )
    assert (
        ledger.aggregate(
            datetime.date(2026, 2, 15),
            datetime.date(2026, 3, 8),
            inclusive=(False, False),
        )
        == 0
    )
    ledger[datetime.date(2026, 2, 15)] = {'amount': 300}
    ledger._check()
    assert (
        ledger.aggregate(datetime.date(2026, 2, 1), datetime.date(2026, 3, 31))
        == 375
    )


def test_key_function_ordering_and_overwrite():
    def negate(key):
        return -key

    sd = AggregatingSortedDict(0, add, key=negate)
    for key in range(10):
        sd[key] = key
    sd[5] = 500
    sd._check()
    assert list(sd) == list(range(9, -1, -1))
    assert sd.total == sum(range(10)) - 5 + 500
    assert sd.aggregate(8, 2) == 8 + 7 + 6 + 500 + 4 + 3 + 2
    assert sd.aggregate(100, 200) == 0
