# AIPPT 端到端生成流程

这份文档解释当前仓库里 AIPPT 的完整生成链路，覆盖以下问题：

- 用户输入主题后，大纲是怎么生成的
- 大纲如何在前端被流式显示和编辑
- 幻灯片 JSON 是怎么从后端流出来的
- 前端是如何把语义 slide JSON 套到模板上的
- 模板里哪些字段在起作用
- 为什么这套流程不是“把 PPT 拆成 JSON”，而是“先生成语义 JSON，再映射为 PPT 页面”

## 1. 先看这套流程的目标产物是什么

这套 AIPPT 流程最终要生成的不是 `.pptx` 文件，也不是原始 PPT 结构，而是当前编辑器能够直接消费的 `Slide[]` 数据。

但在真正生成 `Slide[]` 之前，中间还有一层更抽象的“语义幻灯片数据”，定义在：

- `src/types/AIPPT.ts`

核心类型只有 5 种：

- `cover`
- `contents`
- `transition`
- `content`
- `end`

也就是说，AIPPT 不是直接让模型输出完整画布元素，而是先让模型输出“这一页属于什么类型，需要什么语义内容”，再由前端拿模板去填充。

## 2. 总体分成两个阶段

当前实现可以拆成两个连续阶段：

### 阶段一：主题 -> Markdown 大纲

输入：

- 用户在 AIPPT 对话框里输入主题、语言、风格、模型等参数

输出：

- 一份 Markdown 大纲

### 阶段二：Markdown 大纲 -> 语义 slide JSON -> 模板化 Slide[]

输入：

- 用户确认后的 Markdown 大纲
- 选中的模板或上传的本地 `.pptist` 模板

输出：

- 最终加入编辑器 store 的 `Slide[]`

## 3. 前端入口在哪里

整个前端入口文件是：

- `src/views/Editor/AIPPTDialog.vue`

它管理了三个步骤：

- `setup`：输入主题和参数
- `outline`：查看与编辑大纲
- `template`：选择模板并生成 PPT

关键状态包括：

- `keyword`
- `language`
- `style`
- `model`
- `outline`
- `selectedTemplate`
- `step`

## 4. 大纲生成链路

### 4.1 用户点击“AI 生成”

入口函数：

- `createOutline()`

它先校验 `keyword` 是否为空，然后调用：

- `api.AIPPT_Outline({ content, language, model })`

### 4.2 前端请求封装

对应文件：

- `src/services/index.ts`

其中 `AIPPT_Outline()` 最终会调用：

- `fetchRequest(`${SERVER_URL}/tools/aippt_outline`, { ... })`

请求 body 为：

```json
{
  "content": "主题",
  "language": "中文",
  "model": "glm-4.7-flash",
  "stream": true
}
```

### 4.3 流式响应识别

对应文件：

- `src/services/fetch.ts`

这个封装会根据 `content-type` 判断是否为流式响应。以下类型会被视作流：

- `text/event-stream`
- `application/octet-stream`
- `application/x-ndjson`
- `text/plain`
- `text/markdown`

对于大纲接口，后端返回的是：

- `text/markdown; charset=utf-8`

因此前端会把它作为流来读。

### 4.4 后端大纲接口入口

对应文件：

- `agno_service/http_app.py`

接口是：

- `POST /tools/aippt_outline`

处理流程是：

1. 用 `AIPPTOutlineRequest` 校验请求体
2. 用 `build_outline_command(payload)` 构造运行时命令
3. 调用 `runtime.iter_outline_chunks(command)`
4. 把 chunk 直接作为 `StreamingResponse` 输出

### 4.5 协议层如何封装命令

对应文件：

- `agno_service/protocol.py`

大纲请求会被封装为：

- `command = 'outline.generate'`

上下文里会带：

- `language`
- `requested_model`
- `request_id`

这说明后端已经把 HTTP 请求和内部运行时命令做了解耦。

### 4.6 运行时如何生成大纲

对应文件：

- `agno_service/runtime.py`

链路如下：

