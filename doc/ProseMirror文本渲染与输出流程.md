# ProseMirror 文本渲染与输出流程

这份文档解释 PPTist 中“文本内容是如何被渲染、编辑、再输出回 slide 数据”的完整过程，并明确 ProseMirror 在整套 PPT 渲染链中的职责边界。

需要先给出一个结论：

- ProseMirror 不是整页 PPT 的渲染引擎。
- ProseMirror 负责的是文本内容的结构化编辑、选区管理、富文本命令执行和编辑态 DOM 渲染。
- 整页 PPT 的布局、定位、旋转、形状路径、图片、渐变、阴影等，仍然由 Vue 组件、CSS 和 SVG 负责。

## 1. 先看这套流程处理的对象

在 PPTist 里，文本不是以 ProseMirror JSON 的形式长期存储的，而是以 HTML 字符串的形式挂在元素数据上。

典型的两种文本来源如下：

1. 文本框元素：内容保存在 `elementInfo.content`
2. 形状内文本：内容保存在 `elementInfo.text.content`

也就是说，slide 数据层保存的是“富文本 HTML”，而不是 ProseMirror 的内部文档树。

这个设计非常关键，因为它决定了整条链路的输入和输出：

- 输入给 ProseMirror 的是 HTML 字符串
- ProseMirror 内部处理的是文档树和可编辑 DOM
- 输出回 store 的还是 HTML 字符串

## 2. 三种展示场景，不是同一套组件

这套流程要分成三个场景来看，否则很容易把“编辑画布”和“静态显示”混为一谈。

### 2.1 编辑器画布场景

编辑器画布使用 `EditableElement.vue` 作为元素分发入口，不同元素类型会被分发到各自的可编辑组件：

- 文本元素进入 `TextElement/index.vue`
- 形状元素进入 `ShapeElement/index.vue`

在这个场景下，文本区域会挂载 `ProsemirrorEditor.vue`。也就是说，编辑器里的文本内容显示和编辑，核心都走 ProseMirror。

### 2.2 缩略图场景

缩略图使用 `ThumbnailElement.vue` 分发到各类 Base 组件：

- 文本元素走 `BaseTextElement.vue`
- 形状元素走 `BaseShapeElement.vue`

这里不会创建 ProseMirror 的 `EditorView`，而是直接把 HTML 通过 `v-html` 渲染出来。

### 2.3 放映页场景

放映时使用 `ScreenElement.vue` 分发到各类 Base 组件：

- 文本元素走 `BaseTextElement.vue`
- 形状元素走 `BaseShapeElement.vue`

同样不会创建 ProseMirror 编辑器，而是直接输出静态 HTML。

所以，准确说法应该是：

- 编辑器画布中的文本，由 ProseMirror 驱动
- 缩略图和放映页中的文本，由 HTML 静态渲染驱动

## 3. 编辑器画布里的完整渲染链路

这一部分是理解 ProseMirror 角色的核心。

### 3.1 元素先由 Vue 组件完成外层布局

以文本框为例，`TextElement/index.vue` 先根据元素数据决定它在画布中的位置和样式，例如：

- `top`、`left`
- `width`、`height`
- `rotate`
- `backgroundColor`
- `opacity`
- `lineHeight`
- `letterSpacing`
- `fontFamily`
- `writingMode`

这些都属于 PPT 元素层面的视觉布局，不是 ProseMirror 负责的。

以形状为例，`ShapeElement/index.vue` 会先绘制 SVG 形状本体：

- `path`
- `fill`
- `outline`
- `gradient`
- `pattern`
- `flip`
- `shadow`

然后再在形状内部放置文本容器，并挂上 `ProsemirrorEditor.vue`。

所以在编辑器画布里，其实是两层职责叠加：

1. Vue/SVG 负责“这个元素长什么样、摆在哪里”
2. ProseMirror 负责“这个文本内容怎么显示和怎么编辑”

### 3.2 ProsemirrorEditor 负责创建 EditorView

`ProsemirrorEditor.vue` 是文本编辑内核的封装层。

组件挂载时，会调用 `initProsemirrorEditor()` 创建一个 `EditorView`。这个过程包括三件事：

1. 根据 schema 创建 ProseMirror `Schema`
2. 把已有 HTML 字符串解析为 ProseMirror 文档
3. 根据插件列表创建 `EditorState` 和 `EditorView`

对应的核心逻辑在 `src/utils/prosemirror/index.ts`：

```ts
const schema = new Schema({
  nodes: schemaNodes,
  marks: schemaMarks,
})

export const createDocument = (content: string) => {
  const htmlString = `<div>${content}</div>`
  const parser = new window.DOMParser()
  const element = parser.parseFromString(htmlString, 'text/html').body.firstElementChild
  return DOMParser.fromSchema(schema).parse(element as Element)
}
```

