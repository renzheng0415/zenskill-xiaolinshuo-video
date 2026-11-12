# zenskill-xiaolinshuo-video · 小Lin说式横屏口播成片

把**已定稿的口播 A-roll**（数字人或真人出镜）做成「小Lin说」风格的 16:9 横屏视频：
人物左右切换 + 推镜、另一侧出图表/实拍，B-roll 跟着 A-roll 走并盖住硬切和弱口型，可商用素材 + 署名登记，
音乐床 + 音效混到 -16 LUFS，分段渲染 → 拼接 → 流式校验 → 封面 → <95MB 聊天版。

完整流程、规则与命令见 **[SKILL.md](SKILL.md)**。

### 风格规则（v2）
镜头表现在按"句型"自动起草：开场钩子、术语、主角数字、数字序列、对比、因果链、清单、故事、设问、结论各有对应的镜头写法，
规则来自对小Lin说官方参考片的逐段拆解（`references/xiaolin_style_rules.md`）。铁律不变：硬切/弱口型必须盖 B-roll，屏幕数字必须和口播一致，只用可商用素材，-16 LUFS。
可选：先在 ChatCut 用 Talking-Head Edit Recreation 粗剪，再回本地质检出片（SKILL.md 步骤 2B）。
精修图表前先写画法表和事实文件（见下面第 6 节和 SKILL.md 3B）。


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
#   → 精修 $P/shotlist.yaml：按句型定镜头，再补画法表和 $P/build/facts.md，然后给 B-roll 填素材
#   官方页可用：node $S/web_shot.mjs ；照片/Logo：$XL_PY $S/commons_photo.py / commons_logo.py
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
references/         分镜规则、参考片拆解、画法表、审片要点、资料检索与版式对照（不含截图）
templates/          事实文件模板
NOTICE.md           第三方 MIT 来源说明
assets/sfx/         合成音效（install.sh 生成）
```

## 6. 讲解包装：画法表、事实文件、官网截图

镜头表按句型起草之后，不要只换数字、画面像套模板。精修图表前先做这几件事（细节在 SKILL.md 第 3B 节）：

1. **画法表**（写在 `build/treatment.md`）：每个图形镜头写清骨架、本期真实背景、承担意思的道具。只有骨架加数字的镜头不合格。见 `references/xiaolin_treatment.md`。
2. **事实文件**（从 `templates/facts_template.md` 复制到 `build/facts.md`）：上屏的数字、原文必须能追溯到来源；查不到就换画法，不上假报告。见 `references/research.md`。
3. **官网截图 / Logo**：讲公告或公示页时，用真实页面，不要自己重排成「看起来像官网」的假页面。截图里的新闻图片社照片必须模糊。Logo 只在讲到该机构时用来指代，不改色、不当封面装饰。
4. **审片清单**：样片和逐章抽帧时，看主体是否够大、正在讲的那一项是否最亮、一帧是不是标签太多。见 `references/xiaolin_visual_checklist.md`。
5. **版式对照**：饼图、原文荧光笔、关系图等，本引擎没有的按 `references/layout_mapping.md` 近似，或记到备注里交给 ChatCut，回来仍过本地检查。

小例子（数字是占位，不是真实数据）：口播说到「8万」这个主角数字时，镜头仍用人物对侧大数字，但要补一行画法——背景用本期相关的可商用照片或官方截图，上屏必须写成「8万」而不是「80,000」，并在事实文件里记下官方来源。相邻下一镜如果是几年对比，就换柱状图，不要再连着放一张大数字卡。

```bash
# 截官方页（须安装 Chrome 或 Remotion 自带的 headless Chrome）
# 这三个脚本不内置任何密钥，也不需要 API key
node $S/web_shot.mjs "<官方页网址>" $P/footage_raw/notice.png --w 1440 --h 1500 --wait 9 \
     --boxes "要高亮的原文" --blur "article img, figure img"
$XL_PY $S/commons_photo.py search "查询词" --n 6
$XL_PY $S/commons_logo.py $P/footage_raw/logos "名称=File:Xxx.svg"
```

画法表、审片要点、事实文件模板，以及上面三个脚本，改写自 [howoneai/xiaolin-explainer-packaging](https://github.com/howoneai/xiaolin-explainer-packaging)（MIT License，Copyright (c) 2026 howoneai）。完整声明见 [NOTICE.md](NOTICE.md)。没有换用对方的渲染引擎，也没有采用对方「必须保留 AI 标注」的做法。
