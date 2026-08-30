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
import json
import os
import pathlib
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
LIB = HERE.parent / "lib" / "reachable.sh"
INSTALLER = HERE.parent / "install.sh"
SKEL = pathlib.Path("/etc/skel")

# Vendored verbatim from Debian's `bash` package, /etc/skel. Byte-identical
# across Debian 9-13 and Ubuntu 18.04-24.04 (see research/debian-path-and-dotfiles.md).
# Embedded so the suite RUNS on a machine without /etc/skel instead of skipping
# into a vacuous pass -- and `case_the_vendored_skel_matches_the_distribution`
# fails if the distribution's copy ever diverges from this one.
SKEL_BASHRC = '# ~/.bashrc: executed by bash(1) for non-login shells.\n# see /usr/share/doc/bash/examples/startup-files (in the package bash-doc)\n# for examples\n\n# If not running interactively, don\'t do anything\ncase $- in\n    *i*) ;;\n      *) return;;\nesac\n\n# don\'t put duplicate lines or lines starting with space in the history.\n# See bash(1) for more options\nHISTCONTROL=ignoreboth\n\n# append to the history file, don\'t overwrite it\nshopt -s histappend\n\n# for setting history length see HISTSIZE and HISTFILESIZE in bash(1)\nHISTSIZE=1000\nHISTFILESIZE=2000\n\n# check the window size after each command and, if necessary,\n# update the values of LINES and COLUMNS.\nshopt -s checkwinsize\n\n# If set, the pattern "**" used in a pathname expansion context will\n# match all files and zero or more directories and subdirectories.\n#shopt -s globstar\n\n# make less more friendly for non-text input files, see lesspipe(1)\n[ -x /usr/bin/lesspipe ] && eval "$(SHELL=/bin/sh lesspipe)"\n\n# set variable identifying the chroot you work in (used in the prompt below)\nif [ -z "${debian_chroot:-}" ] && [ -r /etc/debian_chroot ]; then\n    debian_chroot=$(cat /etc/debian_chroot)\nfi\n\n# set a fancy prompt (non-color, unless we know we "want" color)\ncase "$TERM" in\n    xterm-color|*-256color) color_prompt=yes;;\nesac\n\n# uncomment for a colored prompt, if the terminal has the capability; turned\n# off by default to not distract the user: the focus in a terminal window\n# should be on the output of commands, not on the prompt\n#force_color_prompt=yes\n\nif [ -n "$force_color_prompt" ]; then\n    if [ -x /usr/bin/tput ] && tput setaf 1 >&/dev/null; then\n\t# We have color support; assume it\'s compliant with Ecma-48\n\t# (ISO/IEC-6429). (Lack of such support is extremely rare, and such\n\t# a case would tend to support setf rather than setaf.)\n\tcolor_prompt=yes\n    else\n\tcolor_prompt=\n    fi\nfi\n\nif [ "$color_prompt" = yes ]; then\n    PS1=\'${debian_chroot:+($debian_chroot)}\\[\\033[01;32m\\]\\u@\\h\\[\\033[00m\\]:\\[\\033[01;34m\\]\\w\\[\\033[00m\\]\\$ \'\nelse\n    PS1=\'${debian_chroot:+($debian_chroot)}\\u@\\h:\\w\\$ \'\nfi\nunset color_prompt force_color_prompt\n\n# If this is an xterm set the title to user@host:dir\ncase "$TERM" in\nxterm*|rxvt*)\n    PS1="\\[\\e]0;${debian_chroot:+($debian_chroot)}\\u@\\h: \\w\\a\\]$PS1"\n    ;;\n*)\n    ;;\nesac\n\n# enable color support of ls and also add handy aliases\nif [ -x /usr/bin/dircolors ]; then\n    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"\n    alias ls=\'ls --color=auto\'\n    #alias dir=\'dir --color=auto\'\n    #alias vdir=\'vdir --color=auto\'\n\n    alias grep=\'grep --color=auto\'\n    alias fgrep=\'fgrep --color=auto\'\n    alias egrep=\'egrep --color=auto\'\nfi\n\n# colored GCC warnings and errors\n#export GCC_COLORS=\'error=01;31:warning=01;35:note=01;36:caret=01;32:locus=01:quote=01\'\n\n# some more ls aliases\nalias ll=\'ls -alF\'\nalias la=\'ls -A\'\nalias l=\'ls -CF\'\n\n# Add an "alert" alias for long running commands.  Use like so:\n#   sleep 10; alert\nalias alert=\'notify-send --urgency=low -i "$([ $? = 0 ] && echo terminal || echo error)" "$(history|tail -n1|sed -e \'\\\'\'s/^\\s*[0-9]\\+\\s*//;s/[;&|]\\s*alert$//\'\\\'\')"\'\n\n# Alias definitions.\n# You may want to put all your additions into a separate file like\n# ~/.bash_aliases, instead of adding them here directly.\n# See /usr/share/doc/bash-doc/examples in the bash-doc package.\n\nif [ -f ~/.bash_aliases ]; then\n    . ~/.bash_aliases\nfi\n\n# enable programmable completion features (you don\'t need to enable\n# this, if it\'s already enabled in /etc/bash.bashrc and /etc/profile\n# sources /etc/bash.bashrc).\nif ! shopt -oq posix; then\n  if [ -f /usr/share/bash-completion/bash_completion ]; then\n    . /usr/share/bash-completion/bash_completion\n  elif [ -f /etc/bash_completion ]; then\n    . /etc/bash_completion\n  fi\nfi\n'

