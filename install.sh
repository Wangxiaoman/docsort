#!/usr/bin/env bash
# docsort 一键安装脚本（POSIX sh 兼容，bash/sh/dash 均可执行）
# 用法: sh install.sh [--mirror] [--offline 离线wheel目录]
#   --mirror        使用清华 PyPI 镜像加速安装（国内环境推荐）
#   --offline DIR   离线安装：从本地 wheel 目录安装（配合 make_offline_bundle.sh 使用）
set -eu
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
VENV=".venv"
PIP_EXTRA=""
OFFLINE_DIR=""

while [ $# -gt 0 ]; do
  case "$1" in
    --mirror) PIP_EXTRA="-i https://pypi.tuna.tsinghua.edu.cn/simple" ;;
    --offline) OFFLINE_DIR="$2"; shift ;;
    *) echo "未知参数: $1（可用 --mirror / --offline DIR）"; exit 1 ;;
  esac
  shift
done

echo "==> 检查 Python ($PYTHON)"
if ! command -v "$PYTHON" > /dev/null 2>&1; then
  echo "错误: 未找到 $PYTHON。"
  echo "  Debian/Ubuntu:  apt install -y python3 python3-venv python3-pip"
  echo "  CentOS/RHEL:    yum install -y python3"
  echo "  macOS:          系统自带，或 brew install python"
  exit 1
fi

"$PYTHON" - <<'EOF' || exit 1
import sys
v = sys.version_info
if v < (3, 9):
    print(f"错误: Python 版本过低 ({v.major}.{v.minor})，需要 3.9+")
    sys.exit(1)
if v >= (3, 13):
    # rapidocr(onnxruntime) 新版支持 3.13；paddle 2.x 仅到 3.12
    print(f"  提示: Python {v.major}.{v.minor} 可用 rapidocr 后端；"
          f"如需 ocr.backend=paddle 请改用 3.9~3.12")
else:
    print(f"  Python {v.major}.{v.minor}.{v.micro} OK")
EOF

echo "==> 创建虚拟环境 $VENV"
if [ ! -d "$VENV" ]; then
  # venv 模块缺失时（Debian 最小系统常见）给出可执行的修复命令
  if ! "$PYTHON" -m venv "$VENV" 2>venv_err.log; then
    cat venv_err.log >&2
    rm -rf "$VENV" venv_err.log
    echo "错误: 创建虚拟环境失败。多数情况是缺少 venv 组件："
    echo "  Debian/Ubuntu:  apt install -y python3-venv"
    exit 1
  fi
  rm -f venv_err.log
fi
# shellcheck disable=SC1091
. "$VENV/bin/activate"

echo "==> 升级 pip"
pip install --upgrade pip -q

if [ -n "$OFFLINE_DIR" ]; then
  echo "==> 离线安装依赖（wheel 目录: $OFFLINE_DIR）"
  INSTALL_CMD="pip install --no-index --find-links $OFFLINE_DIR -r requirements.txt"
else
  if [ -n "$PIP_EXTRA" ]; then
    echo "==> 使用清华镜像安装依赖"
  else
    echo "==> 安装依赖（首次需联网，rapidocr 约 60MB）"
  fi
  # shellcheck disable=SC2086
  INSTALL_CMD="pip install -r requirements.txt $PIP_EXTRA"
fi
# shellcheck disable=SC2086
$INSTALL_CMD

echo "==> 校验基础依赖"
python -c "import fitz, cv2, yaml, numpy; print('  基础依赖 OK (PyMuPDF/OpenCV/PyYAML)')"

echo "==> 校验 OCR 后端"
# shellcheck disable=SC2086
python - <<'EOF'
import importlib
backends = []
for mod, name in (("rapidocr_onnxruntime", "rapidocr"), ("paddleocr", "paddle")):
    try:
        importlib.import_module(mod)
        backends.append(name)
        print(f"  {name} OK")
    except ImportError:
        pass
if not backends:
    print("  [警告] 未安装任何 OCR 后端，可改用 ocr.backend=text（仅 PDF 文本层）")
else:
    try:
        import yaml
        with open("rules.yaml", encoding="utf-8") as f:
            backend = (yaml.safe_load(f).get("ocr", {}) or {}).get("backend", "paddle")
        status = "OK" if backend in backends else "未安装!"
        print(f"  rules.yaml 当前使用: {backend} -> {status}")
    except FileNotFoundError:
        print(f"  [提示] 未找到 rules.yaml，默认后端 paddle；可用后端: {', '.join(backends)}")
EOF

echo "==> 校验命令行入口"
python -m docsort --help > /dev/null && echo "  docsort 命令 OK"

echo
echo "安装完成。使用方式："
if [ -f rules.yaml ]; then
  echo "  rules.yaml 已存在，直接使用（可用 tests/ocr_probe.py 自检 OCR 后端）"
else
  echo "  首次使用请创建配置: cp rules.example.yaml rules.yaml（如不存在则参考 README）"
fi
echo "  ./docsort.sh run <文件或目录> --config rules.yaml"
echo "  ./docsort.sh watch <监控目录> --config rules.yaml"
