"""Check the archived US minigun thermal traces.

The traces were produced with the temporary RECOMP_TS2_MINIGUN_TRACE probe.
They remain useful because they contain the accepted-shot heat before and
after 000B35C0, the pose heat before and after 000B3E10, logical tick counts,
and the minigun mode.
"""

from __future__ import annotations

import argparse
import re
import struct
from dataclasses import dataclass
from pathlib import Path


SHOT_RE = re.compile(
    r"^\[TS2-MINI-SHOT\] frame (\d+) .*? step (\d+)/([\d.]+) "
    r".*? mode (\d+) state (\d+) held4c (\d+) pulse (\d+) "
    r"heat ([0-9a-f]+) [^ ]+ -> ([0-9a-f]+) [^ ]+ "
    r"rate ([0-9a-f]+) [^ ]+ -> [0-9a-f]+ [^ ]+ "
    r"counter (\d+) -> (\d+)"
)
POSE_RE = re.compile(
    r"^\[TS2-MINI-POSE\] frame (\d+) .*? step (\d+)/([\d.]+) "
    r"kind (\w+) .*? mode (\d+) state (\d+) held4c (\d+) pulse (\d+) "
    r"heat ([0-9a-f]+) [^ ]+ -> ([0-9a-f]+) [^ ]+ "
    r"rate ([0-9a-f]+) [^ ]+ -> [0-9a-f]+ [^ ]+ "
    r"counter (\d+) -> (\d+)"
)


def as_float(bits: str) -> float:
    return struct.unpack(">f", bytes.fromhex(bits))[0]


@dataclass(frozen=True)
class Pose:
    frame: int
    ticks: int
    kind: str
    mode: int
    held: int
    heat: float
    heat_after: float
    counter: int
    counter_after: int


@dataclass(frozen=True)
class Shot:
    frame: int
    ticks: int
    mode: int
    heat: float
    heat_after: float
    rate: float
    counter: int
    counter_after: int


def read_trace(path: Path) -> tuple[list[Pose], list[Shot]]:
    poses: list[Pose] = []
    shots: list[Shot] = []
    for line in path.read_text(errors="replace").splitlines():
        match = POSE_RE.match(line)
        if match:
            groups = match.groups()
            poses.append(
                Pose(
                    frame=int(groups[0]),
                    ticks=int(groups[1]),
                    kind=groups[3],
                    mode=int(groups[4]),
                    held=int(groups[6]),
                    heat=as_float(groups[8]),
                    heat_after=as_float(groups[9]),
                    counter=int(groups[11]),
                    counter_after=int(groups[12]),
                )
            )
            continue
        match = SHOT_RE.match(line)
        if match:
            groups = match.groups()
            shots.append(
                Shot(
                    frame=int(groups[0]),
                    ticks=int(groups[1]),
                    mode=int(groups[3]),
                    heat=as_float(groups[7]),
                    heat_after=as_float(groups[8]),
                    rate=as_float(groups[9]),
                    counter=int(groups[10]),
                    counter_after=int(groups[11]),
                )
            )
    return poses, shots


def accepted(shots: list[Shot]) -> list[Shot]:
    return [shot for shot in shots if shot.counter_after > shot.counter]


def first_heat_denial(shots: list[Shot]) -> Shot | None:
    return next(
        (
            shot
            for shot in shots
            if shot.rate >= 16.0
            and shot.heat > 0.9
            and shot.counter_after == shot.counter
        ),
        None,
    )


def milestones(shots: list[Shot]) -> dict[int, tuple[float, float]]:
    return {
        shot.counter_after: (shot.heat, shot.heat_after)
        for shot in accepted(shots)
    }


def first_61_logical_ticks(poses: list[Pose], shots: list[Shot]) -> dict[int, int]:
    ticks = 0
    started = False
    result: dict[int, int] = {}
    events = sorted(
        [(pose.frame, 0, pose) for pose in poses]
        + [(shot.frame, 1, shot) for shot in shots]
    )
    for _, kind, event in events:
        if not started:
            if kind == 0:
                if not event.held:
                    continue
                started = True
            else:
                continue
        if kind == 0:
            ticks += event.ticks
        elif event.counter_after > event.counter and event.counter_after <= 61:
            result[event.counter_after] = ticks
    return result


def check_close(actual: float, expected: float, label: str) -> None:
    if abs(actual - expected) > 1e-6:
        raise AssertionError(f"{label}: {actual:.9f} != {expected:.9f}")


def main() -> int:
    parser = argparse.ArgumentParser()
    root = Path(__file__).resolve().parents[2] / "build/engine-audit/minigun-investigation"
    parser.add_argument("--reference", type=Path, default=root / "baseline-60-trace.log")
    parser.add_argument("--capped", type=Path, default=root / "fix1-60-trace.log")
    parser.add_argument("--uncapped", type=Path, default=root / "fix1-uncapped-trace.log")
    parser.add_argument(
        "--secondary", type=Path, default=root / "fix2-uncapped-secondary-trace.log"
    )
    args = parser.parse_args()

    reference_poses, reference_shots = read_trace(args.reference)
    capped_poses, capped_shots = read_trace(args.capped)
    uncapped_poses, uncapped_shots = read_trace(args.uncapped)
    _, secondary_shots = read_trace(args.secondary)

    reference_milestones = milestones(reference_shots)
    capped_milestones = milestones(capped_shots)
    uncapped_milestones = milestones(uncapped_shots)
    rounds = (1, 20, 40, 60, 61, 80, 90, 97, 100)
    for round_number in rounds:
        expected = reference_milestones[round_number]
        for label, actual in (
            ("capped", capped_milestones[round_number]),
            ("uncapped", uncapped_milestones[round_number]),
        ):
            check_close(actual[0], expected[0], f"{label} round {round_number} heat")
            check_close(actual[1], expected[1], f"{label} round {round_number} shot heat")

    for label, shots in (("capped", capped_shots), ("uncapped", uncapped_shots)):
        denial = first_heat_denial(shots)
        assert denial and denial.counter == 97, f"{label}: first heat denial is not round 97"

    reference_ticks = first_61_logical_ticks(reference_poses, reference_shots)
    uncapped_ticks = first_61_logical_ticks(uncapped_poses, uncapped_shots)
    for round_number in reference_ticks:
        assert uncapped_ticks[round_number] - reference_ticks[round_number] == 1, (
            f"round {round_number}: logical firing deadline differs"
        )

    for pose in uncapped_poses:
        if pose.kind == "synthetic":
            assert pose.heat == pose.heat_after, "a zero-tick render changed heat"

    cooling_error = 0.0
    for pose in uncapped_poses:
        if pose.held or pose.counter != pose.counter_after or pose.kind == "synthetic":
            continue
        d = pose.ticks / 60.0
        expected = pose.heat - 0.12 * d
        expected = max(0.0, expected - (1.05 - expected) * 0.15 * d)
        cooling_error = max(cooling_error, abs(pose.heat_after - expected))
    assert cooling_error <= 5e-7, f"cooling mismatch: {cooling_error}"

    secondary_accepted = [shot for shot in accepted(secondary_shots) if shot.mode == 1]
    assert secondary_accepted, "uncapped secondary pre-spin never entered mode 1"

    print(f"reference / capped / uncapped heat match through round {rounds[-1]}")
    print("first heat-denied attempt: round 97 at both caps")
    print("uncapped accepted-shot deadlines match the 60 Hz reference")
    print("zero-tick renders preserve heat; cooling error <= 5e-7")
    print(f"uncapped secondary mode accepted {len(secondary_accepted)} rounds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