SKEL_PROFILE = '# ~/.profile: executed by the command interpreter for login shells.\n# This file is not read by bash(1), if ~/.bash_profile or ~/.bash_login\n# exists.\n# see /usr/share/doc/bash/examples/startup-files for examples.\n# the files are located in the bash-doc package.\n\n# the default umask is set in /etc/profile; for setting the umask\n# for ssh logins, install and configure the libpam-umask package.\n#umask 022\n\n# if running bash\nif [ -n "$BASH_VERSION" ]; then\n    # include .bashrc if it exists\n    if [ -f "$HOME/.bashrc" ]; then\n\t. "$HOME/.bashrc"\n    fi\nfi\n\n# set PATH so it includes user\'s private bin if it exists\nif [ -d "$HOME/bin" ] ; then\n    PATH="$HOME/bin:$PATH"\nfi\n\n# set PATH so it includes user\'s private bin if it exists\nif [ -d "$HOME/.local/bin" ] ; then\n    PATH="$HOME/.local/bin:$PATH"\nfi\n'

BEGIN = "# >>> BEGIN MOVIAN SDK PATH >>>"
END = "# <<< END MOVIAN SDK PATH <<<"
GUARD = "# If not running interactively, don't do anything"

FAILURES = []


def ok(label, got, want):
    good = got == want
    print(f"  {'ok  ' if good else 'FAIL'} {label}: {got}"
          + ("" if good else f"   (expected {want})"))
    if not good:
        FAILURES.append(f"{label}: got {got!r}, expected {want!r}")


def sh(script, home, extra_env=None, timeout=60, lib=None, open_stdin=False):
    """Run a bash snippet with lib/reachable.sh sourced, against a fixture HOME.

    `lib` selects a mutated copy instead of the real library, so a case can
    prove that a property is load-bearing by removing it.
    """
    env = {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin",
        "TERM": "dumb",
        "MOVIAN_SDK_CONFIG": f"{home}/.config/movian-sdk/config.json",
    }
    env.update(extra_env or {})
    # An OPEN pipe with no writer, not DEVNULL, when a case is proving that the
    # probe's own `</dev/null` matters: with DEVNULL here the child inherits it
    # and the mutant cannot hang, which silently masks the very property under
    # test.
    rfd = wfd = None
    if open_stdin:
        rfd, wfd = os.pipe()
        stdin = rfd
    else:
        stdin = subprocess.DEVNULL
    try:
        return subprocess.run(
            ["/bin/bash", "-c", f'set -euo pipefail\n. "{lib or LIB}"\n{script}'],
            env=env, stdin=stdin, timeout=timeout,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    finally:
        for fd in (rfd, wfd):
            if fd is not None:
                os.close(fd)


def mutate_lib(tmp, find, replace):
    """A copy of lib/reachable.sh with one property removed.

    Mutation testing is the only way to show a guard guards anything: a case
    that stays green when the code it names is deleted is not testing that code.
    Three cases in this file used to do exactly that.
    """
    src = LIB.read_text()
    if find not in src:
        # A mutation target that has vanished means the property this case
        # guards was removed or rewritten. That is a finding, not a crash.
        FAILURES.append(f"mutation target absent from lib/reachable.sh: {find!r}")
        print(f"  FAIL mutation target absent: {find!r}")
        return LIB
    dst = pathlib.Path(tmp) / f"mutant-{abs(hash(find)) % 10**8}.sh"
    dst.write_text(src.replace(find, replace, 1))
    return dst


def wedge_marker(home):
    """A uniquely-named wedge command, so survivors are identifiable in `ps`.

    A bare `sleep 300` in the fixture's ~/.bashrc is indistinguishable from any
    other sleep on the machine -- and HOME is an environment variable, so it
    never appears in the process arguments. The wedge is therefore a script at a
    path unique to this fixture, which `ps -o args` does show.
    """
    marker = home / ".local" / "bin" / "movian-sdk-wedge"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("#!/bin/sh\nexec sleep 300\n")
    marker.chmod(0o755)
    return marker


def survivors_of(marker):
    """Probe shells still wedged on `marker`.

    `timeout` reports 124 whether or not the child died, so the exit status
    cannot tell a killed shell from a surviving one. The process table can.
    """
    out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True, text=True).stdout
    return [int(ln.split()[0]) for ln in out.splitlines() if str(marker) in ln]


