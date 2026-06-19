---
name: x-timeline-archive
description: Archive and export historical X/Twitter account timelines from a public handle using a bundled bird-search backend, browser/session cookies, and optional local proxy. Use when the user asks to collect, export, archive, or analyze tweets/posts from a specific X/Twitter account over a date range, especially when they want CSV, JSONL, raw JSON, checkpointed runs, or a repeatable workflow like archiving the last six months or year of an account.
---

# X Timeline Archive

Use this skill to collect historical posts from one X/Twitter account and export structured files. The bundled script pages backward with `from:{handle} since:{date} until:{date}`, deduplicates by tweet id, writes checkpoint files after every round, and exports CSV, JSONL, raw JSON, and a summary log.

## Requirements

- Python 3.10+
- Node.js 22+
- `AUTH_TOKEN` and `CT0` from an X session the user is authorized to use
- `npm` when proxy mode needs to install `undici`
- macOS for `--proxy auto`; otherwise use `--proxy off` or pass a proxy URL explicitly

## Quick Start

Run the bundled script:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/x-timeline-archive/scripts/archive_x_timeline.py" \
  --handle example_user \
  --since 2025-01-01 \
  --until 2025-07-01 \
  --output-dir ~/Downloads/x-timeline-archive \
  --prefix example_user-2025-01-01-to-2025-06-30 \
  --max-rounds 140
```

Use `until` as an exclusive upper bound. For a request like "through 2026-06-19", pass `--until 2026-06-20`.

## Workflow

1. Resolve the handle from the user request or URL. Strip `https://x.com/`, `https://twitter.com/`, and leading `@`.
2. Choose the date range. For "last six months" or "past year", compute absolute dates from today's date before running.
3. Check that X auth is available. The script uses `AUTH_TOKEN` and `CT0` from the shell, `~/.config/x-timeline-archive/.env`, or a file passed with `--env-file`. It also reads `~/.config/last30days/.env` as a compatibility fallback when present.
4. If the network needs a local proxy, let the script use `--proxy auto` on macOS. It reads `scutil --proxy`, creates a local Node preload in the output directory, and installs `undici` there if needed.
5. Run the script. Keep the terminal session alive until it reaches the requested `since` date or the `max-rounds` cap.
6. Inspect the summary. If `"complete": false`, resume with a wider `--max-rounds` or rerun from the same range; checkpointed outputs already contain the latest completed round.

## Outputs

For a custom `--prefix account-range`, the script writes:

- `account-range.csv` - normalized rows for spreadsheet use
- `account-range.jsonl` - one normalized tweet per line for analysis
- `account-range-raw.json` - raw tweet objects returned by bird-search
- `account-range-summary.json` - counts, range coverage, output paths, and per-round log
- `account-range-checkpoint.json` - same shape as summary, refreshed every round

Normalized fields are `id`, `created_at`, `username`, `url`, `text`, `reply_count`, `retweet_count`, `like_count`, and `view_count`.

## Notes

- The underlying X search often returns about 40 posts per round. High-volume accounts may need hundreds of rounds for a year.
- CSV line counts can exceed tweet counts because tweet text may contain embedded newlines. Use a CSV parser for accurate row counts.
- Do not print or paste `AUTH_TOKEN` or `CT0`. Treat them as session secrets.
- If X requests fail with `fetch failed` but `curl -x http://127.0.0.1:PORT https://x.com/...` works, use `--proxy http://127.0.0.1:PORT` or `--proxy auto`.
- The script uses its bundled `scripts/vendor/bird-search/bird-search.mjs` by default. `--bird-path` exists only for testing or overriding the bundled backend.

## Troubleshooting

Read [references/auth-and-network.md](references/auth-and-network.md) when auth, browser cookies, or proxy setup fails.
