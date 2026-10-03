import pickle
from itertools import islice

import pytest

from sortedcontainers import (
    CursorInvalidError,
    SortedKeyList,
    SortedKeyListCursor,
)


class Record:
    def __init__(self, group, name):
        self.group = group
        self.name = name

    def __repr__(self):
        return f'Record({self.group!r}, {self.name!r})'


def build_skl():
    """Sorted-key list with a run of ten equal keys spanning sublists."""
    skl = SortedKeyList(key=lambda record: record.group)
    skl._reset(4)
    records = [Record(0, 'zero-a'), Record(0, 'zero-b')]
    records += [Record(1, f'one-{num}') for num in range(10)]
    records += [Record(2, 'two-a'), Record(2, 'two-b')]
    skl.update(records)
    return skl, records


def test_cursor_type():
    skl, _ = build_skl()
    assert isinstance(skl.cursor(), SortedKeyListCursor)


def test_cursor_cross_block_run():
    skl, _ = build_skl()
    # The run of group-one records spans multiple sublists (blocks).
    assert sum(1 in block for block in skl._keys) >= 2
    skl._check()


def test_cursor_next_pages():
    skl, records = build_skl()
    cursor = skl.cursor()
    assert [cursor.next() for _ in range(5)] == records[:5]
    assert [cursor.next() for _ in range(9)] == records[5:]
    with pytest.raises(StopIteration):
        cursor.next()


def test_cursor_iterate_pages():
    skl, records = build_skl()
    cursor = skl.cursor()
    pages = []
    while True:
        page = list(islice(cursor.iterate(), 5))
        if not page:
            break
        pages.append(page)
    assert [record for page in pages for record in page] == records


def test_cursor_reverse():
    skl, records = build_skl()
    cursor = skl.cursor(end=True)
    assert list(cursor.iterate(reverse=True)) == records[::-1]
    with pytest.raises(StopIteration):
        cursor.prev()


def test_cursor_prev_steps():
    skl, records = build_skl()
    cursor = skl.cursor(end=True)
    assert cursor.prev() == records[-1]
    assert cursor.prev() == records[-2]


def test_cursor_mixed_direction():
    skl, records = build_skl()
    cursor = skl.cursor()
    assert cursor.next() == records[0]
    assert cursor.next() == records[1]
    # The anchor is exclusive in both directions: stepping back yields the
    # values before the anchor, not the anchor itself.
    assert cursor.prev() == records[0]
    assert cursor.next() == records[1]
    assert cursor.next() == records[2]


def test_cursor_page_then_insert_same_key():
    skl, records = build_skl()
    assert sum(1 in block for block in skl._keys) >= 2

    cursor = skl.cursor()
    page = list(islice(cursor.iterate(), 5))
    assert page == records[:5]
    assert page[-1].name == 'one-2'

    # Insert values with the same key as the anchor.
    extra = [Record(1, 'one-extra-a'), Record(1, 'one-extra-b')]
    skl.update(extra)
    skl._check()

    assert cursor.valid
    # Added values sort after existing group-one records.
    expected = records[5:12] + extra + records[12:]
    assert list(cursor.iterate()) == expected


def test_cursor_page_tail_removal_invalidates():
    skl, records = build_skl()
    cursor = skl.cursor()
    page = list(islice(cursor.iterate(), 5))
    tail = page[-1]

    skl.remove(tail)
    skl._check()

    assert not cursor.valid
    with pytest.raises(CursorInvalidError):
        cursor.next()
    with pytest.raises(CursorInvalidError):
        cursor.prev()
    with pytest.raises(CursorInvalidError):
        cursor.iterate()

    # Re-adding the anchor value under its recorded key restores validity.
    # The value sorts to the end of the equal-key run.
    skl.add(tail)
    skl._check()
    assert cursor.valid
    assert list(cursor.iterate()) == records[12:]


def test_cursor_page_then_delete_tail_and_insert_same_key():
    """Page, delete the page tail, and insert same-key values."""
    skl, records = build_skl()
    assert sum(1 in block for block in skl._keys) >= 2

    cursor = skl.cursor()
    page = list(islice(cursor.iterate(), 5))
    tail = page[-1]

    # Deleting the page tail invalidates the cursor.
    skl.remove(tail)
    assert not cursor.valid
    with pytest.raises(CursorInvalidError):
        cursor.next()

    # Re-anchor after the new page tail and insert same-key values.
    cursor = skl.cursor(after=page[-2])
    extra = [Record(1, 'one-extra-a'), Record(1, 'one-extra-b')]
    skl.update(extra)
    skl._check()

    assert cursor.valid
    expected = records[5:12] + extra + records[12:]
    assert list(cursor.iterate()) == expected


def test_cursor_non_anchor_removal():
    skl, records = build_skl()
    cursor = skl.cursor()
    page = list(islice(cursor.iterate(), 5))

    # Remove values before and after the anchor, neither being the anchor.
    skl.remove(page[0])
    skl.remove(records[7])
    skl._check()

    assert cursor.valid
    expected = [record for record in records[5:] if record is not records[7]]
    assert list(cursor.iterate()) == expected