def kill_survivors(marker):
    for pid in survivors_of(marker):
        try: os.kill(pid, signal.SIGKILL)
        except Exception: pass


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
        (home / ".bashrc").write_text(SKEL_BASHRC)
    else:
        (home / ".bashrc").write_text("# a bashrc the user rewrote\nHISTSIZE=1000\n")
    (home / ".profile").write_text(SKEL_PROFILE)
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
    """The stdin redirect, proved load-bearing by removing it.

    The previous version asserted nothing that could fail: it accepted
    UNDETERMINED as a pass, and UNDETERMINED is exactly what a missing
    `</dev/null` produces. Deleting the redirect from lib/reachable.sh left the
    whole suite green, so the property is now tested by taking it away.

    On `timeout -s KILL`: measured here, SIGTERM and SIGKILL give the SAME
    verdict, the same elapsed time and the same orphaned grandchild, so no case
    in this file can distinguish them. `-s KILL` is kept as defence against a
    bash that ignores SIGTERM, and this comment records that as a belief rather
    than a measurement -- the honest alternative to a green tick proving nothing.
    """
    print("the stdin redirect is load-bearing, proved by removing it")
    home, bindir = fixture(tmp)

    # With the redirect, `read` gets EOF at once and the probe returns a real
    # verdict.
    (home / ".bashrc").write_text('read -r -p "press enter: " _x\n')
    verdict = sh(f'movian_sdk_probe "{bindir}" interactive', home, timeout=30).stdout.strip()
    ok("with the redirect, a real verdict", verdict in ("REACHABLE", "UNREACHABLE"), True)

    # Without it the shell blocks on a terminal that never types, and only the
    # probe's own timeout ends it -- the answer degrades from a measurement to
    # "could not determine".
    mutant = mutate_lib(tmp, "</dev/null ", "")
    mutated = sh(f'movian_sdk_probe "{bindir}" interactive', home, lib=mutant,
                 extra_env={"MOVIAN_SDK_PROBE_TIMEOUT": "3"}, timeout=40,
                 open_stdin=True).stdout.strip()
    ok("without it, no verdict is obtainable", mutated, "UNDETERMINED")
    ok("the redirect decides whether the probe can answer at all",
       verdict != mutated, True)

    # A genuinely wedged startup file is UNDETERMINED rather than a confident
    # UNREACHABLE, and the probe RETURNS rather than hanging.
    marker = wedge_marker(home)
    (home / ".bashrc").write_text(f"{marker}\n")
    started = time.monotonic()
    r = sh(f'movian_sdk_probe "{bindir}" interactive', home,
           extra_env={"MOVIAN_SDK_PROBE_TIMEOUT": "3"}, timeout=40)
    elapsed = time.monotonic() - started
    ok("a wedged startup file is UNDETERMINED", r.stdout.strip(), "UNDETERMINED")
    ok("and the probe returns, bounded by its own timeout", elapsed < 20, True)
    # timeout kills the shell it started, not the grandchild that shell left
    # behind. One orphan survives; recorded here so a later reader knows it was
    # measured rather than missed.
    kill_survivors(marker)


