---
name: zenskill-xiaolinshuo-video
description: 小Lin说式横屏口播成片流水线（16:9 1920×1080 / 24fps）。当用户已经有定稿的口播 A-roll（数字人或真人出镜 mp4 + 配音 wav + SRT，可选硬切断点 breakpoints.tsv / 手势表 gestures.tsv），想做成「小Lin说」风格的财经/知识科普横屏视频时使用：人物左右切换+推镜、另一侧出图表/实拍，B-roll 跟着 A-roll 走并盖住硬切与弱口型，可商用实拍素材检索与署名登记，音乐床+音效混到 -16 LUFS，分段渲染→拼接→流式校验→封面→<95MB 聊天版。不适用于竖屏短视频、纯动画解说或还没定稿的口播稿；内置从小Lin说官方参考片提炼的自动分镜规则（句型→镜头），也可先用 ChatCut 粗剪再回本地质检。精修镜头表前按选题补画法表和事实文件；官方页可用网页截图（图片社照片须模糊），图表须能追溯到来源。
---

# zenskill-xiaolinshuo-video · 小Lin说式横屏口播

把**已经定稿**的口播 A-roll 做成小Lin说风格横屏成片。引擎是打包好的 Remotion 4.0.408 工程（`engine/`），由一份 YAML 镜头表驱动；
所有步骤都有脚本（`scripts/`），每步都有自动检查。源于一个真实项目的实战流程（wutiao-broll），在 `finance-explainer`（wallstreet-explainer）基础上改为横屏口播版式。

> 首次使用：`bash install.sh && bash scripts/selftest.sh`（见 README.md）。之后每个 shell 先 `source scripts/env.sh`，用 `$XL_PY` 跑 Python 脚本。

---

## 0. 铁律（用户已确认，不要擅自改）

**画面**
- 16:9 1920×1080，**24fps** 时间线。成片时间轴 = A-roll 时间轴，所有时间都写 A-roll 的绝对秒。
- 实拍素材**整帧对齐**：30/60fps → 0.8x，25/50fps → 0.96x，24/23.976 → 1x（`conform_footage.py` 自动做）。
- **永远不用 ffmpeg `-shortest`**；音频用 `atrim/apad` 锁到精确采样数。
- 版式（小Lin说）：开场人物在专业场景里（wide 全景），之后人物**左右切换 + 推镜**，另一侧放图表 / 实拍；**画中画小窗只偶尔用**。
- B-roll **在 A-roll 定稿之后**设计并跟着它走：调色匹配（navy/teal 海军蓝-青），**剪在手势上**（推镜关键帧放在手势起点，手势要露在人物镜头里），图表出现在人物旁边。
- **每个硬切断点、每句口型弱的句子都必须用 B-roll 盖住**（编译时 ERROR 拦截）。
- 屏幕上的**数字必须和口播原样一致**（编译时检查字幕里有没有这个数字）。
- **不用粉色 Riso 风格**。节奏快、大量真实素材；梗图/电影片段只用 1–2 秒且必须可商用。

**素材 / 许可**
- 只用可商用来源：Pexels、Pixabay、Mixkit、Wikimedia Commons、Internet Archive（Prelinger）、Library of Congress、Open Beelden、Europeana。
- **禁止 ND（禁止演绎）和 NC（非商用）**许可。
- 每条素材在项目 `credits.json` 登记 `author / page / license / license_url`（编译时缺一条就 ERROR）。
- 每个镜头用**中文 + 英文关键词**搜素材（模板里自动给 `keywords`）。

**声音**
- 人声为主；音乐床约 **-18 dB** 压在人声下，**按拍点循环**；切点音效轻（约 -20 dB）。
- 总响度 **-16 LUFS**，真峰值 **≤ -1 dBTP**。
- 先给用户 **2–3 首音乐候选**试听，选定后再做全片。

**流程 / 交付**
- 先出 **~15 秒样片** → 用户确认 → 再逐章出片（每章给用户看）；用户说"直接整片"才整片。
- 拼接时**音乐连续、全片一条进度条**（同一个 Film 合成按帧段渲染，天然连续）。
- 校验：重复帧/掉帧、咔哒声、音画同步、响度；长片用流式校验。
- 可选封面：16:9 封面**替换前 3 帧**（0.125s，不插帧、不平移时间轴）；9:16 封面文字放在居中 3:4 安全区；所有文字居中。
- 默认**不加 AI 标、不做片尾署名卡**（除非用户要求）；CC BY / BY-SA 署名写进发布文案（`credits_caption.py`）。
- 交付：**原画** `render/full.mp4` + **聊天版** `render/full_1080p_chat.mp4`（1080p 两遍 x264，< 95MB）。
- 每完成一步在项目 `PROGRESS.md` 追加一节（会话随时可能中断，从这里续做，不重做已完成步骤）。

