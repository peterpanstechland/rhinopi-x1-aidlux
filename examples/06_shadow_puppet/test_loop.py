#!/usr/bin/env python3
"""Flow tests for DeskGame. Run: python3 test_loop.py"""

from pathlib import Path

from gestures import Motion
from loop import ALERT, AWAY, CLEAR, MONITOR, PLAY, READY, ROUND, SUMMARY, DeskGame

STILL = Motion()


def _tick(g, m, n, dt=0.4, seen=True, posture=None, chal=0.0):
    for _ in range(n):
        g.step(m, dt, seen, posture, chal)


def _clear_current(g):
    """Report the challenge as finished, like a scene would."""
    for _ in range(40):
        g.step(STILL, 0.2, True, None, 1.0)
        if g.sub != PLAY:
            return True
    return False


def test_alert_after_interval(tmp):
    g = DeskGame(interval=20, path=tmp / "a.json")
    _tick(g, STILL, 60, dt=0.5)
    assert g.present
    assert g.phase == ALERT, g.snapshot()
    assert g.hp == 0


def test_round_runs_every_act(tmp):
    g = DeskGame(interval=8, round_len=4, path=tmp / "b.json")
    _tick(g, STILL, 30, dt=0.5)
    assert g.phase == ALERT
    g.step(Motion(energy=0.6, wings=0.9), 0.3, True)
    assert g.phase == ROUND and g.sub == READY, g.snapshot()
    seen = []
    for _ in range(4):
        _tick(g, STILL, 6, dt=0.4)  # ready count-in
        assert g.sub == PLAY, g.snapshot()
        seen.append(g.act["id"])
        assert _clear_current(g)
        assert g.sub == CLEAR
        _tick(g, STILL, 6, dt=0.4)  # clear card
    assert len(seen) == 4 and len(set(seen)) == 4, seen
    assert g.phase == SUMMARY, g.snapshot()
    assert g.sit_s == 0
    assert g.rounds == 1
    assert g.streak == 1
    assert g.round_score > 0
    assert all(r.cleared for r in g.results)


def test_summary_returns_to_monitor(tmp):
    g = DeskGame(interval=1200, round_len=2, path=tmp / "c.json")
    _tick(g, STILL, 4, dt=0.5)
    g.step(Motion(energy=0.6, hands_up=0.9), 0.6, True)
    assert g.phase == ROUND
    for _ in range(2):
        _tick(g, STILL, 6, dt=0.4)
        _clear_current(g)
        _tick(g, STILL, 6, dt=0.4)
    assert g.phase == SUMMARY
    _tick(g, STILL, 40, dt=0.5)
    assert g.phase == MONITOR, g.snapshot()


def test_round_budget_is_two_minutes(tmp):
    g = DeskGame(interval=6, round_len=4, path=tmp / "d.json")
    _tick(g, STILL, 24, dt=0.5)
    g.step(Motion(energy=0.6, hands_up=0.9), 0.3, True)
    assert g.phase == ROUND
    _tick(g, STILL, 8, dt=0.5)
    assert g.sub == PLAY
    for _ in range(400):  # never finish any challenge
        g.step(STILL, 1.0, True)
        if g.phase != ROUND:
            break
    assert g.phase == SUMMARY, g.snapshot()
    assert 118 <= g.round_time <= 126, g.round_time
    assert len(g.results) == 4
    assert not any(r.cleared for r in g.results)
    assert g.streak == 0


def test_away_pauses_then_resets(tmp):
    g = DeskGame(interval=600, path=tmp / "e.json")
    _tick(g, STILL, 20, dt=0.5)
    assert g.sit_s > 5
    # typing with the head down loses pose for a while; still "at the desk"
    _tick(g, STILL, 60, dt=0.5, seen=False)
    assert g.present and g.phase == MONITOR, g.snapshot()
    _tick(g, STILL, 40, dt=0.5, seen=False)
    assert g.phase == AWAY, g.snapshot()
    frozen = g.sit_s
    _tick(g, STILL, 100, dt=0.5, seen=False)  # 50s away, under the walk window
    assert abs(g.sit_s - frozen) < 0.6, (frozen, g.sit_s)
    _tick(g, STILL, 800, dt=0.5, seen=False)  # past 5 min away
    assert g.sit_s == 0, g.snapshot()
    assert g.streak == 0


def test_hands_up_starts_round_early(tmp):
    g = DeskGame(interval=1200, path=tmp / "f.json")
    _tick(g, STILL, 4, dt=0.5)
    g.step(Motion(energy=0.5, hands_up=0.8), 0.6, True)
    assert g.phase == ROUND, g.snapshot()


def test_posture_average_tracked(tmp):
    g = DeskGame(interval=1200, path=tmp / "g.json")
    _tick(g, STILL, 10, dt=0.4, posture=70.0)
    assert 69 < g.posture_mean < 71, g.posture_mean
    assert g.posture_grade == "B"


def main():
    tmp = Path(__file__).resolve().parent / ".tmp_test"
    tmp.mkdir(exist_ok=True)
    for old in tmp.glob("*.json"):
        old.unlink()
    for old in tmp.glob("*.tmp"):
        old.unlink()
    for fn in (
        test_alert_after_interval,
        test_round_runs_every_act,
        test_summary_returns_to_monitor,
        test_round_budget_is_two_minutes,
        test_away_pauses_then_resets,
        test_hands_up_starts_round_early,
        test_posture_average_tracked,
    ):
        fn(tmp)
        print("ok", fn.__name__)
    print("loop ok")


if __name__ == "__main__":
    main()
