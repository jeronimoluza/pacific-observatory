"""`po notify`: one alert line to Telegram or, as the fallback, to files.

Backends (src/configs/notify.yaml; PO_NOTIFY_CONFIG points at another file):

- telegram: `asm-exec curl ...` with the token and chat id as
  {{resolve:secretsmanager:<secret_id>:SecretString:<key>}}, so the secret resolves at
  runtime and never enters this process. Unconfigured (empty secret_id, no asm-exec)
  or failed -> file.
- file: appends to <file.log> (only while <file.log_mount> is mounted, so nothing lands
  on / under an unmounted 5TB) and rewrites <file.latest>, the newest lines first.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

SEVERITIES = ("rojo", "amarillo", "info", "signoff")
CONFIG = Path(__file__).resolve().parents[1] / "configs" / "notify.yaml"
TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"


def load_config() -> dict:
    return yaml.safe_load(Path(os.environ.get("PO_NOTIFY_CONFIG", CONFIG)).read_text())


def _resolve(secret_id: str, key: str) -> str:
    return "{{resolve:secretsmanager:" + f"{secret_id}:SecretString:{key}" + "}}"


def _telegram(cfg: dict, text: str) -> str | None:
    """None when sent, else why not."""
    t = cfg.get("telegram") or {}
    sid = t.get("secret_id") or ""
    exe = t.get("exec") or ["asm-exec"]
    if not sid:
        return "telegram secret_id empty"
    if not shutil.which(exe[0]):
        return f"{exe[0]} not on PATH"
    url = TELEGRAM_URL.format(token=_resolve(sid, t.get("token_key", "token")))
    argv = [*exe, "curl", "-sS", "--fail", "--max-time", "20", "-o", "/dev/null", url,
            "-d", f"chat_id={_resolve(sid, t.get('chat_id_key', 'chat_id'))}", "--data-urlencode", "text@-"]
    try:
        r = subprocess.run(argv, input=text, text=True, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        return "telegram timed out"
    return None if r.returncode == 0 else f"telegram rc={r.returncode}"


def _file(cfg: dict, line: str) -> list[str]:
    f = cfg["file"]
    wrote = []
    mount = Path(f["log_mount"])
    if os.path.ismount(mount):
        log = Path(f["log"])
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a") as out:
            out.write(line + "\n")
        wrote.append(str(log))
    latest = Path(f["latest"]).expanduser()
    latest.parent.mkdir(parents=True, exist_ok=True)
    old = [x for x in latest.read_text().splitlines() if x.startswith("- ")] if latest.exists() else []
    keep = int(f.get("latest_lines", 20))
    tmp = latest.with_suffix(".tmp")
    tmp.write_text(f"# po alerts, newest first (last {keep})\n\n" + "\n".join([f"- {line}", *old][:keep]) + "\n")
    os.replace(tmp, latest)
    wrote.append(str(latest))
    return wrote


def notify(severity: str, message: str, cfg: dict | None = None) -> str:
    """Send one alert; return where it went."""
    if severity not in SEVERITIES:
        raise ValueError(f"severity {severity!r} not in {SEVERITIES}")
    cfg = cfg or load_config()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    message = " ".join(message.split())
    line = f"{ts} {severity.upper()} {socket.gethostname()} {message}"
    why = "backend file"
    if cfg.get("backend") == "telegram":
        why = _telegram(cfg, line)
        if why is None:
            return "telegram"
    return f"file ({why}): " + ", ".join(_file(cfg, f"{line}  [{why}]" if why != "backend file" else line))


def from_status(week_dir: Path, step: str, state: str, msg: str) -> None:
    """The STATUS_<step> lines that alert. A run's FAILED repeats its step's, so only the step's goes."""
    if state in ("BLOCKED", "ABORTED") or (state == "FAILED" and step != "run"):
        severity = "rojo"
    elif state == "AWAITING_SIGNOFF":
        severity = "signoff"
    elif state == "DONE" and step == "run":
        severity = "info"
    else:
        return
    try:
        where = str(week_dir).replace(str(Path.home()), "~", 1)
        notify(severity, f"{where} {step}: {state} {msg}")
    except Exception as e:  # an alert must never stop the chain it reports on
        print(f"po notify failed: {type(e).__name__}: {e}", file=sys.stderr)
