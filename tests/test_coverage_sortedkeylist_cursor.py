import random
from bisect import bisect_right
from itertools import islice

import pytest

from sortedcontainers import CursorInvalidError, SortedKeyList


class Item:
    """Identity-based item that cannot be serialized or ordered."""

    def __init__(self, key, name):
        self.key = key
        self.name = name

    def __repr__(self):
        return f'Item({self.key}, {self.name})'

    def __reduce__(self):
        raise TypeError('Item is not serializable')


def make_items(count, key=lambda num: num):
    return [Item(key(num), f'v{num}') for num in range(count)]


def test_cursor_empty():
    skl = SortedKeyList(key=lambda item: item.key)
    cursor = skl.cursor()
    assert cursor.index == 0
    assert list(cursor) == []
    assert list(reversed(cursor)) == []


def test_cursor_forward_pagination_duplicate_keys():
    items = make_items(50, key=lambda num: num % 7)
    skl = SortedKeyList(items, key=lambda item: item.key)
    skl._reset(4)
    skl._check()

    cursor = skl.cursor()
    pages = []
    while True:
        page = list(islice(cursor, 6))
        if not page:
            break
        pages.append(page)

    assert [item for page in pages for item in page] == list(skl)
    assert cursor.index == len(skl)


def test_cursor_page_delete_tail_insert_same_key():
    # Same-key objects span multiple blocks. Take a page, delete the page
    # tail, and insert more objects with the same key. The documented
    # contract: the cursor keeps its position; the next page starts with
    # the object that followed the deleted tail, and new same-key objects
    # are appended at the end of the key run.
    items = make_items(20, key=lambda num: 7)
    skl = SortedKeyList(items, key=lambda item: item.key)
    skl._reset(4)
    skl._check()
    assert len(skl._lists) > 1

    cursor = skl.cursor()
    page = list(islice(cursor, 6))
    assert page == items[:6]

    skl.discard(page[-1])
    extras = make_items(2, key=lambda num: 7)
    skl.update(extras)
    skl._check()

    assert list(islice(cursor, 6)) == items[6:12]
    assert list(cursor) == items[12:] + extras
    assert cursor.index == len(skl)


def test_cursor_reverse_pagination():
    items = make_items(30, key=lambda num: num % 4)
    skl = SortedKeyList(items, key=lambda item: item.key)
    skl._reset(4)

    cursor = skl.cursor(after=skl[-1])
    pages = []
    while True:
        page = list(islice(reversed(cursor), 5))
        if not page:
            break
        pages.append(page)

    assert [item for page in pages for item in page] == list(skl)[::-1]
    assert cursor.index == 0


def test_cursor_reverse_delete_and_insert():
    items = make_items(12, key=lambda num: 3)
    skl = SortedKeyList(items, key=lambda item: item.key)
    skl._reset(4)

    cursor = skl.cursor(after=items[9])
    skl.discard(items[2])
    extras = make_items(2, key=lambda num: 3)
    skl.update(extras)

    assert list(islice(reversed(cursor), 4)) == [
        items[9],
        items[8],
        items[7],
        items[6],
    ]
    assert list(reversed(cursor)) == [items[5], items[4], items[3], items[1], items[0]]
    assert list(reversed(cursor)) == []


