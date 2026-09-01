"""Offline tests for the decision logic, mapped to the report's E1-E10 table.
Run: python tests/test_logic.py   (no broker or network needed)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import logic  # noqa: E402


def env(**kw) -> dict:
    base = dict(roomTemp=23.0, humidity=50.0, bodyTemp=36.6,
                occupancy=True, acMode="auto", warning=False, wifiOk=True)
    base.update(kw)
    return base


CASES = [
    # (label, telemetry, expected comfort state)
    ("E1 normal comfort",      env(roomTemp=23.0),                     "Comfortable"),
    ("E2 warm room",           env(roomTemp=25.5),                     "Warm"),
    ("E3 too warm",            env(roomTemp=28.0),                     "Too Warm"),
    ("E4 high humidity",       env(roomTemp=24.5, humidity=72),        "Warm"),
    ("E5 unoccupied",          env(roomTemp=28.0, occupancy=False),    "Standby"),
    ("E6 sensor fault",        env(warning=True),                      "Invalid Reading"),
    ("E8 manual override",     env(acMode="manual"),                   "Manual Override"),
    ("E10 abnormal body temp", env(bodyTemp=38.4),                     "Alert"),
    ("humid+hot -> too warm",  env(roomTemp=26.2, humidity=66),        "Too Warm"),
]

AC_CASES = [
    # (comfort state, current ac_on, expected desired ac_on)
    ("Too Warm", False, True),
    ("Warm", False, True),
    ("Comfortable", True, False),
    ("Standby", True, False),
    ("Invalid Reading", True, True),   # hold state — automation paused
    ("Alert", False, False),           # hold state
]


def main() -> int:
    failures = 0

    for label, t, expected in CASES:
        got = logic.classify(t).state
        ok = got == expected
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {label:26} -> {got}"
              + ("" if ok else f"  (expected {expected})"))

    for state, cur, expected in AC_CASES:
        got = logic.decide_ac(state, cur)
        ok = got == expected
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  decide_ac({state},{cur}) -> {got}"
              + ("" if ok else f"  (expected {expected})"))

    print("-" * 48)
    print("ALL PASSED" if failures == 0 else f"{failures} FAILURE(S)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
