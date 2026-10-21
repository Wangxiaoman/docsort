#!/usr/bin/env bash
# 制作 docsort 离线安装包（供信创内网服务器使用）
#
# 用法: sh make_offline_bundle.sh [架构] [python版本]
#   架构:        aarch64(默认,飞腾/鲲鹏) | x86_64(海光/兆芯)
#   python版本:  39 | 310 | 311 | 312 | 313  (默认 39)
#
# 示例:
#   sh make_offline_bundle.sh aarch64 39                # 麒麟V10/飞腾, Python 3.9
#   sh make_offline_bundle.sh x86_64 311                # UOS/海光, Python 3.11
#   sh make_offline_bundle.sh aarch64 39 mirror         # 走清华镜像下载
#
# 产物: docsort_offline_<架构>_<版本>.tar.gz
#   目标机解压后: sh install.sh --offline pkgs
#
# 注意: 需在联网机器上执行（macOS/Linux 均可），pip 会交叉下载目标平台的 wheel；
#       目标机的 Python 版本必须与第二个参数一致。
set -eu
cd "$(dirname "$0")"

ARCH="${1:-aarch64}"
PYVER="${2:-39}"
EXTRA=""
if [ "${3:-}" = "mirror" ] || [ "${PIP_INDEX_URL:-}" = "mirror" ]; then
  EXTRA="-i https://pypi.tuna.tsinghua.edu.cn/simple"
fi

case "$ARCH" in
  aarch64) PLAT="manylinux2014_aarch64" ;;
  x86_64)  PLAT="manylinux2014_x86_64" ;;
  *) echo "不支持的架构: $ARCH（可选 aarch64 / x86_64）"; exit 1 ;;
esac
case "$PYVER" in
  39|310|311|312|313) ;;
  *) echo "不支持的 Python 版本: $PYVER（可选 39/310/311/312/313）"; exit 1 ;;
esac

echo "==> 下载 ${PLAT} / CPython ${PYVER} 的 wheel 到 pkgs/"
rm -rf pkgs
# shellcheck disable=SC2086
pip download \
  -r requirements.txt \
  -d pkgs \
  --only-binary=:all: \
  --platform "$PLAT" \
  --python-version "$PYVER" \
  --implementation cp \
  --abi "cp${PYVER}" \
  $EXTRA

echo "==> 打包源码 + wheel"
TARBALL="docsort_offline_${ARCH}_${PYVER}.tar.gz"
tar czf "$TARBALL" \
  --exclude .venv --exclude __pycache__ --exclude "*.pyc" \
  --exclude audit --exclude sorted --exclude failed --exclude case \
  --exclude "docsort_offline_"*.tar.gz \
  docsort/ tests/ rules.yaml README.md requirements.txt \
  install.sh docsort.sh install.bat docsort.bat pkgs 2>/dev/null \
  || tar czf "$TARBALL" \
       --exclude .venv --exclude __pycache__ --exclude "*.pyc" \
       --exclude audit --exclude sorted --exclude failed \
       --exclude "docsort_offline_"*.tar.gz \
       . pkgs

echo "==> 完成: $TARBALL ($(du -h "$TARBALL" | cut -f1))"
echo "目标机（内网）部署："
echo "  1. tar xzf $TARBALL && cd docsort"
echo "  2. sh install.sh --offline pkgs"