1. `iter_outline_chunks(command)`
2. `run(command)`
3. `_run_outline(command)`
4. `stream_outline_markdown(payload)`
5. `providers.iter_run_content(agent, prompt)`

这里真正请求模型的是 `stream_outline_markdown()`。它要求模型：

- 直接输出 Markdown
- 一级标题必须用 `# `
- 章节必须用 `## `
- 小节必须用 `### `
- 要点必须用 `- `
- 不要输出代码块标记

因此前端收到的是可直接展示的 Markdown 文本流。

### 4.7 前端如何消费大纲流

回到 `AIPPTDialog.vue` 的 `createOutline()`：

1. 通过 `stream.body.getReader()` 获取流 reader
2. 使用 `TextDecoder('utf-8')` 解码 chunk
3. 把 chunk 直接追加到 `outline.value`
4. 在 `outlineCreating` 为 `true` 时，用 `<pre>` 实时展示
5. 流结束后调用 `getMdContent(outline.value)` 去掉可能存在的 ```markdown 包裹
6. 去掉 HTML 注释后，切到 `OutlineEditor`

所以大纲阶段的前端体验是：

- 生成中：直接看原始 Markdown 流动
- 生成后：切到可编辑的大纲结构视图

## 5. 大纲编辑阶段发生了什么

生成完成后，`AIPPTDialog.vue` 中会切换到：

- `<OutlineEditor v-model:value="outline" />`

这里编辑的是：

- Markdown 大纲字符串

不是 ProseMirror，也不是 PPT 页面本身。

`OutlineEditor` 的作用是：

- 把 Markdown 行级结构解析成层级条目
- 让用户能增删章节、小节、条目
- 再重新序列化回 Markdown

因此，下一阶段送给后端生成 PPT 的输入，仍然是一份 Markdown 大纲。

## 6. 幻灯片生成请求链路

### 6.1 用户点击“生成”

入口函数：

- `createPPT(template?)`

它会先：

- 设置 loading 状态
- 视情况覆盖现有幻灯片
- 调用 `api.AIPPT({ content: outline.value, language, style, model })`

### 6.2 前端请求封装

`src/services/index.ts` 中的 `AIPPT()` 会请求：

- `POST /tools/aippt`

请求 body 为：

```json
{
  "content": "Markdown 大纲",
  "language": "中文",
  "model": "glm-4.7-flash",
  "style": "通用",
  "stream": true
}
```

### 6.3 后端幻灯片接口入口

对应文件：

- `agno_service/http_app.py`

接口是：

- `POST /tools/aippt`

处理流程是：

1. 用 `AIPPTRequest` 校验请求体
2. 用 `build_deck_command(payload)` 构造命令
3. 调用 `runtime.iter_slides(command)`
4. 再通过 `encode_slide_stream(...)` 包装成 SSE 输出

这里的输出格式不是纯文本，而是：

```text
data: {json}\n\n
```

也就是标准的 SSE 行格式。

## 7. 后端是怎么把大纲变成 slide JSON 的

这一段是整个系统的核心。

### 7.1 命令进入运行时

在 `HeadlessRuntime.run()` 中，`deck.generate` 会进入：

- `_run_deck(command)`

然后继续调用：

- `stream_deck_slides(payload)`

### 7.2 运行时先解析 Markdown 大纲

对应函数：

- `parse_outline_markdown(markdown)`
- `get_outline_slide_targets(markdown)`

这里会把 Markdown 大纲解析成：

- `title`
- `chapters[]`
- `sections[]`
- `bullets[]`

并计算：

- 章节数 `chapter_count`
- 小节数 `section_count`
- 最低流式页数 `minimum_streamed_slide_count`

这个最低页数的规则是：

- 每章至少 1 页 `transition`
- 每章至少 1 页 `content`
- 如果章节下有多个 `###` 小节，则每个小节至少 1 页 `content`

### 7.3 默认封面页和目录页先行补齐

在 `stream_deck_slides()` 一开始，后端就会先输出：

- `build_default_cover_slide(payload.content, payload.language)`
- `build_default_contents_slide(payload.content)`

