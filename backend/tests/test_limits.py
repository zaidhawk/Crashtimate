import pytest
from starlette.requests import Request

from app.limits import RateLimiter, client_ip


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def request(forwarded: str | None = None, client: tuple[str, int] | None = ("10.0.0.1", 1234)):
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "headers": headers, "client": client})


def test_allows_up_to_the_limit_then_reports_the_wait():
    clock = Clock()
    limiter = RateLimiter(2, 60, clock)

    assert limiter.retry_after("a") is None
    clock.now += 10
    assert limiter.retry_after("a") is None
    clock.now += 10
    assert limiter.retry_after("a") == pytest.approx(40)


def test_window_slides():
    clock = Clock()
    limiter = RateLimiter(2, 60, clock)
    limiter.retry_after("a")
    clock.now += 30
    limiter.retry_after("a")

    clock.now += 31  # the first request has aged out, the second hasn't
    assert limiter.retry_after("a") is None
    assert limiter.retry_after("a") is not None


def test_blocked_requests_do_not_extend_the_wait():
    clock = Clock()
    limiter = RateLimiter(1, 60, clock)
    limiter.retry_after("a")

    for _ in range(5):
        clock.now += 10
        assert limiter.retry_after("a") is not None

    clock.now += 10
    assert limiter.retry_after("a") is None


def test_keys_are_independent():
    limiter = RateLimiter(1, 60, Clock())

    assert limiter.retry_after("a") is None
    assert limiter.retry_after("b") is None


def test_zero_means_unlimited():
    limiter = RateLimiter(0, 60, Clock())

    assert all(limiter.retry_after("a") is None for _ in range(100))


def test_expired_visitors_are_forgotten(monkeypatch):
    monkeypatch.setattr("app.limits._SWEEP_THRESHOLD", 3)
    clock = Clock()
    limiter = RateLimiter(5, 60, clock)
    for key in "abcd":
        limiter.retry_after(key)

    clock.now += 61
    limiter.retry_after("e")

    assert set(limiter._hits) == {"e"}


@pytest.mark.parametrize(
    ("forwarded", "hops", "expected"),
    [
        (None, 0, "10.0.0.1"),
        ("203.0.113.9", 0, "10.0.0.1"),  # header ignored unless we're behind a proxy
        ("203.0.113.9", 1, "203.0.113.9"),
        ("6.6.6.6, 203.0.113.9", 1, "203.0.113.9"),  # the visitor forged the first entry
        ("203.0.113.9, 172.16.0.1", 2, "203.0.113.9"),
        (None, 1, "10.0.0.1"),
        ("203.0.113.9", 2, "10.0.0.1"),
    ],
)
def test_client_ip(forwarded, hops, expected):
    assert client_ip(request(forwarded), hops) == expected


def test_client_ip_without_a_socket_address():
    assert client_ip(request(client=None), 0) == "unknown"