---

## 1. 输入契约

放进 `<项目>/input/`：

| 文件 | 必需 | 说明 |
|---|---|---|
| `aroll.mp4` | ✓ | 定稿口播画面，**24fps 恒定帧率**，1920×1080（其他分辨率引擎会缩放）。数字人/真人均可 |
| `voice.wav` | ✓（若 mp4 带音轨可省） | 配音，时长应 = A-roll 帧数/24（差 >1 帧报警） |
| `aroll.srt` | ✓ | 字幕，时间 = A-roll 绝对秒。用于字幕、模板分镜、数字一致性检查 |
| `breakpoints.tsv` | 推荐 | 硬切断点。列：`断点 类型 时间(s) 帧 前句 后句 前链 后链 建议`；`建议` 里的 `覆盖 a–b s` 会被解析为覆盖区间 |
| `gestures.tsv` | 推荐 | 手势。列：`句 句起(s) 句止(s) 计划手势 重音词 重音时刻(s) 实测手部入画区间(s)`；区间写 `2.3-2.9`，无手势写 `无` |
| `sentence_table.tsv` | 可选 | 句表（含口型偏差列）；口型均差 ≥70ms 或 ≤1 帧比例 <30% 的句子判为弱口型 |

样例见 `examples/demo/make_inputs.sh` 生成的文件。弱口型也可手工给：`--weak 032,074` 或 `--weak-ranges 12.3-15.0`。

## 2. 项目目录（`init_project.sh` 建好）

```
<项目>/
  input/            原始输入（上表）
  footage_raw/      下载的原始素材（任意帧率/尺寸）
  music/            bed.(wav|mp3) 选定音乐；candidates/ 候选与 SOURCES.md
  public/           Remotion public 目录：assets/aroll.mp4、footage/<id>.mp4|jpg（conform 后）、fonts/
  build/            aroll.json footage.json film.json mix.wav mix_report.json sfx_events.json bundle/ logs/
  render/           parts/<段>.mp4  review/<段>.mp4+抽帧  cover_16x9.png cover_9x16.png  full.mp4  full_1080p_chat.mp4  verify_*.json
  shotlist.yaml     镜头表（唯一需要人/智能体精修的文件）
  credits.json      素材署名登记
  PROGRESS.md       进度日志
```

> ⚠ 项目路径里**不要有 `.`**（如 `~/.cache/x`、`v1.2/`）：Remotion 图像序列输出目录不接受带点的路径；脚本会自动退到系统临时目录（可用 `XL_FRAMES_DIR` 指定）。

## 3. 镜头表 `shotlist.yaml`（引擎的唯一输入）

完整示例：`examples/demo/shotlist.yaml`（3 镜）与 `examples/demo/gallery.yaml`（所有图表组件）。类型定义：`engine/src/lib/types.ts`。

```yaml
meta: {title: "栏目条文字", grade: navy, aiLabel: null, progress: true}
aroll: {src: assets/aroll.mp4, subject: {x: 0.5, y: 0.37}, drift: 0.015}   # subject=人物脸部中心(0–1)；机位不同可加 zones
subs: {srt: input/aroll.srt, max_chars: 16}
checks:                     # 编译时据此拦截
  hard_cuts: [{t: 4.5, cover: [4.1, 4.9]}]
  weak: [{from: 12.3, to: 15.0}]
  gestures: [{from: 2.3, to: 2.9}]
parts: [{name: open, from: 0, to: 15.2}, {name: ch1, from: 15.2, to: 98.0}]   # 首尾相接覆盖全片
music: {src: music/bed.mp3, gain_db: -18, bpm: 120, beat_offset: 0, loop_beats: 64}
sfx: {auto: true, extra: [{t: 12.0, name: ding, gain: -20}]}
cover: {bg: footage/x.jpg, kicker: "2026", title: ["主标题"], highlight: "高亮词", lines: ["副标题"]}
shots:                      # 首尾相接、无空隙；时间吸附到 1/24 s
  - {id: s1, from: 0, to: 2.0, kind: person, framing: wide, push: {at: 0.3, factor: 1.06, dur: 1.2}}
  - id: s2; kind: person; framing: left|right|close; trans: cut|punch|whip|wipe|iris|slam|sweep
    panel: {chart: {type: bignum, at: 3.2, text: "108%", label: "价格涨了"}}    # 或 panel.items
  - {id: s3, kind: broll, media: {src: footage/city.mp4, start: 0}, tags: [{t: "叠字", at: 4.3}], pip: {x: 1480, y: 600, d: 300}}
  - {id: s4, kind: card, bg: {src: footage/x.mp4, blur: 18}, chart: {type: bars, ...}}
  - {id: s5, kind: chapter, chapter: {n: "01", lines: [{t: "第一章", at: 20.1}]}}
```