def case_host_noise_does_not_reach_the_verdict(tmp):
    """Host chatter is real; the point is that the VERDICT is immune to it.

    The previous version asserted only that `bash -ic` printed something on
    stderr -- bash's own job-control complaint, true under `--norc`, and it
    called no SDK function at all. It could not fail for any reason connected to
    this repository. What actually matters is that the probe reports on the
    fixture and not on the developer's machine, so that is what is asserted.
    """
    print("host noise is loud, and the verdict ignores it")
    home, bindir = fixture(tmp)

    # Deliberately noisy startup file, on top of whatever the host's
    # /etc/bash.bashrc already says.
    (home / ".bashrc").write_text(
        'echo "NOISE on stdout"\necho "NOISE on stderr" >&2\n')
    ok("no dotfile provides it -> UNREACHABLE despite the noise",
       sh(f'movian_sdk_probe "{bindir}" interactive', home).stdout.strip(),
       "UNREACHABLE")

    (home / ".bashrc").write_text(
        f'echo "NOISE on stdout"\necho "NOISE on stderr" >&2\nPATH="{bindir}:$PATH"\n')
    ok("the dotfile provides it -> REACHABLE despite the same noise",
       sh(f'movian_sdk_probe "{bindir}" interactive', home).stdout.strip(),
       "REACHABLE")

    # And the verdict is the only thing on stdout: a caller parsing it must not
    # have to strip the host's or the user's chatter.
    r = sh(f'movian_sdk_probe "{bindir}" interactive', home)
    ok("stdout carries the verdict and nothing else",
       r.stdout.strip().splitlines(), ["REACHABLE"])


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

    # Positive control. Without it this case would pass on a fixture where the
    # ~/.bashrc is never sourced at all -- proving nothing about quoting and
    # everything about the harness. The same payload written UNQUOTED must fire.
    control = pathlib.Path(tmp) / "CONTROL"
    (home / ".bashrc").write_text(f'x=$(touch {control})\n')
    subprocess.run(["/bin/bash", "-ic", "true"],
                   env={"HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb"},
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, timeout=30)
    ok("the control DOES fire, so the fixture really is sourced",
       control.exists(), True)


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
    # Assert against a string the tree actually contains. The previous version
    # grepped for "an ordinary terminal answers", which no longer exists
    # anywhere after the diagnosis was rewritten -- so it compared False to
    # False and stayed green under the exact regression it names.
    ok("it does not claim the terminal shape is the broken one",
       "an ordinary terminal does not" in r.stderr, False)
    ok("the wrong-way-round sentence is a real string in lib/reachable.sh",
       "an ordinary terminal does not" in LIB.read_text(), True)


def case_a_backup_is_taken_before_the_first_edit(tmp):
    print("the user's startup file is backed up, and a symlink stays a symlink")
    home, bindir = fixture(tmp)
    real = pathlib.Path(tmp) / "dotfiles-bashrc"
    shutil.move(str(home / ".bashrc"), real)
    (home / ".bashrc").symlink_to(real)          # as stow/chezmoi would leave it
    before = real.read_text()
    sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{bindir}" apply', home)
    baks = sorted(home.glob(".bashrc.movian-sdk.bak-*"))
    ok("a backup was taken", len(baks), 1)
    ok("backup holds the original", baks[0].read_text() == before, True)
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


# --- cases added from the Orca orchestration review (run_255978bddcf3) --------

def case_a_probe_that_never_launched_is_undetermined(tmp):
    """Exit 125/126/127 mean the probe never ran -- that is not a verdict.

    `env` resolves `timeout` and `timeout` resolves `bash` along the SCRUBBED
    PATH, so when the bindir is the only entry there is nothing left to run.
    That used to fall into the catch-all arm and print UNREACHABLE: a confident
    statement about a measurement that never happened, which is the exact defect
    class this file exists to prevent.
    """
    print("a probe that never launched is UNDETERMINED, not UNREACHABLE")
    home, bindir = fixture(tmp)
    (home / ".bashrc").write_text(f'PATH="{bindir}:$PATH"\n')

    # No usable PATH for the probe's own tools once the bindir is scrubbed out.
    ok("cannot launch -> UNDETERMINED",
       sh(f'movian_sdk_probe "{bindir}" interactive', home,
          extra_env={"PATH": str(bindir)}).stdout.strip(),
       "UNDETERMINED")

    # Two guards cover this between them -- an early return when the probe's own
    # tools are unreachable, and the 125/126/127 arm for a launch that fails
    # some other way. Either alone still yields UNDETERMINED, so the mutant has
    # to remove both to show what the pair is preventing.
    mutant = mutate_lib(tmp, "    125|126|127) printf 'UNDETERMINED\\n' ;;", "")
    mutant2 = pathlib.Path(tmp) / "mutant-nolaunch-guard.sh"
    mutant2.write_text(mutant.read_text().replace(
        "    printf 'UNDETERMINED\\n'\n    return 0\n  fi", "    :\n  fi", 1))
    ok("with neither guard it degrades to a false UNREACHABLE",
       sh(f'movian_sdk_probe "{bindir}" interactive', home, lib=mutant2,
          extra_env={"PATH": str(bindir)}).stdout.strip(),
       "UNREACHABLE")


