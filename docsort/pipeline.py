"""处理流水线：单个文件从接入到分类到路由的完整编排。"""
from __future__ import annotations

import shutil
import time
import traceback
from pathlib import Path
from typing import List

from . import audit, ingest, preprocess, route
from .classify import Classifier
from .ocr import BaseOCR


def _failed_folder(cfg: dict) -> Path:
    raw = cfg.get("routing", {}).get("failed_folder", "./failed")
    if not raw:
        return Path("")  # 置空则原地保留
    p = Path(raw).expanduser()
    return p if p.is_absolute() else Path.cwd() / p


def process_file(path: Path, cfg: dict, ocr: BaseOCR, verbose: bool = True) -> dict:
    """处理单个文件，返回审计记录。路由/识别异常时移入失败文件夹并抛出。"""
    clf = Classifier(cfg)
    total = {name: 0.0 for name in clf._compiled}
    hits_all: List[dict] = []
    pages_used = 0
    stopped_early = False

    try:
        for idx, text, image in ingest.iter_pages(
                path, cfg.get("ocr", {}), clf.max_pages):
            pages_used += 1
            if image is not None:
                t0 = time.time()
                if verbose:
                    h, w = image.shape[:2]
                    if not cfg.get("preprocess", {}).get("enabled", True):
                        print(f"  第 {idx + 1} 页图像 {w}x{h}，预处理已关闭，直接 OCR…")
                    else:
                        print(f"  第 {idx + 1} 页图像 {w}x{h}，预处理中…")
                img = preprocess.process(image, cfg.get("preprocess", {}))
                if verbose:
                    print(f"  预处理完成 ({time.time() - t0:.1f}s)，OCR 识别中…")
                t1 = time.time()
                text = ocr.recognize(img)
                if verbose:
                    print(f"  OCR 完成 ({time.time() - t1:.1f}s)，{len(text.splitlines())} 行文本")
            if text:
                scores, hits = clf.score_page(text)
                for k, v in scores.items():
                    total[k] = total.get(k, 0.0) + v
                hits_all.extend(hits)
            if verbose:
                print(f"  第 {idx + 1} 页完成，当前得分: "
                      f"{ {k: int(v) for k, v in total.items() if v > 0} }")
            if pages_used >= clf.max_pages or clf.should_stop(total):
                stopped_early = clf.should_stop(total) and pages_used < clf.max_pages
                break

        doc_type, confidence, low_conf = clf.decide(total, pages_used)
        result = {
            "file": str(path),
            "type": doc_type,
            "confidence": confidence,
            "low_confidence": low_conf,
            "pages_used": pages_used,
            "stopped_early": stopped_early,
            "scores": {k: int(v) for k, v in total.items() if v > 0},
            "hits": hits_all[:50],
        }

        actions = route.dispatch(path, doc_type, confidence, cfg, result)
        result["actions"] = actions
        audit.append(cfg, result)
        if verbose:
            print(f"  => 判定: {doc_type} (置信度 {confidence:.2f}, "
                  f"扫描 {pages_used} 页{'，提前终止' if stopped_early else ''})")
            for a in actions:
                print(f"     {a}")
        return result
    except Exception as e:
        record = {
            "file": str(path),
            "type": "error",
            "error": str(e),
            "traceback": traceback.format_exc(limit=3),
        }
        try:
            audit.append(cfg, record)
        except Exception:
            pass
        failed = _failed_folder(cfg)
        if str(failed):
            failed.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(path), str(failed / path.name))
                record["moved_to"] = str(failed / path.name)
            except shutil.Error:
                pass  # 同名冲突等，保留原地
        if verbose:
            print(f"  [error] 处理失败: {e}")
        raise


def process_target(target: Path, cfg: dict, ocr: BaseOCR, verbose: bool = True) -> List[dict]:
    """处理一个文件或目录下所有支持文件。"""
    from .ingest import supported

    results: List[dict] = []
    if target.is_file():
        if not supported(target):
            raise ValueError(f"不支持的文件类型: {target}")
        results.append(process_file(target, cfg, ocr, verbose))
        return results
    if target.is_dir():
        files = sorted(p for p in target.iterdir()
                       if p.is_file() and supported(p) and not p.name.startswith("."))
        if verbose:
            print(f"目录 {target} 共 {len(files)} 个待处理文件")
        for p in files:
            if verbose:
                print(f"[{p.name}]")
            try:
                results.append(process_file(p, cfg, ocr, verbose))
            except Exception:
                continue  # 失败已入失败文件夹，继续处理下一个
        return results
    raise FileNotFoundError(f"路径不存在: {target}")
