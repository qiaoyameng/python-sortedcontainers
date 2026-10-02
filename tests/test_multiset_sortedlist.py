from collections import Counter

import pytest

from sortedcontainers import SortedKeyList, SortedList


def item_group(item):
    return item.group


class GroupedItem:
    def __init__(self, group, name):
        self.group = group
        self.name = name

    def __eq__(self, other):
        return (
            isinstance(other, GroupedItem)
            and self.group == other.group
            and self.name == other.name
        )

    def __hash__(self):
        return hash((self.group, self.name))


def counts(values):
    return Counter(
        tuple(value) if isinstance(value, list) else value for value in values
    )


def test_multiset_operations_across_blocks():
    left = SortedList([1, 1, 1, 2, 2, 3, 5, 5])
    right = SortedList([1, 1, 2, 2, 2, 4, 5])
    left._reset(4)
    right._reset(3)
    left_before = list(left)
    right_before = list(right)

    assert left.multiset_intersection(right) == [1, 1, 2, 2, 5]
    assert left.multiset_union(right) == [1, 1, 1, 2, 2, 2, 3, 4, 5, 5]
    assert left.multiset_sum(right) == [
        1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 4, 5, 5, 5
    ]
    assert left.multiset_difference(right) == [1, 3, 5]
    assert left.multiset_symmetric_difference(right) == [1, 2, 3, 4, 5]

    assert list(left) == left_before
    assert list(right) == right_before

    operations = [
        left.multiset_intersection(right),
        left.multiset_union(right),
        left.multiset_sum(right),
        left.multiset_difference(right),
        left.multiset_symmetric_difference(right),
    ]
    expected = [
        Counter([1, 1, 2, 2, 5]),
        Counter([1, 1, 1, 2, 2, 2, 3, 4, 5, 5]),
        Counter([1] * 5 + [2] * 5 + [3, 4, 5, 5, 5]),
        Counter([1, 3, 5]),
        Counter([1, 2, 3, 4, 5]),
    ]

    for result, expected_counts in zip(operations, expected):
        assert type(result) is SortedList
        assert result.key is None
        assert result._load == left._load
        assert counts(result) == expected_counts
        result._check()


def test_multiset_empty_operand_preserves_configuration():
    left = SortedList([1, 1, 2])
    right = SortedList()
    left._reset(4)
    right._reset(4)

    for result in (
        left.multiset_intersection(right),
        right.multiset_difference(left),
    ):
        assert type(result) is SortedList
        assert result.key is None
        assert result._load == left._load
        assert result == []
        result._check()

    assert left.multiset_sum(right) == [1, 1, 2]
    assert left.multiset_difference(right) == [1, 1, 2]
    assert right.multiset_symmetric_difference(left) == [1, 1, 2]


def test_sorted_key_list_matches_values_within_same_key():
    left = SortedKeyList(
        [
            GroupedItem(1, 'a'),
            GroupedItem(1, 'b'),
            GroupedItem(1, 'b'),
            GroupedItem(2, 'a'),
        ],
        key=item_group,
    )
    right = SortedKeyList(
        [
            GroupedItem(1, 'b'),
            GroupedItem(1, 'c'),
            GroupedItem(2, 'a'),
            GroupedItem(2, 'a'),
        ],
        key=item_group,
    )
    left._reset(4)
    right._reset(4)
    left_before = [(item.group, item.name) for item in left]
    right_before = [(item.group, item.name) for item in right]

    intersection = left.multiset_intersection(right)
    union = left.multiset_union(right)
    total = left.multiset_sum(right)
    difference = left.multiset_difference(right)
    symmetric_difference = left.multiset_symmetric_difference(right)

    assert [(item.group, item.name) for item in intersection] == [
        (1, 'b'),
        (2, 'a'),
    ]
    assert [(item.group, item.name) for item in union] == [
        (1, 'a'),
        (1, 'b'),
        (1, 'b'),
        (1, 'c'),
        (2, 'a'),
        (2, 'a'),
    ]
    assert [(item.group, item.name) for item in total] == [
        (1, 'a'),
        (1, 'b'),
        (1, 'b'),
        (1, 'b'),
        (1, 'c'),
        (2, 'a'),
        (2, 'a'),
        (2, 'a'),
    ]
    assert [(item.group, item.name) for item in difference] == [
        (1, 'a'),
        (1, 'b'),
    ]
    assert [(item.group, item.name) for item in symmetric_difference] == [
        (1, 'a'),
        (1, 'b'),
        (1, 'c'),
        (2, 'a'),
    ]

    for result in (
        intersection,
        union,
        total,
        difference,
        symmetric_difference,
    ):
        assert type(result) is SortedKeyList
        assert result.key is item_group
        assert result._load == left._load
        result._check()

    assert [(item.group, item.name) for item in left] == left_before
    assert [(item.group, item.name) for item in right] == right_before


