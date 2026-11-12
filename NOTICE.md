# 第三方来源说明

本仓库中有一部分说明和脚本改写自：

- 仓库：https://github.com/howoneai/xiaolin-explainer-packaging
- 许可证：MIT License
- 版权：Copyright (c) 2026 howoneai

按 MIT 许可证，使用、修改、合并这些内容时，需要保留上面的版权声明和许可声明。完整许可证原文见本文件末尾。

合入范围（改写后放入本 skill，不以对方引擎替换本引擎）：

- `references/xiaolin_treatment.md`（画法设计表、道具承担意思）
- `references/xiaolin_visual_checklist.md`（讲解画面审片要点）
- `references/research.md`（事实文件、来源分级、网页截图和 Logo 取用）
- `references/layout_mapping.md`（对方版式对本引擎的对应关系）
- `templates/facts_template.md`
- `scripts/commons_photo.py`、`scripts/commons_logo.py`、`scripts/web_shot.mjs`

未合入、也未放入本仓库的内容：

- 对方整套 Remotion 引擎、6 套主题底图、演示照片和道具
- 对方分镜 API（`scenes.py` / `story_core.py`）和整片渲染脚本
- 对方默认要求保留的「AI 生成 · 非本人」标注（与本 skill 第 0 节铁律冲突）
- 字体「优设标题黑」（对方仓库也不分发；其官网未写明允许再分发）
- 世界地图示意数据 `world110.json`（涉及中国疆域时不能当标准地图用）

对方仓库里 `templates/engine/public/fonts/` 的字体是 SIL Open Font License 1.1，不受上面的 MIT 覆盖；本仓库没有拷这些字体。Remotion 本身需要遵守 Remotion 的许可（个人、3 人以内的公司和非营利组织可免费使用；更大的公司要另购授权）。

第 0 节铁律未改。

---

MIT License

Copyright (c) 2026 howoneai

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
