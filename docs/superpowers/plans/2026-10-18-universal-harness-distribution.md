# Universal Harness Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make `ds-search` Harness-neutral and installable/updatable through the `npx skills` CLI.

**Architecture:** Keep the canonical skill at `skills/ds-search/` with one `SKILL.md`, relative references, and the existing Python scripts. Treat the GitHub repository as the distribution source; let `npx skills` choose project/global scope and supported Agent targets. Keep Codex UI metadata optional and isolated in `agents/openai.yaml`.

**Tech Stack:** Markdown/YAML, Python 3.10+ standard library, existing unittest suite, `npx skills` CLI 1.7.2 for discovery/install smoke checks.

**Spec:** `docs/superpowers/specs/2026-10-18-universal-harness-distribution-design.md`

## Global Constraints

- Preserve `skills/ds-search/SKILL.md` as the canonical distributable entrypoint.
- Use `npx skills add owner/repo --skill ds-search` for installation and `npx skills update ds-search` for updates.
- Do not combine `npx skills add --list` with `--json`; CLI 1.7.2 rejects that combination.
- Do not add an npm runtime package or commit consumer-generated `skills-lock.json`.
- Do not change DeepSeek endpoints, credential handling, API behavior, or security boundaries.
- Keep `agents/openai.yaml` optional and Codex-specific; no other Harness metadata is fabricated.
- Do not access real API keys, system credential stores, or paid DeepSeek endpoints in tests.

## Review Focus

- The documented GitHub source and skill selector must resolve the nested `skills/ds-search/SKILL.md` path.
- README commands must distinguish global/project scope, selected/all Agents, copy versus symlink, and update prerequisites.
- Generic Skill instructions must not assume Codex paths, reload behavior, or invocation syntax.
- `--list` discovery must be read-only and its output assertion must tolerate CLI presentation text.
- A temporary project install must not write to the user’s global Harness directories or leave lock files in the repository.

---

### Task 1: Make Skill instructions Harness-neutral

**Files:**
- Modify: `skills/ds-search/SKILL.md`
- Modify: `skills/ds-search/agents/openai.yaml`
- Modify: `docs/design.md`

**Interfaces:**
- `SKILL.md` remains frontmatter plus relative `scripts/` and `references/` paths.
- Description keeps the `ds-search` / DeepSeek search / fetch / setup trigger coverage.
- `$ds-search` may remain only in optional UI/default-prompt examples, never as the only invocation mechanism.

- [x] **Step 1: Write a failing documentation assertion** that the Skill entrypoint contains no Codex-specific installation/path assumptions and still links existing relative references.
- [x] **Step 2: Run the focused assertion and verify it fails against current Codex-specific wording.**
- [x] **Step 3: Rewrite the Skill instructions** to describe a Harness-injected Skill, preserve the credential safety rules, and explain that scripts resolve relative to the installed Skill root.
- [x] **Step 4: Keep/update `agents/openai.yaml`** as optional Codex UI metadata with quoted fields and an explicit `$ds-search` default prompt; do not make it a runtime dependency.
- [x] **Step 5: Update the prior design document** to record the repository’s standard layout and external CLI ownership of target directories.
- [x] **Step 6: Run the focused assertion and Skill validator; expect PASS.**

### Task 2: Rewrite README and supporting docs around `npx skills`

**Files:**
- Modify: `README.md`
- Modify: `SECURITY.md`
- Modify: `skills/ds-search/references/setup.md`
- Modify: `skills/ds-search/references/api.md`
- Modify: `docs/verification.md`

**Interfaces:**
- Canonical GitHub source: `NieAnSHOW/ds-search`.
- Preferred commands:
  - `npx skills add NieAnSHOW/ds-search --skill ds-search --agent '*' --global --copy --yes`
  - `npx skills add NieAnSHOW/ds-search --skill ds-search --agent '*' --copy --yes`
  - `npx skills update ds-search --global --yes`
  - `npx skills update ds-search --project --yes`
- Discovery command: `npx --yes skills@1.7.2 add . --list`; verify the discovered name separately from the canonical source path, and never append `--json` to `--list`.

- [x] **Step 1: Write documentation checks** for the canonical install/update commands, no Codex-only default flow, no literal secret assignments, and the `--list`/`--json` incompatibility.
- [x] **Step 2: Run checks against current docs and verify they fail** because manual Codex copy is currently the primary installation path.
- [x] **Step 3: Rewrite README installation** with GitHub source, global/project scope, `--agent` selection, `--copy`, `--yes`, discovery, update, and consumer-owned `skills-lock.json` explanation.
- [x] **Step 4: Generalize usage language** to “Harness/Agent” while preserving one optional Codex example and all existing key-safety instructions.
- [x] **Step 5: Update setup/API/security/verification references** so their commands and limitations agree with README and the approved spec.
- [x] **Step 6: Run documentation checks and link/structure validation; expect PASS.**

### Task 3: Add `npx skills` discovery and isolated installation verification

**Files:**
- Modify: `tests/test_repository.py`
- Modify: `tools/check_repository.py` only if a generic layout check is missing
- Modify: `.gitignore` only if consumer lock/install artifacts are not ignored

**Interfaces:**
- Tests invoke `npx skills` only with a local source and a temporary working directory.
- No test may use `--global`, mutate the real home directory, access a real credential store, or call DeepSeek.

- [x] **Step 1: Add a failing test** that runs `npx --yes skills add <repo> --list`, checks exit 0 and finds `ds-search` in the CLI output, then independently asserts the canonical `skills/ds-search/SKILL.md` path exists in the source tree.
- [x] **Step 2: Add an isolated install smoke test** using a temporary project and `--copy --yes`; assert the installed Skill has `SKILL.md`, scripts, and references, and the repository has no `skills-lock.json` afterward.
- [x] **Step 3: Run the new tests and confirm the expected failure or skip cleanly** when `npx` is unavailable; do not make unrelated CI failures look like product failures.
- [x] **Step 4: Implement the minimum repository validator/test helper** needed to make the checks deterministic and safe.
- [x] **Step 5: Run the new tests and the default 60-test suite (with 2 opt-in skips); expect PASS.**

### Task 4: Final verification and package review

**Files:**
- Modify only files required by review findings.

- [x] **Step 1: Run `python3 -m unittest discover -s tests -v`.**
- [x] **Step 2: Run `python3 tools/check_repository.py`, the Skill Creator validator, `python3 -m compileall -q skills/ds-search/scripts tools`, and `git diff --check`.**
- [x] **Step 3: Run a temporary extracted Skill smoke test from an unrelated cwd with no `DEEPSEEK_API_KEY`.**
- [x] **Step 4: Run independent code/documentation review** focused on Harness neutrality, CLI command correctness, and secret safety; fix only actionable findings with regression tests.
- [x] **Step 5: Re-run all checks and record results/limitations in `docs/verification.md`.**

The plan does not publish to npm, create consumer lock files, or run a real `npx skills update` against a user installation. Those actions belong to the user’s target Harness environment.
