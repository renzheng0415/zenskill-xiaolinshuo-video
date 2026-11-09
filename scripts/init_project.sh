#!/usr/bin/env bash
# 用法：bash scripts/init_project.sh <项目目录>
# 建好项目骨架（input/ public/ build/ render/ music/ footage_raw/），复制字体，写 PROGRESS.md 模板。幂等。
set -euo pipefail
source "$(dirname "$0")/env.sh"
P="${1:?用法: init_project.sh <项目目录>}"
mkdir -p "$P"/{input,footage_raw,music/candidates,public/assets,public/footage,public/fonts,build,render/parts,render/review}
P="$(cd "$P" && pwd)"
for f in "$XL_ENGINE_DIR"/public/fonts/*.otf; do
  [ -e "$f" ] || { echo "⚠ 引擎里没有字体文件（先跑 install.sh），渲染会回落系统字体"; break; }
  [ -e "$P/public/fonts/$(basename "$f")" ] || cp "$f" "$P/public/fonts/"
done
[ -e "$P/credits.json" ] || echo "[]" > "$P/credits.json"
[ -e "$P/PROGRESS.md" ] || cat > "$P/PROGRESS.md" <<EOF
# PROGRESS · $(basename "$P")
（每完成一步追加一节：时间、产物路径、校验结果、下一步。中断后从这里接着做。）

## $(date '+%Y-%m-%d %H:%M') 初始化
- 项目骨架已建：input/ public/ build/ render/ music/ footage_raw/
- 下一步：把 A-roll mp4 / voice.wav / SRT / breakpoints.tsv / gestures.tsv 放进 input/，运行 prepare_aroll.py
EOF
echo "✓ 项目就绪：$P"
ls "$P"
