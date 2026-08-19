# Security Policy

## Supported versions

Only the latest version on the `main` branch is supported.

## Reporting a vulnerability

Do not open a public issue for a secret leak or an exploitable security problem.

Use GitHub's private vulnerability reporting for this repository when available. If it is not available, contact the maintainer privately through the GitHub profile and include:

- A short description of the issue.
- The affected file and version or commit.
- Reproduction steps that do not include real API keys.
- The possible impact.
- A suggested fix, if known.

The maintainer will acknowledge a report and coordinate a fix before public disclosure when practical.

## API key handling

- Never commit Exa API keys.
- Never paste keys into issues, pull requests, screenshots, or logs.
- Treat a key exposed in Git history as compromised and rotate it.
- Protect `exa_gateway.db`, `exa_gateway.db-wal`, and `exa_gateway.db-shm`.
- Keep Hermes dashboard authentication enabled before exposing the dashboard.

## Scope

This project is a local Hermes plugin. Exa's service, accounts, API, and infrastructure are outside this repository's security scope; report Exa service issues to Exa.
