#!/usr/bin/env python3
"""PROTOTYPE for movian-plugin-sdk#40 -- throwaway, not a committed test.

Drives real bash shell shapes against a synthetic HOME, inside the envelope the
map fixed: git + bash + python3 + TMPDIR, no container.

It exists to answer four things the ticket could not settle on paper:

  1. is `bash -i` in a non-tty usable, or does the noise/hang make it unusable?
  2. does overriding HOME actually isolate the shell?
  3. is the real install.sh under test, or an extracted function?
  4. what does a failure have to print to name its own cause?

`--fix-path` does not exist yet, so the block apply/remove below is a STAND-IN
for it. Proving the mechanism here is the point: it is cheaper to be wrong in a
prototype than in install.sh.
"""
import os, pathlib, shutil, subprocess, sys, tempfile

SKEL = pathlib.Path("/etc/skel")
BEGIN, END = "# >>> BEGIN MOVIAN SDK PATH >>>", "# <<< END MOVIAN SDK PATH <<<"
GUARD = "# If not running interactively, don't do anything"

REACHABLE, UNREACHABLE, UNDETERMINED = "REACHABLE", "UNREACHABLE", "UNDETERMINED"


def block(bindir):
    return (f'{BEGIN}\n'
            f'if [[ ":$PATH:" != *":{bindir}:"* ]]; then\n'
            f'  PATH="{bindir}:$PATH"\n'
            f'fi\n'
            f'{END}\n\n')


def fixture(tmp, *, bindir="{home}/.local/bin", make_bindir=True, anchor=True):
    """A fresh HOME carrying Debian's own skel dotfiles."""
    home = pathlib.Path(tmp)
    shutil.copy(SKEL / ".bashrc", home / ".bashrc")
    shutil.copy(SKEL / ".profile", home / ".profile")
    if not anchor:                       # a user who rewrote their ~/.bashrc
        (home / ".bashrc").write_text("# my own bashrc\nHISTSIZE=1000\n")
    b = pathlib.Path(bindir.format(home=home))
    if make_bindir:
        b.mkdir(parents=True, exist_ok=True)
        mdev = b / "mdev"
        mdev.write_text("#!/bin/sh\necho ok\n")
        mdev.chmod(0o755)
    return home, b


def apply_block(home, bindir):
    """STAND-IN for `install.sh --fix-path`. Inserts ABOVE the interactive guard."""
    p = home / ".bashrc"
    text = p.read_text()
    text = remove_block(home, quiet=True)          # rewrite in place, never stack
    lines = text.splitlines(True)
    for i, ln in enumerate(lines):
        if ln.startswith(GUARD):
            p.write_text("".join(lines[:i]) + block(bindir) + "".join(lines[i:]))
            return True
    return False                                    # anchor absent -> refuse


def remove_block(home, quiet=False):
    """Exact inverse of apply_block.

    The block is written as BEGIN..END followed by one blank line, so removal
    must drop that blank line too. Getting this wrong leaves the file one line
    longer after every apply/remove round-trip -- which the prototype caught.
    """
    p = home / ".bashrc"
    lines = p.read_text().splitlines(True)
    out, i = [], 0
    while i < len(lines):
        if lines[i].startswith(BEGIN):
            while i < len(lines) and not lines[i].startswith(END):
                i += 1
            i += 1                                  # step over END
            if i < len(lines) and lines[i].strip() == "":
                i += 1                              # and the blank we wrote
            continue
        out.append(lines[i])
        i += 1
    text = "".join(out)
    if not quiet:
        p.write_text(text)
    return text


