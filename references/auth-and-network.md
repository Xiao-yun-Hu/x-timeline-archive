# Auth and Network Notes

Use this reference only when `archive_x_timeline.py` cannot authenticate or cannot connect to X.

## Authentication

The timeline archiver needs the same two X session cookies used by the bundled bird-search client:

- `AUTH_TOKEN`
- `CT0`

Preferred sources:

1. Shell environment variables.
2. `~/.config/x-timeline-archive/.env`.
3. Values previously extracted from a local browser session by another trusted setup flow.
4. `~/.config/last30days/.env`, for compatibility with machines that already use that skill.

Keep env files private:

```bash
chmod 600 ~/.config/x-timeline-archive/.env
```

To check whether the backend sees credentials without printing secrets:

```bash
set -a
source ~/.config/x-timeline-archive/.env
set +a
node ~/.codex/skills/x-timeline-archive/scripts/vendor/bird-search/bird-search.mjs --whoami
```

If this prints `env AUTH_TOKEN`, credentials are present. It does not prove network access works.

## Browser Cookie Extraction

If credentials are not present but the user is logged into X in Chrome, Firefox, Safari, or Brave, extract cookies only with explicit user consent. Do not display cookie values.

For Chrome on macOS, the logged-in X profile may be `Profile 1` or `Profile 2`, not `Default`. Check only cookie names and counts when diagnosing:

```bash
python3 - <<'PY'
import sqlite3
from pathlib import Path
base = Path.home() / "Library/Application Support/Google/Chrome"
for db in sorted(base.glob("*/Cookies")):
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = con.execute(
            "select host_key, name, count(*) from cookies "
            "where host_key like '%x.com' and name in ('auth_token','ct0') "
            "group by host_key,name"
        ).fetchall()
        con.close()
    except Exception:
        rows = []
    if rows:
        print(db)
        for row in rows:
            print(" ", row)
PY
```

If Safari cookie reads fail with Full Disk Access errors, either grant access in System Settings or use Chrome/Firefox cookies instead.

## Network and Proxy

X may be blocked on direct command-line networking while the system browser works through a local proxy. Diagnose with:

```bash
curl -I -L --max-time 20 https://x.com
scutil --proxy
```

If direct `curl` fails and `scutil --proxy` shows `HTTPProxy`/`HTTPSProxy` on `127.0.0.1`, run the archiver with `--proxy auto`. The script will use the macOS system proxy.

If needed, pass the proxy explicitly:

```bash
python3 archive_x_timeline.py ... --proxy http://127.0.0.1:33210
```

The script uses a Node preload with `undici.ProxyAgent`, stored under the output directory. It may run `npm install --prefix <output-dir> undici@latest` the first time proxy mode is used.
