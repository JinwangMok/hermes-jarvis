# Watch Sources

Seed source definitions for the external hot-issue tracker.

Subdirs:
- `official/`: official company/newsroom/blog and project-origin sources
- `reaction/`: community/repost/discussion surfaces
- `analysis/`: industry analysis/commentary sources
- `media/`: broader media surfaces, usually lower weighted because they are noisier
- `user/`: later user-added sources via onboarding workflow

Status guidance:
- `enabled: true` + `validation_status: verified` => safe starter seed
- `enabled: false` + `validation_status: partial|blocked` => staged only