def probe(home, shape, *, path="/usr/bin:/bin", stdin_null=True, timeout=6):
    """Ask one shell shape whether it can reach `mdev`.

    Every argument here is load-bearing; see the trap cases at the bottom.
    """
    flag = {"login": "-lc", "interactive": "-ic", "noninteractive": "-c"}[shape]
    env = {"HOME": str(home), "PATH": path, "TERM": "dumb"}
    # An OPEN pipe with no writer is what a real terminal looks like to `read`.
    # subprocess.PIPE would not do: run() closes it immediately, so `read` sees
    # EOF and the hang never reproduces -- the prototype caught that too.
    rfd = wfd = None
    if stdin_null:
        stdin = subprocess.DEVNULL
    else:
        rfd, wfd = os.pipe()
        stdin = rfd
    try:
        r = subprocess.run(["/bin/bash", flag, "command -v mdev"],
                           env=env, stdin=stdin,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        # Python SIGKILLs the child. A bash implementation MUST use
        # `timeout -s KILL`: interactive bash shrugs off SIGTERM.
        return UNDETERMINED
    finally:
        for fd in (rfd, wfd):
            if fd is not None:
                os.close(fd)
    return REACHABLE if r.returncode == 0 else UNREACHABLE


# --------------------------------------------------------------------------

FAILURES = []

def check(label, got, want):
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {label}: {got}" + ("" if ok else f"  (expected {want})"))
    if not ok:
        FAILURES.append(f"{label}: got {got}, expected {want}")


def case_34_red(tmp):
    print("case 1 -- #34 reproduced RED (skel dotfiles, bindir already exists)")
    home, b = fixture(tmp)
    check("login shell", probe(home, "login"), REACHABLE)
    check("non-login interactive", probe(home, "interactive"), UNREACHABLE)
    check("non-interactive (agent)", probe(home, "noninteractive"), UNREACHABLE)


def case_fix_applied(tmp):
    print("case 2 -- after the managed block is applied above the guard")
    home, b = fixture(tmp)
    assert apply_block(home, str(b))
    check("login shell", probe(home, "login"), REACHABLE)
    check("non-login interactive", probe(home, "interactive"), REACHABLE)
    check("non-interactive stays unreachable (served SDK-side, #41)",
          probe(home, "noninteractive"), UNREACHABLE)


def case_idempotent_in_file(tmp):
    print("case 3 -- idempotent IN THE FILE, and not in $PATH")
    home, b = fixture(tmp)
    apply_block(home, str(b)); apply_block(home, str(b)); apply_block(home, str(b))
    n = (home / ".bashrc").read_text().count(BEGIN)
    check("block appears once after 3 applies", f"{n} block(s)", "1 block(s)")
    # the login duplicate Debian itself creates, and no guard can prevent
    out = subprocess.run(["/bin/bash", "-lc", "echo $PATH"],
                         env={"HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb"},
                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL).stdout.decode()
    dupes = out.strip().split(":").count(str(b))
    check("login shell carries the entry twice (Debian's .profile sources "
          ".bashrc, then prepends UNGUARDED)", f"{dupes} entries", "2 entries")


def case_bindir_change(tmp):
    print("case 4 -- a changed MOVIAN_SDK_BINDIR leaves no stale line")
    home, b = fixture(tmp)
    apply_block(home, str(b))
    other = home / "opt" / "bin"; other.mkdir(parents=True)
    shutil.copy(b / "mdev", other / "mdev"); (other / "mdev").chmod(0o755)
    apply_block(home, str(other))
    text = (home / ".bashrc").read_text()
    check("exactly one block", f"{text.count(BEGIN)} block(s)", "1 block(s)")
    check("old bindir gone from the file", str(b) in text, False)
    check("new bindir reachable", probe(home, "interactive"), REACHABLE)


def case_removal(tmp):
    print("case 5 -- removal restores the file byte for byte")
    home, b = fixture(tmp)
    before = (home / ".bashrc").read_text()
    apply_block(home, str(b))
    remove_block(home)
    check("file identical to before", (home / ".bashrc").read_text() == before, True)
    check("and unreachable again", probe(home, "interactive"), UNREACHABLE)


def case_no_anchor(tmp):
    print("case 6 -- no guard anchor: REFUSE, never fall back to an EOF append")
    home, b = fixture(tmp, anchor=False)
    applied = apply_block(home, str(b))
    check("apply refused", applied, False)
    check("nothing was written", BEGIN in (home / ".bashrc").read_text(), False)


def case_trap_unscrubbed_path(tmp):
    print("case 7 -- TRAP: an unscrubbed PATH makes the probe pass in both directions")
    home, b = fixture(tmp)                       # no block: truly unreachable
    honest = probe(home, "interactive")
    inherited = probe(home, "interactive", path=f"{b}:/usr/bin:/bin")
    check("scrubbed PATH tells the truth", honest, UNREACHABLE)
    check("inherited PATH lies", inherited, REACHABLE)
    print("       ^ both are the SAME fixture. This is why the check lives in lib/ once.")


def case_trap_hang(tmp):
    print("case 8 -- TRAP: a ~/.bashrc that reads input hangs the probe")
    home, b = fixture(tmp)
    with open(home / ".bashrc", "a") as f:
        f.write('\nread -p "press enter: " _x\n')
    check("stdin=/dev/null -> answers", probe(home, "interactive"), UNREACHABLE)
    check("stdin=pipe -> UNDETERMINED, not a hang",
          probe(home, "interactive", stdin_null=False, timeout=4), UNDETERMINED)


def case_home_is_not_isolation(tmp):
    print("case 9 -- overriding HOME does NOT isolate the shell")
    home, b = fixture(tmp)
    r = subprocess.run(["/bin/bash", "-ic", "true"],
                       env={"HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb"},
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE)
    leaked = bool(r.stderr.strip())
    check("host /etc/bash.bashrc still speaks into the fixture", leaked, True)
    print(f"       leaked: {r.stderr.decode().strip().splitlines()[:1]}")
    print("       -> assert exit codes, never stdout/stderr text.")


def main():
    cases = [case_34_red, case_fix_applied, case_idempotent_in_file,
             case_bindir_change, case_removal, case_no_anchor,
             case_trap_unscrubbed_path, case_trap_hang, case_home_is_not_isolation]
    for c in cases:
        with tempfile.TemporaryDirectory() as tmp:
            c(tmp)
        print()
    if FAILURES:
        print(f"prototype: {len(FAILURES)} FAILURE(S)")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print(f"prototype: OK -- {len(cases)} cases, each naming its own cause")
    return 0


if __name__ == "__main__":
    sys.exit(main())
