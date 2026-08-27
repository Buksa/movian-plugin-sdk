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
_CEILING = ""


def _git_local_env_vars() -> list[str]:
    """git's own list of the variables that select a repository."""
    done = subprocess.run(["git", "rev-parse", "--local-env-vars"],
                          capture_output=True, text=True)
    return done.stdout.split() if done.returncode == 0 else [
        "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY"]


_GIT_LOCAL_ENV = _git_local_env_vars()
# Fixtures build_cases() creates that later checks reuse.
FIXTURES: dict[str, Path] = {}


def locate(root: str | None, config: str | None = None,
           extra_env: dict[str, str] | None = None) -> tuple[int, str]:
    """Run `movian_sdk_locate` and return its exit code and stderr.

    The code is read from the process, never through a pipeline: `cmd | head`
    reports head's status, and a check measured that way is not a check.
    """
    env = dict(os.environ)
    env.pop("MOVIAN_CORE", None)
    # Repository selection from the caller's environment would classify the
    # fixtures by whatever repo the developer happens to be in. locate.sh
    # clears these itself now; the harness must not depend on that to be
    # testing what it thinks it is.
    for name in _GIT_LOCAL_ENV:
        env.pop(name, None)
    if root is not None:
        env["MOVIAN_CORE"] = root
    env["MOVIAN_SDK_CONFIG"] = config if config else "/nonexistent/config.json"
    if _CEILING:
        # TMPDIR may itself sit inside a git worktree, and git walks upward:
        # the "unrelated directory" fixture would then be classified by the
        # enclosing repository and the case would fail for a reason that has
        # nothing to do with the locator.
        env["GIT_CEILING_DIRECTORIES"] = _CEILING
    env.update(extra_env or {})
    done = subprocess.run(
        ["bash", "-c", '. "$1"; movian_sdk_locate', "_", str(LOCATE)],
        capture_output=True, text=True, env=env,
    )
    return done.returncode, done.stderr


def git(root: Path, *args: str) -> None:
    """Run git with the developer's own configuration kept out of it.

    Commit signing, `core.hooksPath` and templates are all global settings
    that make a synthetic commit fail or behave differently, and this suite is
    documented as needing no setup. `GIT_CONFIG_GLOBAL`/`_SYSTEM` pointed at
    /dev/null is the supported way to say "none of that".
    """
    subprocess.run(["git", "-C", str(root), "-c", "commit.gpgsign=false",
                    "-c", "core.hooksPath=/dev/null", *args],
                   check=True, capture_output=True,
                   env={**os.environ,
                        "GIT_CONFIG_GLOBAL": os.devnull,
                        "GIT_CONFIG_SYSTEM": os.devnull,
                        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


def movian_checkout(root: Path, *, with_mdev: bool) -> None:
    """A git checkout that looks like this project.

    `src/main.c` is the marker the locator uses: being a work tree says
    nothing about being Movian, and plenty of unrelated directories are
    version-controlled.
    """
    # The markers the locator requires: this build system and this property
    # system, together. Either alone is something any C project may have.
    (root / "src" / "prop").mkdir(parents=True, exist_ok=True)
    (root / "src" / "main.c").write_text("int main(void){return 0;}\n",
                                         encoding="utf-8")
    (root / "src" / "prop" / "prop.h").write_text("/* prop */\n",
                                                  encoding="utf-8")
    (root / "support" / "devtools").mkdir(parents=True, exist_ok=True)
    (root / "support" / "configure.inc").write_text("# configure\n",
                                                    encoding="utf-8")
    if with_mdev:
        (root / "support" / "devtools" / "mdev").write_text("#!/bin/sh\n",
                                                            encoding="utf-8")
    git(root, "init", "-q", ".")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "a revision")


def _git_out(root: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True,
                          env={**os.environ,
                               "GIT_CONFIG_GLOBAL": os.devnull,
                               "GIT_CONFIG_SYSTEM": os.devnull})
    return done.stdout


def _printed_fix(message: str) -> str | None:
    """The `fix:` command out of a diagnosis, joined across its backslash.

    Read from the message rather than retyped, so the test exercises what a
    reader would actually paste.
    """
    lines = message.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("fix: cd "):
            continue
        command = stripped[len("fix: "):]
        while command.endswith("\\") and index + 1 < len(lines):
            index += 1
            command = command[:-1] + " " + lines[index].strip()
        return command
    return None


def build_cases(tmp: Path) -> list[tuple[str, str, list[str], list[str]]]:
    """(label, root, must appear in stderr, must NOT appear)."""
    unrelated = tmp / "unrelated"
    unrelated.mkdir()

    checkout = tmp / "checkout"
    checkout.mkdir()
    movian_checkout(checkout, with_mdev=False)
    git(checkout, "checkout", "-q", "-b", "wsd-test")

    # A git repository that is not this project. Being version-controlled is
    # no evidence at all, and treating it as such regressed the one verdict
    # that used to be right.
    foreign = tmp / "foreign"
    foreign.mkdir()
    git(foreign, "init", "-q", ".")
    git(foreign, "commit", "-q", "--allow-empty", "-m", "not movian")

    # A C project with the conventional `src/main.c` and nothing else of
    # this one. Accepting either marker alone called this a Movian checkout.
    cproject = tmp / "cproject"
    (cproject / "src").mkdir(parents=True)
    (cproject / "src" / "main.c").write_text("int main(void){return 0;}\n",
                                             encoding="utf-8")
    git(cproject, "init", "-q", ".")
    git(cproject, "add", "-A")
    git(cproject, "commit", "-q", "-m", "a C project")

    # HEAD carries `mdev` and the working tree does not. Three ways that
    # happens, and the fixture used to be only the first -- so the
    # `--ignore-skip-worktree-bits` path the message advertises was never
    # once executed by this suite.
    sparse = tmp / "sparse"
    sparse.mkdir()
    movian_checkout(sparse, with_mdev=True)
    git(sparse, "sparse-checkout", "init", "--cone")
    git(sparse, "sparse-checkout", "set", "src")
    FIXTURES["sparse"] = sparse

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
         ["unrelated directory", "IS a Movian checkout", "inside the"]),
        ("an unrelated directory",
         str(unrelated),
         ["has no support/devtools/mdev", "unrelated directory"],
         ["IS a Movian checkout", "inside the", "not of Movian"]),
        ("a checkout on a revision without mdev",
         str(checkout),
         ["has no support/devtools/mdev", "IS a Movian checkout", "wsd-test",
          "update this checkout"],
         ["unrelated directory", "inside the Movian checkout",
          "revision DOES carry it", "not of Movian"]),
        ("a path inside a checkout rather than its root",
         str(checkout / "src"),
         ["inside the Movian checkout at", str(checkout)],
         ["unrelated directory", "IS a Movian checkout"]),
        ("a git repository that is not this project",
         str(foreign),
         ["not of Movian", "unrelated directory"],
         ["IS a Movian checkout", "update this checkout",
          "revision DOES carry it"]),
        ("a checkout whose HEAD has mdev but the file is gone",
         str(sparse),
         ["revision DOES carry it", "--ignore-skip-worktree-bits",
          "checkout HEAD", "sparse-checkout"],
         ["unrelated directory", "a revision without it"]),
        ("a C project that merely has src/main.c",
         str(cproject),
         ["not of Movian", "unrelated directory"],
         ["IS a Movian checkout", "update this checkout"]),
        ("a checkout with mdev but no built binary",
         str(complete),
         ["no executable build.debug/movian", "configure-linux-debug.sh"],
         ["unrelated directory", "IS a Movian checkout"]),
    ]


