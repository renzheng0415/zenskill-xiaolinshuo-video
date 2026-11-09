"""zenskill-xiaolinshuo-video 公共函数：路径、ffprobe、SRT/TSV 解析、镜头表读写。
所有脚本都只依赖 CLI 参数 / 环境变量，不写死任何项目路径。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(os.environ.get("XL_SKILL_DIR") or Path(__file__).resolve().parent.parent)
ENGINE_DIR = Path(os.environ.get("XL_ENGINE_DIR") or SKILL_DIR / "engine")
FPS = 24
W, H = 1920, 1080


def die(msg: str, code: int = 1):
    print(f"✗ {msg}", file=sys.stderr)
    sys.exit(code)


def run(cmd, check=True, capture=False, cwd=None, env=None, quiet=False):
    if not quiet:
        print("$", " ".join(str(c) for c in cmd) if isinstance(cmd, (list, tuple)) else cmd, flush=True)
    r = subprocess.run([str(c) for c in cmd] if isinstance(cmd, (list, tuple)) else cmd, shell=not isinstance(cmd, (list, tuple)),
                       cwd=cwd, env=env, text=True, capture_output=capture, stdin=subprocess.DEVNULL)
    if check and r.returncode != 0:
        if capture:
            sys.stderr.write((r.stdout or "")[-4000:] + (r.stderr or "")[-4000:])
        die(f"command failed ({r.returncode}): {cmd if isinstance(cmd, str) else ' '.join(map(str, cmd))[:300]}")
    return r


def need(binary: str):
    if not shutil.which(binary):
        die(f"找不到 {binary}，请先运行 install.sh（或 source scripts/env.sh）")


def npx() -> list[str]:
    return ["npx", "--no-install"]


# ---------------- ffprobe ----------------
def probe(path) -> dict:
    r = run(["ffprobe", "-v", "error", "-show_entries",
             "stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,duration,sample_rate,channels,pix_fmt:format=duration,size",
             "-of", "json", str(path)], capture=True, quiet=True)
    return json.loads(r.stdout)


def vstream(p: dict):
    return next((s for s in p.get("streams", []) if s.get("codec_type") == "video"), None)


def astream(p: dict):
    return next((s for s in p.get("streams", []) if s.get("codec_type") == "audio"), None)


def frac(s: str | None) -> float:
    if not s or s in ("0/0",):
        return 0.0
    if "/" in s:
        a, b = s.split("/")
        return float(a) / float(b) if float(b) else 0.0
    return float(s)


def duration(path) -> float:
    p = probe(path)
    return float(p.get("format", {}).get("duration") or 0)


def count_frames(path) -> int:
    r = run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets",
             "-of", "csv=p=0", str(path)], capture=True, quiet=True)
    return int(re.sub(r"\D", "", r.stdout) or 0)


# ---------------- 时间 ----------------
def F(t: float, fps: int = FPS) -> int:
    """秒 → 帧（四舍五入到 24fps 帧格）"""
    return int(round(t * fps))


def snap(t: float, fps: int = FPS) -> float:
    return round(F(t, fps) / fps, 6)


def ts(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:06.3f}"


# ---------------- SRT / TSV ----------------
def parse_srt(path) -> list[dict]:
    txt = Path(path).read_text(encoding="utf-8-sig")
    out = []
    for block in re.split(r"\n\s*\n", txt.replace("\r", "").strip()):
        lines = [l for l in block.split("\n") if l.strip()]
        tl = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if tl is None:
            continue
        a, b = [x.strip() for x in lines[tl].split("-->")]
        def sec(x):
            h, m, s = x.replace(",", ".").split(":")
            return int(h) * 3600 + int(m) * 60 + float(s.split()[0])
        idx = lines[0].strip() if tl > 0 else str(len(out) + 1)
        out.append({"i": idx, "s": sec(a), "e": sec(b), "t": " ".join(lines[tl + 1:]).strip()})
    return out


def parse_tsv(path) -> list[dict]:
    rows = []
    lines = [l.rstrip("\n").rstrip("\r") for l in Path(path).read_text(encoding="utf-8-sig").split("\n") if l.strip()]
    if not lines:
        return rows
    head = lines[0].split("\t")
    for l in lines[1:]:
        cells = l.split("\t")
        rows.append({head[i]: (cells[i] if i < len(cells) else "") for i in range(len(head))})
    return rows


def col(row: dict, *names, default=""):
    """按候选列名（中/英）取值；也接受列名前缀匹配，例如 '时间' 匹配 '时间(s)'"""
    for n in names:
        if n in row:
            return row[n]
    for n in names:
        for k in row:
            if k.lower().startswith(n.lower()):
                return row[k]
    return default


def parse_ranges(s: str) -> list[tuple[float, float]]:
    """'4.5-4.75, 11.33-11.83' / '无' / '' → [(4.5,4.75),...]"""
    out = []
    for a, b in re.findall(r"(\d+(?:\.\d+)?)\s*[-–~]\s*(\d+(?:\.\d+)?)", s or ""):
        out.append((float(a), float(b)))
    return out


# ---------------- 项目 ----------------
class Project:
    def __init__(self, root):
        self.root = Path(root).resolve()
        if not self.root.exists():
            die(f"项目目录不存在：{self.root}（先运行 scripts/init_project.sh）")
        self.public = self.root / "public"
        self.build = self.root / "build"
        self.render = self.root / "render"
        self.input = self.root / "input"
        for d in (self.public, self.build, self.render):
            d.mkdir(parents=True, exist_ok=True)

    @property
    def film_json(self):
        return self.build / "film.json"

    def shotlist_path(self):
        for n in ("shotlist.yaml", "shotlist.yml", "shotlist.json"):
            p = self.root / n
            if p.exists():
                return p
        die(f"{self.root} 下没有 shotlist.yaml / shotlist.json（先跑 build_shotlist.py 或手写）")

    def load_film(self) -> dict:
        if not self.film_json.exists():
            die("build/film.json 不存在，先运行 compile_shotlist.py")
        return json.loads(self.film_json.read_text(encoding="utf-8"))

    def credits(self) -> list:
        p = self.root / "credits.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

    def sfx_dir(self) -> Path:
        p = self.root / "sfx"
        return p if p.exists() and any(p.glob("*.wav")) else SKILL_DIR / "assets" / "sfx"


def load_yaml_or_json(path: Path):
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    try:
        import yaml  # type: ignore
    except ImportError:
        die("需要 PyYAML：source scripts/env.sh（install.sh 会装进 .venv）")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def ebur128(path) -> dict:
    """ffmpeg ebur128：返回 {'I': LUFS, 'LRA':, 'TP': dBTP}"""
    r = subprocess.run(["ffmpeg", "-nostdin", "-nostats", "-hide_banner", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    txt = r.stderr[r.stderr.rfind("Summary:"):]
    def g(pat):
        m = re.search(pat, txt)
        return float(m.group(1)) if m else float("nan")
    return {"I": g(r"I:\s+(-?[\d.]+) LUFS"), "LRA": g(r"LRA:\s+(-?[\d.]+) LU"), "TP": g(r"Peak:\s+(-?[\d.inf]+) dBFS")}
