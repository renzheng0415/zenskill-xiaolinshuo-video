#!/usr/bin/env bash
# 生成一套 6 秒的合成输入（无任何版权素材）：A-roll（testsrc2 + 模拟人声的调制正弦）、配音 wav、SRT、
# 硬切断点 / 手势表、2 条不同帧率的空镜（30fps、25fps，用来测 conform）、1 张图、1 条短于成片的占位音乐（测按拍点循环）。
# 用法：bash examples/demo/make_inputs.sh <项目目录>
set -euo pipefail
source "$(dirname "$0")/../../scripts/env.sh"
P="${1:?项目目录}"
I="$P/input"; R="$P/footage_raw"; mkdir -p "$I" "$R" "$P/music"
FF="ffmpeg -nostdin -v error -y"
# 人声：200Hz + 谐波，4Hz 音节起伏，每句 2 秒一个平滑包络（无硬边 → 无咔哒）
VOICE="0.22*(sin(2*PI*200*t)+0.4*sin(2*PI*400*t)+0.2*sin(2*PI*600*t))*(0.6+0.4*sin(2*PI*4*t))*pow(sin(PI*mod(t\,2)/2)\,2)"
$FF -f lavfi -i "aevalsrc='$VOICE|$VOICE':s=48000:d=6" -c:a pcm_s16le "$I/voice.wav"
# A-roll：1920x1080 24fps，6 秒；画面中央画一个「人物」（圆脸+身体），叠加时间码，便于看推镜/左右机位
$FF -f lavfi -i "testsrc2=size=1920x1080:rate=24:duration=6" -i "$I/voice.wav" \
  -filter_complex "[0:v]eq=brightness=-0.25:saturation=0.4,drawbox=x=760:y=560:w=400:h=520:color=0x2C7BE5@0.95:t=fill,drawbox=x=840:y=250:w=240:h=300:color=0xE8C9A0@1:t=fill,drawbox=x=890:y=470:w=140:h=24:color=0x7A3B2E@1:t=fill,drawtext=text='A-ROLL %{pts\\:hms}':x=60:y=980:fontsize=40:fontcolor=white,format=yuv420p[v]" \
  -map "[v]" -map 1:a -c:v libx264 -preset veryfast -crf 18 -r 24 -c:a aac -b:a 192k -shortest "$I/aroll.mp4" 2>/dev/null || \
$FF -f lavfi -i "testsrc2=size=1920x1080:rate=24:duration=6" -i "$I/voice.wav" \
  -filter_complex "[0:v]eq=brightness=-0.25:saturation=0.4,drawbox=x=760:y=560:w=400:h=520:color=0x2C7BE5@0.95:t=fill,drawbox=x=840:y=250:w=240:h=300:color=0xE8C9A0@1:t=fill,format=yuv420p[v]" \
  -map "[v]" -map 1:a -c:v libx264 -preset veryfast -crf 18 -r 24 -c:a aac -b:a 192k -t 6 "$I/aroll.mp4"
# 注：上面生成 *输入素材* 时用了 -shortest（这是造测试源，不是出片）；出片流程里从不使用 -shortest。
cat > "$I/aroll.srt" <<'EOF'
1
00:00:00,200 --> 00:00:01,800
2026年先看大盘

2
00:00:02,200 --> 00:00:03,800
第一条，价格涨了108%

3
00:00:04,200 --> 00:00:05,800
最后记住这三点
EOF
printf '断点\t类型\t时间(s)\t帧\t前句\t后句\t前链\t后链\t建议\n1\t链间\t4.5\t108\t002\t003\tK01\tK02\t此处为硬切(回到母版姿态)，需B-roll盖住，建议覆盖 4.1–4.9s\n' > "$I/breakpoints.tsv"
printf '句\t句起(s)\t句止(s)\t计划手势\t重音词\t重音时刻(s)\t实测手部入画区间(s)\n001\t0.0\t2.0\t双手不入画\t2026年\t0.3\t无\n002\t2.0\t4.0\t右手半张掌抬入画面\t108%%\t3.2\t2.3-2.9\n003\t4.0\t6.0\t双手不入画\t三点\t5.2\t无\n' > "$I/gestures.tsv"
# 空镜：30fps 城市感（mandelbrot 缩放）、25fps 生命游戏、1 张渐变图
$FF -f lavfi -i "mandelbrot=size=1280x720:rate=30" -t 3 -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p "$R/demo_city.mp4"
$FF -f lavfi -i "life=size=1280x720:rate=25:mold=10:ratio=0.1:death_color=#0E1C22:life_color=#5FD3C9,scale=1280:720:flags=neighbor" -t 3 -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p "$R/demo_grid.mp4"
$FF -f lavfi -i "gradients=size=2400x1350:c0=0x0E1C22:c1=0x1F3E48:c2=0x2C7BE5:nb_colors=3:speed=0" -frames:v 1 "$R/demo_bg.jpg" 2>/dev/null || \
$FF -f lavfi -i "color=c=0x1F3E48:size=2400x1350" -frames:v 1 "$R/demo_bg.jpg"
# 占位音乐 4.5 秒 @120bpm（短于成片 → 测按拍点回接）
"$XL_PY" "$XL_SKILL_DIR/scripts/make_audio_assets.py" music "$P/music/bed.wav" --seconds 4.5 --bpm 120 >/dev/null
# 署名（合成素材也按规矩登记）
cat > "$P/credits.json" <<'EOF'
[
 {"id": "demo_city", "source": "synthetic (ffmpeg mandelbrot)", "title": "demo city", "author": "selftest", "page": "local", "license": "CC0", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/"},
 {"id": "demo_grid", "source": "synthetic (ffmpeg life)", "title": "demo grid", "author": "selftest", "page": "local", "license": "CC0", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/"},
 {"id": "demo_bg", "source": "synthetic (ffmpeg gradients)", "title": "demo bg", "author": "selftest", "page": "local", "license": "CC0", "license_url": "https://creativecommons.org/publicdomain/zero/1.0/"}
]
EOF
echo "✓ demo 输入已生成：$I  $R  $P/music/bed.wav"