- `kind`：`person`（人物 + 另一侧面板）、`broll`（实拍/图片 + 叠字，可选圆形人物小窗 `pip`）、`card`（模糊实拍底 + 居中图表/条目）、`chapter`（章节卡）。
- 图表 `chart.type`：`bignum` `bars` `line` `compare` `list` `timeline`；条目 `items[].k`：`m` 灰小字 `p` 胶囊 `h` 荧光笔 `b` 大字 `x` 划线 `a` 箭头。
- 屏幕上出现但口播没念的数字会 ERROR；确实需要时该镜写 `unspoken_ok: true`。

## 3A. 小Lin说风格自动分镜规则（从官方参考片提炼）

完整规则：`references/xiaolin_style_rules.md`；证据（时间码 + 画面描述）：`references/xiaolin_reference_analysis.md`。
**第 0 节铁律优先**：硬切/弱口型必须盖 B-roll、屏幕数字与口播原样一致、只用可商用素材——这三条压过下面所有规则。

**先给每句字幕定句型，再按句型出镜头：**

| 句型（怎么认） | 镜头 |
|---|---|
| 开场钩子（片头 1–3 句） | person wide 居中 → 说主题词那句开头切 close（约 1.2 倍台阶推近）→ 主题卡 card（外文小字 `m` + 主题词 `b`，2.5–3.5 秒，压住下一句开头）→ 快切 broll 串烧（每镜 0.6–1.4 秒，只有第一镜带圆形 pip） |
| 术语（叫做/号称/被称作 + 引号词） | 术语说出后 0–3 秒内切 card：`m` 外文小字 + `b` 术语，停 1.5–3 秒，trans: cut |
| 单个主角数字 | person left/right + 对侧 `bignum`；`text` 用口播原样写法；`at` = 这句字幕开头 +0.1 秒 |
| 数字序列（走势/几年对比/排名/换算） | card + `line`/`bars`；每根柱子 `at` = 说到它那句的开头；排名的主角柱单独上色；镜头 ≥4 秒加圆形 pip；走势线拆两镜"边说边画" |
| 路过的数字（串烧、故事里顺嘴带过） | 不做图表，只靠字幕 |
| 对比（而/但/官方…黑市/不是…而是） | person left/right + `compare` 面板 |
| 因果链（≥3 步 因为/就会/导致） | ≤3 步：person left/right，面板 `p` 词 → `a` 箭头 → … → `h` 结果，逐个在说到时出现；>3 步：card 全屏 + 圆形 pip |
| 后果清单（连续 ≥3 个并列短语） | 连续 card，每个 1.2–1.6 秒：`m` 修饰语 + `h` 关键词（负面用 BAD 色） |
| 故事/例子 | broll 段 4–16 秒，每镜 0.8–2.1 秒 |
| 设问/吐槽 | person close（台阶推近），不放面板 |
| 结论/观点 | person wide，最多一个关键词 tags |

**机位：**没有面板时人物居中（wide/close）；有面板时才 left/right（参考片人物从不换边，铁律的左右切换只在给图表让位时用）。
`aroll.presets.close.zoom` 设为 wide 的约 1.2 倍，模仿参考片"一下子推近一档"的台阶推镜；手势镜头仍按铁律慢推（`push.dur: 0.6`）。

**节奏目标：**约 25–35 个切点/分钟；人物镜头 2.5–6 秒；B-roll 成段出现（不要人物/实拍一镜一换）；人物占比 30–45%；pip ≤ 镜头数 10%；`subs.max_chars: 14`。

