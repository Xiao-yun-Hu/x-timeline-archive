帮我装 x-timeline-archive，按 https://raw.githubusercontent.com/Xiao-yun-Hu/x-timeline-archive/main/SKILL.md 这个 skill 操作

> [!WARNING]
> **Use a burner account.** Prefer a dedicated X account you control instead of a personal/main account, because this tool uses session cookies. Do not use this tool to bypass access controls, rate limits, suspensions, or platform restrictions.

# X Timeline Archive

Archive posts from a single public X/Twitter account timeline into CSV, JSONL, and raw JSON files.

This tool archives your own account or accounts you are authorized to access.

This repository is also packaged as a Codex skill. If you only want the command-line tool, run `scripts/archive_x_timeline.py` directly.

## What It Does

The tool queries X search with:

```text
from:{handle} since:{YYYY-MM-DD} until:{YYYY-MM-DD}
```

It walks backward through the requested date range, deduplicates tweet ids, and writes checkpointed outputs after every round.

## Requirements

- Python 3.10+
- Node.js 22+
- `npm`, only needed when `--proxy auto` or an explicit proxy is used
- `AUTH_TOKEN` and `CT0` cookies from an X session you are authorized to use
- macOS is the best-tested environment. Linux can work with env-provided cookies and `--proxy off` or an explicit proxy URL.

`--proxy auto` uses macOS `scutil --proxy`. On non-macOS systems, use `--proxy off` or pass a proxy URL explicitly.

## Setup

Create a private env file:

```bash
mkdir -p ~/.config/x-timeline-archive
chmod 700 ~/.config/x-timeline-archive
cat > ~/.config/x-timeline-archive/.env <<'EOF'
AUTH_TOKEN=replace-with-your-auth-token
CT0=replace-with-your-ct0
EOF
chmod 600 ~/.config/x-timeline-archive/.env
```

To get these values manually from your own browser session:

1. Log in to X in your browser.
2. Open developer tools.
3. Go to the Application/Storage cookies view for `https://x.com`.
4. Copy the cookie values named `auth_token` and `ct0`.
5. Put them into the env file as `AUTH_TOKEN` and `CT0`.

Do not commit or share these values.

## Usage

From a cloned repository:

```bash
python3 scripts/archive_x_timeline.py \
  --handle example_user \
  --since 2025-01-01 \
  --until 2025-07-01 \
  --output-dir ~/Downloads/x-timeline-archive \
  --prefix example_user-2025-01-01-to-2025-06-30 \
  --max-rounds 140
```

`--until` is exclusive. To include posts through `2025-06-30`, pass `--until 2025-07-01`.

## Outputs

For `--prefix account-range`, the tool writes:

- `account-range.csv` - normalized rows for spreadsheet use
- `account-range.jsonl` - one normalized tweet per line
- `account-range-raw.json` - raw tweet objects returned by bird-search
- `account-range-summary.json` - count, coverage, output paths, and per-round log
- `account-range-checkpoint.json` - refreshed after every round

CSV line counts can exceed tweet counts because tweet text may contain embedded newlines. Use a CSV parser for accurate row counts.

## Codex Skill Files

- `SKILL.md` is the agent-facing skill manifest and workflow.
- `agents/openai.yaml` is UI metadata for skill-aware agent environments.
- `references/` contains troubleshooting notes for agents and humans.

If you are only using the CLI, you can ignore `agents/openai.yaml`.

## Notes

- The bundled `scripts/vendor/bird-search/` code is based on `@steipete/bird` and carries its own MIT license file.
- Use this only with accounts and sessions you are authorized to access, and respect applicable laws, platform terms, and rate limits.
