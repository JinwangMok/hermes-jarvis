# Public / Private Sync Strategy

This repository may be maintained in two GitHub destinations:
- private operational repo: `origin`
- public open-source repo: `public`

Current intended mapping:
- `origin` → `JinwangMok/jinwang-jarvis` (private)
- `public` → `JinwangMok/hermes-jarvis` (public)

## Goal
Keep the private repo usable for real personal deployment while publishing a sanitized, reusable version to the public repo.

## Recommended policy

### Push to both repos when
- the change is generic
- it contains no private paths, account IDs, channel IDs, or personal notes
- it improves reusable behavior, docs, tests, config templates, or public-safe defaults

Examples:
- generic config support
- install script improvements
- test fixes
- reusable README/docs updates
- approval loop logic that does not expose personal data

### Push only to private repo when
- the change includes personal account names
- the change includes personal sender maps or email identities
- the change includes private wiki paths, Discord channel IDs, or credentials
- the change is tightly coupled to one user's environment

Examples:
- `config/pipeline.local.yaml`
- real sender maps
- private deployment notes
- experiments tied to one mailbox/calendar setup

## Safe workflow
1. Do development locally.
2. Keep tracked defaults public-safe.
3. Keep personal runtime values in ignored files such as:
   - `config/pipeline.local.yaml`
   - `config/sender-map.md`
4. Before pushing public changes, review:
   - `git diff`
   - `git status`
   - README / docs for personal references
5. Push generic changes to `public`.
6. Push operational/private changes only to `origin`.

## Suggested commands

### Inspect remotes
```bash
git remote -v
```

### Push generic/public-safe changes
```bash
git push public main
```

### Push private operational changes
```bash
git push origin main
```

### Push to both after confirming the diff is sanitized
```bash
git push origin main
git push public main
```

## Practical rule of thumb
If a stranger can clone the repo and benefit from the change without learning anything personal about the operator, it probably belongs in `public` too.

If the change reveals who the operator is, where they work, what channels they use, or what mailboxes they own, keep it private.