**引擎表达不了的参考片手法**（不要硬凑，记在 `build/shotlist_review.md` 备注里，或交给 ChatCut 路径）：人物居中两侧各一张卡、圆角矩形小窗、一镜内多次台阶推近、片名溶解转场、单位换算型数字（违反铁律，永远不做）。



## 3B. 每期按选题定制画法（讲解画面不要像套模板）

完整做法：`references/xiaolin_treatment.md`；版式怎么用现有组件表达：`references/layout_mapping.md`；上屏数字和原文怎么查：`references/research.md`。
**第 0 节铁律优先**。这一步不改口播，也不换引擎。

镜头表模板出来后、精修图表之前，先在 `build/treatment.md` 写一张表：场景 | 覆盖哪几句 | 骨架 | 背景（选题真实画面） | 道具和动作 | 事实编号。检查 4 点：

- 每个图形场景至少有一样本期专属的东西（选题照片、本期道具、真实 Logo 或官方截图）。只有骨架加数字，不合格。
- 道具要承担意思，拿掉之后意思变弱才算选对；相邻场景的画法不要重样。
- 需要上屏的数字、原文、截图先写入 `build/facts.md`（模板 `templates/facts_template.md`）。查不到就换画法，不上假原文、不上拼凑表。
- 本引擎没有的版式（原文荧光笔、饼图、关系图、白卡等）按 `layout_mapping.md` 近似，或写进 `build/shotlist_review.md` / ChatCut 备注，回来仍过 `compile_shotlist.py`。

开场钩子、设问、结论仍然优先给全屏人物。

## 4. 步骤与命令

```bash
source <skill>/scripts/env.sh            # 设置 XL_SKILL_DIR / XL_ENGINE_DIR / XL_PY / PATH
S=$XL_SKILL_DIR/scripts; P=~/videos/my_ep   # 项目目录（路径不含 "."）
```

### 步骤 1 · 建项目 + A-roll 入库体检
```bash
bash $S/init_project.sh $P
cp aroll.mp4 voice.wav aroll.srt breakpoints.tsv gestures.tsv $P/input/
$XL_PY $S/prepare_aroll.py $P --aroll $P/input/aroll.mp4 --voice $P/input/voice.wav   # [--drop-first-dup] [--force-24]
```
检查 24fps 恒定帧率、首帧重复、配音时长 = 帧数/24；产出 `public/assets/aroll.mp4`（无声）+ `build/voice.wav`。

### 步骤 2 · 生成镜头表模板（跟着 A-roll 走）
```bash
$XL_PY $S/build_shotlist.py $P --srt $P/input/aroll.srt --breakpoints $P/input/breakpoints.tsv \
  --gestures $P/input/gestures.tsv [--sentences $P/input/sentence_table.tsv] [--weak 032,074] --title "栏目条"
```
产出 `shotlist.yaml`（media 为 TODO，带中英关键词）+ `build/shotlist_review.md`。规则：开场 wide；硬切/弱口型 → B-roll；手势 → 人物镜头且推镜起点 = 手势起点；
其余人物左/右交替（约 35–45% 时长）与 ~2 秒一切的实拍交替；「第X条/章」→ 章节卡；口播里的数字 → 原样大数字/叠字。
**然后精修**：给每个 B-roll 填素材、设计图表、调左右/推镜，让图表出现在人物身边。

**按 3A 精修（小Lin说风格）**：模板出来后，逐句标句型（钩子/术语/数字/对比/因果/清单/故事/设问/结论），按 3A 的表改 `kind / framing / panel / chart / trans`：
- 把"人物–实拍一镜一换"的地方并成"人物段 2.5–6 秒 + B-roll 段 4–16 秒"；
- 路过的数字删掉大数字卡，只留字幕；主角数字和数字序列才做图表，出现时刻放在那句字幕开头；
- 术语句后面补术语卡，因果链补逐步面板；
- 每改完一轮跑 `compile_shotlist.py --draft`，0 ERROR 才往下走。

**按 3B 补画法（不要只换数字）**：句型定完后，给每个图形场景写画法表和事实文件。底图换成选题真实画面或官方截图，图表数字必须能在 `build/facts.md` 找到来源；只有骨架和数字的镜头要补背景或改回人物+字幕。本引擎做不到的画法记入 `build/shotlist_review.md`，不要为此改铁律，也不要改已经定稿的口播。


### 步骤 2B（可选）· ChatCut 粗剪 → 回本地质检

