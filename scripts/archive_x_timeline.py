#!/usr/bin/env python3
import argparse
import csv
import email.utils
import json
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date {value!r}; use YYYY-MM-DD") from exc


def normalize_handle(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^https?://(?:www\.)?(?:x|twitter)\.com/", "", value)
    value = value.split("?", 1)[0].strip("/")
    value = value.lstrip("@")
    if "/" in value:
        value = value.split("/", 1)[0]
    if not re.fullmatch(r"[A-Za-z0-9_]{1,15}", value):
        raise argparse.ArgumentTypeError(f"invalid X handle: {value!r}")
    return value


def default_output_dir(handle: str) -> Path:
    return Path.home() / "Downloads" / f"{handle}-timeline"


def load_dotenvs(env_paths: list[Path]) -> dict[str, str]:
    env = os.environ.copy()
    for env_path in env_paths:
        if not env_path.exists():
            continue
        for line in env_path.read_text().splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env.setdefault(key, value)
    return env


def find_bird(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        if path.exists():
            return path
        raise FileNotFoundError(f"bird-search not found: {path}")

    bundled = Path(__file__).resolve().parent / "vendor" / "bird-search" / "bird-search.mjs"
    if bundled.exists():
        return bundled

    # Compatibility fallback for local machines that used earlier versions of
    # this skill before bird-search was bundled here. New installs should use
    # the bundled backend above.
    home = Path.home()
    candidates = [
        home / ".agents/skills/last30days/scripts/lib/vendor/bird-search/bird-search.mjs",
        home / ".codex/skills/last30days/scripts/lib/vendor/bird-search/bird-search.mjs",
        home / ".claude/skills/last30days/scripts/lib/vendor/bird-search/bird-search.mjs",
    ]
    cache_roots = [
        home / ".codex/plugins/cache",
        home / ".claude/plugins/cache",
    ]
    for root in cache_roots:
        if root.exists():
            candidates.extend(root.glob("**/last30days*/**/scripts/lib/vendor/bird-search/bird-search.mjs"))
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("Could not find bird-search.mjs. Expected bundled scripts/vendor/bird-search/bird-search.mjs or pass --bird-path.")


def macos_system_proxy() -> str | None:
    try:
        proc = subprocess.run(["scutil", "--proxy"], text=True, capture_output=True, timeout=5)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    data: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        match = re.match(r"\s*(HTTPSEnable|HTTPSProxy|HTTPSPort|HTTPEnable|HTTPProxy|HTTPPort)\s*:\s*(.+)\s*$", line)
        if match:
            data[match.group(1)] = match.group(2)
    if data.get("HTTPSEnable") == "1" and data.get("HTTPSProxy") and data.get("HTTPSPort"):
        return f"http://{data['HTTPSProxy']}:{data['HTTPSPort']}"
    if data.get("HTTPEnable") == "1" and data.get("HTTPProxy") and data.get("HTTPPort"):
        return f"http://{data['HTTPProxy']}:{data['HTTPPort']}"
    return None


def ensure_proxy_preload(output_dir: Path, proxy_url: str, env: dict[str, str]) -> tuple[Path, dict[str, str]]:
    preload = output_dir / "proxy-preload.cjs"
    preload.write_text(
        'const { ProxyAgent, setGlobalDispatcher } = require("undici");\n'
        'const proxyUrl = process.env.HTTPS_PROXY || process.env.HTTP_PROXY;\n'
        "if (proxyUrl) setGlobalDispatcher(new ProxyAgent(proxyUrl));\n"
    )
    if not (output_dir / "node_modules" / "undici").exists():
        subprocess.run(
            ["npm", "install", "--prefix", str(output_dir), "undici@latest"],
            check=True,
            text=True,
        )
    child_env = env.copy()
    child_env["HTTPS_PROXY"] = proxy_url
    child_env["HTTP_PROXY"] = proxy_url
    existing = child_env.get("NODE_OPTIONS", "")
    require_opt = f"--require {preload}"
    child_env["NODE_OPTIONS"] = f"{existing} {require_opt}".strip()
    return preload, child_env


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return email.utils.parsedate_to_datetime(value)
    except Exception:
        return None


def normalize_tweet(tweet: dict, fallback_handle: str) -> dict:
    created = parse_dt(tweet.get("created_at") or tweet.get("createdAt"))
    author = tweet.get("author") or {}
    username = author.get("username") or fallback_handle
    tweet_id = str(tweet.get("id") or tweet.get("id_str") or "")
    return {
        "id": tweet_id,
        "created_at": created.isoformat() if created else "",
        "username": username,
        "url": f"https://x.com/{username}/status/{tweet_id}" if tweet_id else "",
        "text": tweet.get("text") or "",
        "reply_count": tweet.get("replyCount") or tweet.get("reply_count") or "",
        "retweet_count": tweet.get("retweetCount") or tweet.get("retweet_count") or "",
        "like_count": tweet.get("likeCount") or tweet.get("favorite_count") or tweet.get("like_count") or "",
        "view_count": tweet.get("viewCount") or tweet.get("view_count") or "",
        "raw": tweet,
        "_dt": created,
    }


def run_query(bird: Path, env: dict[str, str], handle: str, since: date, until_day: date, count: int, timeout: int) -> list[dict]:
    query = f"from:{handle} since:{since.isoformat()} until:{until_day.isoformat()}"
    cmd = ["node", str(bird), query, "--count", str(count), "--json"]
    proc = subprocess.run(cmd, env=env, text=True, capture_output=True, timeout=timeout)
    if proc.returncode != 0:
        try:
            payload = json.loads(proc.stdout or "{}")
        except Exception:
            payload = {"error": proc.stderr.strip() or proc.stdout.strip()}
        raise RuntimeError(payload.get("error") or proc.stderr.strip() or "bird-search failed")
    payload = json.loads(proc.stdout or "[]")
    if isinstance(payload, dict) and payload.get("error"):
        raise RuntimeError(payload["error"])
    if not isinstance(payload, list):
        raise RuntimeError(f"unexpected bird-search payload: {type(payload).__name__}")
    return [normalize_tweet(item, handle) for item in payload]


def write_outputs(output_dir: Path, prefix: str, handle: str, since: date, until: date, until_day: date, seen: dict, history: list, final: bool) -> dict:
    ordered = sorted(
        seen.values(),
        key=lambda row: row["_dt"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    raw_path = output_dir / f"{prefix}-raw.json"
    jsonl_path = output_dir / f"{prefix}.jsonl"
    csv_path = output_dir / f"{prefix}.csv"
    summary_path = output_dir / f"{prefix}-summary.json"
    checkpoint_path = output_dir / f"{prefix}-checkpoint.json"

    raw_path.write_text(json.dumps([row["raw"] for row in ordered], ensure_ascii=False, indent=2))
    with jsonl_path.open("w") as f:
        for row in ordered:
            out = {k: v for k, v in row.items() if k not in {"raw", "_dt"}}
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
    if ordered:
        fields = ["id", "created_at", "username", "url", "text", "reply_count", "retweet_count", "like_count", "view_count"]
        with csv_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in ordered:
                writer.writerow({field: row.get(field, "") for field in fields})

    summary = {
        "handle": handle,
        "since": since.isoformat(),
        "until": until.isoformat(),
        "count": len(ordered),
        "newest": ordered[0]["created_at"] if ordered else "",
        "oldest": ordered[-1]["created_at"] if ordered else "",
        "complete": bool(final),
        "next_until": until_day.isoformat(),
        "rounds": history,
        "files": {
            "raw_json": str(raw_path),
            "jsonl": str(jsonl_path),
            "csv": str(csv_path),
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    checkpoint_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export an X/Twitter account timeline to CSV, JSONL, and raw JSON.")
    parser.add_argument("--handle", required=True, type=normalize_handle, help="X handle, @handle, or x.com URL")
    parser.add_argument("--since", required=True, type=parse_date, help="Inclusive lower bound, YYYY-MM-DD")
    parser.add_argument("--until", required=True, type=parse_date, help="Exclusive upper bound, YYYY-MM-DD")
    parser.add_argument("--output-dir", type=Path, help="Output directory")
    parser.add_argument("--prefix", help="Output filename prefix")
    parser.add_argument("--max-rounds", type=int, default=120)
    parser.add_argument("--count", type=int, default=100, help="Requested result count per bird-search call")
    parser.add_argument("--sleep", type=float, default=1.5, help="Seconds to sleep between rounds")
    parser.add_argument("--timeout", type=int, default=90, help="Per-query timeout in seconds")
    parser.add_argument("--env-file", type=Path, help="Optional env file with AUTH_TOKEN and CT0")
    parser.add_argument("--bird-path", help="Optional path to bird-search.mjs; defaults to the bundled backend")
    parser.add_argument("--proxy", default="auto", help="'auto', 'off', or proxy URL like http://127.0.0.1:33210")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.until <= args.since:
        raise SystemExit("--until must be after --since")

    output_dir = (args.output_dir or default_output_dir(args.handle)).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = args.prefix or f"{args.handle}-{args.since.isoformat()}-to-{(args.until - timedelta(days=1)).isoformat()}"
    bird = find_bird(args.bird_path)

    if args.env_file:
        env_files = [args.env_file.expanduser()]
    else:
        env_files = [
            Path.home() / ".config/x-timeline-archive/.env",
            Path.home() / ".config/last30days/.env",
        ]
    env = load_dotenvs(env_files)
    if not env.get("AUTH_TOKEN") or not env.get("CT0"):
        raise SystemExit(
            "Missing AUTH_TOKEN/CT0. Add them to the shell env, "
            "~/.config/x-timeline-archive/.env, or pass --env-file."
        )

    proxy_url = None
    if args.proxy.lower() != "off":
        proxy_url = macos_system_proxy() if args.proxy.lower() == "auto" else args.proxy
    if proxy_url:
        _, env = ensure_proxy_preload(output_dir, proxy_url, env)

    seen: dict[str, dict] = {}
    history: list[dict] = []
    until_day = args.until
    complete = False

    for round_num in range(1, args.max_rounds + 1):
        rows = run_query(bird, env, args.handle, args.since, until_day, args.count, args.timeout)
        new_rows = [row for row in rows if row["id"] and row["id"] not in seen]
        for row in new_rows:
            seen[row["id"]] = row
        dated = [row["_dt"] for row in rows if row["_dt"]]
        record = {
            "round": round_num,
            "until": until_day.isoformat(),
            "returned": len(rows),
            "new": len(new_rows),
            "oldest": min(dated).isoformat() if dated else "",
            "newest": max(dated).isoformat() if dated else "",
        }
        history.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
        write_outputs(output_dir, prefix, args.handle, args.since, args.until, until_day, seen, history, final=False)

        if not rows or not dated:
            complete = True
            break
        oldest = min(dated).date()
        if oldest <= args.since:
            complete = True
            break
        next_until = oldest
        if next_until >= until_day:
            next_until = until_day - timedelta(days=1)
        until_day = next_until
        time.sleep(args.sleep)

    summary = write_outputs(output_dir, prefix, args.handle, args.since, args.until, until_day, seen, history, final=complete)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if complete else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