def test_sorted_key_list_matches_unhashable_values_within_same_key():
    left = SortedKeyList(
        [['a', 1], ['b', 1], ['b', 2], ['c', 1]],
        key=len,
    )
    right = SortedKeyList(
        [['b', 1], ['d', 2], ['c', 1], ['c', 1]],
        key=len,
    )

    assert left.multiset_intersection(right) == [['b', 1], ['c', 1]]
    assert counts(left.multiset_union(right)) == Counter(
        [
            ('a', 1),
            ('b', 1),
            ('b', 2),
            ('c', 1),
            ('c', 1),
            ('d', 2),
        ]
    )
    assert counts(left.multiset_sum(right)) == Counter(
        [
            ('a', 1),
            ('b', 1),
            ('b', 1),
            ('b', 2),
            ('c', 1),
            ('c', 1),
            ('c', 1),
            ('d', 2),
        ]
    )
    assert counts(left.multiset_difference(right)) == Counter(
        [('a', 1), ('b', 2)]
    )
    assert counts(left.multiset_symmetric_difference(right)) == Counter(
        [('a', 1), ('b', 2), ('c', 1), ('d', 2)]
    )

    for operation in (
        'multiset_union',
        'multiset_sum',
        'multiset_difference',
        'multiset_symmetric_difference',
    ):
        getattr(left, operation)(right)._check()

    assert list(left) == [['a', 1], ['b', 1], ['b', 2], ['c', 1]]
    assert list(right) == [['b', 1], ['d', 2], ['c', 1], ['c', 1]]


def test_multiset_rejects_incompatible_keys():
    left = SortedKeyList([1, 2], key=lambda value: value)
    right = SortedKeyList([1, 2], key=lambda value: -value)

    with pytest.raises(TypeError, match='incompatible key'):
        left.multiset_intersection(right)

    with pytest.raises(TypeError, match='SortedList'):
        left.multiset_intersection([1, 2])


def test_multiset_merge_does_not_resort(monkeypatch):
    class Counted:
        comparisons = 0

        def __init__(self, value):
            self.value = value

        def __lt__(self, other):
            type(self).comparisons += 1
            return self.value < other.value

        def __eq__(self, other):
            return isinstance(other, Counted) and self.value == other.value

        def __hash__(self):
            return hash(self.value)

    left = SortedList([Counted(value) for value in [1, 1, 2, 3, 3]])
    right = SortedList([Counted(value) for value in [1, 2, 2, 3, 4]])
    left._reset(4)
    right._reset(4)

    def fail_sorted(*args, **kwargs):
        raise AssertionError('multiset operation resorted its inputs')

    monkeypatch.setattr('builtins.sorted', fail_sorted)
    Counted.comparisons = 0
    result = left.multiset_symmetric_difference(right)

    assert [item.value for item in result] == [1, 2, 3, 4]
    assert Counted.comparisons < len(left) + len(right)