def case_bindir_must_be_absolute(tmp):
    """A relative bindir in ~/.bashrc is a PATH hijack, so it is refused.

    `--fix-path` writes the bindir into ~/.bashrc, where a relative entry lands
    at the FRONT of PATH in every shell and resolves against whatever directory
    the user is in -- so `./mybin/git` in any checked-out repository would run
    instead of git. install.sh demanded an absolute path for the core and none
    for the bindir, which is the more dangerous of the two.
    """
    print("a relative bindir is refused before it reaches any file")
    home, _ = fixture(tmp)
    r = sh('movian_sdk_normalise_bindir "mybin" || echo REFUSED', home)
    ok("refused", "REFUSED" in r.stdout, True)
    ok("and says why", "absolute path" in r.stderr, True)

    # install.sh must refuse too, before it creates directories or edits files.
    workdir = pathlib.Path(tmp) / "cwd"; workdir.mkdir()
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb",
           "MOVIAN_SDK_BINDIR": "mybin",
           "MOVIAN_SDK_LIBDIR": str(home / ".local/lib/movian-sdk"),
           "MOVIAN_SDK_CONFIG": str(home / ".config/movian-sdk/config.json")}
    before = (home / ".bashrc").read_text()
    r = subprocess.run(["/bin/bash", str(INSTALLER), "--fix-path"], env=env, cwd=workdir,
                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, timeout=120)
    ok("install.sh exits non-zero", r.returncode != 0, True)
    ok("and wrote nothing to ~/.bashrc", (home / ".bashrc").read_text() == before, True)
    ok("and created no relative bindir", (workdir / "mybin").exists(), False)


def case_bindir_spelling_does_not_change_the_verdict(tmp):
    """One directory, one answer, however it is spelled.

    The scrub and the `$bindir/mdev` comparison are both textual, so a trailing
    slash used to make a WORKING install report UNREACHABLE -- and `mdev doctor`
    report a permanent MISMATCH for the same reason.
    """
    print("a trailing slash is the same directory, and gets the same verdict")
    home, bindir = fixture(tmp)
    sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{bindir}" apply', home)
    verdicts = set()
    for spelling in (f"{bindir}", f"{bindir}/", f"{bindir}//", str(bindir).replace("/.local", "//.local")):
        r = sh(f'movian_sdk_probe "$(movian_sdk_normalise_bindir "{spelling}")" interactive', home)
        verdicts.add(r.stdout.strip())
    ok("every spelling agrees", sorted(verdicts), ["REACHABLE"])


def case_unwritable_config_does_not_abort_the_installer(tmp):
    """jq succeeds on a read-only config -- it writes to the temp file.

    The failure therefore landed on the unguarded `cat > "$config"`, and `set -e`
    aborted the script from INSIDE the branch meant to report honestly: no
    WARNING, no reachability report, and the temp file left behind.
    """
    print("a read-only config warns, and the installer still finishes")
    home, bindir = fixture(tmp, with_mdev=False)
    cfg = home / ".config" / "movian-sdk" / "config.json"
    cfg.write_text('{"core": "/some/core"}\n')
    cfg.chmod(0o444)
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb",
           "MOVIAN_SDK_BINDIR": str(bindir),
           "MOVIAN_SDK_LIBDIR": str(home / ".local/lib/movian-sdk"),
           "MOVIAN_SDK_CONFIG": str(cfg)}
    r = subprocess.run(["/bin/bash", str(INSTALLER)], env=env, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                       timeout=120)
    cfg.chmod(0o644)
    ok("it warns", "could not record bin" in r.stdout, True)
    ok("it does not claim success", "recorded bin ->" in r.stdout, False)
    ok("it still reports reachability", "reachable: login" in r.stdout, True)
    ok("and does not gate", r.returncode, 0)


def case_diagnosis_claims_nothing_about_an_unmeasured_shape(tmp):
    """An UNDETERMINED shape was never measured, so nothing may be said of it."""
    print("the diagnosis makes no claim about a shape it could not measure")
    home, bindir = fixture(tmp)
    r = sh(f'MOVIAN_SDK_REACH_LOGIN=UNDETERMINED\n'
           f'MOVIAN_SDK_REACH_INTERACTIVE=UNREACHABLE\n'
           f'movian_sdk_explain_unreachable "{bindir}" "" UNREACHABLE', home)
    ok("it says the login shape was not measured",
       "LOGIN shape could not be measured" in r.stderr, True)
    ok("and does not assert login works",
       "a login shell finds it" in r.stderr, False)


