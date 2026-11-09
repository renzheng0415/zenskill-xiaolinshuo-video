# BUILD_REPORT · zenskill-xiaolinshuo-video

构建/验收时间：2026-11-09（本机 Linux）。验收方式：先删除 `.venv/`、`engine/node_modules/`（含 Chrome Headless Shell）、下载的字体与合成音效，
再从零运行 `bash install.sh` → `bash scripts/selftest.sh`。完整日志：`build_logs/install.log`、`build_logs/selftest.log`（不进 tar 包）。

## 环境
```
Linux 6.12.113+ x86_64
Debian GNU/Linux 13 (trixie)
v24.22.1
ffmpeg version 7.1.5-0+deb13u1 Copyright
Python 3.13.5
```

## 结果
| 步骤 | 结果 | 用时 |
|---|---|---|
| `bash install.sh`（从零） | **INSTALL OK**（10/10 自检 OK） | 26 s |
| `bash scripts/selftest.sh` | **SELFTEST PASS**；`full.mp4` 与 `full_1080p_chat.mp4` 均 VERIFY PASS（0 fail，1 warn） | 58 s |

| 解包 tar.gz 到空目录后 `install.sh` + `selftest.sh`（clean-room） | **INSTALL OK / SELFTEST PASS** | 约 80 s |

唯一 WARN：`face_stutter` 在 2.042s / 3.458s —— 分别是镜头切点（s1→s2）和 s2 推镜结束处，合成 A-roll 本身是静态图形，属预期。

## 自检中修掉的问题（本轮）
1. `selftest.sh` 5b：`set -o pipefail` 下 `compile | grep` 拿到的是 compile 的退出码 1 → 改为捕获输出 + 同时校验退出码非 0 且含「ERROR…硬切」。
2. Remotion `--sequence` 输出目录路径里不能有 `.`（把最后一个点后当扩展名）→ 自检目录改名 `selftest_run/`；`render_parts.py` 遇到带点路径自动退到无点的临时目录（`XL_FRAMES_DIR` 可指定）。
3. 聊天版两遍编码第 1 遍 `-an` 时 filtergraph 的音频输出未连接 → 第 1 遍也映射音频到 null。
4. 图表卡底部与字幕重叠 → 卡片图表上移 120px、缩高。
5. install.sh 字体下载增加 jsDelivr 镜像回退（GitHub 不通时）。

## install.sh 输出（末尾）
```
  ✓ Python 3.13.5 (/usr/bin/python3.13)

==> Python venv（.venv）
  numpy 2.5.4 | scipy 1.18.1 | soundfile 0.14.0 | pyloudnorm ok | PyYAML 6.0.3

==> 引擎 npm 依赖（npm ci，按 package-lock 锁定 Remotion 4.0.408）

added 181 packages in 2s
  ✓ remotion + @remotion/* 全部 4.0.408

==> CJK 字体 → engine/public/fonts
  ✓ 下载 NotoSansSC-Bold.otf（https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/SC）
  ✓ 下载 NotoSansSC-Black.otf（https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/SC）

==> 合成音效 → assets/sfx（无第三方版权）
✓ 14 个音效 → assets/sfx

==> Remotion Chrome Headless Shell
Getting Headless Shell - 105 Mb/108.9 Mb
Got Headless Shell
Has browser at /workspace/zenskill-xiaolinshuo-video/engine/node_modules/.remotion/chrome-headless-shell/linux64/chrome-headless-shell-linux64/chrome-headless-shell

==> 自检
  node >= 22 (v24.22.1)              OK
  ffmpeg + libx264                   OK
  ffprobe                            OK
  python venv imports                OK
  remotion 4.0.408                   OK
  engine typecheck (tsc)             OK
  fonts NotoSansSC Bold/Black        OK
  sfx (assets/sfx)                   OK
  chrome headless shell              OK
  compositions (Film/CoverH/CoverV)  OK

INSTALL OK  下一步：bash scripts/selftest.sh

real	0m26.062s
user	0m24.689s
sys	0m4.138s
EXIT 0
```

