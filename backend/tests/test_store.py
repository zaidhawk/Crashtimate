from datetime import UTC, datetime, timedelta

import pytest

from app.store import Store, StoredPhoto

SHA = "a" * 64
OTHER_SHA = "b" * 64


class Clock:
    def __init__(self):
        self.now = datetime(2026, 3, 1, 12, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta):
        self.now += timedelta(**delta)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store(clock) -> Store:
    return Store(clock=clock)


def test_photo_round_trip(store):
    store.save_photo(SHA, b"jpeg bytes", 640, 480)

    assert store.get_photo(SHA) == StoredPhoto(b"jpeg bytes", 640, 480)
    assert store.get_photo(OTHER_SHA) is None


def test_analysis_is_cached_per_detector(store):
    store.save_analysis(SHA, "claude:opus:medium", '{"a": 1}', "claude-opus-5-5")

    hit = store.get_analysis(SHA, "claude:opus:medium")
    assert (hit.report, hit.model) == ('{"a": 1}', "claude-opus-5-5")
    assert store.get_analysis(SHA, "claude:opus:high") is None
    assert store.get_analysis(OTHER_SHA, "claude:opus:medium") is None


def test_latest_analysis_ignores_the_detector(store, clock):
    store.save_analysis(SHA, "mock", "old", None)
    clock.advance(minutes=1)
    store.save_analysis(SHA, "claude", "new", "claude-opus-5-5")

    assert store.latest_analysis(SHA).report == "new"
    assert store.latest_analysis(OTHER_SHA) is None


def test_share_round_trip_with_photos_in_order(store, clock):
    store.save_photo(SHA, b"first", 10, 20)
    store.save_photo(OTHER_SHA, b"second", 30, 40)

    share = store.create_share('{"total": 5}', [OTHER_SHA, SHA])

    loaded = store.get_share(share.id)
    assert loaded.payload == '{"total": 5}'
    assert loaded.created_at == clock.now
    assert store.get_share_photo(share.id, 0).data == b"second"
    assert store.get_share_photo(share.id, 1).data == b"first"
    assert store.get_share_photo(share.id, 2) is None
    assert store.get_share("nope") is None


def test_share_ids_are_unique_and_short(store):
    ids = {store.create_share("{}", []).id for _ in range(50)}

    assert len(ids) == 50
    assert all(len(share_id) == 12 for share_id in ids)


def test_daily_limit_stops_at_the_limit_and_resets_the_next_day(store, clock):
    assert [store.reserve_analysis(2) for _ in range(3)] == [True, True, False]
    assert store.analyses_today() == 2

    clock.advance(days=1)

    assert store.reserve_analysis(2)
    assert store.analyses_today() == 1


def test_no_daily_limit_when_zero(store):
    assert all(store.reserve_analysis(0) for _ in range(5))


def test_purge_deletes_old_rows_but_keeps_photos_of_live_shares(store, clock):
    store.save_photo(SHA, b"shared", 1, 1)
    store.save_photo(OTHER_SHA, b"orphan", 1, 1)
    store.save_analysis(SHA, "mock", "{}", None)
    old_share = store.create_share("{}", [])
    clock.advance(days=20)
    live_share = store.create_share("{}", [SHA])
    clock.advance(days=20)

    store.purge(timedelta(days=30))

    assert store.get_share(old_share.id) is None
    assert store.get_share(live_share.id) is not None
    assert store.get_analysis(SHA, "mock") is None
    assert store.get_photo(SHA) is not None
    assert store.get_photo(OTHER_SHA) is None

    clock.advance(days=20)
    store.purge(timedelta(days=30))

    assert store.get_share(live_share.id) is None
    assert store.get_photo(SHA) is None


def test_data_survives_reopening_the_file(tmp_path):
    path = str(tmp_path / "test.db")
    first = Store(path)
    first.save_photo(SHA, b"data", 1, 1)
    first.close()

    second = Store(path)
    assert second.get_photo(SHA).data == b"data"
    second.close()
