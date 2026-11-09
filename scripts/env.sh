# shellcheck shell=bash
# 用法：source scripts/env.sh   —— 把本 skill 的 node（如 install.sh 装在 .tools）、Python venv、引擎路径放进环境
_xl_src="${BASH_SOURCE[0]:-$0}"
XL_SKILL_DIR="$(cd "$(dirname "$_xl_src")/.." && pwd)"
export XL_SKILL_DIR
export XL_ENGINE_DIR="${XL_ENGINE_DIR:-$XL_SKILL_DIR/engine}"
[ -d "$XL_SKILL_DIR/.tools/node/bin" ] && export PATH="$XL_SKILL_DIR/.tools/node/bin:$PATH"
[ -d "$XL_SKILL_DIR/.tools/ffmpeg" ] && export PATH="$XL_SKILL_DIR/.tools/ffmpeg:$PATH"
if [ -x "$XL_SKILL_DIR/.venv/bin/python" ]; then
  export XL_PY="$XL_SKILL_DIR/.venv/bin/python"
else
  export XL_PY="$(command -v python3)"
fi
export PYTHONDONTWRITEBYTECODE=1
# Remotion 下载的 Chrome Headless Shell 缓存在引擎 node_modules 里，无需额外变量
unset _xl_src