def test_cursor_key_update_invalidates():
    skl, records = build_skl()
    cursor = skl.cursor()
    page = list(islice(cursor.iterate(), 5))
    anchor = page[-1]

    # Remove and re-add the anchor under a different key.
    skl.remove(anchor)
    anchor.group = 9
    skl.add(anchor)
    skl._check()

    assert not cursor.valid
    with pytest.raises(CursorInvalidError):
        cursor.next()


def test_cursor_in_place_key_mutation_invalidates():
    skl, records = build_skl()
    cursor = skl.cursor()
    page = list(islice(cursor.iterate(), 5))
    anchor = page[-1]

    # Mutate the anchor's key in place.
    anchor.group = 9

    assert not cursor.valid
    with pytest.raises(CursorInvalidError):
        cursor.next()


def test_cursor_clear_invalidates():
    skl, _ = build_skl()
    cursor = skl.cursor()
    cursor.next()
    skl.clear()
    assert not cursor.valid
    with pytest.raises(CursorInvalidError):
        cursor.next()


def test_cursor_sentinels_stay_valid():
    skl, _ = build_skl()
    start = skl.cursor()
    end = skl.cursor(end=True)
    skl.clear()
    assert start.valid
    assert end.valid
    assert list(start.iterate()) == []
    assert list(end.iterate(reverse=True)) == []


def test_cursor_factory_errors():
    skl, records = build_skl()
    with pytest.raises(ValueError):
        skl.cursor(after=Record(1, 'missing'))
    with pytest.raises(ValueError):
        skl.cursor(after=records[0], end=True)


def test_cursor_anchor_identity():
    class Token:
        def __init__(self, key, serial):
            self.key = key
            self.serial = serial

        def __eq__(self, other):
            return (self.key, self.serial) == (other.key, other.serial)

        def __hash__(self):
            return hash((self.key, self.serial))

    first = Token(1, 'same')
    second = Token(1, 'same')
    assert first == second

    skl = SortedKeyList(key=lambda token: token.key)
    skl.update([first, second])

    # An equal but distinct value may not anchor a cursor.
    with pytest.raises(ValueError):
        skl.cursor(after=Token(1, 'same'))

    # Removing the equal twin leaves the cursor valid.
    cursor = skl.cursor(after=first)
    pos = next(num for num, token in enumerate(skl) if token is second)
    skl.pop(pos)
    assert cursor.valid
    with pytest.raises(StopIteration):
        cursor.next()

    # Removing the anchor invalidates even though an equal value remains.
    skl.add(second)
    pos = next(num for num, token in enumerate(skl) if token is first)
    skl.pop(pos)
    assert not cursor.valid


def test_cursor_duplicate_anchor_object():
    skl, records = build_skl()
    anchor = records[5]
    skl.add(anchor)
    skl._check()

    cursor = skl.cursor(after=anchor)
    pos = next(num for num, record in enumerate(skl) if record is anchor)
    skl.pop(pos)
    skl._check()
    assert cursor.valid


def test_cursor_unserializable_values():
    class Local:
        def __init__(self, num):
            self.num = num

    values = [Local(num) for num in range(5)]

    # Local classes cannot be pickled; cursors never serialize values.
    with pytest.raises((pickle.PicklingError, AttributeError)):
        pickle.dumps(values[0])

    skl = SortedKeyList(values, key=lambda local: local.num % 2)
    cursor = skl.cursor()
    page = [cursor.next() for _ in range(3)]
    assert page == sorted(values, key=lambda local: local.num % 2)[:3]
    skl.remove(page[-1])
    assert not cursor.valid


def test_cursor_empty_list():
    skl = SortedKeyList(key=lambda record: record.group)
    cursor = skl.cursor()
    assert cursor.valid
    with pytest.raises(StopIteration):
        cursor.next()
    with pytest.raises(StopIteration):
        cursor.prev()
    end_cursor = skl.cursor(end=True)
    assert end_cursor.valid
    with pytest.raises(StopIteration):
        end_cursor.next()
    with pytest.raises(StopIteration):
        end_cursor.prev()


def test_cursor_bounds():
    skl, _ = build_skl()
    with pytest.raises(StopIteration):
        skl.cursor().prev()
    with pytest.raises(StopIteration):
        skl.cursor(end=True).next()


def test_cursor_repr():
    skl, records = build_skl()
    assert repr(skl.cursor()) == 'SortedKeyListCursor(start)'
    assert repr(skl.cursor(end=True)) == 'SortedKeyListCursor(end)'
    cursor = skl.cursor()
    cursor.next()
    assert repr(cursor) == f'SortedKeyListCursor(after={records[0]!r})'


def test_normal_iterators_unchanged():
    skl, records = build_skl()
    assert list(skl) == records
    assert list(reversed(skl)) == records[::-1]
    assert list(skl.irange_key(1, 1)) == records[2:12]
