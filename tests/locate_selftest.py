#!/usr/bin/env python3
"""Falsify lib/locate.sh: prove each diagnosis names its own cause.

The locator refuses on four distinct grounds and prints a fix for each. Three
of them used to share one message — "point at a Movian checkout, not an
unrelated directory" — which is right for an unrelated directory and wrong for
a real clone sitting on a revision that predates `support/devtools/mdev`. That
is the case actually met (movian-plugin-sdk#32): the cause is the revision, and
the advice sent the reader to check the path.

So this asserts the discriminating direction. Each case is built on disk, run
through the locator, and required to produce ITS message and not another's — a
message that fits every failure is the bug this suite exists to prevent.

    python3 tests/locate_selftest.py

Exit: 0 every case diagnosed distinctly, 1 otherwise.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOCATE = HERE.parent / "lib" / "locate.sh"


def locate(root: str | None, config: str | None = None) -> tuple[int, str]:
    """Run `movian_sdk_locate` and return its exit code and stderr.

    The code is read from the process, never through a pipeline: `cmd | head`
    reports head's status, and a check measured that way is not a check.
    """
    env = dict(os.environ)
    env.pop("MOVIAN_CORE", None)
    if root is not None:
        env["MOVIAN_CORE"] = root
    env["MOVIAN_SDK_CONFIG"] = config if config else "/nonexistent/config.json"
    done = subprocess.run(
        ["bash", "-c", '. "$1"; movian_sdk_locate', "_", str(LOCATE)],
        capture_output=True, text=True, env=env,
    )
    return done.returncode, done.stderr


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True,
                   capture_output=True,
                   env={**os.environ,
                        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


def build_cases(tmp: Path) -> list[tuple[str, str, list[str], list[str]]]:
    """(label, root, must appear in stderr, must NOT appear)."""
    unrelated = tmp / "unrelated"
    unrelated.mkdir()

    checkout = tmp / "checkout"
    (checkout / "support" / "devtools").mkdir(parents=True)
    (checkout / "src").mkdir()
    git(checkout, "init", "-q", ".")
    git(checkout, "commit", "-q", "--allow-empty", "-m", "old revision")
    git(checkout, "checkout", "-q", "-b", "wsd-test")

    complete = tmp / "complete"
    (complete / "support" / "devtools").mkdir(parents=True)
    (complete / "support" / "devtools" / "mdev").write_text("#!/bin/sh\n")
    (complete / "build.debug").mkdir()

    good = tmp / "good"
    (good / "support" / "devtools").mkdir(parents=True)
    (good / "support" / "devtools" / "mdev").write_text("#!/bin/sh\n")
    (good / "build.debug").mkdir()
    binary = good / "build.debug" / "movian"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o755)

    return [
        ("a path that is not a directory",
         str(tmp / "does-not-exist"),
         ["is not a directory"],
         ["unrelated directory", "IS a git checkout", "inside the checkout"]),
        ("an unrelated directory",
         str(unrelated),
         ["has no support/devtools/mdev", "unrelated directory"],
         ["IS a git checkout", "inside the checkout"]),
        ("a checkout on a revision without mdev",
         str(checkout),
         ["has no support/devtools/mdev", "IS a git checkout", "wsd-test",
          "update this checkout"],
         ["unrelated directory", "inside the checkout"]),
        ("a path inside a checkout rather than its root",
         str(checkout / "src"),
         ["inside the checkout at", str(checkout)],
         ["unrelated directory", "IS a git checkout"]),
        ("a checkout with mdev but no built binary",
         str(complete),
         ["no executable build.debug/movian", "configure-linux-debug.sh"],
         ["unrelated directory", "IS a git checkout"]),
    ]


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)

        for label, root, expected, forbidden in build_cases(tmp):
            code, err = locate(root)
            if code == 0:
                print(f"  FAIL {label}: locator accepted it")
                failures += 1
                continue
            missing = [text for text in expected if text not in err]
            leaked = [text for text in forbidden if text in err]
            if missing or leaked:
                print(f"  FAIL {label}")
                if missing:
                    print(f"       missing from the message: {missing}")
                if leaked:
                    print(f"       another case's message leaked in: {leaked}")
                print("       " + "\n       ".join(err.strip().splitlines()))
                failures += 1
            else:
                print(f"  ok   {label}")

        # The happy path, so a locator that refuses everything cannot pass
        # this suite by refusing distinctly.
        good = tmp / "good"
        code, err = locate(str(good))
        if code != 0:
            print(f"  FAIL a complete core: refused with {err.strip()!r}")
            failures += 1
        else:
            print("  ok   a complete core resolves")

        # No core named at all is its own message, not a crash.
        code, err = locate(None)
        if code == 0 or "no Movian core configured" not in err:
            print(f"  FAIL nothing configured: {code} {err.strip()!r}")
            failures += 1
        else:
            print("  ok   nothing configured -> says so")

    if failures:
        print(f"selftest: FAILED ({failures} case(s) not diagnosed distinctly)")
        return 1
    print("selftest: OK -- 7 cases, each naming its own cause")
    return 0


if __name__ == "__main__":
    sys.exit(main())
