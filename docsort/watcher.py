"""watch 模式：轮询监控目录，文件稳定（大小/修改时间不再变化）后处理。"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict, Tuple

from .ingest import supported
from .pipeline import process_target


def watch(directory: Path, cfg: dict, ocr, interval: float = 3.0) -> None:
    print(f"[watch] 监控目录: {directory.resolve()}（每 {interval:g}s 轮询，Ctrl+C 退出）")
    seen: Dict[Path, Tuple[int, int]] = {}
    stable: Dict[Path, int] = {}
    try:
        while True:
            for p in sorted(directory.iterdir()):
                if not p.is_file() or p.name.startswith(".") or not supported(p):
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                sig = (st.st_mtime_ns, st.st_size)
                if seen.get(p) == sig:
                    stable[p] = stable.get(p, 0) + 1
                    if stable[p] >= 2:  # 连续两轮无变化，认为写入完成
                        print(f"[watch] 发现新文件: {p.name}")
                        try:
                            process_target(p, cfg, ocr)
                        except Exception as e:
                            print(f"[watch] {p.name} 处理失败: {e}")
                        seen.pop(p, None)
                        stable.pop(p, None)
                else:
                    seen[p] = sig
                    stable[p] = 0
            # 清理已消失文件的跟踪
            alive = {p for p in seen if p.exists()}
            seen = {p: v for p, v in seen.items() if p in alive}
            stable = {p: v for p, v in stable.items() if p in alive}
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[watch] 已退出")
        os._exit(0)
