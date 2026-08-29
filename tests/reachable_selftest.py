#!/usr/bin/env python3
"""Falsify lib/reachable.sh: prove the check answers, and answers for a reason.

The check this replaces (movian-plugin-sdk#34) was wrong in BOTH directions at
once -- it warned from a shell that happened to carry the bindir, and stayed
silent from a login shell while every ordinary terminal failed. So the cases
below assert the discriminating direction, not merely that something is printed.

Four properties of the probe fail SILENTLY when omitted -- each produces a
confident wrong answer rather than an error -- and each has its own case here:

  * an unscrubbed PATH makes the probe pass in BOTH directions (case 7)
  * stdin must be /dev/null or a ~/.bashrc that reads input hangs it (case 8)
  * HOME is not isolation: the host /etc/bash.bashrc still speaks (case 9)
  * a fixture with no bindir yet reproduces the WRONG direction, because
    install.sh's `mkdir -p` runs AFTER ~/.profile evaluated `if [ -d ]`
    (avoided by construction: every fixture creates the bindir first)

Needs no Movian core and no SDK configuration. It needs git, bash, jq, awk and
Python, and writes synthetic homes under TMPDIR.
"""
import pathlib
import shlex
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
LIB = HERE.parent / "lib" / "reachable.sh"
INSTALLER = HERE.parent / "install.sh"
SKEL = pathlib.Path("/etc/skel")

BEGIN = "# >>> BEGIN MOVIAN SDK PATH >>>"
GUARD = "# If not running interactively, don't do anything"

FAILURES = []


def ok(label, got, want):
    good = got == want
    print(f"  {'ok  ' if good else 'FAIL'} {label}: {got}"
          + ("" if good else f"   (expected {want})"))
    if not good:
        FAILURES.append(f"{label}: got {got!r}, expected {want!r}")


