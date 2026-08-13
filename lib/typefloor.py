#!/usr/bin/env python3
"""Does this .d.ts actually check a plugin, or does it only look like it?

The failure this exists for (movian#183): a plugin author points `tsc` at
`$(mdev core)/generated/movian-api.d.ts`, gets a clean pass, and the pass means
nothing -- because the core checkout predates the declarations that do the
checking. A stale artifact is indistinguishable from a current one at the point
of use: both produce green, and green is what the author is told to look for.

Three things that look like the fix are not:

* **Comparing `movianRevision` to the checkout's HEAD.** The artifact is
  generated *before* the commit that carries it exists, so the stamp trails HEAD
  in every correct tree -- movian6 at 977a5c5c1 ships an artifact stamped
  a4dae4ec6. That check false-fails a healthy checkout, and `lib/locate.sh` already
  refuses to build gates that "fire constantly and train agents to ignore it".
* **`gen.py --check` in the core.** It answers "is the artifact consistent with
  the source beside it", which a stale checkout satisfies -- measured green, exit
  0, on the very checkout that produced the vacuous pass.
* **Anything shipped inside the core.** A checkout old enough to have the problem
  is old enough to predate the checker. The check must live outside what it
  checks; that is why this file is in the SDK.

So the question is asked directly, in the author's own terms: compile code that
is wrong on purpose and confirm the artifact says so. An artifact that reports
nothing is not passing -- it is not looking.

Exit: 0 floor holds, 1 floor broken, 2 could not run (no tsc).
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Every marked line below is wrong. A usable artifact reports each one.
#
# Deliberately written through the door an author actually walks through -- a
# `Route` callback, whose parameter is typed only if the artifact carries the
# `interface Page` that #178 added. Annotating `function (page: Page)` by hand
# would prove the interface exists while proving nothing about whether ordinary
# plugin code reaches it.
PROBE = """\
import { Route } from 'movian/page';

new Route('typefloor:probe', function (page) {
  page.appendItm('u', 'video', {});
  page.searchable = true;
  var item = page.appendItem('u', 'video', {});
  item.onSelect = function () {};
});

