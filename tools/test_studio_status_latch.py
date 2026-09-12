#!/usr/bin/env python3
"""Prove a workspace change cannot leave Studio permanently unable to poll.

Studio polls the bridge for status under a single-flight latch: ``_tick_once``
sets ``_status_pending`` and only clears it when a result comes back.  The latch
is what stops a slow reply from queueing dozens of duplicate polls.

The bug this guards against: ``_tick_once`` read ``supervisor.client``, found it
alive, set the latch, then called ``_request`` - which read ``supervisor.client``
*again*.  A workspace change tears the bridge down on its own thread, so the
client could become ``None`` between those two reads.  ``_request`` then returned
early without submitting anything, no result ever arrived, and the latch stayed
set for the rest of the session.  Studio never polled again, ``self._lab`` was
never refreshed, and live feedback died until Studio was closed and reopened -
exactly what switching aircraft produced.

Offline: no hardware, no simulator, no bridge, no Tk window.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import queue
import re
import sys
import types


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from muslimsim.gui.studio import MuslimSimStudio


class _Footer:
    def __init__(self):
        self.text = ""

    def set(self, value):
        self.text = str(value)


class _Supervisor:
    """A supervisor whose client can disappear exactly as a real one does."""

    def __init__(self, client):
        self.client = client


class _Client:
    def __init__(self):
        self.calls = []

    def request(self, command, **fields):
        self.calls.append(command)
        return {"ok": True, "cmd": command}


class _Harness:
    """The smallest object the real ``_request`` needs."""

    def __init__(self, client):
        self.supervisor = _Supervisor(client)
        self.footer = _Footer()
        self._results = queue.Queue()
        self._workers = ThreadPoolExecutor(max_workers=1)
        for name in ("_request", "_collect_future"):
            setattr(self, name, types.MethodType(getattr(MuslimSimStudio, name), self))


def check_request_reports_a_dropped_client():
    """No client means nothing was sent, and the caller must be told."""

    harness = _Harness(None)
    try:
        sent = harness._request("status", done=lambda _v: None, health_check=True)
    finally:
        harness._workers.shutdown(wait=False)
    assert sent is False, (
        "_request returned %r with no bridge client. It must report that nothing "
        "was submitted, or a caller holding the single-flight latch never "
        "releases it and Studio stops polling for good." % (sent,)
    )
    print("  [ok] a dropped bridge client is reported to the caller")


def check_request_reports_a_closing_worker_pool():
    """Studio shutting down must not look like a successful submit either."""

    harness = _Harness(_Client())
    harness._workers.shutdown(wait=True)
    sent = harness._request("status", done=lambda _v: None, health_check=True)
    assert sent is False, (
        "_request returned %r after the worker pool closed; no result can arrive "
        "for that call." % (sent,)
    )
    print("  [ok] a closing worker pool is reported to the caller")


def check_a_real_submit_still_delivers():
    """The healthy path must be unchanged: submitted, and the result arrives."""

    client = _Client()
    harness = _Harness(client)
    try:
        sent = harness._request("status", done=lambda _v: None, health_check=True)
        assert sent is True, "_request returned %r on the healthy path" % (sent,)
        done, value, error, health = harness._results.get(timeout=5.0)
        assert error is None, "healthy request raised %r" % (error,)
        assert value == {"ok": True, "cmd": "status"}, value
        assert health is True, "health_check flag was lost"
        assert client.calls == ["status"], client.calls
    finally:
        harness._workers.shutdown(wait=False)
    print("  [ok] a healthy request is submitted and its result is delivered")


def check_tick_releases_the_latch():
    """``_tick_once`` must clear the latch when nothing was submitted."""

    source = (PROJECT / "muslimsim" / "gui" / "studio.py").read_text(encoding="utf-8")
    found = re.search(
        r"self\._status_pending = True\s*\n"
        r"\s*self\._next_status_poll = now \+ [0-9.]+\s*\n"
        r"\s*if not self\._request\(\s*\"status\".*?\n"
        r"(?:\s*#.*\n)*"
        r"\s*self\._status_pending = False",
        source,
    )
    assert found, (
        "The status poll in _tick_once no longer releases _status_pending when "
        "_request reports that nothing was submitted. Without that release the "
        "latch stays set after a workspace change and Studio never polls the "
        "bridge again, so live feedback stops until Studio is restarted."
    )
    print("  [ok] the status poll releases its latch when nothing was submitted")


def check_the_retry_floor_survives_a_no_submit():
    """A failed submit must not let the poll spin.

    ``_next_status_poll`` has to be pushed forward *before* ``_request`` is
    called, so the 0.10 s floor still applies on the path where nothing was
    submitted.  If the release were added without that ordering, a permanently
    absent bridge client would retry as fast as Tk ticks instead of ten times a
    second.
    """

    source = (PROJECT / "muslimsim" / "gui" / "studio.py").read_text(encoding="utf-8")
    block = re.search(
        r"self\._status_pending = True(?P<body>.*?)self\._status_pending = False",
        source,
        re.S,
    )
    assert block, "The status poll block could not be located."
    body = block.group("body")
    floor = body.find("self._next_status_poll = now +")
    request = body.find("self._request(")
    assert floor != -1, "The status poll no longer advances _next_status_poll."
    assert request != -1, "The status poll no longer calls _request."
    assert floor < request, (
        "_next_status_poll is advanced after _request instead of before it. On "
        "the no-submit path the latch is released immediately, so without the "
        "floor already applied Studio would retry every Tk tick rather than at "
        "the intended 10 Hz."
    )
    print("  [ok] the 0.10s retry floor is applied before the request is sent")


def check_only_one_status_request_can_be_in_flight():
    """The latch must still admit exactly one poll at a time."""

    source = (PROJECT / "muslimsim" / "gui" / "studio.py").read_text(encoding="utf-8")
    guard = re.search(
        r"if client is not None and not self\._status_pending and now >= self\._next_status_poll:",
        source,
    )
    assert guard, (
        "The status poll no longer requires `not self._status_pending`. Without "
        "that guard a slow bridge reply would queue one new request per Tk tick "
        "and pile up on the control channel."
    )
    print("  [ok] a new poll still requires the latch to be free")


def main():
    print("Studio status latch:")
    check_request_reports_a_dropped_client()
    check_request_reports_a_closing_worker_pool()
    check_a_real_submit_still_delivers()
    check_tick_releases_the_latch()
    check_the_retry_floor_survives_a_no_submit()
    check_only_one_status_request_can_be_in_flight()
    print("Studio status latch test passed.")


if __name__ == "__main__":
    main()