def case_every_edit_is_backed_up(tmp):
    """A single fixed backup name protected only the first edit."""
    print("each modification takes its own backup, and a no-op takes none")
    home, bindir = fixture(tmp)
    sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{bindir}" remove', home)
    ok("a no-op remove takes no backup", len(list(home.glob(".bashrc.movian-sdk.bak-*"))), 0)
    sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{bindir}" apply', home)
    sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{bindir}" remove', home)
    ok("two real edits, two backups", len(list(home.glob(".bashrc.movian-sdk.bak-*"))), 2)

    # Both halves are load-bearing: a fixed name, or a timestamp without the
    # uniquifier, silently collapses an apply+remove pair inside one second back
    # onto a single file -- and the pre-apply original is the one that is lost.
    mutant = mutate_lib(tmp, 'backup="$rc_file.movian-sdk.bak-$(date +%Y%m%d%H%M%S)"',
                        'backup="$rc_file.movian-sdk.bak-fixed"')
    collapsed = pathlib.Path(tmp) / "mutant-nouniq.sh"
    collapsed.write_text(mutant.read_text().replace(
        '  if [ -e "$backup" ]; then', "  if false; then", 1))
    second = pathlib.Path(tmp) / "second"; second.mkdir(exist_ok=True)
    home2, bindir2 = fixture(str(second))
    sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{bindir2}" apply', home2, lib=collapsed)
    sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{bindir2}" remove', home2, lib=collapsed)
    ok("without both, the two edits share one backup",
       len(list(home2.glob(".bashrc.movian-sdk.bak*"))), 1)


def case_a_large_bashrc_still_gets_fixed(tmp):
    """`grep -q` closes the pipe and `printf` takes SIGPIPE; pipefail then lies.

    It only showed on a file big enough that printf was still writing when grep
    left: an 89KiB ~/.bashrc refused the fix as "no interactive guard" and
    aborted the install, while a stock 3.5KiB one was fine.
    """
    print("a large ~/.bashrc does not fake a missing guard")
    home, bindir = fixture(tmp)
    # Past the 64KiB pipe buffer on purpose: below it `printf` finishes writing
    # before `grep -q` exits, no SIGPIPE is raised, and the bug hides.
    big = (home / ".bashrc").read_text() + ("# padding to exceed the pipe buffer\n" * 3000)
    assert len(big) > 64 * 1024, "fixture must exceed the pipe buffer to exercise SIGPIPE"
    (home / ".bashrc").write_text(big)
    r = sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{bindir}" apply', home)
    ok("the fix applies", (home / ".bashrc").read_text().count(BEGIN), 1)
    ok("and does not claim the guard is missing", "no interactive guard" in r.stderr, False)


def case_path_scrub_does_not_glob(tmp):
    """An unquoted $PATH expansion is subject to pathname expansion."""
    print("a PATH entry containing a glob is not expanded away")
    home, _ = fixture(tmp)
    r = sh('PATH="/usr/bin:/tmp/*:/bin"; movian_sdk_path_without /bin', home)
    ok("the glob survives verbatim", r.stdout.strip(), "/usr/bin:/tmp/*")


def case_the_seven_preambles_are_identical(tmp):
    """Nothing bound the seven copies together, so they could drift apart."""
    print("all seven skill preambles are byte-identical")
    skills = HERE.parent / "plugins" / "movian" / "skills"
    blocks = {}
    for skill in sorted(p for p in skills.iterdir() if (p / "SKILL.md").is_file()):
        text = (skill / "SKILL.md").read_text()
        start = text.find("> **Resolving `mdev` first.**")
        if start < 0:
            continue
        end = text.find("\n\n", text.find("stay identical", start))
        blocks[skill.name] = text[start:end]
    ok("every skill carries one", len(blocks), 7)
    ok("and they are all the same", len(set(blocks.values())), 1)


def case_the_vendored_skel_matches_the_distribution(tmp):
    """The embedded dotfiles must stay what Debian actually ships.

    Vendoring is what lets this suite run anywhere; it must not become licence
    to invent. Where /etc/skel exists, the copies are compared byte for byte, so
    a divergence is a failure rather than a silent drift into fiction. Where it
    does not exist, this case says so plainly instead of passing quietly.
    """
    print("the vendored skel is the distribution's, not an invention")
    if not (SKEL / ".bashrc").is_file():
        print(f"  note  {SKEL}/.bashrc absent -- fidelity unverifiable on this host,")
        print("        the other cases still run against the vendored copy")
        return
    ok("vendored .bashrc matches /etc/skel",
       (SKEL / ".bashrc").read_text() == SKEL_BASHRC, True)
    ok("vendored .profile matches /etc/skel",
       (SKEL / ".profile").read_text() == SKEL_PROFILE, True)
    # The properties the rest of the suite leans on, asserted rather than assumed.
    ok(".bashrc carries the interactive guard", GUARD in SKEL_BASHRC, True)
    ok(".profile adds ~/.local/bin", '"$HOME/.local/bin"' in SKEL_PROFILE, True)
    ok(".bashrc does NOT add it -- the whole point of #34",
       "$HOME/.local/bin" in SKEL_BASHRC, False)


# --- cases from the GPT-5.6-Luna review round --------------------------------

def case_a_colon_in_the_bindir_is_refused(tmp):
    """PATH is colon-separated, so such a directory cannot be represented in it."""
    print("a bindir containing ':' is refused, not silently misread")
    home, _ = fixture(tmp)
    r = sh('movian_sdk_normalise_bindir "/opt/a:b/bin" || echo REFUSED', home)
    ok("refused", "REFUSED" in r.stdout, True)
    ok("and says why", "separates PATH entries" in r.stderr, True)


