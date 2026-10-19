# SDD ledger — plan: docs/superpowers/plans/2026-10-18-universal-harness-distribution.md

## Preflight scan

| Row | Scope | Check | Result |
| --- | --- | --- | --- |
| 1 | Task 1 ↔ Task 2 | Skill wording and README share Harness-neutral invocation and relative paths | Consistent; Task 1 owns entrypoint, Task 2 owns reader-facing prose |
| 2 | Task 1 ↔ Task 3 | Skill layout and discovery/install tests use `skills/ds-search/SKILL.md` | Consistent |
| 3 | Task 2 ↔ Task 3 | README commands match local `npx skills` behavior and isolated test constraints | Consistent; `--list` is separate from `--json` |
| 4 | Task 1 | Files, tests, and interfaces agree | Consistent; optional `agents/openai.yaml` remains isolated |
| 5 | Task 2 | Files, commands, and security constraints agree | Consistent; no secret-bearing examples |
| 6 | Task 3 | Test files and safety requirements agree | Consistent; no global scope or real API/store |
| 7 | Task 4 | Verification commands cover all prior tasks | Consistent |

Ruling: Work in the current checkout on a new local feature branch because no worktree was requested and no suitable active worktree exists; preserve `main` and do not push from the implementation loop.

Task 1: implementation complete (commit 91400c1; initial review pending).
Task 1: fix round 1/5 (1 finding addressed; commits 91400c1..6abe5fb; scoped re-review clean).
Task 1: complete (commits 91400c1..6abe5fb, review clean).
Task 2: implementation complete (commit f719f50; pending task review).
Task 2: review finding (SPEC ❌, QUALITY ❌): document source inspection and optional Codex metadata in README; distinguish project skills-lock.json from global .skill-lock.json/XDG state; clarify discovery runs from ds-search checkout; add executable command-line check forbidding --list with --json. Fix round 1 pending.
Task 2: fix round 1/5 (3 findings addressed; commits f719f50..8373d93; scoped re-review pending).
Task 2: complete (commits f719f50..8373d93, review clean).
Ruling: Task 3 discovery test separates CLI name output from repository path assertion — `skills` 1.7.2 `--list` human output reports the discovered name but not guaranteed nested path; requiring the path in stdout would make the test contradict observed CLI behavior. Cost if wrong: a future CLI could change presentation, but repository layout remains independently pinned.
Task 3: implementation complete (commit b6b5c57; pending task review).
Task 3: review finding (SPEC text conflict, QUALITY ❌): generated brief still says nested path must appear in CLI stdout, but amended plan/ruling and observed CLI require name output plus independent source-path assertion; stale brief is superseded by the amended plan. Also harden test env with an allowlist, pin `skills@1.7.2`, and gate network-dependent npx integration tests behind `RUN_SKILLS_CLI_TESTS=1`. Fix round 1 pending.
Task 3: fix round 1/5 (2 quality findings addressed; commits b6b5c57..2b4f215; stale brief path wording ruled superseded; scoped re-review pending).

Task 4: final verification complete. Default suite passed 60 tests with 2 opt-in CLI skips; `RUN_SKILLS_CLI_TESTS=1` passed all 60. Repository validator, Skill Creator validator, compileall, diff check, and extracted no-credential smoke test passed. Documentation/spec/plan wording was aligned to standalone `--list` discovery and separate `--json`; no runtime/client/tests changed.
Task 4: minor review fix complete. README and verification docs now provide the independent installed-state command `npx skills list --json`, explicitly separate it from `npx --yes skills@1.7.2 add . --list`, and the documentation test asserts the command cannot disappear. Default and opt-in suites, repository/Skill validators, compileall, and diff check all passed.
Task 3: complete (commits b6b5c57..2b4f215, review clean).
Task 4: final whole-branch review clean; minor documentation fix c647363 re-reviewed clean.
