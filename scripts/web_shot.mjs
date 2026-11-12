// Copyright (c) 2026 howoneai. Adapted from howoneai/xiaolin-explainer-packaging.
// Licensed under the MIT License. See NOTICE.md in the skill root.
// 合入本 skill 后：截图里的图片社照片必须模糊；截图只作 broll/card 背景或叠字底，不替代 credits.json 登记。

#!/usr/bin/env node
// Screenshot a real web page (article, GitHub repo/file, report, product site) for on-screen use.
// Drives chrome-headless-shell over the DevTools protocol, so pages whose `load` event never fires
// (ad-heavy news sites) still work: wait a fixed time, clean the page, capture.
//
// node web_shot.mjs <url> <out.png> [--w 1440] [--h 1800] [--scale 2] [--wait 7]
//        [--scroll <px | css selector | text:phrase>] [--hide "sel1,sel2"] [--blur "sel"] [--keep-fixed] [--dark]
//        [--boxes "phrase one||css:img.chart"] [--full <css px | 0>] [--chrome /path/to/chrome] [--port 9333]
// Chrome: --chrome, else $CHROME, else <cwd>/node_modules/.remotion/chrome-headless-shell/**, else Google Chrome.app.
// Cleanup: removes cookie/consent banners, iframes (ads), and position:fixed/sticky overlays (sticky headers,
// newsletter pop-ups) unless --keep-fixed. --hide adds selectors. --dark asks for prefers-color-scheme: dark.
// --blur: heavy blur on matching elements without changing layout (boxes stay valid). Use it on agency photos
// (Getty, AP, Reuters, 视觉中国) and on any image whose rights you cannot clear: news-page screenshots may show the
// article text, not its photos. --scroll text:<phrase> centres the element holding that text (also inside inner scrollers).
// --boxes: finds each phrase in the page text (whitespace-tolerant, curly quotes normalised) and writes
// <out>.boxes.json = {phrase: [[x, y, w, h], ...one rect per text line]} in screenshot pixels, for add_web() marks.
// A "css:<selector>" entry boxes an element instead (charts, images, buttons).
// --full N: capture the page below the fold too (N css px tall, 0 = whole page, max 14000) with the layout of the
// --h viewport. Use it instead of a huge --h: pages sized in vh re-flow when the viewport gets tall.
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const argv = process.argv.slice(2);
if (argv.length < 2) { console.error('usage: node web_shot.mjs <url> <out.png> [options]'); process.exit(2); }
const [url, out] = argv;
const opt = (k, d) => { const i = argv.indexOf('--' + k); return i > 0 ? argv[i + 1] : d; };
const flag = (k) => argv.includes('--' + k);
const W = +opt('w', 1440), H = +opt('h', 1800), SCALE = +opt('scale', 2), WAIT = +opt('wait', 7) * 1000;
const PORT = +opt('port', 9333);

