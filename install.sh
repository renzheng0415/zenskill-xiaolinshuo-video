#!/usr/bin/env bash
# zenskill-xiaolinshuo-video 一键安装（幂等，可反复运行）。macOS（Homebrew）/ Linux（apt；无 sudo 时 Node 装到 .tools/）
#   装：Node 22+、引擎 npm 依赖（package-lock 锁定 remotion / @remotion/* = 4.0.408）、ffmpeg/ffprobe（含 libx264）、
#       Python 3.10+ venv（numpy scipy soundfile pyloudnorm PyYAML）、Noto Sans SC 字体（SIL OFL，下载）、
#       合成音效（无版权）、Remotion Chrome Headless Shell（及 Linux 运行库）。最后打印自检表。
# 选项：XL_SKIP_SYSTEM=1 跳过系统包（只做 npm/venv/字体/浏览器）；XL_NODE_MAJOR=22
set -uo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"
NODE_MAJOR="${XL_NODE_MAJOR:-22}"
OS="$(uname -s)"; ARCH="$(uname -m)"
say(){ printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }
ok(){ printf "  \033[32m✓\033[0m %s\n" "$*"; }
warn(){ printf "  \033[33m⚠\033[0m %s\n" "$*"; }
die(){ printf "  \033[31m✗ %s\033[0m\n" "$*"; exit 1; }
SUDO=""; if [ "$(id -u)" != 0 ]; then command -v sudo >/dev/null && sudo -n true 2>/dev/null && SUDO="sudo"; fi
HAS_APT=0; command -v apt-get >/dev/null && { [ "$(id -u)" = 0 ] || [ -n "$SUDO" ]; } && HAS_APT=1
APT_UPDATED=0
apt_install(){ # 只装缺的包；包名可写 a|b 表示候选
  local miss=()
  for spec in "$@"; do
    local got=""
    for p in ${spec//|/ }; do dpkg -s "$p" >/dev/null 2>&1 && { got=1; break; }; done
    [ -n "$got" ] && continue
    for p in ${spec//|/ }; do apt-cache show "$p" >/dev/null 2>&1 && { miss+=("$p"); break; }; done
  done
  [ ${#miss[@]} -eq 0 ] && return 0
  [ $APT_UPDATED = 1 ] || { $SUDO apt-get update -qq || true; APT_UPDATED=1; }
  DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq --no-install-recommends "${miss[@]}"
}
export PATH="$ROOT/.tools/node/bin:$PATH"
[ "$OS" = Darwin ] && [ -x /opt/homebrew/bin/brew ] && eval "$(/opt/homebrew/bin/brew shellenv)"
[ "$OS" = Darwin ] && [ -x /usr/local/bin/brew ] && eval "$(/usr/local/bin/brew shellenv)"

node_ok(){ command -v node >/dev/null && [ "$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)" -ge "$NODE_MAJOR" ]; }

# ---------------- 1. 系统依赖 ----------------
if [ "${XL_SKIP_SYSTEM:-0}" != 1 ]; then
  if [ "$OS" = Darwin ]; then
    say "macOS：Homebrew 依赖"
    command -v brew >/dev/null || die "需要 Homebrew：/bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    node_ok || { brew install "node@$NODE_MAJOR" && export PATH="$(brew --prefix "node@$NODE_MAJOR")/bin:$PATH"; }
    command -v ffmpeg >/dev/null || brew install ffmpeg
    py_ok=0; for p in python3.13 python3.12 python3.11 python3.10 python3; do command -v $p >/dev/null && $p -c 'import sys; exit(0 if sys.version_info>=(3,10) else 1)' 2>/dev/null && py_ok=1 && break; done
    [ $py_ok = 1 ] || brew install python@3.12
  elif [ "$OS" = Linux ]; then
    say "Linux：apt 依赖"
    if [ $HAS_APT = 1 ]; then
      apt_install ca-certificates curl xz-utils ffmpeg python3 python3-venv python3-pip fontconfig \
        libnss3 libdbus-1-3 libatk1.0-0t64\|libatk1.0-0 libgbm1 libasound2t64\|libasound2 libxrandr2 libxkbcommon0 libxfixes3 \
        libxcomposite1 libxdamage1 libatk-bridge2.0-0t64\|libatk-bridge2.0-0 libpango-1.0-0 libcairo2 libcups2t64\|libcups2 \
        || warn "部分 apt 包安装失败（继续）"
      PYV=$(python3 -c 'import sys;print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>/dev/null || echo "")
      [ -n "$PYV" ] && apt_install "python$PYV-venv" >/dev/null 2>&1 || true
      if ! node_ok; then
        say "NodeSource 安装 Node $NODE_MAJOR"
        curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | $SUDO -E bash - >/dev/null && $SUDO apt-get install -y -qq nodejs || warn "NodeSource 失败，改用官方二进制"
      fi
    else
      warn "没有 apt 或 sudo：请自行安装 ffmpeg、python3(>=3.10, 含 venv) 与 Chrome 运行库；Node 会装到 .tools/"
    fi
    if ! node_ok; then
      say "下载官方 Node $NODE_MAJOR 二进制到 .tools/node"
      case "$ARCH" in x86_64) NA=x64;; aarch64|arm64) NA=arm64;; *) die "不支持的架构 $ARCH";; esac
      FN=$(curl -fsSL "https://nodejs.org/dist/latest-v${NODE_MAJOR}.x/SHASUMS256.txt" | awk '{print $2}' | grep "linux-$NA.tar.xz$" | head -1)
      [ -n "$FN" ] || die "拿不到 Node 下载地址"
      mkdir -p .tools && rm -rf .tools/node && curl -fsSL "https://nodejs.org/dist/latest-v${NODE_MAJOR}.x/$FN" | tar -xJ -C .tools && mv ".tools/${FN%.tar.xz}" .tools/node
    fi
  else
    die "不支持的系统 $OS（Windows 请用 WSL2）"
  fi
fi

# ---------------- 2. 工具版本检查 ----------------
say "检查 node / ffmpeg / python"
node_ok || die "需要 Node >= $NODE_MAJOR（当前 $(node -v 2>/dev/null || echo 无)）"
ok "node $(node -v)  npm $(npm -v)"
command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null || die "缺 ffmpeg/ffprobe"
ffmpeg -hide_banner -encoders 2>/dev/null | grep libx264 >/dev/null || die "ffmpeg 没编进 libx264"
ok "$(ffmpeg -version | head -1 | cut -c1-60)"
PY=""; for p in python3.13 python3.12 python3.11 python3.10 python3; do
  command -v $p >/dev/null && $p -c 'import sys; exit(0 if sys.version_info>=(3,10) else 1)' 2>/dev/null && { PY=$(command -v $p); break; }; done
[ -n "$PY" ] || die "需要 Python >= 3.10"
ok "$($PY --version) ($PY)"

# ---------------- 3. Python venv ----------------
say "Python venv（.venv）"
if [ ! -x .venv/bin/python ]; then
  $PY -m venv .venv || die "venv 创建失败（Debian/Ubuntu: apt install python3-venv）"
fi
.venv/bin/python -m pip install -q --upgrade pip >/dev/null 2>&1 || true
.venv/bin/python -m pip install -q -r requirements.txt || die "pip 安装失败"
.venv/bin/python -c "import numpy, scipy, soundfile, pyloudnorm, yaml; print('  numpy', numpy.__version__, '| scipy', scipy.__version__, '| soundfile', soundfile.__version__, '| pyloudnorm ok | PyYAML', yaml.__version__)"

# ---------------- 4. 引擎 npm 依赖 ----------------
say "引擎 npm 依赖（npm ci，按 package-lock 锁定 Remotion 4.0.408）"
cd engine
want=$(node -p 'require("./package-lock.json").packages["node_modules/remotion"].version')
have=$(node -p 'try{require("./node_modules/remotion/package.json").version}catch(e){""}' 2>/dev/null)
if [ "$have" = "$want" ] && [ node_modules/.package-lock.json -nt package-lock.json ]; then ok "node_modules 已是 remotion $have，跳过"
else npm ci --no-audit --no-fund --loglevel=error || die "npm ci 失败"; fi
bad=$(node -e 'const fs=require("fs");const d="node_modules/@remotion";let b=[];for(const p of fs.readdirSync(d)){const v=require(`./${d}/${p}/package.json`).version;if(v!=="4.0.408"&&p!=="licensing")b.push(p+"@"+v)}console.log(b.join(" "))')
[ -z "$bad" ] && ok "remotion + @remotion/* 全部 4.0.408" || die "版本不一致：$bad"
cd "$ROOT"

# ---------------- 5. 字体（Noto Sans SC，SIL OFL 1.1） ----------------
say "CJK 字体 → engine/public/fonts"
mkdir -p engine/public/fonts
FBASES="${XL_FONT_BASE:-} https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/SC https://cdn.jsdelivr.net/gh/notofonts/noto-cjk@main/Sans/SubsetOTF/SC"
for w in Bold Black; do
  f="engine/public/fonts/NotoSansSC-$w.otf"
  if [ -s "$f" ] && [ "$(wc -c <"$f")" -gt 1000000 ]; then ok "$f 已存在"; continue; fi
  got=0
  for b in $FBASES; do   # GitHub 不通时自动换 jsDelivr 镜像；也可 XL_FONT_BASE=自己的镜像目录URL
    curl -fsSL --retry 2 --connect-timeout 15 -o "$f.part" "$b/NotoSansSC-$w.otf" && [ "$(wc -c <"$f.part")" -gt 1000000 ] && mv "$f.part" "$f" && { ok "下载 NotoSansSC-$w.otf（$b）"; got=1; break; }
    rm -f "$f.part"
  done
  [ $got = 1 ] || warn "字体 $w 下载失败：可手动把 NotoSansSC-$w.otf 放进 engine/public/fonts/（否则渲染回落系统 CJK 字体）"
done
[ -s engine/public/fonts/OFL.txt ] || curl -fsSL -o engine/public/fonts/OFL.txt https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/LICENSE 2>/dev/null || curl -fsSL -o engine/public/fonts/OFL.txt https://cdn.jsdelivr.net/gh/notofonts/noto-cjk@main/Sans/LICENSE 2>/dev/null || true

# ---------------- 6. 合成音效 ----------------
say "合成音效 → assets/sfx（无第三方版权）"
if [ "$(ls assets/sfx/*.wav 2>/dev/null | wc -l)" -ge 10 ]; then ok "已存在"; else .venv/bin/python scripts/make_audio_assets.py sfx assets/sfx; fi

# ---------------- 7. Chrome Headless Shell ----------------
say "Remotion Chrome Headless Shell"
( cd engine && npx --no-install remotion browser ensure ) 2>&1 | tail -3 || warn "browser ensure 失败"

# ---------------- 8. 自检 ----------------
say "自检"
PASS=1
chk(){ if ( eval "$2" ) >/dev/null 2>&1; then printf "  %-34s \033[32mOK\033[0m\n" "$1"; else printf "  %-34s \033[31mFAIL\033[0m\n" "$1"; PASS=0; fi; }
chk "node >= $NODE_MAJOR ($(node -v))" node_ok
chk "ffmpeg + libx264" "ffmpeg -hide_banner -encoders | grep libx264 >/dev/null"
chk "ffprobe" "ffprobe -version"
chk "python venv imports" ".venv/bin/python -c 'import numpy,scipy,soundfile,pyloudnorm,yaml'"
chk "remotion 4.0.408" "[ \"\$(node -p 'require(\"./engine/node_modules/remotion/package.json\").version')\" = 4.0.408 ]"
chk "engine typecheck (tsc)" "cd engine && npx --no-install tsc --noEmit"
chk "fonts NotoSansSC Bold/Black" "[ -s engine/public/fonts/NotoSansSC-Bold.otf ] && [ -s engine/public/fonts/NotoSansSC-Black.otf ]"
chk "sfx (assets/sfx)" "[ \$(ls assets/sfx/*.wav | wc -l) -ge 10 ]"
chk "chrome headless shell" "cd engine && npx --no-install remotion browser ensure"
chk "compositions (Film/CoverH/CoverV)" "cd engine && npx --no-install remotion compositions src/index.ts 2>&1 | grep CoverV >/dev/null"
echo
if [ $PASS = 1 ]; then printf "\033[1;32mINSTALL OK\033[0m  下一步：bash scripts/selftest.sh\n"; else printf "\033[1;31mINSTALL INCOMPLETE\033[0m（见上面 FAIL 项）\n"; exit 1; fi
