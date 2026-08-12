#!/usr/bin/env python3
"""Falsify typefloor.py: prove each planted defect is load-bearing.

A floor that cannot fail is the defect it was built to prevent, so this asserts
the opposite direction — take an artifact that passes, reintroduce one historical
hole at a time, and require the floor to notice, naming the right probe line.

The mutations are not invented. Each is a bug that actually shipped or was
actually caught:

  Page.searchable declared     -- the invented property from movian#183
  Item.onSelect declared       -- the phantom four sites assigned (movian#177)
  appendItem returns any       -- exactly what movian#177 changed
  appendItm declared           -- the typo the corpus run found (movian#175)

Run it against any artifact that currently passes:

    python3 tests/typefloor_selftest.py --dts "$(mdev core)/generated/movian-api.d.ts"

Exit: 0 all mutations detected, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FLOOR = HERE.parent / "lib" / "typefloor.py"


def insert_member(text: str, interface: str, member: str) -> str:
    """Add a member to `interface <name> {` in a movian/page declaration."""
    marker = f"interface {interface} {{"
    index = text.index(marker) + len(marker)
    return text[:index] + f"\n    {member}" + text[index:]


# (label, mutate, probe line that must stop reporting)
MUTATIONS = [
    ("Page.searchable declared",
     lambda t: insert_member(t, "Page", "searchable: any;"), 5),
    ("Item.onSelect declared",
     lambda t: insert_member(t, "Item", "onSelect: any;"), 7),
    ("appendItem returns any",
     lambda t: re.sub(r"(appendItem\([^)]*\)): Item;", r"\1: any;", t), 7),
    ("appendItm declared",
     lambda t: insert_member(
         t, "Page", "appendItm(url?: any, type?: any, metadata?: any): Item;"), 4),
]


def floor(dts: Path) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(FLOOR), "--dts", str(dts)],
        capture_output=True, text=True)
    return result.returncode, result.stdout + result.stderr


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="typefloor_selftest")
    parser.add_argument("--dts", required=True, type=Path,
                        help="an artifact that currently passes the floor")
    args = parser.parse_args(argv)

    if not args.dts.is_file():
        print(f"selftest: {args.dts} does not exist.")
        return 1
    baseline = args.dts.read_text()

    code, output = floor(args.dts)
    if code != 0:
        print("selftest: the baseline artifact does not pass the floor, so no")
        print("  mutation of it would prove anything. Point --dts at a current one.")
        print(output.rstrip())
        return 1
    print(f"selftest: baseline OK -- {args.dts}")

    failures = 0
    with tempfile.TemporaryDirectory(prefix="typefloor-selftest-") as tmp:
        mutant = Path(tmp) / "movian-api.d.ts"

        for label, mutate, line in MUTATIONS:
            try:
                text = mutate(baseline)
            except ValueError:
                print(f"  FAIL {label}: the artifact has no site to mutate — the")
                print("       mutation is stale, not the floor")
                failures += 1
                continue
            if text == baseline:
                print(f"  FAIL {label}: mutation changed nothing (pattern no longer"
                      " matches the emitted shape)")
                failures += 1
                continue

            mutant.write_text(text)
            code, output = floor(mutant)
            if code == 0:
                print(f"  FAIL {label}: floor still passes — this hole could ship")
                failures += 1
            elif f"probe.ts:{line} expected" not in output:
                print(f"  FAIL {label}: floor failed, but not at probe.ts:{line}")
                print("       " + "\n       ".join(output.splitlines()[:6]))
                failures += 1
            else:
                print(f"  ok   {label} -> probe.ts:{line} stops reporting")

        # Nothing at all must not read as nothing wrong.
        mutant.write_text("")
        code, _ = floor(mutant)
        if code == 0:
            print("  FAIL empty artifact: floor passes on a file with no declarations")
            failures += 1
        else:
            print("  ok   empty artifact -> floor fails")

    if failures:
        print(f"selftest: FAILED ({failures} mutation(s) undetected)")
        return 1
    print(f"selftest: OK -- {len(MUTATIONS) + 1} mutations all detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
