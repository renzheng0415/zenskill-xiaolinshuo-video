#!/usr/bin/env bash
# 开箱自检：合成 6 秒素材 → 走完整条流水线（含模板生成、conform、编译检查、混音、分段渲染、封面、拼接、聊天版）→ verify。
# 用法：bash scripts/selftest.sh [工作目录，默认 <skill>/selftest_run]     环境变量 XL_CONCURRENCY 控制渲染并发
set -euo pipefail
exec </dev/null   # 后台运行时 ffmpeg 读终端会被 SIGTTIN 挂起
source "$(dirname "$0")/env.sh"
S="$XL_SKILL_DIR/scripts"; PY="$XL_PY"
P="${1:-$XL_SKILL_DIR/selftest_run}"   # 不用点开头的目录名：Remotion 帧序列目录路径里不能有 "."
T0=$(date +%s)
step(){ printf "\n\033[1;36m[%s] %s\033[0m\n" "$(( $(date +%s) - T0 ))s" "$*"; }
rm -rf "$P"; mkdir -p "$P"

step "1/12 初始化项目 + 合成输入"
bash "$S/init_project.sh" "$P" >/dev/null
bash "$XL_SKILL_DIR/examples/demo/make_inputs.sh" "$P"

step "2/12 A-roll 入库体检"
"$PY" "$S/prepare_aroll.py" "$P" --aroll "$P/input/aroll.mp4" --voice "$P/input/voice.wav"

step "3/12 从 SRT+断点+手势生成镜头表模板（流程验证）"
"$PY" "$S/build_shotlist.py" "$P" --srt "$P/input/aroll.srt" --breakpoints "$P/input/breakpoints.tsv" --gestures "$P/input/gestures.tsv" \
  --title "DEMO" --out shotlist_template.yaml --force
"$PY" "$S/compile_shotlist.py" "$P" --draft --shotlist "$P/shotlist_template.yaml" --film-out "$P/build/film_template.json" | tail -3

step "4/12 素材 conform（30fps→0.8x、25fps→0.96x 整帧）"
"$PY" "$S/conform_footage.py" "$P" --all
"$PY" - "$P" <<'EOF'
import json,sys; db=json.load(open(sys.argv[1]+"/build/footage.json"))
assert db["demo_city"]["rate"]==0.8 and db["demo_grid"]["rate"]==0.96, db
print("✓ conform 速度正确：demo_city 30fps→0.8x，demo_grid 25fps→0.96x")
EOF

step "5/12 编译 3 镜样片镜头表（严格检查）"
cp "$XL_SKILL_DIR/examples/demo/shotlist.yaml" "$P/shotlist.yaml"
"$PY" "$S/compile_shotlist.py" "$P"
step "5b 规则检查能拦住问题：把 s2 拉长盖住硬切 → 必须报 ERROR"
sed 's/to: 3.9/to: 4.6/; s/from: 3.9/from: 4.6/' "$P/shotlist.yaml" > "$P/shotlist_bad.yaml"
BAD_RC=0; BAD_OUT=$("$PY" "$S/compile_shotlist.py" "$P" --shotlist "$P/shotlist_bad.yaml" --film-out "$P/build/film_bad.json" 2>&1) || BAD_RC=$?
echo "$BAD_OUT" | grep "硬切" || true
if [ "$BAD_RC" != 0 ] && echo "$BAD_OUT" | grep -q "ERROR.*硬切"; then echo "✓ 硬切落在人物镜头被拦住（exit $BAD_RC）"; else echo "✗ 规则检查失效"; exit 1; fi

step "6/12 混音（人声 + 拍点循环音乐床 -18dB + 合成音效 → -16 LUFS）"
"$PY" "$S/mix.py" "$P"

step "7/12 分段渲染（open / ch1）+ 审片版"
"$PY" "$S/render_parts.py" "$P" --all --review

step "8/12 封面 16:9 + 9:16"
"$PY" "$S/cover.py" "$P"

step "9/12 拼接：封面替换前 3 帧 + 原画 + 聊天版（两遍 <95MB）"
"$PY" "$S/assemble.py" "$P" --cover "$P/render/cover_16x9.png"

step "10/12 组件画廊静帧（bars/line/compare/list/timeline/chapter）"
"$PY" "$S/compile_shotlist.py" "$P" --shotlist "$XL_SKILL_DIR/examples/demo/gallery.yaml" --film-out "$P/build/gallery.json"
mkdir -p "$P/render/gallery"
for fr in 18 42 66 90 114 138; do
  (cd "$XL_ENGINE_DIR" && npx --no-install remotion still "$P/build/bundle" Film "$P/render/gallery/g_$fr.png" --props="$P/build/gallery.json" --frame=$fr --log=error)
done
ls "$P/render/gallery" | wc -l | xargs -I{} echo "✓ {} 张画廊静帧"

step "11/12 署名文案"
"$PY" "$S/credits_caption.py" "$P" --all | tail -2

step "12/12 校验成片（流式）"
RC=0
"$PY" "$S/verify.py" "$P/render/full.mp4" --expect-frames 144 --voice "$P/build/voice.wav" --cover "$P/render/cover_16x9.png" --json "$P/render/verify_full.json" || RC=1
"$PY" "$S/verify.py" "$P/render/full_1080p_chat.mp4" --expect-frames 144 --voice "$P/build/voice.wav" --max-mb 95 --json "$P/render/verify_chat.json" || RC=1

echo
ls -la "$P/render" | grep -E "mp4|png" || true
if [ $RC = 0 ]; then
  printf "\n\033[1;32mSELFTEST PASS\033[0m（%ss）成片：%s\n" "$(( $(date +%s) - T0 ))" "$P/render/full.mp4"
else
  printf "\n\033[1;31mSELFTEST FAIL\033[0m 见上面 FAIL 项\n"; exit 1
fi
