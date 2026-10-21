"""审计日志：每次识别追加一条 JSONL 记录，可回溯。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


def append(cfg: dict, record: dict) -> None:
    log_path = Path(cfg.get("audit", {}).get("log", "./audit/docsort.jsonl")).expanduser()
    if not log_path.is_absolute():
        log_path = Path.cwd() / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"time": datetime.now().isoformat(timespec="seconds"), **record}
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
