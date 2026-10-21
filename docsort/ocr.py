"""OCR 后端封装。支持 paddleocr / rapidocr(onnxruntime) / 仅文本层三种。"""
from __future__ import annotations

import numpy as np


class OCRError(RuntimeError):
    pass


class BaseOCR:
    name = "base"

    def __init__(self, cfg: dict = None):
        pass

    def recognize(self, img: np.ndarray) -> str:
        raise NotImplementedError


class TextOnlyOCR(BaseOCR):
    """不做图像 OCR。PDF 靠文本层，纯图片页将无文本产出。"""

    name = "text"

    def recognize(self, img: np.ndarray) -> str:
        return ""


class PaddleOCRWrapper(BaseOCR):
    """PaddleOCR CPU 版（PP-OCRv4），纯本地推理。"""

    name = "paddle"

    def __init__(self, cfg: dict):
        import os
        import platform
        import time

        try:
            import paddle
            from paddleocr import PaddleOCR  # 延迟导入，未安装时给出清晰提示
        except ImportError as e:
            raise OCRError(
                "未安装 paddleocr。请先执行: pip install paddlepaddle paddleocr\n"
                "或改用轻量后端: 配置 ocr.backend=rapidocr 并 pip install rapidocr-onnxruntime"
            ) from e

        # macOS 上 OpenMP 线程超订是首次推理挂起的常见原因，默认单线程最稳
        threads = int(cfg.get("cpu_threads", 1))
        os.environ.setdefault("OMP_NUM_THREADS", str(threads))
        try:
            paddle.set_num_threads(threads)
        except AttributeError:  # paddle 2.x 用 set_flags
            try:
                paddle.set_flags({"FLAGS_cpu_numeric_threads": threads,
                                  "FLAGS_omp_num_threads": threads})
            except Exception:
                pass
        except Exception:
            pass
        # mkldnn 在部分 macOS/Python 组合下会挂起，默认仅非 macOS 开启
        mkldnn = bool(cfg.get("enable_mkldnn", platform.system() != "Darwin"))

        print(f"[ocr] paddle {paddle.__version__} ｜ 线程 {threads} ｜ "
              f"mkldnn {'on' if mkldnn else 'off'} ｜ 初始化引擎…")
        t0 = time.time()
        self._engine = PaddleOCR(
            use_angle_cls=bool(cfg.get("use_angle_cls", True)),
            lang=cfg.get("lang", "ch"),
            show_log=bool(cfg.get("show_log", False)),
            cpu_threads=threads,
            enable_mkldnn=mkldnn,
        )
        print(f"[ocr] 引擎加载完成 ({time.time() - t0:.1f}s)，预热推理中（首次较慢）…")
        t1 = time.time()
        dummy = np.full((64, 320, 3), 255, dtype=np.uint8)
        self._engine.ocr(dummy, cls=False)
        print(f"[ocr] 预热完成 ({time.time() - t1:.1f}s)，引擎就绪")

    def recognize(self, img: np.ndarray) -> str:
        result = self._engine.ocr(img, cls=True)
        lines = []
        for page in result or []:
            if not page:
                continue
            for item in page:
                # 2.x 格式: [box, (text, score)]
                if item and len(item) >= 2 and item[1]:
                    text = item[1][0]
                    if text:
                        lines.append(text)
        return "\n".join(lines)


class RapidOCRWrapper(BaseOCR):
    """RapidOCR（onnxruntime），依赖轻，精度接近 PaddleOCR。"""

    name = "rapidocr"

    def __init__(self, cfg: dict):
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as e:
            raise OCRError(
                "未安装 rapidocr-onnxruntime。请执行: pip install rapidocr-onnxruntime"
            ) from e
        self._engine = RapidOCR()

    def recognize(self, img: np.ndarray) -> str:
        result, _ = self._engine(img)
        lines = []
        for item in result or []:
            # 格式: [box, text, score]
            if item and len(item) >= 2 and item[1]:
                lines.append(item[1])
        return "\n".join(lines)


_BACKENDS = {
    "paddle": PaddleOCRWrapper,
    "rapidocr": RapidOCRWrapper,
    "text": TextOnlyOCR,
}


def create_ocr(cfg: dict) -> BaseOCR:
    backend = (cfg.get("backend") or "paddle").lower()
    if backend not in _BACKENDS:
        raise OCRError(f"未知 OCR 后端: {backend}（可选 paddle / rapidocr / text）")
    return _BACKENDS[backend](cfg)
