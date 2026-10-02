"""Tests for :class:`sortedcontainers.priorityqueue.PriorityQueue`."""

import pytest

from sortedcontainers import PriorityQueue


class Task:
    def __init__(self, name, priority):
        self.name = name
        self.priority = priority

    def __repr__(self):
        return f'Task({self.name!r}, priority={self.priority})'


def task_key(task):
    return task.priority


def test_basic_priority_order():
    pq = PriorityQueue(key=task_key)
    pq.put(Task('a', 3))
    pq.put(Task('b', 1))
    pq.put(Task('c', 2))
    assert [t.name for t in pq] == ['b', 'c', 'a']
    assert pq.peek().name == 'b'
    assert pq.pop().name == 'b'
    assert len(pq) == 2


def test_managed_refresh_changes_priority():
    a = Task('a', 5)
    b = Task('b', 1)
    c = Task('c', 3)
    pq = PriorityQueue([a, b, c], key=task_key, managed=True)

    assert [t.name for t in pq] == ['b', 'c', 'a']

    # Mutate a in place; the cached key is stale until refresh.
    a.priority = 0
    assert [t.name for t in pq] == ['b', 'c', 'a']

    pq.refresh(a)
    pq._check()
    assert [t.name for t in pq] == ['a', 'b', 'c']

    # Ranking check via bisect on keys.
    backing = pq._list
    assert [entry.key for entry in backing] == [0, 1, 3]
    assert backing.bisect_key_left(1) == 1
    assert pq.peek() is a


def test_refresh_downward_then_upward():
    members = [Task(ch, pri) for ch, pri in zip('abcd', [10, 20, 30, 40])]
    pq = PriorityQueue(members, key=task_key, managed=True)

    members[2].priority = 5
    pq.refresh(members[2])
    pq._check()
    assert [t.name for t in pq] == ['c', 'a', 'b', 'd']

    members[2].priority = 100
    pq.refresh(members[2])
    pq._check()
    assert [t.name for t in pq] == ['a', 'b', 'd', 'c']


def test_refresh_into_equal_key_region():
    a = Task('a', 1)
    b = Task('b', 2)
    c = Task('c', 2)
    d = Task('d', 3)
    pq = PriorityQueue([a, b, c, d], key=task_key, managed=True)

    a.priority = 2
    pq.refresh(a)
    pq._check()

    names = [t.name for t in pq]
    assert sorted(names) == ['a', 'b', 'c', 'd']
    assert names[-1] == 'd'
    assert set(names[:3]) == {'a', 'b', 'c'}

    # The moved entry sorts at the end of the equal-key run.
    assert names.index('a') == 2

    # Refreshing again with the same key is a no-op.
    order_before = [(t is a) for t in pq]
    pq.refresh(a)
    pq._check()
    assert [(t is a) for t in pq] == order_before


def test_same_instance_enqueued_multiple_times():
    a = Task('a', 2)
    b = Task('b', 1)
    pq = PriorityQueue(key=task_key, managed=True)
    pq.put(a)
    pq.put(b)
    pq.put(a)

    assert len(pq) == 3
    assert pq.count(a) == 2
    assert pq.count(b) == 1

    pq._check()
    assert [t.name for t in pq] == ['b', 'a', 'a']

    # Change the shared instance; refresh moves every occurrence.
    a.priority = 0
    pq.refresh(a)
    pq._check()
    assert [t.name for t in pq] == ['a', 'a', 'b']
    assert [entry.key for entry in pq._list] == [0, 0, 1]

    # remove() removes only one occurrence.
    pq.remove(a)
    assert pq.count(a) == 1
    assert a in pq
    pq._check()
    pq.remove(a)
    assert a not in pq
    pq._check()


def test_equal_but_distinct_instances_are_independent():
    class EqTask:
        def __init__(self, tag, priority):
            self.tag = tag
            self.priority = priority

        def __eq__(self, other):
            return isinstance(other, EqTask) and self.priority == other.priority

        def __hash__(self):
            return hash(self.priority)

    x = EqTask('x', 5)
    y = EqTask('y', 5)
    assert x == y and x is not y

    pq = PriorityQueue(key=lambda t: t.priority, managed=True)
    pq.put(x)
    pq.put(y)
    assert len(pq) == 2
    pq._check()

    x.priority = 1
    pq.refresh(x)
    pq._check()
    ordered = list(pq)
    assert ordered[0] is x
    assert ordered[1] is y
    assert [entry.key for entry in pq._list] == [1, 5]

    # discard by identity removes only x.
    pq.discard(x)
    assert x not in pq
    assert y in pq
    pq._check()


def test_key_function_raises_leaves_structure_consistent():
    state = {'armed': False}

    def flaky_key(task):
        if state['armed'] and task.name == 'boom':
            raise RuntimeError('key failure')
        return task.priority

    a = Task('a', 1)
    boom = Task('boom', 2)
    c = Task('c', 3)
    pq = PriorityQueue(key=flaky_key, managed=True)
    pq.put(a)
    pq.put(boom)
    pq.put(c)

    boom.priority = 0
    state['armed'] = True
    with pytest.raises(RuntimeError, match='key failure'):
        pq.refresh(boom)

    # Entries, cached keys and identity index all remain consistent with the
    # last successfully computed key (2).
    pq._check()
    assert [entry.key for entry in pq._list] == [1, 2, 3]
    assert [t.name for t in pq] == ['a', 'boom', 'c']
    assert pq.count(boom) == 1
    assert pq._index[id(boom)][1] == 2

    # Queue still works.
    boom.priority = 2
    boom.name = 'fixed'
    pq.refresh(boom)
    pq._check()
    assert [t.name for t in pq] == ['a', 'fixed', 'c']


def test_comparison_failure_leaves_structure_consistent():
    a = Task('a', 1)
    b = Task('b', 2)
    c = Task('c', 3)
    pq = PriorityQueue([a, b, c], key=task_key, managed=True)

    b.priority = object()  # not comparable with ints
    with pytest.raises(TypeError):
        pq.refresh(b)

    pq._check()
    assert [entry.key for entry in pq._list] == [1, 2, 3]
    assert [t.name for t in pq] == ['a', 'b', 'c']
    assert pq._index[id(b)][1] == 2


def test_refresh_requires_managed_mode():
    pq = PriorityQueue([Task('a', 1)], key=task_key)
    with pytest.raises(RuntimeError):
        pq.refresh(Task('a', 1))


def test_refresh_unknown_member_raises():
    pq = PriorityQueue(key=task_key, managed=True)
    with pytest.raises(ValueError):
        pq.refresh(Task('a', 1))


def test_large_random_workload_internal_consistency():
    import random

    random.seed(20261003)
    pq = PriorityQueue(key=task_key, managed=True)
    members = [Task(f't{i}', random.randrange(100)) for i in range(2000)]
    for member in members:
        pq.put(member)
    # A handful of duplicate insertions.
    for member in random.sample(members, 50):
        pq.put(member)
    pq._check()
    assert len(pq) == 2050

    for member in random.sample(members, 300):
        member.priority = random.randrange(100)
        pq.refresh(member)
    pq._check()

    keys = [entry.key for entry in pq._list]
    assert keys == sorted(keys)
    for member in members:
        assert pq._index[id(member)][1] == member.priority

    # Rankings: every entry sits in the same-key run for its member.
    for member in members:
        left = pq._list.bisect_key_left(member.priority)
        right = pq._list.bisect_key_right(member.priority)
        positions = [
            pos
            for pos in range(left, right)
            if pq._list[pos].member is member
        ]
        assert positions, member.name