适合：用户想先在 ChatCut 里看一版粗剪，或者想让 ChatCut 帮着出动效。**本地 Remotion 流水线仍是正式出片路径**，ChatCut 只是前置。

1. **先问积分**：任何会生成新画面/配音/数字人/口型/音乐，或云端导出的操作，先报预估积分，用户点头再做。默认不生成新的人脸、不克隆声音。
2. 在 ChatCut 新建项目，导入用户自己的 A-roll（数字人或真人口播）。小Lin说官方参考片只作"风格参考"导入（不放进时间线、不出现在成片里）。
3. 用 ChatCut 现成预设 **Talking-Head Edit Recreation**（参照参考片重做口播剪辑），并把 3A 规则（`references/xiaolin_style_rules.md`）作为剪辑要求交给它。ChatCut 端的工作流说明另存为 ChatCut 技能「小Lin说式横屏口播」。
4. 粗剪出来后，把它的**镜头切点、每镜类型、图表文字**抄回本项目的 `shotlist.yaml`（时间仍以 A-roll 绝对秒为准），素材换成可商用来源并登记 `credits.json`。
5. 回到本地：`compile_shotlist.py`（硬切/弱口型覆盖、数字一致、许可）→ 步骤 6 混音（-16 LUFS / ≤ -1 dBTP）→ 步骤 7 先出 15 秒样片。
6. 如果用户坚持直接用 ChatCut 导出的成片：至少跑一遍 `verify.py`（帧数/响度/音画同步），并人工对照 `checks.hard_cuts` 和字幕逐个核对硬切是否被盖住、屏幕数字是否与口播一致、素材许可是否可商用；任何一项不过就回本地流水线重做那一段。

### 步骤 2C · 事实文件 + 官方页截图（和步骤 2/3 一起做）

图形镜头上屏前，把数字、原文、照片、截图写入 `$P/build/facts.md`（抄 `templates/facts_template.md`）。规则见 `references/research.md`：查不到不上屏；地方数据用当地官方口径；推算数字只有口播也用同一写法才能上屏。

需要官方页面、公告或报道的真实画面时，用网页截图，不要自己重排成假页面：

```bash
node $S/web_shot.mjs "<url>" $P/footage_raw/<名字>.png --w 1440 --h 1500 --wait 9 \
     --boxes "要高亮的原文" --blur "article img, figure img"
$XL_PY $S/commons_photo.py search "查询词" --n 6
$XL_PY $S/commons_logo.py $P/footage_raw/logos "名称=File:Xxx.svg"
```

截图里的图片社照片必须模糊。照片和 Logo 仍要写入 `credits.json`，再走步骤 4 conform。Logo 只在讲到该产品或机构时用来指代，不改色、不当封面装饰。

### 步骤 3 · 找素材（只用可商用来源）+ 登记署名
```bash
$XL_PY $S/fetch_footage.py search "城市 航拍 夜景" "city aerial night" --kind video --save /tmp/hits.json
$XL_PY $S/fetch_footage.py get $P --hits /tmp/hits.json --pick 2 --id city_night       # 下载 + 自动写 credits.json
$XL_PY $S/fetch_footage.py add $P --id x --source Mixkit --author Mixkit --page <页面> \
  --license "Mixkit License" --license-url https://mixkit.co/license/ --url <直链>       # 无 API 来源手动登记
```
API key（可选）只从环境变量或 `~/.config/xiaolinshuo/keys.env` 读：`PEXELS_API_KEY`、`PIXABAY_API_KEY`、`EUROPEANA_API_KEY`；
Wikimedia / Internet Archive / LoC 无需 key。脚本自动排除 ND/NC。

### 步骤 4 · 素材整帧 conform
```bash
$XL_PY $S/conform_footage.py $P --all          # footage_raw/* → public/footage/<id>.mp4|jpg + build/footage.json
```

### 步骤 5 · 编译镜头表 + 规则检查
```bash
$XL_PY $S/compile_shotlist.py $P [--draft]     # → build/film.json；ERROR 退出码 1
```
ERROR：镜头不连续 / 硬切或弱口型落在人物镜头 / 屏幕数字与口播不一致 / 素材缺失 / credits 缺字段 / ND·NC 许可。
WARN：B-roll >3.5s、人物 >6s、手势被盖住、画中画过多、素材不够长、粉色配色。`--draft` 允许 TODO 素材（深色占位）先出审片版。

