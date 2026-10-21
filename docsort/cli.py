"""docsort 命令行入口。

用法:
  docsort run <文件或目录> --config rules.yaml     # 单文件 / 批量
  docsort watch <目录> --config rules.yaml         # 常驻监控
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, config
from .ocr import create_ocr
from .pipeline import process_target
from .watcher import watch


def _apply_preprocess_flags(args, cfg: dict) -> None:
    """命令行预处理开关覆盖 YAML 配置。"""
    pp = cfg.setdefault("preprocess", {})
    if getattr(args, "no_preprocess", False):
        pp["enabled"] = False
    for step in ("deshadow", "denoise", "deskew", "clahe"):
        if getattr(args, f"no_{step}", False):
            pp[step] = False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="docsort",
        description="本地文档识别分类路由工具：PDF/图片 → 预处理 → OCR → 分类 → 路由")
    parser.add_argument("--version", action="version", version=f"docsort {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # 预处理开关（run/watch 共用）：不传则按配置文件执行
    def add_preprocess_flags(p):
        p.add_argument("--no-preprocess", action="store_true",
                       help="跳过全部预处理（去噪/纠偏/去阴影/增强），图像直接 OCR")
        p.add_argument("--no-denoise", action="store_true", help="关闭去噪")
        p.add_argument("--no-deshadow", action="store_true", help="关闭去阴影")
        p.add_argument("--no-deskew", action="store_true", help="关闭纠偏")
        p.add_argument("--no-clahe", action="store_true", help="关闭对比度增强")

    p_run = sub.add_parser("run", help="处理单个文件或整个目录")
    p_run.add_argument("path", help="待处理文件或目录")
    p_run.add_argument("--config", default="rules.yaml", help="YAML 配置文件路径")
    p_run.add_argument("--quiet", action="store_true", help="减少输出")
    p_run.add_argument("--output-dir", default=None, metavar="DIR",
                       help="分类输出根目录，覆盖配置里的 routing.output_dir（模板中 {output_dir}）")
    add_preprocess_flags(p_run)

    p_watch = sub.add_parser("watch", help="监控目录，新文件自动处理")
    p_watch.add_argument("path", help="监控目录")
    p_watch.add_argument("--config", default="rules.yaml", help="YAML 配置文件路径")
    p_watch.add_argument("--interval", type=float, default=3.0, help="轮询间隔秒数")
    p_watch.add_argument("--output-dir", default=None, metavar="DIR",
                         help="分类输出根目录，覆盖配置里的 routing.output_dir（模板中 {output_dir}）")
    add_preprocess_flags(p_watch)

    args = parser.parse_args(argv)
    cfg = config.load(args.config)
    _apply_preprocess_flags(args, cfg)
    if getattr(args, "output_dir", None):
        cfg.setdefault("routing", {})["output_dir"] = args.output_dir

    ocr = create_ocr(cfg.get("ocr", {}))
    backend = cfg.get("ocr", {}).get("backend", "paddle")
    print(f"docsort {__version__} ｜ OCR 后端: {backend} ｜ 配置: {args.config}")

    if args.command == "run":
        process_target(Path(args.path), cfg, ocr, verbose=not args.quiet)
        return 0
    if args.command == "watch":
        directory = Path(args.path)
        if not directory.is_dir():
            print(f"错误: {directory} 不是目录", file=sys.stderr)
            return 2
        watch(directory, cfg, ocr, interval=args.interval)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