## selftest.sh 输出（末尾）
```
Rendered 1/1
Getting composition
Rendered 0/1
Rendered 0/1
Rendered 1/1
Getting composition
Rendered 0/1
Rendered 0/1
Rendered 1/1
Getting composition
Rendered 0/1
Rendered 0/1
Rendered 1/1
Getting composition
Rendered 0/1
Rendered 0/1
Rendered 1/1
✓ 6 张画廊静帧

[55s] 11/12 署名文案

✓ /workspace/zenskill-xiaolinshuo-video/selftest_run/render/credits_caption.txt

[55s] 12/12 校验成片（流式）
PASS  format: h264 1920x1080 24.000fps audio=aac 48000Hz, 3.5MB
PASS  pts: 144 帧，不规则间隔 0 处 []
PASS  frames: 144 / 期望 144
PASS  dup_frames: 孤立重复帧 0 个 []
WARN  face_stutter: 人物区卡帧 2 处 [2.042, 3.458]（剪切点/推镜起步可忽略）
PASS  black: 黑帧段 []
PASS  cover: 前 4 帧与封面均差 [0.35, 0.35, 0.35, 37.0]（前 3 帧应≈0，第 4 帧应明显不同）
PASS  audio_clicks: 咔哒/断音 0 []
PASS  audio_onsets: 突兀起止 0 []
PASS  audio_tail: 末尾 20ms RMS 0.0000
PASS  loudness: I=-16.0 LUFS（目标 -16±1.0） TP=-5.9 dBTP（≤-1.0） LRA=2.0
PASS  av_duration: 视频 6.000s / 音频 6.016s
PASS  av_sync: 成片音轨 vs 定稿配音偏移 [0.0, 0.0, 0.0] ms（≤42ms）
VERIFY PASS  (0 fail, 1 warn)  /workspace/zenskill-xiaolinshuo-video/selftest_run/render/full.mp4
PASS  format: h264 1920x1080 24.000fps audio=aac 48000Hz, 4.6MB
PASS  size: 4.6 MB < 95.0
PASS  pts: 144 帧，不规则间隔 0 处 []
PASS  frames: 144 / 期望 144
PASS  dup_frames: 孤立重复帧 0 个 []
WARN  face_stutter: 人物区卡帧 2 处 [2.042, 3.458]（剪切点/推镜起步可忽略）
PASS  black: 黑帧段 []
PASS  audio_clicks: 咔哒/断音 0 []
PASS  audio_onsets: 突兀起止 0 []
PASS  audio_tail: 末尾 20ms RMS 0.0000
PASS  loudness: I=-16.0 LUFS（目标 -16±1.0） TP=-5.9 dBTP（≤-1.0） LRA=2.0
PASS  av_duration: 视频 6.000s / 音频 6.016s
PASS  av_sync: 成片音轨 vs 定稿配音偏移 [0.0, 0.0, 0.0] ms（≤42ms）
VERIFY PASS  (0 fail, 1 warn)  /workspace/zenskill-xiaolinshuo-video/selftest_run/render/full_1080p_chat.mp4

-rw-r--r-- 1 box box 1450780 Nov  9 00:56 cover_16x9.png
-rw-r--r-- 1 box box 1238255 Nov  9 00:56 cover_9x16.png
-rw-r--r-- 1 box box 3465008 Nov  9 00:56 full.mp4
-rw-r--r-- 1 box box 4597028 Nov  9 00:56 full_1080p_chat.mp4

SELFTEST PASS（58s）成片：/workspace/zenskill-xiaolinshuo-video/selftest_run/render/full.mp4
EXIT 0
```

## 包内文件（不含 node_modules / .venv / selftest_run / build_logs）
```
4.0K	./.gitignore
4.0K	./PROGRESS.md
8.0K	./README.md
16K	./SKILL.md
8.0K	./assets/sfx/click.wav
16K	./assets/sfx/cut.wav
228K	./assets/sfx/ding.wav
132K	./assets/sfx/impact.wav
24K	./assets/sfx/pop.wav
304K	./assets/sfx/riser.wav
96K	./assets/sfx/slam-1.wav
96K	./assets/sfx/slam-2.wav
96K	./assets/sfx/slam-3.wav
60K	./assets/sfx/swish-1.wav
48K	./assets/sfx/swish-2.wav
68K	./assets/sfx/swish-3.wav
12K	./assets/sfx/tap.wav
104K	./assets/sfx/whoosh.wav
4.0K	./engine/.gitignore
96K	./engine/package-lock.json
4.0K	./engine/package.json
8.5M	./engine/public/fonts/NotoSansSC-Black.otf
8.2M	./engine/public/fonts/NotoSansSC-Bold.otf
8.0K	./engine/public/fonts/OFL.txt
4.0K	./engine/remotion.config.ts
4.0K	./engine/src/Cover.tsx
8.0K	./engine/src/Film.tsx
4.0K	./engine/src/Root.tsx
12K	./engine/src/components/Charts.tsx
8.0K	./engine/src/components/Media.tsx
8.0K	./engine/src/components/Panel.tsx
8.0K	./engine/src/components/PersonLayer.tsx
8.0K	./engine/src/components/Primitives.tsx
4.0K	./engine/src/index.ts
4.0K	./engine/src/lib/theme.ts
4.0K	./engine/src/lib/types.ts
4.0K	./engine/tsconfig.json
4.0K	./examples/demo/gallery.yaml
8.0K	./examples/demo/make_inputs.sh
4.0K	./examples/demo/shotlist.yaml
12K	./install.sh
4.0K	./requirements.txt
4.0K	./scripts/assemble.py
16K	./scripts/build_shotlist.py
4.0K	./scripts/chat_encode.py
16K	./scripts/compile_shotlist.py
8.0K	./scripts/conform_footage.py
4.0K	./scripts/cover.py
4.0K	./scripts/credits_caption.py
4.0K	./scripts/env.sh
16K	./scripts/fetch_footage.py
4.0K	./scripts/init_project.sh
8.0K	./scripts/make_audio_assets.py
12K	./scripts/mix.py
8.0K	./scripts/music_candidates.py
8.0K	./scripts/prepare_aroll.py
12K	./scripts/render_parts.py
8.0K	./scripts/selftest.sh
12K	./scripts/verify.py
8.0K	./scripts/xl_common.py
```
