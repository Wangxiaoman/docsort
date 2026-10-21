#!/usr/bin/env bash
# docsort 执行包装脚本（自动激活虚拟环境）
# 用法:
#   ./docsort.sh run <文件或目录> --config rules.yaml
#   ./docsort.sh watch <监控目录> --config rules.yaml
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "尚未安装，请先执行: sh install.sh"
  exit 1
fi
# 无 UTF-8 locale 的极简系统上保证中文路径/输出正常
if [ -z "${LANG:-}" ] || [ "${LANG:-}" = "C" ] || [ "${LANG:-}" = "POSIX" ]; then
  LANG=C.UTF-8
  LC_ALL=C.UTF-8
  export LANG LC_ALL
fi
# shellcheck disable=SC1091
. .venv/bin/activate
exec python -m docsort "$@"