def main() -> int:
    global _CEILING
    failures = 0
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        _CEILING = str(tmp)

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

        # Git reads which repository to work on from the environment before
        # it looks at `-C`, so a hook or wrapping tool that exports GIT_DIR
        # would redirect the probes at ITS repository and misjudge this one.
        checkout = tmp / "checkout"
        code, err = locate(str(checkout),
                           extra_env={"GIT_DIR": str(tmp / "foreign" / ".git"),
                                      "GIT_WORK_TREE": str(tmp / "foreign")})
        if code == 0 or "IS a Movian checkout" not in err:
            print("  FAIL GIT_DIR redirects the probe: " + err.strip())
            failures += 1
        else:
            print("  ok   an exported GIT_DIR does not redirect the probe")

        # The printed remedy is run, not read. Three ways the file goes
        # missing, and the message must carry one command that restores all
        # three -- asserting the wording only proves the wording.
        deleted = tmp / "deleted"
        deleted.mkdir()
        movian_checkout(deleted, with_mdev=True)
        (deleted / "support" / "devtools" / "mdev").unlink()

        staged = tmp / "staged"
        staged.mkdir()
        movian_checkout(staged, with_mdev=True)
        git(staged, "rm", "-q", "--cached", "support/devtools/mdev")
        (staged / "support" / "devtools" / "mdev").unlink()

        # Each fixture asserts the state it claims to be in first. Without
        # this the sparse case degraded into a second ordinary deletion and
        # the suite still passed -- proving the remedy against a condition
        # that was never created is the failure this suite is about.
        preconditions = {
            "a staged deletion":
                lambda root: "support/devtools/mdev" in _git_out(
                    root, "diff", "--cached", "--name-only", "--diff-filter=D"),
            "a sparse-checkout exclusion":
                lambda root: any(
                    line.startswith("S ") and line.endswith("support/devtools/mdev")
                    for line in _git_out(root, "ls-files", "-t").splitlines()),
        }

        for label, where in (("an ordinary deletion", deleted),
                             ("a staged deletion", staged),
                             ("a sparse-checkout exclusion",
                              FIXTURES["sparse"])):
            check = preconditions.get(label)
            if check is not None and not check(where):
                print(f"  FAIL {label}: the fixture is not in that state")
                failures += 1
                continue
            code, err = locate(str(where))
            if code == 0 or "revision DOES carry it" not in err:
                print(f"  FAIL {label}: not diagnosed -- {err.strip()}")
                failures += 1
                continue
            command = _printed_fix(err)
            if command is None:
                print(f"  FAIL {label}: no runnable fix in the message")
                failures += 1
                continue
            run = subprocess.run(["bash", "-c", command], cwd=str(where),
                                 capture_output=True, text=True,
                                 env={**os.environ,
                                      "GIT_CONFIG_GLOBAL": os.devnull,
                                      "GIT_CONFIG_SYSTEM": os.devnull})
            restored = (where / "support" / "devtools" / "mdev").exists()
            if not restored:
                print(f"  FAIL {label}: the printed fix did not restore it")
                print(f"       $ {command}")
                print("       " + (run.stderr.strip() or "(no stderr)"))
                failures += 1
            else:
                print(f"  ok   the printed fix restores {label}")

        # A path the reader must paste back into a shell. `cd '<root>'` is
        # unrunnable the moment the path contains a quote, and the message
        # exists to be pasted.
        awkward = tmp / "it's a core"
        awkward.mkdir()
        movian_checkout(awkward, with_mdev=True)
        (awkward / "support" / "devtools" / "mdev").unlink()
        code, err = locate(str(awkward))
        command = _printed_fix(err)
        if code == 0 or command is None:
            print("  FAIL an awkward path: not diagnosed")
            failures += 1
        else:
            run = subprocess.run(["bash", "-c", command],
                                 capture_output=True, text=True,
                                 env={**os.environ,
                                      "GIT_CONFIG_GLOBAL": os.devnull,
                                      "GIT_CONFIG_SYSTEM": os.devnull})
            if not (awkward / "support" / "devtools" / "mdev").exists():
                print("  FAIL an awkward path: the printed fix does not run")
                print(f"       $ {command}")
                print("       " + (run.stderr.strip() or "(no stderr)"))
                failures += 1
            else:
                print("  ok   a path with a quote and spaces stays pasteable")

        # The wrapper clears everything `git rev-parse --local-env-vars`
        # names. That is safe only while the ceiling -- a sandbox bound, not
        # a repository selection -- stays off that list. It is off it on git
        # 2.43, so preserving it would be code no test could exercise; the
        # premise is pinned instead, and this fails the day git changes it.
        if "GIT_CEILING_DIRECTORIES" in _GIT_LOCAL_ENV:
            print("  FAIL git now lists GIT_CEILING_DIRECTORIES as a local env "
                  "var, so movian_sdk_git() strips the sandbox bound too")
            failures += 1
        else:
            print("  ok   the ceiling is not a variable the wrapper clears")

        # And the wrapper does clear the ones that ARE on that list -- proved
        # by effect, since a subshell could never have changed the caller's
        # copy anyway.
        outer = tmp / "ceiling" / "outer"
        (outer / "inner").mkdir(parents=True)
        git(outer, "init", "-q", ".")
        probe = subprocess.run(
            ["bash", "-c",
             '. "$1"; movian_sdk_git "$2" rev-parse --show-toplevel',
             "_", str(LOCATE), str(outer / "inner")],
            capture_output=True, text=True,
            env={**os.environ, "GIT_DIR": str(LOCATE.parent.parent / ".git")})
        if probe.returncode == 0 and str(outer) not in probe.stdout:
            print("  FAIL GIT_DIR still redirects the wrapper: "
                  + probe.stdout.strip())
            failures += 1
        else:
            print("  ok   an exported GIT_DIR does not redirect the wrapper")

        # The installer refuses before the shim exists, so it needs the same
        # diagnosis or a new user never sees it.
        installer = HERE.parent / "install.sh"
        done = subprocess.run(
            ["bash", str(installer), str(tmp / "checkout")],
            capture_output=True, text=True,
            env={**os.environ,
                 "MOVIAN_SDK_BINDIR": str(tmp / "ib"),
                 "MOVIAN_SDK_LIBDIR": str(tmp / "il"),
                 "MOVIAN_SDK_CONFIG": str(tmp / "ic.json")})
        if done.returncode == 0 or "IS a Movian checkout" not in done.stderr:
            print("  FAIL install.sh does not distinguish the revision: "
                  + done.stderr.strip()[-200:])
            failures += 1
        else:
            print("  ok   install.sh gives the same diagnosis")

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
    print("selftest: OK -- 18 cases, each naming its own cause")
    return 0


if __name__ == "__main__":
    sys.exit(main())