def sh(script, home, extra_env=None, timeout=60):
    """Run a bash snippet with lib/reachable.sh sourced, against a fixture HOME."""
    env = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "TERM": "dumb",
        "MOVIAN_SDK_CONFIG": f"{home}/.config/movian-sdk/config.json",
    }
    env.update(extra_env or {})
    return subprocess.run(
        ["/bin/bash", "-c", f'set -euo pipefail\n. "{LIB}"\n{script}'],
        env=env, stdin=subprocess.DEVNULL, timeout=timeout,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def fixture(tmp, *, anchor=True, with_mdev=True):
    """A synthetic HOME carrying Debian's own skel dotfiles.

    The bindir is created BEFORE any shell runs. A fixture that omits this
    reproduces the opposite of #34: ~/.profile's `if [ -d "$HOME/.local/bin" ]`
    is evaluated at login, and install.sh only creates the directory afterwards,
    so the FIRST login-shell install legitimately warns and only the second is
    silent.
    """
    home = pathlib.Path(tmp) / "home"
    (home / ".local" / "bin").mkdir(parents=True)
    (home / ".config" / "movian-sdk").mkdir(parents=True)
    if anchor:
        shutil.copy(SKEL / ".bashrc", home / ".bashrc")
    else:
        (home / ".bashrc").write_text("# a bashrc the user rewrote\nHISTSIZE=1000\n")
    shutil.copy(SKEL / ".profile", home / ".profile")
    bindir = home / ".local" / "bin"
    if with_mdev:
        mdev = bindir / "mdev"
        mdev.write_text("#!/bin/sh\necho ok\n")
        mdev.chmod(0o755)
    return home, bindir


# --------------------------------------------------------------------------

def case_reproduces_34(tmp):
    print("the probe reproduces #34: login yes, ordinary terminal no")
    home, bindir = fixture(tmp)
    for shape, want in (("login", "REACHABLE"), ("interactive", "UNREACHABLE"),
                        ("noninteractive", "UNREACHABLE")):
        r = sh(f'movian_sdk_probe "{bindir}" {shape}', home)
        ok(shape, r.stdout.strip(), want)


def case_block_makes_it_reachable(tmp):
    print("the managed block lands above the guard and closes the gap")
    home, bindir = fixture(tmp)
    sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{bindir}" apply', home)
    lines = (home / ".bashrc").read_text().splitlines()
    ok("block precedes the interactive guard",
       lines.index(BEGIN) < lines.index(GUARD), True)
    ok("interactive", sh(f'movian_sdk_probe "{bindir}" interactive', home).stdout.strip(),
       "REACHABLE")
    ok("non-interactive is NOT claimed (served SDK-side, #41)",
       sh(f'movian_sdk_probe "{bindir}" noninteractive', home).stdout.strip(),
       "UNREACHABLE")


def case_idempotent_in_the_file(tmp):
    print("idempotent in the FILE -- and provably not in $PATH")
    home, bindir = fixture(tmp)
    for _ in range(3):
        sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{bindir}" apply', home)
    ok("one block after three applies",
       (home / ".bashrc").read_text().count(BEGIN), 1)
    r = subprocess.run(["/bin/bash", "-lc", "echo $PATH"],
                       env={"HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb"},
                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True,
                       stderr=subprocess.DEVNULL)
    # Debian's ~/.profile SOURCES ~/.bashrc, then prepends its own UNGUARDED
    # line. No guard written into ~/.bashrc can prevent the second entry, which
    # is why #34's "idempotent" cannot mean idempotent in $PATH.
    ok("a login shell carries the entry twice, by Debian's design",
       r.stdout.strip().split(":").count(str(bindir)), 2)


def case_bindir_change_leaves_nothing_stale(tmp):
    print("a changed MOVIAN_SDK_BINDIR rewrites in place")
    home, bindir = fixture(tmp)
    other = home / "opt" / "bin"
    other.mkdir(parents=True)
    shutil.copy(bindir / "mdev", other / "mdev")
    (other / "mdev").chmod(0o755)
    sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{bindir}" apply', home)
    sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{other}" apply', home)
    text = (home / ".bashrc").read_text()
    ok("exactly one block", text.count(BEGIN), 1)
    ok("the old bindir is gone", str(bindir) in text, False)
    ok("the new one is reachable",
       sh(f'movian_sdk_probe "{other}" interactive', home).stdout.strip(), "REACHABLE")


def case_removal_is_an_exact_inverse(tmp):
    print("removal restores the file byte for byte")
    home, bindir = fixture(tmp)
    before = (home / ".bashrc").read_text()
    sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{bindir}" apply', home)
    sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{bindir}" remove', home)
    # The block is written with a trailing blank line. Stripping only the body
    # leaves the file one line longer on every cycle, so --unfix-path would
    # quietly grow a user's ~/.bashrc. That defect is why this case exists.
    ok("identical to before", (home / ".bashrc").read_text() == before, True)
    ok("and unreachable again",
       sh(f'movian_sdk_probe "{bindir}" interactive', home).stdout.strip(), "UNREACHABLE")


def case_missing_anchor_refuses(tmp):
    print("no interactive guard: refuse, never append at EOF")
    home, bindir = fixture(tmp, anchor=False)
    r = sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{bindir}" apply || true', home)
    ok("nothing was written", BEGIN in (home / ".bashrc").read_text(), False)
    ok("and it says which line it wanted", GUARD in r.stderr, True)
    # An EOF append would satisfy the interactive shape and leave
    # `ssh host 'mdev ...'` broken while reporting success -- a partial fix
    # presented as a complete one, the defect class #34 was filed about.


def case_unscrubbed_path_would_lie(tmp):
    print("TRAP: an unscrubbed PATH passes in both directions")
    home, bindir = fixture(tmp)          # no block: genuinely unreachable
    honest = sh(f'movian_sdk_probe "{bindir}" interactive', home).stdout.strip()
    lying = sh(f'movian_sdk_probe "{bindir}" interactive', home,
               extra_env={"PATH": f"{bindir}:/usr/bin:/bin"}).stdout.strip()
    ok("scrubbing keeps the verdict honest", honest, "UNREACHABLE")
    # The bindir arrives in PATH exactly as it would when the installer is run
    # from a shell that already has it -- the #34 false-pass, reproduced. It
    # stays UNREACHABLE only because movian_sdk_path_without removes it.
    ok("and survives an inherited PATH", lying, "UNREACHABLE")


def case_a_reading_bashrc_is_undetermined(tmp):
    print("TRAP: a ~/.bashrc that reads input is UNDETERMINED, not a hang")
    home, bindir = fixture(tmp)
    with open(home / ".bashrc", "a") as f:
        f.write('\nread -r -p "press enter: " _x\n')
    # stdin is /dev/null inside the probe, so `read` gets EOF rather than
    # blocking. Without that redirect this call does not return at all.
    r = sh(f'movian_sdk_probe "{bindir}" interactive', home, timeout=30)
    ok("answers instead of hanging", r.stdout.strip() in ("UNREACHABLE", "UNDETERMINED"), True)

    # And the timeout itself must kill: interactive bash does not reliably die
    # on SIGTERM, so `timeout` without -s KILL can return while the shell lives.
    with open(home / ".bashrc", "w") as f:
        f.write("sleep 300\n")
    r = sh(f'movian_sdk_probe "{bindir}" interactive', home,
           extra_env={"MOVIAN_SDK_PROBE_TIMEOUT": "3"}, timeout=30)
    ok("a wedged startup file is UNDETERMINED", r.stdout.strip(), "UNDETERMINED")


def case_home_is_not_isolation(tmp):
    print("HOME is not isolation -- assert verdicts, never output text")
    home, _ = fixture(tmp)
    r = subprocess.run(["/bin/bash", "-ic", "true"],
                       env={"HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb"},
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE, text=True)
    # The host's /etc/bash.bashrc is read regardless of HOME. It does not touch
    # PATH on a stock Debian, so it is noise rather than corruption -- but that
    # is a property of the host, not a guarantee. Hence: verdicts, not text.
    ok("the host still speaks into the fixture", bool(r.stderr.strip()), True)


def case_installer_records_bin(tmp):
    print("install.sh records where it put the shims")
    home, bindir = fixture(tmp, with_mdev=False)
    cfg = home / ".config" / "movian-sdk" / "config.json"
    cfg.write_text('{\n  "core": "/nonexistent/core"\n}\n')
    env = {
        "HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb",
        "MOVIAN_SDK_BINDIR": str(bindir),
        "MOVIAN_SDK_LIBDIR": str(home / ".local/lib/movian-sdk"),
        "MOVIAN_SDK_CONFIG": str(cfg),
    }
    subprocess.run(["/bin/bash", str(INSTALLER)], env=env, stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    import json
    got = json.loads(cfg.read_text())
    ok("bin recorded", got.get("bin"), str(bindir))
    # Merged, not rewritten: a config carrying "core" must keep it, and
    # lib/locate.sh parses with jq so key order is irrelevant.
    ok("core preserved", got.get("core"), "/nonexistent/core")
    ok("the shim resolves through the record",
       sh('movian_sdk_bindir', home, extra_env={"MOVIAN_SDK_CONFIG": str(cfg)}).stdout.strip(),
       str(bindir))


def case_installer_warns_where_it_used_to_be_silent(tmp):
    print("install.sh warns from a LOGIN shell -- the case that was silent")
    home, bindir = fixture(tmp, with_mdev=False)
    env = {
        "HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb",
        "MOVIAN_SDK_BINDIR": str(bindir),
        "MOVIAN_SDK_LIBDIR": str(home / ".local/lib/movian-sdk"),
        "MOVIAN_SDK_CONFIG": str(home / ".config/movian-sdk/config.json"),
    }
    # A LOGIN shell running the installer: ~/.profile has already put the bindir
    # on this shell's PATH, so the old `case ":$PATH:"` check saw success and
    # said nothing, while every ordinary terminal still failed.
    r = subprocess.run(["/bin/bash", "-lc", f'"{INSTALLER}"'], env=env,
                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, timeout=120)
    ok("it warns", "not reachable from every shell that will run mdev" in r.stdout, True)
    ok("and names the shape that failed, not a fixed story",
       "an ordinary terminal does not" in r.stdout, True)
    ok("it names a runnable fix", "install.sh --fix-path" in r.stdout, True)
    ok("and does not gate", r.returncode, 0)


def case_printed_fix_actually_works(tmp):
    print("the printed fix is RUN, and it fixes what it claimed")
    home, bindir = fixture(tmp, with_mdev=False)
    env = {
        "HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb",
        "MOVIAN_SDK_BINDIR": str(bindir),
        "MOVIAN_SDK_LIBDIR": str(home / ".local/lib/movian-sdk"),
        "MOVIAN_SDK_CONFIG": str(home / ".config/movian-sdk/config.json"),
    }
    subprocess.run(["/bin/bash", str(INSTALLER)], env=env, stdin=subprocess.DEVNULL,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    ok("unreachable before the fix",
       sh(f'movian_sdk_probe "{bindir}" interactive', home).stdout.strip(), "UNREACHABLE")
    r = subprocess.run(["/bin/bash", str(INSTALLER), "--fix-path"], env=env,
                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, timeout=120)
    ok("--fix-path succeeds", r.returncode, 0)
    ok("reachable after it",
       sh(f'movian_sdk_probe "{bindir}" interactive', home).stdout.strip(), "REACHABLE")
    ok("and the installer now says so", "interactive    REACHABLE" in r.stdout, True)


# --- cases added from the Codex review of PR #42 ---------------------------

def case_legacy_config_does_not_resolve_to_slash_mdev(tmp):
    print("a config predating the bin key resolves to nothing, not to /mdev")
    home, _ = fixture(tmp)
    cfg = home / ".config" / "movian-sdk" / "config.json"
    cfg.write_text('{\n  "core": "/some/core"\n}\n')
    # The expression the seven skill preambles tell an agent to run. Plain
    # `.bin + "/mdev"` yields the string "/mdev" here -- jq's null + string --
    # so the agent would take a nonexistent root-level path for the shim, with
    # a zero exit status, in exactly the session the preamble exists for.
    r = subprocess.run(
        ["/bin/bash", "-c",
         f'jq -er \'.bin // empty | . + "/mdev"\' "{cfg}"'],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    ok("prints nothing", r.stdout.strip(), "")
    ok("and fails", r.returncode != 0, True)
    ok("movian_sdk_bindir also refuses",
       sh('movian_sdk_bindir || echo NONE', home,
          extra_env={"MOVIAN_SDK_CONFIG": str(cfg)}).stdout.strip(), "NONE")


def case_bindir_is_written_as_data_not_code(tmp):
    print("a bindir with shell metacharacters is data, never executed")
    home, _ = fixture(tmp)
    canary = pathlib.Path(tmp) / "CANARY"
    evil = f"/tmp/$(touch {canary})/bin"
    sh(f'movian_sdk_fix_path "$HOME/.bashrc" {shlex.quote(evil)} apply', home)
    subprocess.run(["/bin/bash", "-ic", "true"],
                   env={"HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb"},
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=30)
    ok("no command substitution fired", canary.exists(), False)


def case_damaged_markers_refuse_rather_than_truncate(tmp):
    print("a half-open block is refused, not interpreted")
    home, bindir = fixture(tmp)
    original = (home / ".bashrc").read_text()
    lines = original.splitlines(True)
    # The user kept BEGIN and deleted END. A naive strip treats the whole tail
    # as block body: 117 lines in, 3 out, from a command meant to remove five.
    lines.insert(4, BEGIN + "\nPATH=/x:$PATH\n")
    (home / ".bashrc").write_text("".join(lines))
    damaged = (home / ".bashrc").read_text()
    for mode in ("remove", "apply"):
        r = sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{bindir}" {mode} || true', home)
        ok(f"{mode} refuses", "markers" in r.stderr and "refusing to edit" in r.stderr, True)
        ok(f"{mode} left the file untouched", (home / ".bashrc").read_text(), damaged)


def case_the_diagnosis_names_the_shape_that_failed(tmp):
    print("the warning describes the shell that actually failed")
    home, bindir = fixture(tmp)
    # The reverse of #34: ~/.bashrc provides the path, ~/.profile does not.
    (home / ".bashrc").write_text(f'PATH="{bindir}:$PATH"\n')
    (home / ".profile").write_text("")
    r = sh(f'movian_sdk_reachability_report "{bindir}"\n'
           f'movian_sdk_explain_unreachable "{bindir}" "" "$MOVIAN_SDK_REACH_WORST"', home)
    ok("login is the failing shape", "reachable: login          UNREACHABLE" in r.stdout, True)
    ok("and the message says so, not the opposite",
       "a LOGIN shell does not" in r.stderr, True)
    ok("it does not claim terminals are broken",
       "an ordinary terminal answers" in r.stderr, False)


def case_a_backup_is_taken_before_the_first_edit(tmp):
    print("the user's startup file is backed up, and a symlink stays a symlink")
    home, bindir = fixture(tmp)
    real = pathlib.Path(tmp) / "dotfiles-bashrc"
    shutil.move(str(home / ".bashrc"), real)
    (home / ".bashrc").symlink_to(real)          # as stow/chezmoi would leave it
    before = real.read_text()
    sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{bindir}" apply', home)
    ok("backup exists", (home / ".bashrc.movian-sdk.bak").is_file(), True)
    ok("backup holds the original",
       (home / ".bashrc.movian-sdk.bak").read_text() == before, True)
    # An atomic rename would replace the symlink with a regular file, breaking a
    # dotfiles repository. Redirection writes through it.
    ok("still a symlink", (home / ".bashrc").is_symlink(), True)
    ok("the dotfiles file itself was updated", BEGIN in real.read_text(), True)


def case_installer_reports_a_failed_merge(tmp):
    print("install.sh does not claim to have recorded bin when it could not")
    home, bindir = fixture(tmp, with_mdev=False)
    cfg = home / ".config" / "movian-sdk" / "config.json"
    cfg.write_text("this is not json\n")
    env = {
        "HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb",
        "MOVIAN_SDK_BINDIR": str(bindir),
        "MOVIAN_SDK_LIBDIR": str(home / ".local/lib/movian-sdk"),
        "MOVIAN_SDK_CONFIG": str(cfg),
    }
    r = subprocess.run(["/bin/bash", str(INSTALLER)], env=env, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                       timeout=120)
    ok("it warns", "could not record bin" in r.stdout, True)
    ok("it does not claim success", "recorded bin ->" in r.stdout, False)
    ok("the broken config is left alone", cfg.read_text(), "this is not json\n")


def main():
    if not SKEL.joinpath(".bashrc").is_file():
        print(f"reachable_selftest: SKIP -- {SKEL}/.bashrc is absent, so there is no")
        print("  Debian-shaped fixture to build. This suite asserts against the")
        print("  dotfiles the distribution ships, not against invented ones.")
        return 0

    cases = [
        case_reproduces_34,
        case_block_makes_it_reachable,
        case_idempotent_in_the_file,
        case_bindir_change_leaves_nothing_stale,
        case_removal_is_an_exact_inverse,
        case_missing_anchor_refuses,
        case_unscrubbed_path_would_lie,
        case_a_reading_bashrc_is_undetermined,
        case_home_is_not_isolation,
        case_installer_records_bin,
        case_installer_warns_where_it_used_to_be_silent,
        case_printed_fix_actually_works,
        # from the Codex review of PR #42
        case_legacy_config_does_not_resolve_to_slash_mdev,
        case_bindir_is_written_as_data_not_code,
        case_damaged_markers_refuse_rather_than_truncate,
        case_the_diagnosis_names_the_shape_that_failed,
        case_a_backup_is_taken_before_the_first_edit,
        case_installer_reports_a_failed_merge,
    ]
    for c in cases:
        with tempfile.TemporaryDirectory() as tmp:
            c(tmp)
    print()
    if FAILURES:
        print(f"reachable_selftest: {len(FAILURES)} FAILURE(S)")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print(f"reachable_selftest: OK -- {len(cases)} cases, each naming its own cause")
    return 0


if __name__ == "__main__":
    sys.exit(main())
