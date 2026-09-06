# Debian's `~/.profile`, `~/.bashrc`, and how `~/.local/bin` reaches PATH

> **Point-in-time survey — read the ticket that consumes it, not this, for current rules.**
> Investigated on the date stated below against the distribution images as they then stood.
> It is a measurement record behind the shim-reachability contract
> [#35](https://github.com/Buksa/movian-plugin-sdk/issues/35), not a substitute for whatever
> that map decides. **Where the two disagree the map wins.** This file establishes facts; it
> decides nothing and fixes nothing.
> Distribution dotfiles are `dpkg` conffiles and can change in a stable release via a point
> update. Every hash below is pinned to an image digest recorded in §8 — re-measure before
> trusting a hash rather than a shape.

Research for [issue #37](https://github.com/Buksa/movian-plugin-sdk/issues/37),
part of the shim-reachability map [#35](https://github.com/Buksa/movian-plugin-sdk/issues/35).
Investigated 2026-08-28.

**Sources.** Three kinds, marked on every claim:

- **[MEASURED]** — run on this machine against a real distribution image or a real man page
  extracted from one. Docker was used **as an evidence-gathering tool only**; nothing here
  proposes a container as a test dependency (#35 forbids that, and this file respects it).
  The exact commands are in §8.
- **[PRIMARY]** — fetched from the document that owns the claim: a man page shipped by the
  package, an upstream specification, the Debian BTS, the Debian archive's own changelog.
- **[BELIEVED]** — reasoning not backed by either of the above. Used sparingly and always
  labelled. **Nothing in §0–§5 is [BELIEVED] unless it says so.**

---

## 0. Headline answers

1. `/etc/skel/.profile` and `/etc/skel/.bashrc` on Debian are shipped by the **`bash`**
   package, not `base-files`. Both are dpkg **conffiles**. [MEASURED]
2. Debian ships **`.profile`**, not `.bash_profile`. There is no `/etc/skel/.bash_profile`.
   [MEASURED]
3. `~/.local/bin` is added **only** by `~/.profile`, lines 24–27, behind an
   `if [ -d "$HOME/.local/bin" ]` guard. Debian's `~/.bashrc` contains **no** PATH assignment
   of any kind. [MEASURED]
4. The stanza first appears in **Debian 10 (buster)**. Debian 9 (stretch) and 8 (jessie) do
   not have it. On Ubuntu it appears earlier — **16.04 (xenial)** — but in a *different,
   unguarded* form. [MEASURED]
5. `/etc/skel/.bashrc`'s non-interactive guard sits at **lines 5–9**. An append at
   end-of-file is **not** dead code for any interactive shell, which is the case #34 is
   about. It **is** dead for `ssh host 'mdev …'`. [MEASURED]
6. **No dotfile placement reaches a plain local `bash -c`.** That shape reads neither
   `~/.profile` nor `~/.bashrc`. Since #35 states the primary user is an agent running
   non-interactive shells, this is the finding with the widest consequences. [MEASURED]
7. `~/.config/environment.d/` covers **only** processes started by the systemd *user* service
   manager. Its own man page says ssh logins are excluded. `/etc/profile.d/` covers login
   shells only. `~/.pam_environment` is off by default since Linux-PAM 1.4.0 and deprecated
   since 1.5.0, and Debian 13 does not enable it. **None of the three is a better-behaved
   target than the dotfile.** [PRIMARY + MEASURED]
8. Five things contradict or sharpen the premise in #34. They are in §7.

---

## 1. `/etc/skel/.profile` — exact contents

**Debian 13 (trixie), `bash` 5.2.37-2+b9, 807 bytes, 27 lines.** [MEASURED]
Reproduced verbatim with line numbers, because the line numbers matter to §3 and §7:

```
 1  # ~/.profile: executed by the command interpreter for login shells.
 2  # This file is not read by bash(1), if ~/.bash_profile or ~/.bash_login
 3  # exists.
 4  # see /usr/share/doc/bash/examples/startup-files for examples.
 5  # the files are located in the bash-doc package.
 6
 7  # the default umask is set in /etc/profile; for setting the umask
 8  # for ssh logins, install and configure the libpam-umask package.
 9  #umask 022
10
11  # if running bash
12  if [ -n "$BASH_VERSION" ]; then
13      # include .bashrc if it exists
14      if [ -f "$HOME/.bashrc" ]; then
15  	. "$HOME/.bashrc"
16      fi
17  fi
18
19  # set PATH so it includes user's private bin if it exists
20  if [ -d "$HOME/bin" ] ; then
21      PATH="$HOME/bin:$PATH"
22  fi
23
24  # set PATH so it includes user's private bin if it exists
25  if [ -d "$HOME/.local/bin" ] ; then
26      PATH="$HOME/.local/bin:$PATH"
27  fi
```

(Lines 15 and 21/26 are indented with a literal tab and four spaces respectively, exactly as
shown. The file ends at line 27 with a trailing newline.)

Four facts a synthetic fixture must preserve: [MEASURED]

- **The `~/.local/bin` stanza is last** (lines 24–27), *after* the `~/bin` stanza.
- **It is guarded by `if [ -d "$HOME/.local/bin" ]`.** If the directory does not exist when
  the login shell starts, nothing is added — and nothing re-checks later in that session.
- **`~/.bashrc` is sourced at line 15, before either PATH stanza.** Anything a user appends
  to `~/.bashrc` therefore runs *before* `.profile` prepends `~/.local/bin`. This is the
  mechanism behind the duplicate-PATH result in §5.
- **`PATH` is never `export`ed here.** It does not need to be — `/etc/profile` line 9 already
  exported it (see §4.2) — but a fixture that starts from an unexported PATH will not
  reproduce Debian.

### 1.1 Which package ships it

```
$ dpkg -S /etc/skel/.profile
bash: /etc/skel/.profile
$ dpkg -S /etc/skel/.bashrc
bash: /etc/skel/.bashrc
```

**`bash`, not `base-files`.** [MEASURED, Debian 8/9/10/11/12/13 and Ubuntu 14.04–24.04 — the
answer is `bash` on every one.] Both files are listed as conffiles in `/var/lib/dpkg/status`
under the `bash` package, so a local edit survives upgrades and shows up in `dpkg --verify`.
[MEASURED]

This matters for provenance: the release in which the stanza appeared is a `bash` package
version, and the changelog to cite is `bash`'s (§2), not `base-files`'.

`base-files` ships `/etc/profile` — the *system-wide* login file, which is a different file
and does **not** mention `~/.local/bin` (§4.2). [MEASURED]

### 1.2 `.profile`, not `.bash_profile` — and why that is load-bearing

`/etc/skel/` on Debian 13 contains exactly `.bash_logout`, `.bashrc`, `.profile`. There is no
`.bash_profile` and no `.bash_login`. [MEASURED]

bash(1), Debian 13, `bash` 5.2.37-2, INVOCATION: [PRIMARY — extracted from the man page
shipped by the package]

> When bash is invoked as an interactive login shell, or as a non-interactive shell with the
> `--login` option, it first reads and executes commands from the file `/etc/profile`, if that
> file exists. After reading that file, it looks for `~/.bash_profile`, `~/.bash_login`, and
> `~/.profile`, in that order, and reads and executes commands from the **first one that
> exists and is readable**.

So `~/.profile` is read only when the user has neither `~/.bash_profile` nor `~/.bash_login`.
Measured consequence: with a `~/.bash_profile` present, a login shell does **not** read
`~/.profile`, and `~/.local/bin` is on PATH in *no* shell shape at all. [MEASURED — §7.4]

### 1.3 `~/.bashrc` has no equivalent stanza

`grep -rn "local/bin" /etc/skel/` on Debian 13 returns exactly two lines, both in `.profile`
(25 and 26). `/etc/skel/.bashrc` contains no `PATH=` assignment anywhere in its 113 lines.
[MEASURED]

Same result on Debian 8, 9, 10, 11, 12, 13 and Ubuntu 14.04, 16.04, 18.04, 20.04, 22.04,
24.04: **no Debian- or Ubuntu-shipped `~/.bashrc` has ever put `~/.local/bin` on PATH.**
[MEASURED]

---

## 2. Since when — bounded release claims

### 2.1 The Debian changelog entry

From the Debian archive's own changelog for `bash` 5.2.37-2: [PRIMARY —
`metadata.ftp-master.debian.org/changelogs/main/b/bash/bash_5.2.37-2_changelog`]

```
bash (4.4.18-1) unstable; urgency=medium

  * bash 4.4.18 release (bash 4.4 patchlevel 18).
  ...
  * skel.profile: Add $HOME/.local/bin if it exists. Closes: #839155.
  ...

 -- Matthias Klose <doko@debian.org>  Tue, 06 Feb 2018 12:20:45 +0100
```

Debian bug **#839155**, *"bash: $HOME/.local/bin missing from $PATH again"*, filed
2016-09-29, fixed in `bash/4.4.18-1`. [PRIMARY — Debian BTS] Its predecessor **#820856**,
*"bash: Please add ~/.local/bin to the default $PATH"*, filed 2016-04-13, asked for it
originally, citing `pip install --user` and Fedora's precedent. [PRIMARY — Debian BTS]

Note the "again" in #839155's title: the directory was added once, lost, and added back in
the guarded form. The BTS records #820856 as fixed in `bash/4.3-15`, but **no `4.3-15` exists
in the Debian changelog** — it goes `4.3-14` → `4.4~beta-1`. [MEASURED against the changelog]
The safest reading is that the pre-4.4.18 attempt never reached a Debian stable release; the
release table below is measured directly and does not depend on resolving this. [BELIEVED]

### 2.2 Measured release table

Every row is `grep -rn "local/bin" /etc/skel/` inside the official image. [MEASURED]

| Release | `bash` version | `~/.local/bin` in `/etc/skel/.profile`? | Form |
|---|---|---|---|
| Debian 8 jessie | 4.3-11+deb8u2 | **no** | — |
| Debian 9 stretch | 4.4-5 | **no** | — |
| Debian 10 buster | 5.0-4 | **yes** | `if [ -d ]` guarded, lines 24–27 |
| Debian 11 bullseye | 5.1-2+deb11u1 | **yes** | identical |
| Debian 12 bookworm | 5.2.15-2+b13 | **yes** | identical |
| Debian 13 trixie | 5.2.37-2+b9 | **yes** | identical |
| Ubuntu 14.04 trusty | 4.3-7ubuntu1.7 | **no** | — |
| Ubuntu 16.04 xenial | 4.3-14ubuntu1.4 | **yes** | **unguarded**, see below |
| Ubuntu 18.04 bionic | 4.4.18-2ubuntu1.3 | **yes** | `if [ -d ]` guarded, lines 24–27 |
| Ubuntu 20.04 focal | 5.0-6ubuntu1.2 | **yes** | identical |
| Ubuntu 22.04 jammy | 5.1-6ubuntu1.1 | **yes** | identical |
| Ubuntu 24.04 noble | 5.2.21-2ubuntu4 | **yes** | identical |

**So "a fresh Debian machine has `~/.local/bin` in `~/.profile`" is true for buster (2019)
and later, and false for stretch and earlier.** For the SDK's purposes that is every
supported Debian, but the claim should be written as "Debian 10+ / Ubuntu 18.04+" rather than
"Debian".

**Ubuntu 16.04 is the one that breaks the pattern.** Its `/etc/skel/.profile` is 20 lines and
its last line is: [MEASURED]

```
PATH="$HOME/bin:$HOME/.local/bin:$PATH"
```

Unconditional, both directories in one assignment, **no `if [ -d ]` guard**. A test fixture
that only ever writes Debian's guarded form is not modelling xenial. Xenial is out of
standard support, so this is documented as a boundary rather than a case to cover. [BELIEVED
— the support judgement, not the measurement]

### 2.3 Byte-identity across releases — useful for a fixture

Debian 10 through Debian 13 ship a **byte-identical** `/etc/skel/.profile`, and Debian 9
through Debian 13 a byte-identical `/etc/skel/.bashrc`. [MEASURED]

| File | md5 | Releases sharing it |
|---|---|---|
| `.profile` (807 B, 27 lines) | `f4e81ade7d6f9fb342541152d08e7a97` | Debian 10, 11, 12, 13; Ubuntu 18.04, 20.04, 22.04, 24.04 |
| `.profile` (675 B, 22 lines) | `ecb6d3479ac3823f1da7f314d871989b` | Debian 8, 9 |
| `.profile` (20 lines) | `905f748ceda81747600e9a593b42f3e4` | Ubuntu 16.04 |
| `.bashrc` (3526 B, 113 lines) | `ee35a240758f374832e809ae0ea4883a` | Debian 9, 10, 11, 12, 13 |
| `.bashrc` (117 lines) | `1f98b8f3f3c8f8927eca945d59dcc1c6` | Ubuntu 16.04, 18.04, 20.04, 22.04, 24.04 |
| `.bashrc` (114 lines) | `f110abe5b3cfd324c2e5128eb4733879` | Ubuntu 14.04 |
| `.bashrc` | `e62ae447bdd228160f1f0b6bab8a7fd3` | Debian 8 |

sha256 for the trixie pair, for a fixture that wants a stronger pin: [MEASURED]

```
28b4a453b68dde64f814e94bab14ee651f4f162e15dd9920490aa1d49f05d2a4  /etc/skel/.profile
afae8986f549c6403410e029f9cce7983311512d04b1f02af02e4ce0af0dd2bf  /etc/skel/.bashrc
```

**One `.profile` and one `.bashrc` cover Debian 10–13 and Ubuntu 18.04–24.04.** A test does
not need a matrix; it needs one faithful pair. That is the fact #40 most needs.

### 2.4 A release where `~/.bashrc` *does* add it: Fedora

Fedora 42, `/etc/skel/.bashrc`, shipped by `bash-5.2.37-1.fc42`: [MEASURED]

```
 1  # .bashrc
 2
 3  # Source global definitions
 4  if [ -f /etc/bashrc ]; then
 5      . /etc/bashrc
 6  fi
 7
 8  # User specific environment
 9  if ! [[ "$PATH" =~ "$HOME/.local/bin:$HOME/bin:" ]]; then
10      PATH="$HOME/.local/bin:$HOME/bin:$PATH"
11  fi
12  export PATH
...
18  if [ -d ~/.bashrc.d ]; then
```

Three differences from Debian that are worth naming because they are the shape Debian *could*
have had: [MEASURED]

- The PATH line is **in `.bashrc`**, so it covers non-login interactive shells natively.
- There is **no interactive guard at all** in Fedora's `.bashrc`, so the line also runs in the
  ssh-non-interactive case of §3.2.
- Fedora ships `~/.bashrc.d/` — a **per-user drop-in directory**. Debian has no equivalent, in
  either `~/.bashrc` or `/etc/bash.bashrc`. [MEASURED — §4.2]
- Fedora ships `/etc/skel/.bash_profile`, not `.profile`, and it sources `~/.bashrc`.

---

## 3. `/etc/skel/.bashrc` — the guard, and where a line can go

### 3.1 The guard, verbatim, with its line numbers

Debian 13, `/etc/skel/.bashrc`, 3526 bytes, 113 lines. Lines 1–11: [MEASURED]

```
 1  # ~/.bashrc: executed by bash(1) for non-login shells.
 2  # see /usr/share/doc/bash/examples/startup-files (in the package bash-doc)
 3  # for examples
 4
 5  # If not running interactively, don't do anything
 6  case $- in
 7      *i*) ;;
 8        *) return;;
 9  esac
10
11  # don't put duplicate lines or lines starting with space in the history.
```

**What precedes it:** lines 1–3 are a three-line comment header, line 4 is blank. Nothing
executable runs before the guard.

**What follows it:** line 10 is blank; line 11 begins the history settings (`HISTCONTROL`,
`shopt -s histappend`, `HISTSIZE`, `HISTFILESIZE`), then `checkwinsize`, `lesspipe`,
`debian_chroot`, the `PS1` block, the xterm title block, `dircolors`/`ls` aliases,
`~/.bash_aliases`, and finally lines 104–113, the bash-completion block, which is the end of
the file:

```
104  # enable programmable completion features (you don't need to enable
105  # this, if it's already enabled in /etc/bash.bashrc and /etc/profile
106  # sources /etc/bash.bashrc).
107  if ! shopt -oq posix; then
108    if [ -f /usr/share/bash-completion/bash_completion ]; then
109      . /usr/share/bash-completion/bash_completion
110    elif [ -f /etc/bash_completion ]; then
111      . /etc/bash_completion
112    fi
113  fi
```

The guard is **byte-identical on Debian 8, 9, 10, 11, 12, 13 and Ubuntu 14.04 through 24.04** —
always at lines 5–9, always the same five lines. [MEASURED] It is the single most stable thing
in this survey and the right thing for a fixture to reproduce exactly.

### 3.2 Where a PATH line can go without being dead code

The honest answer has two halves, and #34's summary only states the first.

**For every interactive shell, an append at end-of-file is fine.** The `return` on line 8
fires only when `$-` lacks `i`, i.e. only for non-interactive shells — and a non-interactive
shell normally never reads `~/.bashrc` at all. So lines 10–113, and anything appended after
113, run in every interactive shell. Measured, with `~/.local/bin/mdev` present in a synthetic
`HOME` carrying stock skel files: [MEASURED]

| `~/.bashrc` | `bash -ic 'command -v mdev'` |
|---|---|
| stock | not found |
| stock + 3 lines appended at EOF | `$HOME/.local/bin/mdev` |

**For `ssh host 'mdev …'`, an EOF append is dead code.** bash(1) INVOCATION, Debian 13:
[PRIMARY]

> Bash attempts to determine when it is being run with its standard input connected to a
> network connection, as when executed by the historical remote shell daemon, usually rshd,
> or the secure shell daemon sshd. If bash determines it is being run non-interactively in
> this fashion, it reads and executes commands from `/etc/bash.bashrc` and `~/.bashrc`, if
> these files exist and are readable.

So in that one shape `~/.bashrc` *is* read non-interactively — and the guard on lines 5–9
returns on line 8 before reaching anything appended. Measured with a real `sshd` and a real
`ssh` inside the container: [MEASURED]

| `~/.bashrc` | `ssh localhost 'command -v mdev'` |
|---|---|
| stock | not found |
| + lines appended at EOF | **not found** |
| + lines appended at EOF, with a dedup guard | **not found** |
| + the same lines inserted **after line 4**, above the guard | `$HOME/.local/bin/mdev` |

**Therefore:** the insertion point that covers the shape #34 measured is *end of file*. The
insertion point that additionally covers `ssh host 'mdev …'` is *between line 4 and line 5*,
above the guard. The second costs a duplicate PATH entry in a non-login login shell (§5) and
means editing the middle of a dpkg conffile rather than appending to it.

---

## 4. Alternatives to editing a dotfile

### 4.1 `~/.config/environment.d/*.conf` (systemd)

environment.d(5), systemd 257.13 as shipped in Debian 13, APPLICABILITY section, verbatim:
[PRIMARY — extracted from the man page in the package]

> Environment variables exported by the user service manager (`systemd --user` instance
> started in the `user@uid.service` system service) are passed to any services started by that
> service manager. In particular, this may include services which run user shells. For example
> in the GNOME environment, the graphical terminal emulator runs as the
> `gnome-terminal-server.service` user unit, which in turn runs the user shell, so that shell
> will inherit environment variables exported by the user manager. **For other instances of
> the shell, not launched by the user service manager, the environment they inherit is defined
> by the program that starts them.**

> Note that these files do not affect the environment block of the service manager itself, but
> exclusively the environment blocks passed to the services it manages.

> **Specifically, for ssh logins, the sshd(8) service builds an environment that is a
> combination of variables forwarded from the remote system and defined by sshd** […]

Assessment:

| | |
|---|---|
| Covers | shells descended from `systemd --user` — i.e. a graphical terminal emulator on a systemd desktop |
| Does **not** cover | ssh sessions (stated explicitly above), TTY logins, any shell launched by something outside the user manager, the user manager itself |
| Reaches a non-login non-interactive shell? | Only if that shell was itself started by the user manager. A `bash -c` spawned by an agent process that was not is unaffected. |
| Needs re-login / reload? | The generator runs when the user manager starts. Changing a file needs `systemctl --user daemon-reload` at minimum, and in practice a new session, because already-running services keep their old environment block. [BELIEVED — the man page does not state a reload procedure; the "does not affect the service manager itself" paragraph implies it] |
| Fits this repo? | **No.** WSL, which #35 counts as Linux, frequently has no `systemd --user` at all. And the map's stated primary user is an agent, precisely the "launched by something else" case. |

`PATH=` in `environment.d` is also syntactically limited: the man page's own example is
`PATH=/opt/foo/bin:$PATH`, and it says "No other elements of shell syntax are supported" —
there is no `if [ -d ]`, so the guard behaviour of §1 cannot be reproduced. [PRIMARY]

### 4.2 `/etc/profile.d/*.sh`

`/etc/profile` on Debian 13, shipped by `base-files`, in full: [MEASURED]

```
# /etc/profile: system-wide .profile file for the Bourne shell (sh(1))
# and Bourne compatible shells (bash(1), ksh(1), ash(1), ...).

if [ "$(id -u)" -eq 0 ]; then
  PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
else
  PATH="/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games"
fi
export PATH
...
if [ -d /etc/profile.d ]; then
  for i in $(run-parts --list --regex '^[a-zA-Z0-9_][a-zA-Z0-9._-]*\.sh$' /etc/profile.d); do
    if [ -r $i ]; then
      . $i
    fi
  done
  unset i
fi
```

Assessment:

| | |
|---|---|
| Covers | **login shells only** — `/etc/profile` is read only by an interactive login shell or `bash --login`, per bash(1) INVOCATION (§1.2). Exactly the same coverage as `~/.profile`, which is the coverage that is already failing. |
| Does not cover | non-login interactive shells (the failing case), plain non-interactive shells |
| Needs root? | **Yes.** `install.sh` runs unprivileged and installs into `$HOME`. |
| Re-login? | Yes. |
| Fits this repo? | **No.** It needs root and it fixes nothing that `~/.profile` was not already doing. |

`/etc/profile.d/` is **empty** on a stock Debian 13. [MEASURED] Debian Policy §9.9 also warns
against relying on it: [PRIMARY — Debian Policy, *The Operating System*, §9.9 *Environment
variables*]

> Programs installed on the system PATH (`/bin`, `/usr/bin`, `/sbin`, `/usr/sbin`, or similar
> directories) must not depend on custom environment variable settings to get reasonable
> defaults. This is because such environment variables would have to be set in a system-wide
> configuration file such as a file in `/etc/profile.d`, **which is not supported by all
> shells**.

Debian Policy has **no section on a user's PATH**, and does not specify a default PATH value
for interactive users. [PRIMARY — searched ch-opersys; there is no such requirement] It is
worth recording the absence: the repo cannot cite Policy in support of any user-PATH claim,
because Policy does not make one.

The system-wide file that *does* cover non-login interactive shells is `/etc/bash.bashrc`
(read by bash for interactive non-login shells, per §6). But it carries the same class of
guard on **line 7** — `[ -z "${PS1-}" ] && return` — it is a `bash` conffile requiring root,
and Debian ships **no drop-in directory for it**. [MEASURED]

### 4.3 `~/.pam_environment` — deprecated, and off on Debian

pam_env(8), Linux-PAM as shipped in Debian 13, verbatim: [PRIMARY — extracted from the man
page in the package]

> **`user_readenv=0|1`**
> Turns on or off the reading of the user specific environment file. 0 is off, 1 is on. **By
> default this option is off** as user supplied environment variables in the PAM environment
> could affect behavior of subsequent modules in the stack without the consent of the system
> administrator.
>
> **Due to problematic security this functionality is deprecated since the 1.5.0 version and
> will be removed completely at some point in the future.**

Dates, from the Linux-PAM NEWS file and release tags: [PRIMARY]

- **1.4.0**, released **2020-06-08** — *"pam_env: Changed the default to not read the user
  `.pam_environment` file"*.
- **1.5.0**, released **2020-11-10** — *"pam_env: Reading of the user environment is
  deprecated and will be removed at some point in the future."*
- Not yet removed as of 1.7.2 (2026-01-22). [PRIMARY — NEWS through the current tag]

And on Debian 13 it is not merely defaulted off, it is not requested anywhere: [MEASURED]

```
$ grep -rn "pam_env" /etc/pam.d/
/etc/pam.d/login:51: session  required  pam_env.so readenv=1
/etc/pam.d/login:54: session  required  pam_env.so readenv=1 envfile=/etc/default/locale
/etc/pam.d/su:36:    session  required  pam_env.so readenv=1
/etc/pam.d/sshd:44:  session  required  pam_env.so
/etc/pam.d/sshd:47:  session  required  pam_env.so envfile=/etc/default/locale
```

Every occurrence uses `readenv` (which reads `/etc/environment`); **not one uses
`user_readenv`.** So `~/.pam_environment` is read by nothing on a stock Debian 13.

| | |
|---|---|
| Covers | nothing, on Debian 13 as shipped |
| Needs | a root edit to `/etc/pam.d/*` to add `user_readenv=1`, to enable a facility upstream has deprecated |
| Re-login? | Yes — PAM session setup only runs at login |
| Fits this repo? | **No.** Deprecated upstream, disabled by default, and disabled again by Debian's PAM configuration. |

`/etc/environment` *is* read (by `pam_env`'s `readenv=1`) and does reach every PAM session
including ssh — but it is root-owned, is a flat `KEY=VAL` file with no shell expansion, so it
cannot express `$HOME`, and is empty on a stock Debian 13. [MEASURED] It is not a viable
target for a per-user `$HOME/.local/bin`.

### 4.4 Summary

**No alternative is better-behaved than the dotfile for this problem.** Each either needs
root, or covers strictly less than `~/.bashrc` does, or is deprecated. The dotfile edit —
appending to `~/.bashrc` — remains the correct target, and its limits (§3.2, §5) are the real
limits of the fix, not an artefact of choosing the wrong file.

---

## 5. Measured behaviour of candidate edits

Method: a synthetic `HOME` with `/etc/skel/.profile` and `/etc/skel/.bashrc` copied in
verbatim and an executable at `$HOME/.local/bin/mdev`, driven with
`env -i HOME=… TERM=xterm PATH=/usr/local/bin:/usr/bin:/bin bash …` so nothing leaks from the
parent shell. This is exactly the container-free construction #40 needs; it was run inside a
container here only to guarantee stock dotfiles. [MEASURED]

Variants:

- **A** — Debian's own three lines appended at EOF of `~/.bashrc`:
  ```sh
  if [ -d "$HOME/.local/bin" ] ; then
      PATH="$HOME/.local/bin:$PATH"
  fi
  ```
- **B** — the same, with a dedup guard, appended at EOF:
  ```sh
  case ":$PATH:" in
      *":$HOME/.local/bin:"*) ;;
      *) PATH="$HOME/.local/bin:$PATH" ;;
  esac
  ```
- **C** — variant B's lines inserted **after line 4**, above the interactive guard.

**Reachability** (`command -v mdev`): [MEASURED]

| | `bash -lc` | `bash --login -ic` | `bash -ic` | `bash -c` | `ssh h 'cmd'` |
|---|---|---|---|---|---|
| stock skel | found | found | **not found** | **not found** | **not found** |
| A | found | found | found | **not found** | **not found** |
| B | found | found | found | **not found** | **not found** |
| C | found | found | found | **not found** | found |

**PATH copies of `~/.local/bin`**: [MEASURED]

| | `bash -lc` | `bash --login -ic` | `bash -ic` | `bash -c` |
|---|---|---|---|---|
| stock skel | 1 | 1 | 0 | 0 |
| A | 1 | **2** | 1 | 0 |
| B | 1 | **2** | 1 | 0 |
| C | **2** | **2** | 1 | 0 |

Three things follow, and the second is not obvious:

1. **`bash -c` is unreachable by any dotfile.** Every variant leaves it at 0. Confirmed
   directly: appending `echo BASHRC-WAS-READ >&2` to `~/.bashrc` and
   `echo PROFILE-WAS-READ >&2` to `~/.profile` produces no output at all from
   `env -i HOME=… bash -c true`. [MEASURED]

2. **The dedup guard does not prevent the duplicate in an interactive login shell — nothing
   in `~/.bashrc` can.** The order is: `~/.profile` line 15 sources `~/.bashrc` (which adds
   copy 1, the guard finding PATH clean), then `~/.profile` line 26 prepends
   `~/.local/bin` **unconditionally, with no dedup of its own** (copy 2). The second copy is
   added by Debian's file after ours has finished. Variant B is therefore *not* more
   idempotent than variant A for a login shell; it is only more idempotent against a user
   running `source ~/.bashrc` repeatedly in a live shell, which variant A would grow without
   bound. [MEASURED]

3. **Variant C makes `bash -lc` worse** (2 copies instead of 1), because a line above the
   guard also runs when `~/.profile` sources `~/.bashrc` in a non-interactive login shell.
   Covering ssh costs this.

A duplicate PATH entry is harmless to lookup — the first match wins — but any message that
promises an "idempotent" edit should mean *idempotent in the file*, not *idempotent in
`$PATH`*, because the latter is not achievable from `~/.bashrc` on Debian.

### 5.1 The exact lines to recommend

Given the above, the shortest correct recommendation is **Debian's own three lines**, copied
out of `/etc/skel/.profile` lines 25–27, appended to `~/.bashrc`:

```sh
# make ~/.local/bin reachable from non-login shells too
if [ -d "$HOME/.local/bin" ] ; then
    PATH="$HOME/.local/bin:$PATH"
fi
```

Reasons this form, rather than the guarded one: it is literally the line Debian already ships
one file over, so it is recognisable and reviewable; the dedup guard buys nothing for the
login-shell duplicate (§5 point 2); and the shorter form is likelier to be pasted correctly.
[BELIEVED — a judgement, not a measurement. The measurements say A and B are equivalent for
every shape in the table, so this is a readability preference, and #34's own wording already
says "three lines".]

Two caveats a message must carry, both measured:

- The path must be **the installer's `bindir`**, not a hardcoded `~/.local/bin`.
  `install.sh:14` honours `MOVIAN_SDK_BINDIR`, and Debian's `~/.profile` only ever adds
  `~/bin` and `~/.local/bin` — so with a custom bindir the "your `~/.profile` already adds it"
  half of the story is simply false. [MEASURED — `install.sh:14`]
- It takes effect in **new** shells. The current shell needs
  `. ~/.bashrc` or `export PATH="$HOME/.local/bin:$PATH"` to see it now.

---

## 6. Authoritative table: shell invocation shape → files read, in order

Every row is bash(1) INVOCATION as shipped by Debian 13's `bash` 5.2.37-2, cross-checked
against the measured behaviour of §5. [PRIMARY + MEASURED]

| Invocation | Files read, in order | Reaches `~/.local/bin` on stock Debian? |
|---|---|---|
| interactive login shell (`bash -l`, TTY login, `ssh host` with no command, `login`) | `/etc/profile`; then **the first that exists** of `~/.bash_profile`, `~/.bash_login`, `~/.profile`. Debian's `~/.profile` in turn sources `~/.bashrc` (its line 15) after `/etc/bash.bashrc` was sourced by `/etc/profile`. | **yes**, via `~/.profile` — *if* `~/.local/bin` exists at that moment and no `~/.bash_profile` shadows it |
| non-interactive login shell (`bash -lc 'cmd'`) | same as above. `~/.bashrc` is sourced by `~/.profile`, but its guard returns on line 8. | **yes** |
| interactive non-login shell (a terminal emulator; `bash -i`) | `/etc/bash.bashrc`, then `~/.bashrc` | **no** — this is #34's failure |
| non-interactive shell (`bash -c 'cmd'`, `bash script.sh`) | `$BASH_ENV` only, if set. **No `/etc/profile`, no `~/.profile`, no `/etc/bash.bashrc`, no `~/.bashrc`.** | **no**, and no dotfile can change that |
| non-interactive with stdin on a network socket (`ssh host 'cmd'`, rshd) | `/etc/bash.bashrc`, then `~/.bashrc` — but both return at their non-interactive guards | **no** |
| invoked as `sh`, interactive login or `--login` | `/etc/profile`, then `~/.profile` (no `~/.bash_profile` / `~/.bash_login` step) | **yes** |
| invoked as `sh`, interactive non-login | `$ENV` only | **no** |
| invoked as `sh`, non-interactive | nothing | **no** |
| `--posix` | `$ENV` only, in interactive shells. "No other startup files are read." | **no** |
| any of the above with `--noprofile` | skips `/etc/profile` and the `~/.bash_profile`/`~/.bash_login`/`~/.profile` step | **no** |
| any of the above with `--norc` | skips `/etc/bash.bashrc` and `~/.bashrc` | unchanged |
| effective uid ≠ real uid, no `-p` | **no startup files are read at all** | **no** |
| interactive login shell **exiting** | `~/.bash_logout` | n/a |

The two rows to keep in mind for this repo: **"interactive non-login"** is the shape the user
hit, and **"non-interactive"** is the shape an agent uses — and the second reads nothing at
all.

---

## 7. What contradicts or sharpens the premise in #34

#34 says: *"On a fresh Debian 13 stand `~/.local/bin` is added by `~/.profile` […] Run the
installer from a login shell and it says nothing at all"* and *"the fix is three lines in
`~/.bashrc`"*. The core of that is confirmed. Five things around it are not.

### 7.1 On a *truly* fresh machine, a login-shell install **does** warn

Measured by running this repo's actual `install.sh` inside `debian:13` as a fresh non-root
user with stock skel dotfiles: [MEASURED]

| Scenario | `"not on PATH"` warnings |
|---|---|
| `~/.local/bin` **does not exist**, install via `bash -lc ./install.sh` | **1** |
| second run, in a **new** login shell (directory now exists) | **0** |
| `~/.local/bin` does not exist, install via plain `bash -c ./install.sh` | 1 |

The mechanism: `install.sh:19` does `mkdir -p "$bindir"` — but that runs *after* `~/.profile`
has already evaluated `if [ -d "$HOME/.local/bin" ]` and found nothing. So the login shell
that runs the first install genuinely does not have the directory on PATH, and the existing
check correctly warns.

**The silent-and-broken case therefore requires `~/.local/bin` to have already existed when
the login shell started** — because of an earlier `pip install --user`, an earlier
`install.sh` run, or a second login. That is a very common state, so #34's conclusion stands;
but "a fresh Debian 13 stand" is not the precise trigger, and a test that builds a genuinely
empty `HOME` will reproduce the *wrong* direction unless it creates `~/.local/bin` before
starting the login shell. This is the single most important thing here for #40's fixture.

And after that second, silent install, reachability is exactly as #34 reports: [MEASURED]

```
bash -lc  -> /home/u/.local/bin/mdev
bash -ic  -> NOTFOUND
bash -c   -> NOTFOUND
```

### 7.2 Three lines in `~/.bashrc` do not fix the agent case

#35 states the primary user is an agent, and that those sessions are non-interactive shells.
§5 measures that **no** placement in `~/.bashrc` or `~/.profile` reaches `bash -c`. Whatever
the warning says to a human, it does not make `mdev` reachable to a non-interactive
`bash -c` that did not inherit PATH from an ancestor. The available levers there are the
parent process's environment, `BASH_ENV`, or invoking `$HOME/.local/bin/mdev` by absolute
path — all outside what a dotfile edit can do.

### 7.3 An EOF append is dead code for `ssh host 'mdev …'`

§3.2. bash reads `~/.bashrc` for a network-stdin non-interactive shell, and the guard on
lines 5–9 returns before reaching the append. #34's "three lines in `~/.bashrc`" is correct
for the shape it measured and silently incorrect for this one.

### 7.4 `~/.profile` is not guaranteed to be read at all

If the user has a `~/.bash_profile` — which many third-party installers create — bash reads it
*instead of* `~/.profile`, and `~/.local/bin` is then on PATH in no shape whatever. Measured:
with a `~/.bash_profile` present, `bash -lc 'command -v mdev'` returns not-found even though
`~/.profile` contains the stanza and `~/.local/bin/mdev` exists. [MEASURED]

Any message that asserts "your `~/.profile` already adds it" is asserting something the
installer has not checked. Checking is cheap: `[ -e "$HOME/.bash_profile" ]`.

### 7.5 "Idempotent" cannot mean idempotent in `$PATH`

§5 point 2. An interactive login shell will list `~/.local/bin` twice after any `~/.bashrc`
edit, and the second entry comes from Debian's own unguarded `~/.profile` line 26. #34's
requirement 4 asks for an idempotent edit; that is achievable in the *file* (don't append
twice) but not in `$PATH`, and the wording should say which it means.

### 7.6 Also worth recording (not a contradiction)

- `install.sh:78-81` compares against `$bindir`, which is `MOVIAN_SDK_BINDIR` when set.
  Debian's `~/.profile` only knows about `~/bin` and `~/.local/bin`, so for a custom bindir
  the whole "Debian already adds it" narrative does not apply. [MEASURED — `install.sh:14`]
- Debian's `~/.profile` adds `~/bin` too (lines 19–22), *before* `~/.local/bin`. A user with
  `~/bin` on PATH is a legitimate alternative install target.

---

## 8. Appendix: how this was measured

Docker was used as an **evidence-gathering tool during research**, never as a test dependency.
#35 forbids a container in `tests/`; that constraint is why this file exists, and nothing here
weakens it. Every finding above is stated so that it can be reproduced in `tests/` with only
`git`, `bash`, `python3` and `TMPDIR` — a synthetic `HOME` holding the §1 and §3.1 files.

Images, by digest, as pulled on 2026-08-28:

```
debian:13   sha256:f324c7ff54321e8d9c588493a20244965938ce0aa50bbd1022d38010e9ffc4b1
debian:10   sha256:58ce6f1271ae1c8a2006ff7d3e54e9874d839f573d8009c20154ad0f2fb0a225
debian:9    sha256:c5c5200ff1e9c73ffbf188b4a67eb1c91531b644856b4aefe86a58d2f0cb05be
fedora:42   sha256:99e203b80b1c3d8f7e161ec10a68fd02b081ef83a3963553e513c82846b97814
```

`debian:8`, `debian:11`, `debian:12`, `ubuntu:14.04`, `ubuntu:16.04`, `ubuntu:18.04`,
`ubuntu:20.04`, `ubuntu:22.04`, `ubuntu:24.04` were pulled the same day by tag.

Representative commands:

```sh
# §1, §2, §3 — the skel files and their provenance
docker run --rm debian:13 bash -c \
  'dpkg -S /etc/skel/.profile /etc/skel/.bashrc; cat -n /etc/skel/.profile; \
   cat -n /etc/skel/.bashrc; md5sum /etc/skel/.profile /etc/skel/.bashrc'

# §2.1 — the Debian archive's own changelog
curl -sS https://metadata.ftp-master.debian.org/changelogs/main/b/bash/bash_5.2.37-2_changelog \
  | grep -B12 -A4 'local/bin'

# §1.2, §4, §6 — real man pages, extracted from the packages that ship them
docker run --rm debian:13 bash -c \
  'apt-get -qq update && apt-get -qq install -y --reinstall bash man-db groff-base \
   && apt-get -qq install -y libpam-modules systemd \
   && man 1 bash && man 8 pam_env && man 5 environment.d'

# §5 — shell shapes against a synthetic HOME, no container semantics involved
docker run --rm debian:13 bash -c '
  H=/tmp/fakehome; mkdir -p "$H/.local/bin"
  cp /etc/skel/.profile "$H/.profile"; cp /etc/skel/.bashrc "$H/.bashrc"
  printf "#!/bin/sh\necho ok\n" > "$H/.local/bin/mdev"; chmod +x "$H/.local/bin/mdev"
  env -i HOME=$H TERM=xterm PATH=/usr/bin:/bin bash -ic "command -v mdev || echo NOTFOUND"'

# §3.2 — the ssh row, with a real sshd
docker run --rm debian:13 bash -c \
  'apt-get -qq update && apt-get -qq install -y openssh-server openssh-client && ...'

# §7.1 — this repo's install.sh against a fresh user
docker run --rm -v "$PWD":/src:ro debian:13 bash -c \
  'useradd -m u; cp -r /src /home/u/sdk; chown -R u:u /home/u/sdk
   cp /etc/skel/.profile /etc/skel/.bashrc /home/u/; chown u:u /home/u/.profile /home/u/.bashrc
   su u -c "cd /home/u/sdk && bash -lc ./install.sh" | grep -c "not on PATH"'
```

Primary documents fetched:

- bash(1) INVOCATION — from the `bash` 5.2.37-2 package in `debian:13`, not from a website.
- pam_env(8), environment.d(5) — from `libpam-modules` and `systemd` 257.13-1~deb13u1 in
  `debian:13`.
- Debian BTS [#820856](https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=820856),
  [#839155](https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=839155).
- Debian archive changelog for `bash` 5.2.37-2.
- [Debian Policy, ch. 9 *The Operating System*](https://www.debian.org/doc/debian-policy/ch-opersys.html),
  §9.9 *Environment variables*.
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir/latest/).
- [Linux File System Hierarchy (UAPI Group)](https://uapi-group.org/specifications/specs/linux_file_system_hierarchy/).
- [Linux-PAM `NEWS`](https://raw.githubusercontent.com/linux-pam/linux-pam/master/NEWS) and
  release tag dates via the GitHub API.

### 8.1 A note on `file-hierarchy(7)`

The obvious thing to cite for `~/.local/bin` is systemd's `file-hierarchy(7)`. **On a current
systemd it no longer contains the entry.** Measured on `debian:13`, systemd 257.13-1~deb13u1:
`zcat /usr/share/man/man7/file-hierarchy.7.gz | grep -c local/bin` returns **0**. The man page
is now a four-paragraph stub whose DESCRIPTION says only: [MEASURED]

> Operating systems using the **systemd**(1) system and service manager are organized based on
> a file system hierarchy inspired by UNIX, as described in **Linux File System Hierarchy**.

…linking to `https://uapi-group.org/specifications/specs/linux_file_system_hierarchy/`. The
same is true of `man/file-hierarchy.xml` in systemd's git `main`. [PRIMARY]

**So cite the UAPI Group specification, not the man page.** Its `~/.local/bin/` entry, verbatim:
[PRIMARY]

> **`~/.local/bin/`** — Executables that shall appear in the user's `$PATH` search path. It is
> recommended not to place executables in this directory that are not useful for invocation
> from a shell; these should be placed in a subdirectory of `~/.local/lib/` instead.

Note what this does and does not say: it says `~/.local/bin` *shall* appear in `$PATH`. It
does not say who is responsible for putting it there, and it does not specify a mechanism. So
it supports the claim "`~/.local/bin` belongs on PATH" and supports nothing about *which file*
should do it.

### 8.2 XDG does not define `~/.local/bin`

The XDG Base Directory Specification defines `XDG_DATA_HOME` (default `$HOME/.local/share`),
`XDG_CONFIG_HOME` (default `$HOME/.config`), `XDG_STATE_HOME` (default `$HOME/.local/state`),
and the cache and runtime directories. **There is no `XDG_BIN_HOME`.** The spec's only mention
of an executables directory is the single sentence: [PRIMARY]

> User-specific executable files may be stored in `$HOME/.local/bin`.

— outside the environment-variable framework, with no default-value or override semantics.

**Therefore, if this repo wants an upstream citation for `~/.local/bin`, the UAPI Group
specification (§8.1) is the one that says it belongs on `$PATH`; XDG only says the directory
may be used, and Debian Policy says nothing at all (§4.2).** Anything stronger than that is an
assertion this repo would be making on its own.
