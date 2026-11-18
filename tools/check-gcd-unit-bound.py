#!/usr/bin/env python3
# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only
"""Independent whole-interval obligations for the optional fixed-unit upper.

Checks the returned bound, not the implementation's chosen denominator:
any strict refinement must cover Q/17 and exclude every higher section n<=16.
Together with the real-GCD theorem this covers every real value in each tested
interval, rather than only sampling floating-point inputs. Unsupported/invalid
caller cases test bitwise fallback only; they are not certified caller bounds.
"""

import argparse
import hashlib
import json
import math
import random
import struct
import subprocess
from fractions import Fraction as F
from pathlib import Path


def bits(value):
    return struct.unpack(">Q", struct.pack(">d", value))[0]


def floating(value):
    return struct.unpack(">d", struct.pack(">Q", value))[0]


def classic(lo, hi, unit):
    q = abs(unit)
    return min(q, max(abs(lo), abs(hi))) if lo > 0 or hi < 0 else q


def fixtures():
    rows = []

    def add(lo, hi, unit, upper=None):
        if upper is None:
            upper = classic(lo, hi, unit)
        rows.append(tuple(map(bits, (lo, hi, unit, upper))))

    for unit in (
        1.0,
        -1.0,
        4.0,
        -4.0,
        0.125,
        2.0**-1022,
        math.ulp(0.0),
        float.fromhex("0x1.fffffffffffffp+1023"),
    ):
        for denominator in range(1, 21):
            for k in (-17, -1, 0, 1, 17):
                try:
                    value = float(F(abs(unit)) * k / denominator)
                except OverflowError:
                    continue
                lower, upper = (
                    math.nextafter(value, -math.inf),
                    math.nextafter(value, math.inf),
                )
                if not math.isfinite(lower):
                    lower = value
                if not math.isfinite(upper):
                    upper = value
                add(lower, upper, unit)
                add(value, value, unit)
                if value < upper:
                    add(upper, upper, unit)
    rng = random.Random(56178)
    for _ in range(600):
        values = []
        while len(values) < 3:
            value = floating(rng.getrandbits(64))
            if math.isfinite(value):
                values.append(value)
        lo, hi = sorted(values[:2])
        unit = values[2]
        if unit == 0:
            unit = 1.0
        add(lo, hi, unit)
        if len(rows) % 5 == 0:
            add(lo, hi, unit, math.inf)
    nan = floating(0x7FF8000000000042)
    for lo, hi, unit in (
        (2, 1, 1),
        (math.nan, 1, 1),
        (-math.inf, math.inf, 1),
        (1, math.inf, 1),
        (1, 2, 0),
        (1, 2, -0.0),
        (1, 2, math.inf),
        (1, 2, nan),
    ):
        for upper in (0.0, -0.0, -2.0, -math.inf, math.inf, nan, 7.0):
            add(lo, hi, unit, upper)
    for upper in (-0.0, 0.0, -2.0, nan):
        add(1, 2, 1, upper)
    return list(dict.fromkeys(rows))


def check(row, output):
    lo, hi, unit, old = map(floating, row)
    if (
        math.isnan(old)
        or old <= 0
        or not all(map(math.isfinite, (lo, hi, unit)))
        or lo > hi
        or unit == 0
    ):
        assert output == row[3], ("fallback bits", row, output)
        return "fallback"
    value = floating(output)
    assert not math.isnan(value) and 0 <= value <= old, ("nonwidening", row, output)
    if output == row[3]:
        return "unchanged"
    q = abs(F(unit))
    bound = F(value)
    assert bound >= q / 17, ("tail", row, output)
    for denominator in range(1, 17):
        if q / denominator <= bound:
            continue
        # Exact integer exclusion using signed integer division, independent
        # of GMP's rational/ceil/floor functions used by the native owner.
        lower = F(lo) * denominator / q
        upper = F(hi) * denominator / q
        first = -((-lower.numerator) // lower.denominator)
        last = upper.numerator // upper.denominator
        assert first > last, ("excluded higher GCD section", row, output, denominator)
    return "refined"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--probe", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    rows = fixtures()
    text = "".join(" ".join(f"{v:016x}" for v in row) + "\n" for row in rows)
    root = Path(__file__).resolve().parents[1]
    record = {
        "passed": False,
        "status": "started",
        "probe": str(a.probe),
        "cases": len(rows),
        "input_bits_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "scope": "Whole-interval returned-bound obligations per fixture plus bitwise fallback. No consumer rendering or universal implementation proof.",
        "inputs": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in (
                "src/common_factor.c",
                "include/graphing/common_factor.h",
                "tests/test_common_factor.c",
                "tools/check-gcd-unit-bound.py",
            )
        },
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(record, indent=2) + "\n")
    try:
        record["probe_sha256"] = hashlib.sha256(a.probe.read_bytes()).hexdigest()
        result = subprocess.run(
            [str(a.probe.resolve()), "--unit-bound-probe"],
            input=text,
            text=True,
            capture_output=True,
            check=True,
            timeout=60,
        )
        assert not result.stderr, ("probe diagnostics", result.stderr)
        outputs = [int(line, 16) for line in result.stdout.splitlines()]
        assert len(outputs) == len(rows)
        counts = {"fallback": 0, "unchanged": 0, "refined": 0}
        for row, value in zip(rows, outputs):
            counts[check(row, value)] += 1
        record.update(
            passed=True,
            status="completed",
            counts=counts,
            output_bits_sha256=hashlib.sha256(result.stdout.encode()).hexdigest(),
        )
    except Exception as error:
        record.update(status="failed", error=repr(error))
        a.output.write_text(json.dumps(record, indent=2) + "\n")
        raise
    a.output.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"passed": True, "cases": len(rows), "counts": counts}))


if __name__ == "__main__":
    main()
