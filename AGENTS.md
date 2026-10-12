# Development agent guidelines

Read **README.md** and the numbered **doc/** manuals before making changes. For repo-based work, GitHub main and reviewed PRs are authoritative; do not infer the repository state from prior chat context.

- Work on a branch; describe changes, tests, limitations and any required manual verification in the PR.
- Keep development/deployment instructions current in the same change. See [02 Development](doc/02-development.md) and [08 Project instructions](doc/08-project-instructions.md).
- Preserve simulator-only behavior unless the user explicitly requests a separately verified hardware implementation.
- BLE reads and writes are different safety classes. Never introduce unreviewed hardware writes or imply CI proves real trainer safety.
- Never commit secrets, personal training data, private identifiers or unredacted diagnostic logs.
- Local-first operation, portable macOS deployment and honest capability reporting are core requirements.
