# movian-plugin-sdk

Portable development layer for Movian plugins: the agent-facing knowledge
(skills, templates, verification rules) that lets an AI agent take a plugin
change from edit through build, launch, and proven verification.

The layer splits in two:

- **Knowledge** — skills, plugin templates, typing and verification rules.
  Fully portable; lives here.
- **Execution** — `mdev` and the Movian build. Bound to a checkout of the
  [core repo](https://github.com/buksa/movian); reached from here through an
  explicit locator contract, not vendored.

Delivery targets: Claude Code (plugin marketplace), Codex (`AGENTS.md`
fragment), OMP (`.lsp.json` / `.omp/lsp.json`).

Status: being charted. See the issue labelled `wayfinder:map`.