def test_cursor_after_before():
    items = make_items(10, key=lambda num: num // 3)
    skl = SortedKeyList(items, key=lambda item: item.key)

    cursor = skl.cursor(after=items[4])
    assert cursor.index == 5
    assert list(cursor) == items[5:]

    cursor = skl.cursor(before=items[4])
    assert cursor.index == 4
    assert list(cursor) == items[4:]

    cursor = skl.cursor(before=items[0])
    assert list(reversed(cursor)) == []

    cursor = skl.cursor(after=items[-1])
    assert list(cursor) == []


def test_cursor_after_before_errors():
    skl = SortedKeyList([1, 2, 3], key=lambda val: val)

    with pytest.raises(ValueError):
        skl.cursor(after=1, before=2)

    with pytest.raises(ValueError):
        skl.cursor(after=4)

    with pytest.raises(ValueError):
        skl.cursor(before=4)


def test_cursor_insert_adjusts_position():
    items = make_items(10, key=lambda num: num // 2)
    skl = SortedKeyList(items, key=lambda item: item.key)
    skl._reset(4)

    cursor = skl.cursor(after=items[4])
    assert cursor.index == 5

    before = Item(0, 'before')
    skl.add(before)
    assert cursor.index == 6

    after = Item(99, 'after')
    skl.add(after)
    assert cursor.index == 6

    same_key = Item(items[5].key, 'same')
    skl.add(same_key)
    assert cursor.index == 6
    assert list(islice(cursor, 2)) == [items[5], same_key]


def test_cursor_delete_adjusts_position():
    items = make_items(10, key=lambda num: 1)
    skl = SortedKeyList(items, key=lambda item: item.key)
    skl._reset(4)

    cursor = skl.cursor(after=items[4])
    assert cursor.index == 5

    skl.discard(items[1])
    assert cursor.index == 4

    # Deleting the most recently yielded value does not disturb the cursor.
    skl.discard(items[4])
    assert cursor.index == 3
    assert list(islice(cursor, 2)) == [items[5], items[6]]

    # Deleting the value at the cursor position skips nothing.
    skl.discard(items[5])
    assert cursor.index == 4
    assert list(islice(cursor, 2)) == [items[7], items[8]]


def test_cursor_pop_and_delitem_adjust_position():
    items = make_items(10, key=lambda num: num // 3)
    skl = SortedKeyList(items, key=lambda item: item.key)
    skl._reset(4)

    cursor = skl.cursor(after=items[5])
    assert cursor.index == 6

    skl.pop(0)
    assert cursor.index == 5

    del skl[0]
    assert cursor.index == 4
    assert list(cursor) == items[6:]


def test_cursor_slice_delete_keeps_valid():
    items = make_items(30, key=lambda num: num % 3)
    skl = SortedKeyList(items, key=lambda item: item.key)
    skl._reset(4)

    ordered = sorted(items, key=lambda item: item.key)
    pos = ordered.index(items[14])

    cursor = skl.cursor(after=items[14])
    assert cursor.index == pos + 1

    del skl[2:8]
    skl._check()
    assert cursor.index == pos + 1 - 6
    assert list(cursor) == ordered[pos + 1 :]


def test_cursor_clear_invalidates():
    skl = SortedKeyList([3, 1, 2], key=lambda val: val)
    cursor = skl.cursor()
    skl.clear()
    with pytest.raises(CursorInvalidError):
        list(cursor)
    with pytest.raises(CursorInvalidError):
        list(reversed(cursor))


def test_cursor_reset_invalidates():
    skl = SortedKeyList([3, 1, 2], key=lambda val: val)
    cursor = skl.cursor()
    skl._reset(10)
    with pytest.raises(CursorInvalidError):
        list(cursor)


def test_cursor_imul_invalidates():
    skl = SortedKeyList([3, 1, 2], key=lambda val: val)
    cursor = skl.cursor()
    skl *= 2
    with pytest.raises(CursorInvalidError):
        list(cursor)


def test_cursor_delitem_all_invalidates():
    skl = SortedKeyList([3, 1, 2], key=lambda val: val)
    cursor = skl.cursor()
    del skl[:]
    with pytest.raises(CursorInvalidError):
        list(cursor)


def test_cursor_bulk_update_keeps_valid():
    items = make_items(10, key=lambda num: num)
    skl = SortedKeyList(items, key=lambda item: item.key)
    cursor = skl.cursor(after=items[4])

    # Bulk update large enough to trigger a rebuild without cursors.
    extras = make_items(100, key=lambda num: 100 + num)
    skl.update(extras)
    skl._check()

    assert cursor.index == 5
    assert list(cursor) == items[5:] + extras


def test_cursor_live_view_no_snapshot():
    items = make_items(5, key=lambda num: num)
    skl = SortedKeyList(items, key=lambda item: item.key)

    cursor = skl.cursor()
    extra = Item(10, 'extra')
    skl.add(extra)

    # The cursor observes mutations; it holds no snapshot of the list.
    assert list(cursor) == items + [extra]


def test_cursor_normal_iterators_unchanged():
    items = make_items(20, key=lambda num: num % 5)
    skl = SortedKeyList(items, key=lambda item: item.key)
    skl._reset(4)

    cursor = skl.cursor()
    list(islice(cursor, 3))

    ordered = sorted(items, key=lambda item: item.key)
    assert list(skl) == ordered
    assert list(reversed(skl)) == ordered[::-1]
    assert list(iter(skl)) == ordered
    assert list(skl.islice(2, 8)) == ordered[2:8]
    assert list(skl.irange_key(1, 3)) == [
        item for item in ordered if 1 <= item.key <= 3
    ]


def test_cursor_random_model():
    random.seed(0)

    skl = SortedKeyList(key=lambda item: item.key)
    skl._reset(4)
    model = []
    cursor = skl.cursor()
    boundary = 0

    for step in range(1000):
        op = random.randrange(6)

        if op in (0, 1, 2) or not model:
            item = Item(random.randrange(5), f'v{step}')
            pos = bisect_right([each.key for each in model], item.key)
            model.insert(pos, item)
            skl.add(item)
            if boundary > pos:
                boundary += 1
        elif op == 3:
            pos = random.randrange(len(model))
            skl.discard(model[pos])
            del model[pos]
            if boundary > pos:
                boundary -= 1
        elif op == 4:
            size = random.randrange(1, 10)
            page = list(islice(cursor, size))
            assert page == model[boundary : boundary + size]
            boundary += len(page)
        else:
            size = random.randrange(1, 10)
            page = list(islice(reversed(cursor), size))
            assert page == model[max(0, boundary - size) : boundary][::-1]
            boundary -= len(page)

        skl._check()
        assert cursor.index == boundary
        assert list(skl) == model
