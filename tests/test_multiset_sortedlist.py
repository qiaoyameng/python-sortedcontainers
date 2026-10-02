from collections import Counter

import pytest

from sortedcontainers import SortedKeyList, SortedList


OPERATIONS = [
    'multiset_intersection',
    'multiset_union',
    'multiset_difference',
    'multiset_symmetric_difference',
    'multiset_sum',
]


def expected_multisets():
    return {
        'multiset_intersection': Counter({1: 3, 2: 2}),
        'multiset_union': Counter({1: 5, 2: 4, 3: 1, 4: 1}),
        'multiset_difference': Counter({1: 2, 3: 1}),
        'multiset_symmetric_difference': Counter({1: 2, 2: 2, 3: 1, 4: 1}),
        'multiset_sum': Counter({1: 8, 2: 6, 3: 1, 4: 1}),
    }


def assert_multiset_operations(left, right, expected, value_key=None):
    left_before = list(left)
    right_before = list(right)

    for operation in OPERATIONS:
        result = getattr(left, operation)(right)

        result_counts = Counter(result)
        if value_key is not None:
            result_counts = Counter(value_key(value) for value in result)

        assert result_counts == expected[operation]
        assert type(result) is type(left)
        assert result.key is left.key
        assert result._load == left._load
        result._check()

        assert list(left) == left_before
        assert list(right) == right_before

        if value_key is not None:
            assert all(result.key(value) == 0 for value in result)


def test_multiset_operations_with_cross_block_duplicates():
    left = SortedList([1] * 5 + [2] * 2 + [3])
    right = SortedList([1] * 3 + [2] * 4 + [4])
    left._reset(4)
    right._reset(4)

    assert len(left._lists) > 1
    assert len(right._lists) > 1
    assert sum(1 for sublist in left._lists if 1 in sublist) > 1
    assert sum(1 for sublist in right._lists if 2 in sublist) > 1

    assert_multiset_operations(left, right, expected_multisets())


class SameKeyItem:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, SameKeyItem) and self.value == other.value

    def __hash__(self):
        return hash(self.value)

    def __repr__(self):
        return f'SameKeyItem({self.value})'


class UnhashableItem:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, UnhashableItem) and self.value == other.value

    __hash__ = None


def test_sorted_key_list_matches_values_inside_equal_key_groups():
    key = lambda item: 0
    left = SortedKeyList(
        [SameKeyItem(1)] * 5 + [SameKeyItem(2)] * 2 + [SameKeyItem(3)],
        key=key,
    )
    right = SortedKeyList(
        [SameKeyItem(1)] * 3 + [SameKeyItem(2)] * 4 + [SameKeyItem(4)],
        key=key,
    )
    left._reset(4)
    right._reset(4)

    assert len(left._lists) > 1
    assert all(sublist_keys == [0] * len(sublist_keys) for sublist_keys in left._keys)

    assert_multiset_operations(
        left,
        right,
        expected_multisets(),
        value_key=lambda item: item.value,
    )


def test_sorted_key_list_does_not_treat_equal_key_group_as_one_value():
    key = lambda item: 0
    left = SortedKeyList([SameKeyItem(1), SameKeyItem(2)], key=key)
    right = SortedKeyList([SameKeyItem(3), SameKeyItem(4)], key=key)

    assert not left.multiset_intersection(right)
    assert Counter(left.multiset_union(right)) == Counter(
        [SameKeyItem(1), SameKeyItem(2), SameKeyItem(3), SameKeyItem(4)]
    )


def test_unhashable_values_match_by_value_inside_equal_key_group():
    key = lambda item: 0
    left = SortedKeyList(
        [UnhashableItem(1), UnhashableItem(1), UnhashableItem(2)],
        key=key,
    )
    right = SortedKeyList(
        [UnhashableItem(1), UnhashableItem(3)],
        key=key,
    )

    intersection = left.multiset_intersection(right)
    union = left.multiset_union(right)

    assert [item.value for item in intersection] == [1]
    assert [item.value for item in union] == [1, 1, 2, 3]


class BrokenEqualityItem:
    def __eq__(self, other):
        raise TypeError('broken equality')

    def __hash__(self):
        return 1


def test_broken_equality_is_not_treated_as_unhashable():
    key = lambda item: 0
    left = SortedKeyList([BrokenEqualityItem()], key=key)
    right = SortedKeyList([BrokenEqualityItem()], key=key)

    with pytest.raises(TypeError, match='broken equality'):
        left.multiset_intersection(right)


class CountedComparable:
    comparisons = 0

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        type(self).comparisons += 1
        return self.value < other.value

    def __eq__(self, other):
        return isinstance(other, CountedComparable) and self.value == other.value

    def __le__(self, other):
        return self.value <= other.value

    def __hash__(self):
        return hash(self.value)


def test_multiset_operations_use_ordered_merge_without_full_resort():
    left = SortedList([CountedComparable(1) for _ in range(8)])
    right = SortedList([CountedComparable(1) for _ in range(8)])
    left._reset(4)
    right._reset(4)

    expected_lengths = {
        'multiset_intersection': 8,
        'multiset_union': 8,
        'multiset_difference': 0,
        'multiset_symmetric_difference': 0,
        'multiset_sum': 16,
    }

    for operation in OPERATIONS:
        CountedComparable.comparisons = 0
        result = getattr(left, operation)(right)

        assert len(result) == expected_lengths[operation]
        assert CountedComparable.comparisons == 2

        result._check()


def test_multiset_operations_reject_incompatible_keys():
    left = SortedKeyList([1], key=lambda value: value)
    right = SortedKeyList([1], key=lambda value: value)

    with pytest.raises(TypeError):
        left.multiset_intersection(right)

    with pytest.raises(TypeError):
        left.multiset_union(SortedList([1]))

    with pytest.raises(TypeError):
        left.multiset_sum([1])
