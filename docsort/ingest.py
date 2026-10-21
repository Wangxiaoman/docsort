"""文件接入层：PDF 逐页产出（文本层优先，无文本层则渲染图像），图片单页产出。"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional, Tuple

import cv2
import numpy as np

try:
    import fitz  # PyMuPDF
except ImportError as e:
    raise ImportError("未安装 PyMuPDF。请执行: pip install PyMuPDF") from e

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}


def supported(path: Path) -> bool:
    return path.suffix.lower() == ".pdf" or path.suffix.lower() in IMAGE_EXTS


def iter_pages(path: Path, ocr_cfg: dict, max_pages: int) -> Iterator[Tuple[int, Optional[str], Optional[np.ndarray]]]:
    """逐页产出 (页码, 文本或None, 图像或None)。

    - PDF 单页有足够文本层 → (i, text, None)，跳过 OCR
    - PDF 单页无文本层（扫描件）→ (i, None, image)，交给预处理+OCR
    - 图片文件 → (0, None, image)
    """
    suffix = path.suffix.lower()
    min_chars = int(ocr_cfg.get("text_layer_min_chars", 30))
    dpi = int(ocr_cfg.get("dpi", 300))

    if suffix == ".pdf":
        with fitz.open(path) as doc:
            limit = min(doc.page_count, max_pages)
            for i in range(limit):
                page = doc.load_page(i)
                text = (page.get_text() or "").strip()
                if len(text) >= min_chars:
                    yield i, text, None
                    continue
                pix = page.get_pixmap(dpi=dpi)
                arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width, pix.n)
                if pix.n == 4:
                    img = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
                else:
                    img = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                yield i, None, img
    elif suffix in IMAGE_EXTS:
        # np.fromfile + imdecode：兼容中文路径
        data = np.fromfile(str(path), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"无法解码图片: {path}")
        yield 0, None, img
    else:
        raise ValueError(f"不支持的文件类型: {suffix}（支持 pdf/{'/'.join(sorted(IMAGE_EXTS))}）")