### 步骤 6 · 音乐候选 → 混音
```bash
$XL_PY $S/music_candidates.py $P --suggest                              # 推荐的可商用曲（只给链接）
$XL_PY $S/music_candidates.py $P <URL或文件A> <B> <C> --start 15 --len 20 # 生成 2–3 首 20 秒试听给用户选
$XL_PY $S/music_candidates.py $P --choose B                             # 选定 → music/bed.<ext>，记下 BPM 写进 shotlist music:
$XL_PY $S/mix.py $P                                                     # → build/mix.wav（-16 LUFS / ≤-1 dBTP）
```
音效由 install.sh 程序合成在 `assets/sfx/`（无版权）；自动按镜头切点/叠字放置并吸附帧格。

### 步骤 7 · 样片 → 逐章渲染
```bash
$XL_PY $S/render_parts.py $P --sample 15            # ~15s 样片 + 审片版 render/review/sample.mp4 → 给用户确认
$XL_PY $S/render_parts.py $P --parts ch1 --review   # 逐章：渲一章给用户看一章
$XL_PY $S/render_parts.py $P --all                  # 用户说整片时
```
同一个 Film 合成按帧段渲（每 300 帧一块、JPEG 序列、失败自动重试 3 次），中间片 crf12 无音频，帧数核对 = 段长。`XL_CONCURRENCY` 控制并发。
样片和逐章抽帧，按 `references/xiaolin_visual_checklist.md` 人眼过一遍：主体够大、当前项最亮、一帧标签不超过两个、字幕和脸没有挡住、数字与口播原样一致、图形镜有本期专属画面。白纸版式、竖条小窗、卡片墙跟拍本引擎做不到，不要硬凑，也不要为了「更像原片」改铁律。
预览可用 `cd engine && npx remotion studio src/index.ts --public-dir $P/public`（props 粘 `build/film.json`）。

### 步骤 8 · 封面（可选）
```bash
$XL_PY $S/cover.py $P [--bg-from footage/x.mp4@1.5 | --bg footage/x.jpg] [--show-safe]
```
→ `render/cover_16x9.png`、`render/cover_9x16.png`（文字居中、在 3:4 安全区内）。
封面和栏目条要先写判断或事实对比，不要用「最大的误区」「你还不知道」「90%买房人太晚知道」「一口气了解」这类公式外壳，也不要写成广告口气。

### 步骤 9 · 拼接 + 聊天版
```bash
$XL_PY $S/assemble.py $P [--cover $P/render/cover_16x9.png] [--chat-mb 95]
```
分段 concat（帧数逐段核对）+ 整条 mix.wav（精确采样数）→ `render/full.mp4`（crf20 / maxrate 5M / AAC 192k）
+ `render/full_1080p_chat.mp4`（两遍 x264，按时长算码率，超限自动重编）。单独压任意片：`$XL_PY $S/chat_encode.py in.mp4 out.mp4 --max-mb 95`。

### 步骤 10 · 校验（流式，长片不爆内存）
```bash
N=$(python3 -c "import json;print(json.load(open('$P/build/film.json'))['meta']['durationInFrames'])")
$XL_PY $S/verify.py $P/render/full.mp4 --expect-frames $N --voice $P/build/voice.wav [--cover $P/render/cover_16x9.png] --json $P/render/verify_full.json
$XL_PY $S/verify.py $P/render/full_1080p_chat.mp4 --expect-frames $N --voice $P/build/voice.wav --max-mb 95
```
FAIL：格式不对、掉帧/跳帧、帧数不符、孤立重复帧 >1%（典型是没 conform）、咔哒/断音、响度不在 -16±1 LUFS 或真峰值 > -1 dBTP、音画偏移 >1 帧、封面没替换前 3 帧、超体积。
WARN 需要人眼确认（静态图/图表可能误报重复帧）。

### 步骤 11 · 发布文案署名
```bash
$XL_PY $S/credits_caption.py $P [--all]     # CC BY / BY-SA 等需要署名的素材 → 贴进发布文案
```

## 5. 与用户的交互节点

