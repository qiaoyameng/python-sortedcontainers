import pickle

import pytest

from sortedcontainers import SortedKeyList, SortedList


class Job:
    def __init__(self, name, priority):
        self.name = name
        self.priority = priority

    def __repr__(self):
        return f"Job({self.name!r}, {self.priority!r})"


def priority(job):
    return job.priority


def ranks(container, jobs):
    return [
        next(index for index, current in enumerate(container) if current is job)
        for job in jobs
    ]


def test_managed_refresh_priority():
    jobs = [Job("a", 1), Job("b", 2), Job("c", 3)]
    skl = SortedKeyList(jobs, key=priority, managed=True)

    jobs[1].priority = 0
    skl.refresh(jobs[1])
    skl._check()

    assert [job.name for job in skl] == ["b", "a", "c"]
    assert ranks(skl, jobs) == [1, 0, 2]


def test_managed_refresh_into_equal_key_interval():
    first = Job("first", 1)
    middle = Job("middle", 2)
    second = Job("second", 2)
    third = Job("third", 3)
    skl = SortedKeyList([first, middle, second, third], key=priority, managed=True)

    first.priority = 2
    skl.refresh(first)
    skl._check()

    assert list(skl) == [middle, second, first, third]
    assert skl.index(first) == 2


def test_managed_refresh_across_segments():
    jobs = [Job(str(value), value % 10) for value in range(30)]
    skl = SortedKeyList(jobs, key=priority, managed=True)
    skl._reset(4)

    target = jobs[1]
    target.priority = 8
    skl.refresh(target)
    skl._check()

    assert [job.name for job in skl] == [
        "0", "10", "20", "11", "21", "2", "12", "22", "3", "13",
        "23", "4", "14", "24", "5", "15", "25", "6", "16", "26",
        "7", "17", "27", "8", "18", "28", "1", "9", "19", "29",
    ]
    assert skl.index(target) == 26


def test_managed_refresh_repeated_instance():
    target = Job("target", 2)
    other = Job("other", 3)
    skl = SortedKeyList([other], key=priority, managed=True)
    skl.add(target)
    skl.add(target)

    target.priority = 1
    skl.refresh(target)
    skl._check()

    assert list(skl) == [target, target, other]
    assert [skl.index(job) if job is not target else 0 for job in skl] == [0, 0, 2]
    assert skl._member_counts[id(target)] == 2


def test_managed_refresh_none_key_comparison_failure_is_safe():
    target = Job("target", None)
    skl = SortedKeyList([target], key=priority, managed=True)
    original = list(skl)

    target.priority = "before"

    with pytest.raises(TypeError):
        skl.refresh(target)

    skl._check()
    assert list(skl) == original

    target.priority = None
    skl._check()


def test_managed_refresh_uses_identity_not_equality():
    class EqualJob(Job):
        def __eq__(self, other):
            return isinstance(other, EqualJob)

    first = EqualJob("first", 1)
    second = EqualJob("second", 1)
    third = EqualJob("third", 3)
    skl = SortedKeyList([first, second, third], key=priority, managed=True)

    first.priority = 3
    skl.refresh(first)
    skl._check()

    assert list(skl) == [second, third, first]
    assert skl._member_keys[id(second)] == 1


def test_unmanaged_refresh_requires_opt_in():
    skl = SortedKeyList([Job("a", 1)], key=priority)

    with pytest.raises(ValueError):
        skl.refresh(skl[0])


def test_managed_requires_key_function():
    with pytest.raises(TypeError):
        SortedList(managed=True)


def test_manage_keyword_alias():
    skl = SortedKeyList([Job("a", 1)], key=priority, manage=True)

    assert skl.managed is True
    assert skl.manage is True


def test_managed_update_tracks_existing_and_repeated_instances():
    target = Job("target", 2)
    skl = SortedKeyList([target], key=priority, managed=True)
    skl.update([Job("a", 1), Job("c", 3), target, target])

    target.priority = 0
    skl.refresh(target)
    skl._check()

    assert [job.name for job in skl[:3]] == ["target", "target", "target"]
    assert skl._member_counts[id(target)] == 3


def test_managed_copy_and_pickle_preserve_mode():
    target = Job("target", 2)
    skl = SortedKeyList([Job("a", 1), target, target], key=priority, managed=True)

    copied = skl.copy()
    pickled = pickle.loads(pickle.dumps(skl))

    for container, managed_target in ((copied, target), (pickled, pickled[1])):
        assert container.managed
        managed_target.priority = 0
        container.refresh(managed_target)
        container._check()
        assert list(container[:2]) == [managed_target, managed_target]
        managed_target.priority = 2


class FailingKeyJob(Job):
    def __init__(self, name, priority):
        super().__init__(name, priority)
        self.fail_key = False


def failing_priority(job):
    if getattr(job, "fail_key", False):
        raise RuntimeError("key failure")
    return job.priority


def test_refresh_key_failure_leaves_consistent_container():
    target = FailingKeyJob("target", 2)
    jobs = [Job("a", 1), target, Job("c", 3)]
    skl = SortedKeyList(jobs, key=failing_priority, managed=True)
    original = list(skl)

    target.priority = 0
    target.fail_key = True

    with pytest.raises(RuntimeError):
        skl.refresh(target)

    skl._check()
    assert list(skl) == original
    assert ranks(skl, jobs) == [0, 1, 2]

    target.fail_key = False
    skl.refresh(target)
    skl._check()
    assert skl.index(target) == 0


class UncomparableKey:
    def __lt__(self, other):
        raise RuntimeError("comparison failure")

    def __gt__(self, other):
        raise RuntimeError("comparison failure")


def test_refresh_comparison_failure_leaves_consistent_container():
    target = Job("target", 2)
    jobs = [Job("a", 1), target, Job("c", 3)]
    use_bad_key = False

    def key(job):
        if use_bad_key and job is target:
            return UncomparableKey()
        return job.priority

    skl = SortedKeyList(jobs, key=key, managed=True)
    original = list(skl)

    use_bad_key = True
    with pytest.raises(RuntimeError):
        skl.refresh(target)

    skl._check()
    assert list(skl) == original

    use_bad_key = False
    target.priority = 0
    skl.refresh(target)
    skl._check()
    assert skl.index(target) == 0
