# Security Policy

## Responsible Use

Use this project only to archive your own X/Twitter account or accounts you are authorized to access. Do not use it to bypass access controls, rate limits, suspensions, blocks, privacy settings, or platform restrictions.

## Account Safety

Use a dedicated account you control rather than a personal/main account. The tool uses session cookies (`AUTH_TOKEN` and `CT0`), and those cookies should be treated as sensitive credentials.

## Secrets Handling

- Never commit `AUTH_TOKEN`, `CT0`, `.env` files, CSV/JSONL/raw exports, or proxy preload files.
- Keep env files private with `chmod 600`.
- Revoke or rotate cookies if they are pasted into a chat, shell history, issue, log, or commit.
- Prefer `~/.config/x-timeline-archive/.env` or `--env-file` over inline shell values.

## Network and Rate Limits

Use conservative date ranges and `--sleep` delays. Stop if X returns auth, rate-limit, abuse, or access-denied errors. Do not add retry loops intended to avoid enforcement.

## Reporting Vulnerabilities

If you find a vulnerability that leaks cookies, writes secrets to output files, ignores `.gitignore`, or enables unintended access, open a private report or contact the repository owner before publishing details.

Please include:

- The affected file or command
- Steps to reproduce
- Whether credentials or exported data can be exposed
- Suggested fix, if known
