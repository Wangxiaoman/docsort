"""图像预处理：去阴影、去噪、纠偏、对比度增强。每步可经配置开关。"""
from __future__ import annotations

import cv2
import numpy as np


def deshadow(img: np.ndarray) -> np.ndarray:
    """形态学估计背景并相除，消除扫描/拍照阴影。"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
    bg = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
    bg = cv2.GaussianBlur(bg, (0, 0), 3)
    norm = cv2.divide(gray, bg, scale=255)
    return cv2.cvtColor(norm, cv2.COLOR_GRAY2BGR)


def denoise(img: np.ndarray) -> np.ndarray:
    """非局部均值去噪，保边缘去扫描噪点。"""
    return cv2.fastNlMeansDenoisingColored(img, None, 5, 5, 7, 15)


def deskew(img: np.ndarray) -> np.ndarray:
    """基于文本主方向的最小外接矩形纠偏，处理 ±45° 内倾斜。"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bitwise_not(gray)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) < 50:  # 内容太少，不足以估计角度
        return img
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.5 or abs(angle) > 45:  # 角度过小或疑似误判
        return img
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


def enhance(img: np.ndarray) -> np.ndarray:
    """CLAHE 自适应直方图均衡，提升暗淡扫描件对比度。"""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


def downscale(img: np.ndarray, max_side: int) -> np.ndarray:
    """大图先降采样：OCR 检测端内部会缩到 960，超大图直接预处理极慢且无精度收益。"""
    h, w = img.shape[:2]
    m = max(h, w)
    if m <= max_side:
        return img
    scale = max_side / float(m)
    return cv2.resize(img, (int(w * scale), int(h * scale)),
                      interpolation=cv2.INTER_AREA)


def process(img: np.ndarray, cfg: dict) -> np.ndarray:
    """按配置顺序执行预处理流水线。enabled=False 时跳过全部增强步骤(仅保留降采样性能保护)。"""
    max_side = int(cfg.get("max_side", 2000))
    if max_side > 0:
        img = downscale(img, max_side)
    if not cfg.get("enabled", True):
        return img
    steps = [
        ("deshadow", deshadow),
        ("denoise", denoise),
        ("deskew", deskew),
        ("clahe", enhance),
    ]
    for key, fn in steps:
        if cfg.get(key, False):
            try:
                img = fn(img)
            except cv2.error as e:  # 单步失败不中断整体流程
                print(f"[warn] 预处理步骤 {key} 失败，跳过: {e}")
    return img
