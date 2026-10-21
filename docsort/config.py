"""YAML 配置加载与默认值合并."""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

DEFAULTS = {
    "ocr": {
        "backend": "paddle",          # paddle | rapidocr | text（仅用 PDF 文本层，图片无法识别）
        "lang": "ch",
        "use_angle_cls": True,        # 方向分类器，自动转正横竖页
        "dpi": 300,                   # PDF 渲染 DPI
        "text_layer_min_chars": 30,   # PDF 单页文本层达到该字符数则跳过 OCR
    },
    "preprocess": {
        "enabled": True,              # 总开关: false 则跳过全部预处理,图像直接送 OCR
        "max_side": 2000,             # 长边超过该值先降采样(性能保护,总开关关闭时仍生效;置 0 彻底关闭)
        "deshadow": True,             # 去阴影（先做，避免阴影干扰后续步骤）
        "denoise": True,              # 去噪
        "deskew": True,               # 纠偏
        "clahe": True,                # 对比度增强
    },
    "classification": {
        "early_stop": True,           # 逐页累计计分，命中即停
        "max_pages": 3,               # 最多识别前几页
        "min_margin": 2,              # 第一名需领先第二名的分数
        "default_threshold": 5,       # 模板未单独配置 threshold 时的默认阈值
    },
    "routing": {
        "output_dir": "./sorted",     # 分类输出根目录,模板中用 {output_dir} 引用; CLI --output-dir 可覆盖
        "action": "move",             # move | copy（folder 路由对原文件的处理方式）
        "on_conflict": "rename",      # rename | skip | overwrite（目标文件已存在时）
        "failed_folder": "./failed",  # 处理异常的文件移入此处；置空则原地保留
        "archive": "",                # 无 folder 路由时文件的归档处（watch 模式建议配置）；置空则原地保留
    },
    "audit": {
        "log": "./audit/docsort.jsonl",
    },
    "templates": {},                  # 分类模板，见 rules.example.yaml
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load(path) -> dict:
    """加载 YAML 配置并与默认值合并。path 不存在时抛 FileNotFoundError."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"配置文件不存在: {p.resolve()}")
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return _deep_merge(DEFAULTS, data)