这里有一个非常重要的动作：

- 先用浏览器原生 `DOMParser` 把 HTML 字符串转成普通 DOM
- 再用 `DOMParser.fromSchema(schema)` 按照 ProseMirror schema 解析成 ProseMirror 文档树

这说明 ProseMirror 不是直接“渲染原始字符串”，而是先把 HTML 规范化为自己的内部文档模型，再根据该模型创建编辑态 DOM。

### 3.3 ProseMirror 的 schema 决定它能理解哪些内容

`src/utils/prosemirror/schema/nodes.ts` 和 `src/utils/prosemirror/schema/marks.ts` 描述了编辑器能识别的文本结构。

当前这套 schema 主要支持：

#### 节点 nodes

- `doc`
- `paragraph`
- `blockquote`
- `ordered_list`
- `bullet_list`
- `list_item`
- `text`

#### 标记 marks

- `strong`
- `em`
- `code`
- `underline`
- `strikethrough`
- `subscript`
- `superscript`
- `fontname`
- `fontsize`
- `forecolor`
- `backcolor`
- `textgradient`
- `link`
- `mark`

这意味着：

- 如果 HTML 里有段落、列表、引用、链接、字号、字体、颜色、上下标等信息，ProseMirror 可以识别并映射成内部结构
- 如果某些结构不在 schema 内，它就不会以 ProseMirror 原生语义的方式存在

### 3.4 插件层负责输入规则、快捷键和历史记录

创建 `EditorView` 时，还会通过 `buildPlugins()` 挂载一组插件，当前主要包括：

- `input rules`
- `keymap`
- `baseKeymap`
- `dropCursor`
- `gapCursor`
- `history`

这些插件解决的是编辑体验层面的能力，例如：

- 键盘行为
- 输入规则
- 光标表现
- 撤销/重做

所以 ProseMirror 在这一步不仅完成“显示”，还把文本区域变成了一个可编辑的富文本运行时。

## 4. 编辑过程中，数据是如何流动的

### 4.1 初始输入：slide 数据中的 HTML

当一个文本元素或形状文字被渲染到编辑器画布时：

- 文本框把 `elementInfo.content` 传给 `ProsemirrorEditor`
- 形状文字把 `text.content` 传给 `ProsemirrorEditor`

这一步的输入仍然只是字符串。

### 4.2 中间态：EditorView 内部的 ProseMirror 文档与 DOM

`ProsemirrorEditor` 初始化完成后，`EditorView` 会维护两套关键状态：

1. ProseMirror 文档树
2. 当前编辑态 DOM

用户看到的内容，其实就是 `EditorView` 根据文档状态管理出来的 DOM。

这时用户做的所有操作，例如：

- 输入文本
- 删除文本
- 改字号
- 改字体
- 改颜色
- 设置对齐
- 切换列表
- 设置缩进
- 设置链接

本质上都是在修改 ProseMirror state，然后再由 `EditorView` 更新对应的 DOM。

### 4.3 工具栏命令是如何进入编辑器的

`ProsemirrorEditor.vue` 监听了富文本命令事件。当外部工具栏发出命令时，它会调用内部的 `execCommand()` 去执行对应逻辑。

例如：

- `fontname`
- `fontsize`
- `color`
- `backcolor`
- `bold`
- `underline`
- `blockquote`
- `align`
- `indent`
- `textIndent`
- `bulletList`
- `orderedList`
- `link`
- `replace`

这些命令有些通过 `toggleMark()` 完成，有些通过自定义 command 完成。换句话说，工具栏并不是直接改 HTML，而是先改 ProseMirror 的状态。

### 4.4 编辑结果如何回写到 slide 数据

`ProsemirrorEditor.vue` 里有一个 `handleInput()`，它会在用户输入后做防抖处理，然后比较当前值和编辑器 DOM：

```ts
emit('update', {
  value: editorView.dom.innerHTML,
  ignore: isHanldeHistory,
})
```

这里非常关键，因为它说明最终写回 store 的不是 ProseMirror 的 JSON，而是：

- `editorView.dom.innerHTML`

父组件收到 `update` 事件后：

- 文本元素会更新 `elementInfo.content`
- 形状元素会更新 `elementInfo.text.content`

到这里，这一轮编辑的“输出”就完成了。

也就是说，这条输出链路是：

```text
HTML 字符串
  -> DOMParser
  -> ProseMirror doc
  -> EditorView DOM
  -> editorView.dom.innerHTML
  -> 回写到 slide JSON
```

## 5. 为什么 store 变化后，编辑器内容还能同步

`ProsemirrorEditor.vue` 里有一个对 `props.value` 的监听：

- 如果编辑器还没初始化，不处理
- 如果编辑器当前有焦点，不强制覆盖
- 如果编辑器当前没有焦点，就把新的 HTML 再次解析成文档并替换进当前 state