这意味着当前流式策略下：

- `cover`
- `contents`

不依赖模型逐页生成，而是服务端自己根据大纲直接构造。

### 7.4 模型流式输出的目标只有两类页

在 `stream_deck_slides()` 给模型的指令里明确要求：

- 只输出 `transition` 和 `content`
- 按 NDJSON 一行一个 JSON 对象输出
- 不要数组
- 不要代码块

因此模型阶段流出的核心对象只有：

- `transition`
- `content`

### 7.5 流式 JSON 如何从半包里被拼出来

模型流回来的通常不是一行一行稳定切好的 JSON，因此后端会调用：

- `parse_streamed_json_objects(chunks)`

这个函数按字符流做了状态机解析，处理：

- `{` / `}` 对象深度
- 字符串中的引号
- 转义字符

它的作用是把不稳定的流式片段重新组合成完整 JSON 对象字符串。

### 7.6 每个 slide 会再做一次归一化

解析出的对象会进入：

- `normalize_stream_slide(raw_slide, outline_markdown, language)`

这个函数会做几件关键事情：

1. 校验 `type`
2. 统一为前端消费格式：
   - `transition` -> `data.title` + `data.text`
   - `content` -> `data.title` + `data.items[]`
3. 对 `content.items` 最多截断到 4 个
4. 如果缺关键字段就丢弃该页
5. 对 `transition.text` 缺省值做 fallback

### 7.7 如果流式结果为空，走结构化回退

如果 `streamed_slide_count == 0`，后端会回退到：

- `generate_slide_document(payload)`

它会要求模型一次性输出 `SlideDeckDocument` 结构化对象，再用：

- `normalize_slides(document, outline_markdown, language)`

把结果整理成统一 slide 格式。

所以当前后端是双通道设计：

- 优先用真正流式 NDJSON
- 若完全拿不到 slide，则退回结构化一次性生成

### 7.8 流末尾会补结束页

如果整个流程里还没有 `end`，后端会在结尾补：

- `{ "type": "end" }`

因此前端总能收到结束页。

## 8. 前端如何消费 slide 流

回到 `AIPPTDialog.vue` 的 `createPPT()`：

1. 通过 `stream.body.getReader()` 读取 SSE 文本流
2. 用 `TextDecoder` 解码
3. 把数据累积到 `pendingChunk`
4. 按换行分割，逐行送进 `processChunk()`

### 8.1 为什么前端还要做一次半包容错

虽然服务端已经按 `data: {json}\n\n` 输出，但浏览器拿到的数据块仍可能跨边界，因此前端仍保留了：

- `pendingChunk`
- `jsonrepair(...)`

这里的目标是尽量兼容：

- SSE 行被拆断
- JSON 片段不完整
- 模型偶发输出不严谨 JSON

### 8.2 `processChunk()` 做了什么

`processChunk(chunk)` 内部会：