def case_marker_whitespace_is_not_damage(tmp):
    """Trailing whitespace on a marker is an editor artefact, not corruption.

    Matching markers exactly made an intact block look half-open, so the
    data-loss guard refused every edit -- a false positive on the one check
    whose whole job is to prevent data loss.
    """
    print("a marker with trailing whitespace is still a valid marker")
    home, bindir = fixture(tmp)
    before = (home / ".bashrc").read_text()
    sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{bindir}" apply', home)
    text = (home / ".bashrc").read_text()
    (home / ".bashrc").write_text(text.replace(END + "\n", END + "   \n"))
    r = sh(f'movian_sdk_fix_path "$HOME/.bashrc" "{bindir}" remove', home)
    ok("removal is not refused", "are damaged" in r.stderr, False)
    ok("the block is gone", BEGIN in (home / ".bashrc").read_text(), False)
    ok("and the rest of the file survived",
       (home / ".bashrc").read_text() == before, True)


def case_diagnosis_without_a_prior_report_says_so(tmp):
    """Unmeasured is not unreachable, even when the function is called alone."""
    print("called with no measurement, the diagnosis states that instead of guessing")
    home, _ = fixture(tmp)
    r = sh('movian_sdk_explain_unreachable /opt/bin "" UNREACHABLE', home)
    ok("it says nothing was measured",
       "no per-shape measurement is available" in r.stderr, True)
    ok("and invents no verdict about login",
       "a login shell finds it" in r.stderr, False)
    ok("nor about the terminal shape",
       "an ordinary terminal does not" in r.stderr, False)


def case_a_shim_run_from_the_checkout_finds_its_library(tmp):
    """`./bin/mdev` is what a developer types; it used to die under $HOME.

    The library directory was assumed to live under ~/.local regardless of where
    the shim itself was, so a shim run straight from the checkout failed with a
    bare "No such file or directory" from the `source` line.
    """
    print("a shim run from the checkout derives its own library directory")
    shim = HERE.parent / "bin" / "mdev"
    env = {k: v for k, v in os.environ.items() if k != "MOVIAN_SDK_LIB"}
    env["HOME"] = "/nonexistent-home-for-this-case"
    r = subprocess.run(["/bin/bash", str(shim), "core"], env=env,
                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=True, timeout=60)
    ok("it does not die looking under $HOME",
       "No such file or directory" in r.stderr, False)


def case_doctor_is_the_second_caller(tmp):
    """"One check, two callers" (#38) -- and the second was never exercised.

    `mdev doctor` runs the same probe as install.sh and adds the bindir
    comparison that is the only honest signal available for the agent shape. No
    case invoked it, so half the contract was asserted by documentation alone.
    """
    print("mdev doctor runs the shared check and reports the recorded bindir")
    home, bindir = fixture(tmp)
    cfg = home / ".config" / "movian-sdk" / "config.json"
    cfg.write_text(json.dumps({"core": "/nonexistent/core", "bin": str(bindir)}) + "\n")

    shim = HERE.parent / "bin" / "mdev"
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb",
           "MOVIAN_SDK_CONFIG": str(cfg),
           "MOVIAN_SDK_LIB": str(HERE.parent / "lib")}
    r = subprocess.run(["/bin/bash", str(shim), "doctor"], env=env,
                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, timeout=120)
    # The core is deliberately absent, so doctor stops at the locator -- which is
    # itself the assertion that reachability is NOT what gates it.
    ok("it fails on the missing core, not on reachability",
       "locator: UNRESOLVED" in r.stdout or "movian-sdk:" in r.stdout, True)

    # With a usable core it reaches the reachability block. Only run this half
    # where a real core is configured; otherwise say so rather than skip quietly.
    real = pathlib.Path.home() / ".config" / "movian-sdk" / "config.json"
    if not real.is_file():
        print("  note  no core configured on this host -- the reachability half of")
        print("        doctor is not exercised here")
        return
    r = subprocess.run(["/bin/bash", str(shim), "doctor"],
                       env={**os.environ, "MOVIAN_SDK_LIB": str(HERE.parent / "lib")},
                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, timeout=180)
    ok("doctor reports the bindir", "bindir:" in r.stdout, True)
    ok("and runs the same shared probe", "reachable: login" in r.stdout, True)


# --- from a real install on a fresh Debian stand -----------------------------