核心逻辑是：

```ts
const { doc, tr } = editorView.state
editorView.dispatch(tr.replaceRangeWith(0, doc.content.size, createDocument(textContent.value)))
```

这一步的意义是：

- 外部 store 变化后，编辑器能重新同步内容
- 但为了避免打断用户当前输入，focus 状态下不会硬替换

这也是为什么它可以在“外部改值”和“内部编辑”之间保持相对稳定。

## 6. 静态输出链路和编辑器链路有什么不同

很多人看到 `.ProseMirror-static` 会误以为静态展示也走了 ProseMirror，其实不是。

### 6.1 缩略图和放映页的文本输出非常直接

`BaseTextElement.vue` 和 `BaseShapeElement.vue` 在静态场景下做的事情很简单：

1. 外层元素仍由 Vue 控制位置、尺寸、旋转、透明度等布局样式
2. 文本区域直接使用 `v-html` 渲染 HTML 字符串
3. 套用 `.ProseMirror-static` 共享样式，让显示效果与编辑器尽量保持一致

例如文本元素的核心写法就是：

```html
<div class="text ProseMirror-static" v-html="elementInfo.content"></div>
```

例如形状文字的核心写法就是：

```html
<div class="ProseMirror-static" v-html="text.content"></div>
```

所以 `.ProseMirror-static` 的含义是：

- 复用 ProseMirror 风格的文本样式约定
- 不是创建了 ProseMirror 编辑器实例

### 6.2 共享样式如何保证显示一致

全局样式 `src/assets/styles/prosemirror.scss` 同时定义了：

- `.ProseMirror`
- `.ProseMirror-static`

两者共享了段落、列表、代码块、引用、上下标、缩进等基础展示规则。

这样做的好处是：

- 编辑器画布中的文本样式一致
- 缩略图中的文本样式一致
- 放映页中的文本样式一致

也就是说，编辑态和静态态虽然不是同一套运行机制，但共享了一套文本视觉规范。

## 7. 形状文本为什么更容易让人误解

形状元素本身由 SVG 渲染，但形状里的文字不是 SVG 文本路径，而是叠在 SVG 上方的普通 HTML 容器。

所以一个形状元素的实际结构是：

1. SVG 负责画出形状轮廓、填充、渐变、描边
2. HTML 容器负责摆放文字区域
3. 文字区域里再使用 ProseMirror 或 `v-html` 显示文本

因此，形状里的文本编辑能力来自 ProseMirror，但形状本体完全不是 ProseMirror 渲染的。

## 8. 用一张流程图看整条链路

```text
slide JSON
  ├─ 文本框: elementInfo.content (HTML)
  └─ 形状文字: elementInfo.text.content (HTML)

编辑器画布
  ├─ EditableElement 分发到 TextElement / ShapeElement
  ├─ Vue/SVG 渲染元素外层外观
  ├─ ProsemirrorEditor 接收 HTML
  ├─ createDocument 解析成 ProseMirror doc
  ├─ EditorView 生成编辑态 DOM
  ├─ 用户输入 / 工具栏命令修改 state
  └─ handleInput 输出 editorView.dom.innerHTML 回写 store

缩略图 / 放映页
  ├─ ThumbnailElement / ScreenElement 分发到 Base 组件
  ├─ Vue/SVG 渲染元素外层外观
  └─ 文本区域直接 v-html 输出 HTML，并套用 ProseMirror-static 样式
```

## 9. 这套设计的本质收益是什么

### 9.1 数据层保持简单

如果整个项目把 ProseMirror 内部文档树直接作为 slide 持久化格式，会把编辑器实现细节渗透到更大的业务层。当前做法把持久化格式收敛到 HTML，耦合更低。

### 9.2 编辑态和静态态可以分开优化

编辑画布需要选区、命令、快捷键、撤销重做，所以挂 ProseMirror 值得。

缩略图和放映页只需要高效显示，不需要完整编辑器，所以直接 `v-html` 更轻。

### 9.3 视觉一致性仍能保住

通过共享 `.ProseMirror` 和 `.ProseMirror-static` 的样式定义，编辑态和静态态即使不走同一套运行时，视觉上仍然尽量统一。

## 10. 最后再用一句话总结

PPTist 里 ProseMirror 的真正角色不是“渲染整页 PPT”，而是“把文本 HTML 临时提升为一个可编辑的富文本运行时，再把编辑结果重新降回 HTML 存回 slide 数据”。

所以从输入到输出，最准确的描述应该是：

```text
slide 中保存 HTML
  -> 进入编辑器时转成 ProseMirror 文档与编辑态 DOM
  -> 编辑完成后再输出为 HTML
  -> 缩略图和放映页直接消费这份 HTML
```

这就是这套文本渲染与输出流程的核心。