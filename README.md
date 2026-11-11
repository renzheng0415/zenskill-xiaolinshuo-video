# zenskill-xiaolinshuo-video · 小Lin说式横屏口播成片

把**已定稿的口播 A-roll**（数字人或真人出镜）做成「小Lin说」风格的 16:9 横屏视频：
人物左右切换 + 推镜、另一侧出图表/实拍，B-roll 跟着 A-roll 走并盖住硬切和弱口型，可商用素材 + 署名登记，
音乐床 + 音效混到 -16 LUFS，分段渲染 → 拼接 → 流式校验 → 封面 → <95MB 聊天版。

完整流程、规则与命令见 **[SKILL.md](SKILL.md)**。

### 风格规则（v2）
镜头表现在按"句型"自动起草：开场钩子、术语、主角数字、数字序列、对比、因果链、清单、故事、设问、结论各有对应的镜头写法，
规则来自对小Lin说官方参考片的逐段拆解（`references/xiaolin_style_rules.md`）。铁律不变：硬切/弱口型必须盖 B-roll，屏幕数字必须和口播一致，只用可商用素材，-16 LUFS。
可选：先在 ChatCut 用 Talking-Head Edit Recreation 粗剪，再回本地质检出片（SKILL.md 步骤 2B）。


## 1. 安装（macOS / Linux，一条命令，可重复运行）

```bash
cd zenskill-xiaolinshuo-video
bash install.sh
```

会检查并按需安装：

| 组件 | 说明 |
|---|---|
| Node.js ≥ 22 | macOS：`brew install node@22`；Linux：NodeSource apt，无 sudo 时下载官方二进制到 `.tools/node` |
| 引擎 npm 依赖 | `engine/` 下 `npm ci`，package-lock 锁定 `remotion` 与全部 `@remotion/*` = **4.0.408** |
| ffmpeg / ffprobe | 需带 libx264；macOS brew，Linux apt |
| Python ≥ 3.10 venv | `.venv/`，装 `requirements.txt`：numpy、scipy、soundfile、pyloudnorm、PyYAML |
| CJK 字体 | Noto Sans SC Bold / Black（SIL OFL 1.1），从 notofonts/noto-cjk 下载到 `engine/public/fonts/` |
| 音效 | 用代码合成到 `assets/sfx/`（无第三方版权） |
| Chrome Headless Shell | `npx remotion browser ensure`；Linux 另装 Chrome 运行库（libnss3、libgbm1 等） |

最后打印自检表（全部 ✓ 才算装好）。选项：`XL_SKIP_SYSTEM=1` 跳过系统包，`XL_NODE_MAJOR=22` 指定 Node 主版本。

## 2. 开箱自检（约 1 分钟）

```bash
bash scripts/selftest.sh
```

用 ffmpeg 合成 6 秒假 A-roll（testsrc + 正弦"人声"）、SRT、硬切断点、手势表、30fps/25fps 两条空镜和一首短音乐，
然后跑完整流水线：入库体检 → 模板生成 → conform（验证 0.8x / 0.96x）→ 编译 3 镜镜头表（并验证规则检查能拦住"硬切落在人物镜头"）
→ 混音 → 分段渲染 + 审片版 → 封面 16:9/9:16 → 拼接（封面替换前 3 帧）+ 聊天版 → 组件画廊静帧 → 署名文案 → **verify**。
看到 `SELFTEST PASS` 即可。产物在 `selftest_run/render/`（`full.mp4`、`full_1080p_chat.mp4`、`cover_*.png`、`review/`、`gallery/`）。

## 3. 用在真实项目上

```bash
source scripts/env.sh                      # 之后用 $XL_PY 跑脚本
S=$XL_SKILL_DIR/scripts; P=~/videos/ep01   # 项目目录（路径里不要有 "."）

bash $S/init_project.sh $P
cp aroll.mp4 voice.wav aroll.srt breakpoints.tsv gestures.tsv $P/input/

$XL_PY $S/prepare_aroll.py   $P --aroll $P/input/aroll.mp4 --voice $P/input/voice.wav
$XL_PY $S/build_shotlist.py  $P --srt $P/input/aroll.srt --breakpoints $P/input/breakpoints.tsv --gestures $P/input/gestures.tsv --title "栏目条"
#   → 精修 $P/shotlist.yaml：给 B-roll 填素材、设计图表、安排人物左右/推镜
$XL_PY $S/fetch_footage.py search "城市 夜景" "city night" --save hits.json
$XL_PY $S/fetch_footage.py get $P --hits hits.json --pick 1 --id city_night
$XL_PY $S/conform_footage.py $P --all
$XL_PY $S/compile_shotlist.py $P            # 规则检查：硬切/弱口型必须盖住、数字与口播一致、署名齐全
$XL_PY $S/music_candidates.py $P --suggest  # 先给 2–3 首候选试听，选定后 --choose
$XL_PY $S/mix.py $P                         # -16 LUFS / ≤ -1 dBTP
$XL_PY $S/render_parts.py $P --sample 15    # ~15 秒样片 → 用户确认
$XL_PY $S/render_parts.py $P --parts ch1 --review   # 逐章出片
$XL_PY $S/cover.py $P                       # 可选封面
$XL_PY $S/assemble.py $P --cover $P/render/cover_16x9.png
$XL_PY $S/verify.py $P/render/full.mp4 --expect-frames <帧数> --voice $P/build/voice.wav --cover $P/render/cover_16x9.png
$XL_PY $S/credits_caption.py $P             # 发布文案里的素材署名
```

每完成一步在 `$P/PROGRESS.md` 记一笔，中断后从那里接着做。

## 4. 素材与版权

- 本包**不含任何第三方素材或音乐**；字体为 SIL OFL（安装时下载），音效由代码合成。
- 实拍只从可商用来源取：Pexels、Pixabay、Mixkit、Wikimedia Commons、Internet Archive（Prelinger）、Library of Congress、Open Beelden、Europeana；自动排除 ND / NC。
- API key（可选）只从环境变量 / `~/.config/xiaolinshuo/keys.env` 读：`PEXELS_API_KEY`、`PIXABAY_API_KEY`、`EUROPEANA_API_KEY`。

## 5. 目录

```
SKILL.md            智能体用的完整工作流
install.sh          一键安装 + 自检
requirements.txt    Python 依赖
engine/             Remotion 4.0.408 引擎（package.json + package-lock.json + src/）
scripts/            各步骤脚本 + selftest.sh + env.sh
examples/demo/      自检 demo（合成输入脚本、3 镜镜头表、组件画廊）
references/         小Lin说风格自动分镜规则与官方参考片文字拆解（不含截图）
assets/sfx/         合成音效（install.sh 生成）
```
