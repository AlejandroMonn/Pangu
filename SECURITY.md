# Security Notes

Chaos-Triage is designed to run locally and does not require a cloud backend.

## What should never be committed

Do not commit any of the following:

- `.env` files
- API keys
- access tokens
- local shell history exports
- logs containing personal brain dumps
- virtual environments
- machine-specific temp or PID files

## Public repo guidance

Before pushing to a public repository:

1. Review `git status`
2. Review `git diff --cached`
3. Confirm no local-only files are staged
4. Confirm no secrets appear in documentation or scripts

## Model and privacy

This app is intended for local inference through Ollama.

That means:

- task text stays on the local machine
- the app does not require external LLM APIs
- privacy still depends on your local machine security and what you choose to commit

## Reporting concerns

If you find a security-sensitive issue in the code or docs, fix it before publishing or sharing the repository further.