1. 收到 A-roll 后：报告体检结果（帧率/时长/硬切数/弱口型句/手势数）。
2. 镜头表模板 + 审阅表 → 说明版式思路；同时给出画法表和事实文件里已核对、未核对的条目。
2a. （走 ChatCut 路径时）任何要花 ChatCut 积分的生成/导出，先报预估积分 → 用户确认 → 再做。
3. **音乐 2–3 首候选**试听 → 用户选。
4. **~15 秒样片** → 用户确认风格（调色、字号、节奏）。
5. 逐章出片（每章审片版 + 抽帧）→ 修改 → 下一章；用户要求时整片。
6. 拼接 + 校验报告 → 可选封面 → 交付原画 + 聊天版 + 署名文案。

## 6. 常见坑（实战记录）

- 30fps 素材原速放进 24fps 时间线 → 每 5 帧重复 1 帧，肉眼可见顿挫 → 一律 conform。
- concat 出来的 A-roll 常有"首帧重复"，会让后面整体晚 1 帧 → `prepare_aroll.py --drop-first-dup`。
- 长片一次渲染会在 OffthreadVideo 取帧处超时/卡死 → 分块渲 + 重试（`render_parts.py` 已做）。
- `-shortest` 会把音频截短/音画差半帧 → 永不使用，统一 atrim/apad。
- 音乐不够长时硬接会咔哒 → `mix.py` 在拍格上回接（80ms 交叉）。
- 后台运行 ffmpeg 读终端会被 SIGTTIN 挂起 → 脚本都加了 `-nostdin`。
- 参考片会把口播"1万"在屏幕写成"10,000"——照抄会被数字检查拦下（铁律：数字原样一致）。主数字永远用口播写法。
- 参考片人物从不换边、小窗用得多；我们按铁律：有面板才左右换、小窗 ≤10% 镜头。别因为"参考片这样"去改铁律。
- 自动模板常把每个数字都做成大数字卡；参考片只给"这句话就是在讲这个数"的数字做图，串烧里顺带的数字只留字幕。
- 只换数字、不换画法，讲解画面会像套模板。图形镜要有本期专属的照片、截图或道具；查不到来源就换画法，不要编原文。
- 不要为了「更像小Lin说」去加 AI 角标、粉色胶片孔，或把口播里的「1万」在屏幕写成「约 10,000」。这些都和铁律冲突。
- 涉及中国疆域的地图，不要用第三方世界示意图充数；没有标准地图就改用别的画法。

## 7. 文件索引

| 路径 | 作用 |
|---|---|
| `install.sh` | 一键安装（macOS Homebrew / Linux apt；幂等），末尾打印自检 |
| `scripts/selftest.sh` | 开箱自检：合成 6 秒素材跑完整流水线 + verify |
| `scripts/env.sh` | 环境变量（node/venv/引擎路径） |
| `scripts/xl_common.py` | 公共函数（路径、ffprobe、SRT/TSV 解析） |
| `scripts/init_project.sh` `prepare_aroll.py` `build_shotlist.py` `fetch_footage.py` `conform_footage.py` `compile_shotlist.py` `music_candidates.py` `make_audio_assets.py` `mix.py` `render_parts.py` `cover.py` `assemble.py` `chat_encode.py` `verify.py` `credits_caption.py` | 各步骤脚本（每个文件头有用法） |
| `engine/` | Remotion 4.0.408 工程：`Film`（人物层/面板/图表/实拍卡/章节卡/字幕/进度条/转场）、`CoverH`/`CoverV` |
| `assets/sfx/` | install.sh 合成的无版权音效 |
| `examples/demo/` | 自检用 demo（输入生成脚本、3 镜镜头表、组件画廊） |
| `references/xiaolin_style_rules.md` | 小Lin说风格自动分镜规则（句型→镜头决策树、节奏目标、引擎做不到的清单） |
| `references/xiaolin_reference_analysis.md` | 官方参考片拆解（时间码 + 画面描述，纯文字，不含截图） |
| `references/xiaolin_treatment.md` | 每期画法设计表（选题真实画面 + 承担意思的道具） |
| `references/xiaolin_visual_checklist.md` | 样片/逐章人眼审片要点（标明本引擎做不到的） |
| `references/research.md` | 上屏资料检索、来源分级、网页截图和 Logo |
| `references/layout_mapping.md` | 对方版式到本引擎组件的对应表 |
| `templates/facts_template.md` | 项目事实文件模板（复制到 `build/facts.md`） |
| `scripts/web_shot.mjs` `commons_photo.py` `commons_logo.py` | 官方页截图、Commons 照片和 Logo（改写自 howoneai，MIT，见 NOTICE.md） |
| `NOTICE.md` | 第三方 MIT 版权与许可声明 |
