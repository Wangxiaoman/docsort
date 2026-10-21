"""PaddleOCR 独立探针：绕过 docsort 流水线，确认 paddle 能否有效调用。

用法: cd docsort && .venv/bin/python tests/ocr_probe.py

输出解读:
- 引擎初始化/首次推理能完成并打印识别文本 → paddle 有效，问题在 docsort 之外
- 卡在"引擎初始化"或"首次推理" → paddle 环境本身有问题（常见: x86_64 Python 走
  Rosetta、OpenMP 线程挂起、内存不足），建议换 rapidocr 后端:
  pip install rapidocr-onnxruntime 并把 rules.yaml 里 ocr.backend 改为 rapidocr
"""
import platform
import sys
import sysconfig
import time

print(f"Python: {sys.version.split()[0]} ({sysconfig.get_platform()})")
print(f"硬件架构: {platform.machine()}")
if sysconfig.get_platform().endswith("x86_64") and platform.machine() == "arm64":
    print("[warn] Python 是 x86_64 版本，paddle 将在 Rosetta 下运行，又慢又易挂，"
          "建议用 ARM 版 Python 重建 venv 或改用 rapidocr 后端")

import cv2
import numpy as np

import paddle

print(f"paddle: {paddle.__version__}")
try:
    paddle.set_num_threads(1)
except Exception:
    pass  # paddle 2.x 运行期不允许改线程 flag，靠 OMP_NUM_THREADS + cpu_threads 参数

from paddleocr import PaddleOCR

img = np.full((64, 320, 3), 255, dtype=np.uint8)
cv2.putText(img, "HELLO 123456", (10, 45),
            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)

t = time.time()
ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=True,
                cpu_threads=1, enable_mkldnn=False)
print(f"① 引擎初始化: {time.time() - t:.1f}s")

t = time.time()
result = ocr.ocr(img, cls=False)
t1 = time.time() - t
print(f"② 首次推理: {t1:.1f}s")

t = time.time()
ocr.ocr(img, cls=False)
print(f"③ 二次推理: {time.time() - t:.1f}s")

texts = [item[1][0] for page in (result or []) for item in (page or []) if item]
print(f"④ 识别结果: {texts}")
if any("123456" in s for s in texts):
    print("结论: paddle 调用有效 ✓")
else:
    print("结论: paddle 可运行但未识别到样例文本，需进一步检查")
