# ZeusOS rearchitecture leaf pattern — 2026-05-08

Use this reference when continuing ZeusOS OS-style repository rearchitecture work through HOOO/interview leaves.

## Operator-facing explanation pattern

Start every leaf report with a plain-language meaning before hashes/tests:

1. One Korean sentence: what changed operationally.
2. Analogy if useful: e.g. path policy = “지도와 출입 규칙”, registry API = “안전하게 읽는 목록”, Minerva bridge = “legacy hooo와 연결될 계약서”.
3. Then evidence: RED/GREEN, static scan, review, commit.
4. End with A/B/C next choices and one recommended path with risk note.

This came from Jinwang asking “알아듣게 설명해” after implementation-heavy reporting.

## Safe leaf sequence used

1. Scaffold and declarative schemas.
2. Aggressive acceptance defense plan.
3. `zeus_os.paths` compatibility firewall:
   - `data`/`state`: legacy runtime truth, not implicitly created/scanned.
   - `credentials`: local/private, no inventory scan.
   - `agent_shim` logical root maps to `agent-shim/`.
4. Wire manifest validation to `ZeusPaths` without broadening old API behavior.
   - Pitfall caught by review: adding `paths=` accidentally made no-arg `validate_repo_manifests()` work. Preserve old TypeError unless explicitly requested.
5. Add read-only declarative registry API before CLI/runtime wiring.
   - `list_registry(...)` returns immutable structured entries; no writes/mkdir/external calls.
6. Add Minerva/HOOO compatibility bridge as declaration-only metadata:
   - `legacyRoot: skills`
   - `legacyName: hooo`
   - `mode: read-only-metadata`
   - `runtimeWiring: false`
7. Add read-only migration inventory before moving anything:
   - inventory `skills/`, `scripts/`, `data/`, `state` only;
   - never read `credentials/**` values;
   - document that `data/` and `state/` require migration map + dry-run + rollback + smoke before movement.
8. Let one ZeusOS-owned caller consume the bridge before claiming runtime progress:
   - preferred safe caller: `audit_hermes_skill_lifecycle(..., zeus_paths=ZeusPaths(...))`;
   - source remains read-only metadata, not execution-path replacement;
   - preserve old fallback when `zeus_paths` is absent or manifest validation fails.
9. A second safe caller can be `build_skill_search_index(..., zeus_paths=ZeusPaths(...))`:
   - add the compatibility bridge as an extra search/index root only;
   - do not change search execution semantics;
   - preserve existing `skill_roots=[]` falsy fallback behavior, because reviewers caught that changing it silently removed the default Hermes builtin root.

## Guardrails

- Do not move or rewrite `data/`, `state`, `credentials`, raw wiki, Hermes core, gateway, systemd, cron, or `~/.hermes` without explicit approval.
- Keep unrelated dirty mail-secretary/runtime work excluded from rearchitecture commits.
- Use TDD: write test, verify RED, minimally implement, verify GREEN.
- Run staged-diff secret/security scan before review.
- Run independent review before commit; treat API broadening, path traversal in manifest metadata, and overclaiming runtime migration as review targets.

## Compatibility bridge security pitfall

A reviewer caught a real issue in the Minerva/HOOO runtime-caller leaf: `legacyName` was validated only as a string, then joined as `skills_root / legacy_name`. A manifest like this would escape the `skills/` root:

```yaml
compatibilityBridge:
  legacyRoot: skills
  legacyName: ../credentials
  mode: read-only-metadata
  runtimeWiring: false
```

Fix pattern:

- Add a RED test that `validate_repo_manifests()` rejects escaping `legacyName`.
- Validate `legacyName` as a single relative name only:
  - no absolute path;
  - no `..` or `.`;
  - no nested `a/b` path unless a future migration explicitly models nested skill roots and validates containment with `resolve().relative_to(...)`.
- Keep this validation in the manifest layer, before runtime callers join paths.

## Evidence commands used repeatedly

Run the staged-diff safety scan from the `requesting-code-review` skill against only the intended staged files, then request independent staged-diff review before commit. Avoid embedding the literal scan regex in this reference because docs-only changes can self-trigger the scan.

## Runtime caller bridge evidence pattern

When connecting the Minerva/HOOO bridge to a caller, use a test like:

- construct a temporary ZeusOS repo with `apps/skill-sets/custom-skills/minerva/app.yaml` and `skills/hooo/SKILL.md`;
- call `audit_hermes_skill_lifecycle(..., include_external_dirs=False, zeus_paths=ZeusPaths(repo_root))`;
- assert a root with `kind == "compatibility_bridge"` and a skill entry with `source == "compatibility_bridge"`;
- assert the entry carries `compatibility_bridge` metadata and still reports `runtime_wiring: false`.

GREEN command used:

```bash
python3 -m compileall -q src/zeus_os/declarative.py src/zeus_os/hermes_skill_lifecycle.py tests/test_declarative_manifests.py tests/test_hermes_skill_lifecycle.py
PYTHONPATH=src pytest -q tests/test_declarative_manifests.py::test_compatibility_bridge_legacy_name_cannot_escape_skills_root tests/test_hermes_skill_lifecycle.py::test_audit_hermes_skill_lifecycle_consumes_minerva_hooo_registry_bridge tests/test_hermes_skill_lifecycle.py tests/test_declarative_manifests.py tests/test_paths.py
```

## Search/index bridge evidence pattern

When connecting the Minerva/HOOO bridge to skill search/index:

- write the RED test first: `build_skill_search_index(..., zeus_paths=ZeusPaths(repo_root))` should include a `compatibility_bridge` root for `skills/hooo`;
- build a temp repo with the required declarative roots (`agents`, `agent-shim/hermes`, `channels`, `apps/.../minerva`) and a legacy `skills/hooo/SKILL.md`;
- do **not** pass `skill_roots=[]` just to isolate the bridge unless the test is explicitly about old fallback semantics;
- add a regression that `skill_roots=[]` still indexes the default Hermes builtin root, because the first implementation accidentally treated an empty list as “no roots” rather than the previous falsy fallback;
- keep `zeus_paths` optional so existing calls without it remain unchanged;
- independent review should check API compatibility, path traversal, hidden runtime writes, and unrelated dirty mixing.

GREEN command used:

```bash
python3 -m compileall -q src/zeus_os/hermes_skill_search.py tests/test_hermes_skill_search.py
PYTHONPATH=src pytest -q tests/test_hermes_skill_search.py tests/test_hermes_skill_context.py tests/test_declarative_manifests.py tests/test_paths.py
```

## Next natural steps

After the first caller bridge, close the phase with a status document before touching higher-risk callers. Then choose among:

1. CLI registry view, but only after isolating unrelated dirty `cli.py` changes.
2. Script classification manifests without moving scripts.
3. A second caller such as skill search/index, again read-only and fallback-preserving.