1. 去掉前缀 `data:`
2. 去掉可能存在的 ```jsonl / ```json / ```
3. 调用 `jsonrepair(text)` 修复轻微 JSON 格式问题
4. `JSON.parse(...)` 得到 `AIPPTSlide`
5. 调用 `AIPPT(templateSlides, [slide])`

这里非常重要：

- 前端不是等所有页回来再一次性生成
- 而是每收到一页 slide，就立刻做一次模板映射

所以当前 AIPPT 在前端侧也是逐页追加的。

## 9. 模板数据从哪里来

模板有两个来源：

### 9.1 预置模板

默认通过：

- `api.getMockData(selectedTemplate.value)`

加载 `public/mocks/template_1.json` 之类的文件。

### 9.2 本地模板

用户也可以上传 `.pptist` 文件。`uploadLocalTemplate()` 会：

1. 读取文件文本
2. `decrypt(reader.result as string)`
3. `JSON.parse(...)`
4. 得到 `{ slides, theme }`
5. 直接把这个模板对象传给 `createPPT({ slides, theme })`

因此模板的本质就是：

- 一组带有页面类型和槽位标记的 `Slide[]`

## 10. 模板映射真正发生在哪里

核心文件：

- `src/hooks/useAIPPT.ts`

这是 AIPPT 从“语义 slide”变成“真实 PPT 页面”的主引擎。

它暴露了三个关键能力：

- `presetImgPool`
- `AIPPT`
- `getMdContent`

其中最核心的是：

- `AIPPT(templateSlides, _AISlides, imgs?)`

## 11. useAIPPT 先做了一次语义页拆分

`AIPPT()` 在正式选模板之前，会先把超长的 `content` / `contents` 页拆开。

### 11.1 `content` 页拆分规则

如果一个 `content` 页里的 `items` 太多：

- 5~6 项拆成 2 页
- 7~8 项拆成 2 页
- 9~10 项拆成 3 页
- 大于 10 项也拆成 3 页

### 11.2 `contents` 页拆分规则

如果目录项太多：

- 11 项拆成 2 页
- 大于 11 项拆成 2 页

拆页后会带上：

- `offset`

这个字段后面用于生成页内编号，例如目录页的 07、08，或内容页的第 5 条、第 6 条。

## 12. 模板是怎么被挑选出来的

### 12.1 按页面类型分桶

`AIPPT()` 会先把模板页分成几类：

- `coverTemplates`
- `contentsTemplates`
- `transitionTemplates`
- `contentTemplates`
- `endTemplates`

分桶依据是模板 slide 自身的：

- `slide.type`

### 12.2 按可用槽位数量选合适模板

函数：

- `getUseableTemplates(templates, n, type)`

作用是根据当前语义页所需的 item 数量，从模板里挑“最接近但不小于需求”的页面。

例如：

- 目录页需要 7 个目录项，就优先找至少有 7 个 `item` 槽位的 `contents` 模板
- 内容页需要 3 个内容项，就优先找至少有 3 个 `item` / `itemTitle` 槽位的 `content` 模板

如果完全找不到足够多槽位的模板，就选槽位最多的那张。

## 13. 模板里的“槽位”靠什么识别

这一层的语义标记来自：

- `src/types/slides.ts`
- 模板 JSON 中元素的 `textType` / `shape.text.type` / `imageType`

### 13.1 文字槽位类型

`TextType` 主要包括：

- `title`
- `content`
- `item`
- `itemTitle`
- `partNumber`
- `itemNumber`

### 13.2 图片槽位类型

图片元素还可以带：

- `pageFigure`
- `itemFigure`
- `background`

### 13.3 模板实例里是什么样

例如 `public/mocks/template_1.json` 中：

- 封面页文字元素会标成 `textType: "title"` 和 `textType: "content"`
- 目录页编号形状内文字会标成 `type: "itemNumber"`
- 目录项标题会标成 `textType: "item"`
- 过渡页编号会标成 `partNumber`
- 内容页会用 `itemTitle` 和 `item` 标记标题与正文

这意味着模板不是靠位置硬编码替换，而是靠语义槽位替换。

## 14. 文本和图片是怎么被真正替换进去的

### 14.1 文本替换

核心函数：

- `getNewTextElement(...)`

它会做这些事：

1. 读取原模板文本元素里的 HTML
2. 通过 `getFontInfo()` 提取字号和字体
3. 用 `getAdaptedFontsize()` 根据容器宽高估算可容纳字号
4. 用浏览器 `DOMParser` 解析模板 HTML
5. 替换第一个文本节点内容
6. 删除多余文本节点
7. 用正则更新 `font-size`

所以这里不是重新造一段全新的 HTML，而是“保留模板原本的富文本骨架和样式语义，只替换文字内容并微调字号”。

### 14.2 图片替换

核心函数：

- `getNewImgElement(el)`

它会：

1. 从图片池中挑一张适配方向的图
2. 根据模板图片框的长宽比计算裁剪范围
3. 生成新的 `clip.range`
4. 覆盖 `src`

这样模板中的图片框不会变形，但会尽量填满。

## 15. 不同类型的语义页如何映射到真实模板

### 15.1 `cover`

逻辑：

- 随机选一个封面模板
- 把 `title` 填到 `title` 槽位
- 把 `text` 填到 `content` 槽位
- 如有图片池，则替换带 `imageType` 的图片元素

### 15.2 `contents`

逻辑：

- 根据目录项数量选合适的目录模板
- 按页面上槽位从上到下、从左到右排序
- 把 `items[]` 填进 `item` 槽位
- 把序号填进 `itemNumber` 槽位
- 多余槽位对应的元素和 group 会被删掉

### 15.3 `transition`

逻辑：

- 过渡页模板只在第一次随机挑一个，后面复用
- `title` 填到 `title`
- `text` 填到 `content`
- 章节序号填到 `partNumber`

### 15.4 `content`

逻辑：

- 根据内容项数量挑合适模板
- 当只有 1 项时，会把正文直接填到 `content` 槽位
- 当有多项时，把每项的 `title` / `text` 分别填到 `itemTitle` / `item`
- 序号填到 `itemNumber`

### 15.5 `end`

逻辑：

- 随机挑一个结束页模板
- 通常只替换可选图片，不改文字骨架

## 16. 生成好的页面如何进入编辑器

在 `useAIPPT.ts` 的最后：

- 如果当前画布还是空的，用 `slidesStore.setSlides(slides)`
- 否则用 `addSlidesFromData(slides)` 追加到现有文稿中

而在 `AIPPTDialog.vue` 的 `createPPT()` 结束时，还会：

- `slidesStore.setTheme(templateTheme)`

因此最终结果不只是插入页面，还会同步模板主题。

## 17. 一张图串起整条链路

```text
用户输入主题
  -> AIPPTDialog.createOutline()
  -> src/services/index.ts AIPPT_Outline()
  -> /tools/aippt_outline
  -> agno_service/http_app.py
  -> protocol.build_outline_command()
  -> runtime.stream_outline_markdown()
  -> 模型流式输出 Markdown
  -> 前端 <pre> 实时显示
  -> OutlineEditor 编辑 Markdown