Plugin.path;
console.log('typefloor');
setTimeout(function () {}, 1);
"""

# (line, accepted codes, what a missing diagnostic would mean)
EXPECTED = [
    (4, {"TS2551", "TS2339"},
     "a misspelled Page method is not caught -- no `interface Page`"),
    (5, {"TS2339"},
     "an invented Page property is not caught -- no `interface Page`"),
    (7, {"TS2339"},
     "an invented Item property is not caught -- `appendItem` returns `any`"),
]

DIAG_RE = re.compile(r"^(?P<file>[^(]+)\((?P<line>\d+),\d+\): error (?P<code>TS\d+):")


def find_tsc() -> list[str] | None:
    direct = shutil.which("tsc")
    if direct:
        return [direct]
    npx = shutil.which("npx")
    if npx:
        probe = subprocess.run([npx, "--no-install", "tsc", "--version"],
                               capture_output=True, text=True)
        if probe.returncode == 0:
            return [npx, "--no-install", "tsc"]
    return None


def run(dts: Path, verbose: bool) -> int:
    tsc = find_tsc()
    if tsc is None:
        print("typefloor: UNVERIFIED -- no `tsc` on PATH and no npx-resolvable one.")
        print(f"  the artifact at {dts} was NOT checked; it may be unusable.")
        print("  fix: npm i -g typescript   (or run this from a repo with it installed)")
        return 2

    version = subprocess.run(tsc + ["--version"], capture_output=True, text=True)
    version_text = version.stdout.strip() or "unknown"

    with tempfile.TemporaryDirectory(prefix="typefloor-") as tmp:
        probe = Path(tmp) / "probe.ts"
        probe.write_text(PROBE)
        # Run from the caller's directory, NOT from `tmp`. `find_tsc()` may have
        # resolved an npx-provided compiler out of the caller's own
        # node_modules; `npx --no-install` re-resolves per invocation from the
        # cwd, so running here from a temp dir under /tmp would fail to find the
        # very compiler just probed -- and npm's decoy `tsc` package answers
        # with prose, not diagnostics, which reads exactly like a vacuous
        # artifact. Explicit input files make tsc ignore any tsconfig.json here,
        # so the caller's project cannot influence the result.
        # Mirror the artifact's own header: lib ES2015, and no `dom` -- lib.dom
        # declares `console` and `Plugin` too, and would answer for a .d.ts that
        # declares neither.
        result = subprocess.run(
            tsc + ["--noEmit", "--lib", "ES2015", "--types",
                   "--strict", "false", str(dts), str(probe.resolve())],
            capture_output=True, text=True)
        output = result.stdout + result.stderr

    seen: dict[int, set[str]] = {}
    unexpected: list[str] = []
    for raw in output.splitlines():
        match = DIAG_RE.match(raw.strip())
        if match is None:
            if raw.strip():
                unexpected.append(raw.strip())
            continue
        if not match.group("file").endswith("probe.ts"):
            unexpected.append(raw.strip())
            continue
        seen.setdefault(int(match.group("line")), set()).add(match.group("code"))

    missing = []
    for line, codes, meaning in EXPECTED:
        got = seen.get(line, set())
        if not (got & codes):
            missing.append((line, codes, meaning, got))

    # A diagnostic on a probe line we did not ask about means the artifact is
    # broken in some third way -- most often the documented globals are absent,
    # which is TS2304 on `Plugin` and TS2584 on `console`.
    for line in sorted(seen):
        if line not in {expected[0] for expected in EXPECTED}:
            unexpected.append(
                f"probe.ts({line}): unrequested {'/'.join(sorted(seen[line]))}")

    # A vacuous artifact is silent AND tsc is happy. Silence with a nonzero
    # status means the compiler never got as far as judging the probe, so the
    # subject was not examined at all -- report "could not run", never FAILED.
    # Anything that fabricates a verdict without reading the artifact is the
    # defect this file exists to catch, including in this file.
    if not seen and result.returncode != 0:
        print("typefloor: UNVERIFIED -- tsc produced no diagnostics and exited "
              f"{result.returncode}.")
        print(f"  the artifact at {dts} was NOT checked; this says nothing "
              "about it.")
        for raw in output.splitlines():
            if raw.strip():
                print(f"  | {raw.rstrip()}")
        return 2

    if verbose:
        print(f"typefloor: tsc {version_text}")
        print(f"typefloor: artifact {dts}")
        for raw in output.splitlines():
            if raw.strip():
                print(f"  | {raw.rstrip()}")

    if not missing and not unexpected:
        print(f"typefloor: OK -- {len(EXPECTED)} planted defects all reported "
              f"(tsc {version_text})")
        return 0

    print("typefloor: FAILED -- this artifact does not check a plugin.")
    print(f"  artifact: {dts}")
    print(f"  tsc:      {version_text}")
    for line, codes, meaning, got in missing:
        expected_codes = "/".join(sorted(codes))
        actual = "/".join(sorted(got)) if got else "nothing"
        print(f"  probe.ts:{line} expected {expected_codes}, got {actual}")
        print(f"    -> {meaning}")
    for note in unexpected:
        print(f"  unexpected: {note}")
    print()
    print("  A green `tsc` against this file proves nothing. Either the core")
    print("  checkout is older than the declarations, or the artifact was never")
    print("  regenerated. Both are fixed the same way:")
    print("    mdev doctor                       # which core is this, how far behind")
    print("    cd \"$(mdev core)\" && git log -1   # and is that the branch you meant")
    print("    python3 support/devtools/metadata/gen.py")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="typefloor",
        description="Confirm a Movian .d.ts reports defects it is supposed to catch.")
    parser.add_argument("--dts", required=True, type=Path,
                        help="path to movian-api.d.ts")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="print the raw tsc output")
    args = parser.parse_args(argv)

    if not args.dts.is_file():
        print(f"typefloor: {args.dts} does not exist.")
        return 1
    # tsc runs in a temp dir, so a caller-relative path would resolve to nothing
    # there -- and tsc reports a missing root file as TS6053 while still emitting
    # no diagnostics for the probe, which reads exactly like a vacuous artifact.
    # Resolve before handing it over: the verdict must depend on the subject.
    return run(args.dts.resolve(), args.verbose)


if __name__ == "__main__":
    sys.exit(main())