def case_the_installing_shell_is_told_it_cannot_see_mdev(tmp):
    """PATH is inherited at exec time; installing cannot change a running shell.

    A user installed successfully, typed `mdev`, got `command not found`, and
    reasonably asked whether that was expected. It is -- but nothing said so, so
    a correct install read as a failed one. The notice is printed on every run,
    because it is true regardless of the reachability verdict, and an
    UNDETERMINED probe is precisely when the reader is left guessing.
    """
    print("the installing shell is told why it cannot see mdev yet")
    home, bindir = fixture(tmp, with_mdev=False)
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb",
           "MOVIAN_SDK_BINDIR": str(bindir),
           "MOVIAN_SDK_LIBDIR": str(home / ".local/lib/movian-sdk"),
           "MOVIAN_SDK_CONFIG": str(home / ".config/movian-sdk/config.json")}
    r = subprocess.run(["/bin/bash", str(INSTALLER)], env=env, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                       timeout=180)
    ok("it says this shell will not see it", "This shell will NOT see mdev" in r.stdout, True)
    ok("and that this is not a failure", "not a failed install" in r.stdout, True)
    ok("and how to get a shell that does", 'exec "$SHELL" -l' in r.stdout, True)

    # And it stays quiet when the bindir IS already on the caller's PATH, so the
    # notice cannot become boilerplate people learn to skip.
    env["PATH"] = f"{bindir}:/usr/bin:/bin"
    r = subprocess.run(["/bin/bash", str(INSTALLER)], env=env, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                       timeout=180)
    ok("silent when the shell can already see it",
       "This shell will NOT see mdev" in r.stdout, False)


def case_undetermined_still_offers_the_remedy(tmp):
    """A failed measurement must not withhold the fix.

    On a machine whose ~/.bashrc takes longer than the probe budget, the
    interactive shape came back UNDETERMINED and the diagnosis said only "rerun,
    or check your ~/.bashrc" -- withholding `--fix-path` from the one reader who
    could not tell whether they needed it. Unmeasured and broken look identical
    from the outside, and the remedy is the same either way.
    """
    print("an unmeasurable shape still names the remedy and how to measure")
    home, bindir = fixture(tmp)
    marker = wedge_marker(home)
    (home / ".bashrc").write_text(f"{marker}\n")
    r = sh(f'movian_sdk_reachability_report "{bindir}"\n'
           f'movian_sdk_explain_unreachable "{bindir}" "/repo" "$MOVIAN_SDK_REACH_WORST"',
           home, extra_env={"MOVIAN_SDK_PROBE_TIMEOUT": "3"}, timeout=60)
    kill_survivors(marker)
    ok("the shape is UNDETERMINED", "interactive    UNDETERMINED" in r.stdout, True)
    ok("it names the budget that was exceeded", "within 3s" in r.stderr, True)
    ok("it says how to time your own startup", "time bash -ic true" in r.stderr, True)
    ok("it names the override", "MOVIAN_SDK_PROBE_TIMEOUT" in r.stderr, True)
    ok("and it still offers --fix-path", "--fix-path" in r.stderr, True)


def main():
    # No SKIP path. The suite used to return success when /etc/skel was absent,
    # so on a minimal container or a non-Debian host it reported OK without
    # exercising a single line of the implementation -- a vacuous pass, which is
    # worse than a failure because it looks like coverage. The skel content is
    # vendored above instead, and its fidelity is itself a case.
    cases = [
        case_reproduces_34,
        case_block_makes_it_reachable,
        case_idempotent_in_the_file,
        case_bindir_change_leaves_nothing_stale,
        case_removal_is_an_exact_inverse,
        case_missing_anchor_refuses,
        case_unscrubbed_path_would_lie,
        case_a_reading_bashrc_is_undetermined,
        case_host_noise_does_not_reach_the_verdict,
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
        # from the Orca orchestration review
        case_a_probe_that_never_launched_is_undetermined,
        case_bindir_must_be_absolute,
        case_bindir_spelling_does_not_change_the_verdict,
        case_unwritable_config_does_not_abort_the_installer,
        case_diagnosis_claims_nothing_about_an_unmeasured_shape,
        case_every_edit_is_backed_up,
        case_a_large_bashrc_still_gets_fixed,
        case_path_scrub_does_not_glob,
        case_the_seven_preambles_are_identical,
        case_the_vendored_skel_matches_the_distribution,
        # from the GPT-5.6-Luna review round
        case_a_colon_in_the_bindir_is_refused,
        case_marker_whitespace_is_not_damage,
        case_diagnosis_without_a_prior_report_says_so,
        case_a_shim_run_from_the_checkout_finds_its_library,
        case_doctor_is_the_second_caller,
        # from a real install on a fresh Debian stand
        case_the_installing_shell_is_told_it_cannot_see_mdev,
        case_undetermined_still_offers_the_remedy,
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