用户确认大纲并选择模板
  -> AIPPTDialog.createPPT()
  -> src/services/index.ts AIPPT()
  -> /tools/aippt
  -> agno_service/http_app.py
  -> protocol.build_deck_command()
  -> runtime.stream_deck_slides()
  -> 默认 cover + contents
  -> 模型流式输出 transition/content NDJSON
  -> SSE 包装 data: {json}\n\n
  -> 前端 processChunk()
  -> jsonrepair + JSON.parse
  -> useAIPPT.AIPPT(templateSlides, [slide])
  -> 按 type 选模板
  -> 按 textType / imageType 填槽位
  -> 生成真实 Slide[]
  -> 写入 slidesStore
```

## 18. 这套架构最关键的设计点

### 18.1 后端只生成语义，不直接生成画布元素

后端生成的是：

- 哪一页是什么类型
- 这一页有哪些标题、正文、内容项

而不是：

- 元素 left / top / width / height
- 路径、渐变、阴影、字体布局

这让模型不必承担版式设计的稳定性问题。

### 18.2 前端掌握最终视觉落地

模板、槽位、字号适配、图片裁切都在前端完成，意味着：

- 视觉一致性更可控
- 模型只需负责内容组织
- 同一份语义 slide 可以映射到不同模板上

### 18.3 流式体验是真正逐页推进的

当前不是“等全部 JSON 生成完成后一次性渲染”，而是：

- 后端逐页 SSE 输出
- 前端逐页修复、解析、映射、插入

因此用户能看到文稿一页一页生成出来。

## 19. 最后用一句话总结

当前 AIPPT 的本质不是“AI 直接生成一份 PPT 文件”，而是：

- 先把主题生成为 Markdown 大纲
- 再把大纲生成为语义级 slide JSON
- 再把 slide JSON 映射到带槽位标记的模板页面
- 最后得到编辑器可直接操作的 `Slide[]`

所以真正稳定的部分在模板和前端映射层，模型主要负责的是内容结构，而不是最终版式。