const findChrome = () => {
  const c = opt('chrome', process.env.CHROME);
  if (c && fs.existsSync(c)) return c;
  const walk = (d, depth = 0) => {
    if (depth > 6 || !fs.existsSync(d)) return null;
    for (const f of fs.readdirSync(d, {withFileTypes: true})) {
      const p = path.join(d, f.name);
      if (f.isFile() && f.name === 'chrome-headless-shell') return p;
      if (f.isDirectory()) { const r = walk(p, depth + 1); if (r) return r; }
    }
    return null;
  };
  const r = walk(path.join(process.cwd(), 'node_modules/.remotion'));
  if (r) return r;
  const mac = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  if (fs.existsSync(mac)) return mac;
  throw new Error('no Chrome found: pass --chrome or run from a Remotion project after one render');
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const chrome = spawn(findChrome(), ['--headless', '--disable-gpu', '--hide-scrollbars', '--no-first-run', '--mute-audio',
  `--remote-debugging-port=${PORT}`, `--window-size=${W},${H}`, `--user-data-dir=/tmp/web_shot_${PORT}`, 'about:blank'], {stdio: 'ignore'});
const kill = () => { try { chrome.kill('SIGKILL'); } catch {} };
const hard = setTimeout(() => { console.error('timeout'); kill(); process.exit(1); }, WAIT + 40000);

let ws, seq = 0; const pending = new Map();
const send = (method, params = {}) => new Promise((res, rej) => {
  const id = ++seq; pending.set(id, {res, rej}); ws.send(JSON.stringify({id, method, params}));
});
try {
  let target;
  for (let i = 0; i < 50 && !target; i++) {
    await sleep(200);
    try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); target = l.find((t) => t.type === 'page'); } catch {}
  }
  if (!target) throw new Error('Chrome did not start');
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
  ws.onmessage = (m) => { const d = JSON.parse(m.data); const p = pending.get(d.id); if (p) { pending.delete(d.id); d.error ? p.rej(new Error(d.error.message)) : p.res(d.result); } };
  await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', {width: W, height: H, deviceScaleFactor: SCALE, mobile: false});
  await send('Network.setUserAgentOverride', {userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'});
  if (flag('dark')) await send('Emulation.setEmulatedMedia', {features: [{name: 'prefers-color-scheme', value: 'dark'}]});
  await send('Page.navigate', {url});
  await sleep(WAIT);
  const hide = opt('hide', '');
  const blur = opt('blur', '');
  const scroll = opt('scroll', '');
  const js = `(() => {
    const kill = (el) => { try { el.remove(); } catch (e) {} };
    document.querySelectorAll('iframe, [id*="cookie" i], [class*="cookie" i], [id*="consent" i], [class*="consent" i], [id*="onetrust" i], [class*="newsletter" i][class*="modal" i]').forEach(kill);
    ${hide ? `document.querySelectorAll(${JSON.stringify(hide)}).forEach(kill);` : ''}
    ${blur ? `document.querySelectorAll(${JSON.stringify(blur)}).forEach((el) => { el.style.filter = 'blur(30px) saturate(.5)'; el.style.opacity = '.5'; });` : ''}
    ${flag('keep-fixed') ? '' : `for (const el of document.querySelectorAll('body *')) { const p = getComputedStyle(el).position; if (p === 'fixed' || p === 'sticky') kill(el); }`}
    document.documentElement.style.overflow = 'auto'; document.body.style.overflow = 'auto';
    const s = ${JSON.stringify(scroll)};
    if (s) {
      if (/^\\d+$/.test(s)) window.scrollTo(0, +s);
      else if (s.startsWith('text:')) {
        // scroll the element holding this text to the middle (works inside inner scroll containers too)
        const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); const q = s.slice(5);
        while (w.nextNode()) if (w.currentNode.nodeValue.includes(q)) { w.currentNode.parentElement.scrollIntoView({block: 'center'}); break; }
      } else { const el = document.querySelector(s); if (el) el.scrollIntoView({block: 'start'}); }
    }
    return [window.scrollY, document.title];
  })()`;
  const r = await send('Runtime.evaluate', {expression: js, returnByValue: true});
  await sleep(800);
  const boxes = opt('boxes', '');
  if (boxes) {
    const bjs = `(() => {
      const S = ${SCALE}, out = {};
      const nodes = []; let text = '';
      const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      while (w.nextNode()) { const n = w.currentNode; nodes.push([n, text.length]); text += n.nodeValue; }
      const norm = (s) => s.replace(/[\\u2018\\u2019]/g, "'").replace(/[\\u201c\\u201d]/g, '"');
      const T = norm(text);
      const loc = (k) => { for (let j = nodes.length - 1; j >= 0; j--) if (nodes[j][1] <= k) return [nodes[j][0], k - nodes[j][1]]; return [nodes[0][0], 0]; };
      for (const q of ${JSON.stringify(boxes.split('||'))}) {
        if (q.startsWith('css:')) {
          const el = document.querySelector(q.slice(4));
          const b = el && el.getBoundingClientRect();
          out[q] = b && b.width > 1 ? [[b.x * S, (b.y + window.scrollY - (${flag('full') ? 0 : 1} * window.scrollY)) * S, b.width * S, b.height * S].map(Math.round)] : null;
          continue;
        }
        // every match, first one that is actually rendered (GitHub code view also keeps the text in a hidden textarea)
        const re = new RegExp(norm(q).replace(/[.*+?^\${}()|[\\]\\\\]/g, '\\\\$&').replace(/\\s+/g, '\\\\s+'), 'g');
        let m, got = null;
        while (!got && (m = re.exec(T))) {
          const [sn, so] = loc(m.index), [en, eo] = loc(m.index + m[0].length);
          const rg = document.createRange(); rg.setStart(sn, so); rg.setEnd(en, Math.min(eo, en.nodeValue.length));
          const lines = [];
          for (const b of rg.getClientRects()) {
            if (b.width < 1 || b.height < 1) continue;
            const l = lines.find((x) => Math.abs(x.y - b.y) < 6);
            if (l) { const x1 = Math.max(l.x + l.w, b.x + b.width); l.x = Math.min(l.x, b.x); l.w = x1 - l.x; l.h = Math.max(l.h, b.height); }
            else lines.push({x: b.x, y: b.y, w: b.width, h: b.height});
          }
          if (lines.length) got = lines.map((l) => [l.x * S, l.y * S, l.w * S, l.h * S].map(Math.round));
        }
        out[q] = got;
      }
      return out;
    })()`;
    const b = await send('Runtime.evaluate', {expression: bjs, returnByValue: true});
    const val = b.result.value || {};
    fs.writeFileSync(out + '.boxes.json', JSON.stringify(val, null, 1));
    for (const [q, v] of Object.entries(val)) console.log(v ? `box ${JSON.stringify(q)} ${JSON.stringify(v)}` : `MISSING ${JSON.stringify(q)}`);
  }
  let cap = {format: 'png'};
  if (argv.includes('--full')) {
    const sh = (await send('Runtime.evaluate', {expression: 'Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)', returnByValue: true})).result.value;
    const n = +opt('full', 0);
    const ch = Math.min(n > 0 ? n : sh, sh, 14000);
    cap = {format: 'png', captureBeyondViewport: true, clip: {x: 0, y: 0, width: W, height: ch, scale: 1}};
  }
  const shot = await send('Page.captureScreenshot', cap);
  fs.writeFileSync(out, Buffer.from(shot.data, 'base64'));
  console.log(`ok ${out} ${W * SCALE}x${H * SCALE} scrollY=${r.result.value?.[0]} title=${JSON.stringify(r.result.value?.[1])}`);
} catch (e) {
  console.error('FAIL', e.message); clearTimeout(hard); kill(); process.exit(1);
}
clearTimeout(hard); try { ws.close(); } catch {} kill(); process.exit(0);
