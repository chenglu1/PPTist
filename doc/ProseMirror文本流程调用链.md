# ProseMirror 文本流程调用链

这份文档是对《ProseMirror 文本渲染与输出流程》的补充版本，重点不是讲概念，而是把真实代码路径、组件分发点、函数调用和数据回流点逐一串起来。

先给结论：

- 编辑器画布中的文本编辑链路会进入 ProseMirror。
- 缩略图和放映页不会创建 ProseMirror `EditorView`，只会消费已经存好的 HTML。
- slide 数据层长期保存的是 HTML 字符串，不是 ProseMirror 内部 JSON。

## 1. 从哪个入口开始

编辑器画布的统一入口是：

- `src/views/Editor/Canvas/EditableElement.vue`

这里通过 `currentElementComponent` 按元素类型进行分发：

- `text` -> `src/views/components/element/TextElement/index.vue`
- `shape` -> `src/views/components/element/ShapeElement/index.vue`
- 其他元素进入各自组件，但不进入 ProseMirror 文本编辑链路

也就是说，只要当前元素是文本框，或者是带文字的形状，它就会进入后续的文本编辑链。

## 2. 文本框的调用链

### 2.1 组件入口

文本框的编辑态组件是：

- `src/views/components/element/TextElement/index.vue`

这个组件做了三类事情：

1. 决定文本框在画布中的外层布局
2. 把当前 HTML 文本内容传给 `ProsemirrorEditor`
3. 接收编辑后的结果并写回 store

### 2.2 关键数据入口

在模板里，文本内容是这样传进去的：

```vue
<ProsemirrorEditor
  :elementId="elementInfo.id"
  :defaultColor="elementInfo.defaultColor"
  :defaultFontName="elementInfo.defaultFontName"
  :editable="!elementInfo.lock"
  :value="elementInfo.content"
  @update="({ value, ignore }) => updateContent(value, ignore)"
/>
```

这说明：

- 当前输入给 ProseMirror 的内容是 `elementInfo.content`
- 它是字符串形式的富文本 HTML

### 2.3 编辑完成后的回写点

文本框的回写函数是：

- `updateContent(content: string, ignore = false)`

内部会调用：

- `slidesStore.updateElement({ id, props: { content } })`

也就是说，ProseMirror 编辑后的内容最终会重新覆盖到文本元素的 `content` 字段中。

### 2.4 其他和文本框相关但不属于 ProseMirror 的逻辑

同文件内还承担了这些职责：

- `handleSelectElement()` 负责选中元素
- `ResizeObserver` 负责根据文本实际高度回写元素高度
- `checkEmptyText()` 负责在文本被清空时删除空文本元素

这些都属于编辑器画布层的行为，不属于 ProseMirror 的核心编辑职责。

## 3. 形状内文字的调用链

### 3.1 组件入口

带文字的形状使用：

- `src/views/components/element/ShapeElement/index.vue`

这个组件比文本框多了一层职责，因为它既要画形状本体，又要管理形状里的文本。

### 3.2 形状本体的渲染不走 ProseMirror

形状本体由以下结构负责：

- `<svg>`
- `<path>`
- `GradientDefs`
- `PatternDefs`
- `useElementFill`
- `useElementOutline`
- `useElementShadow`
- `useElementFlip`

也就是说，下面这些视觉要素都不是 ProseMirror 管的：

- path
- fill
- gradient
- pattern
- outline
- flip
- shadow

### 3.3 形状文字如何进入 ProseMirror

形状组件模板中，文字区域是这样挂载的：

```vue
<ProsemirrorEditor
  v-if="editable || text.content"
  :elementId="elementInfo.id"
  :defaultColor="text.defaultColor"
  :defaultFontName="text.defaultFontName"
  :editable="!elementInfo.lock"
  :value="text.content"
  @update="({ value, ignore }) => updateText(value, ignore)"
/>
```

输入来源是：

- `text.content`

其中 `text` 是计算属性，最终来自：

- `elementInfo.text`

### 3.4 编辑开始点和结果回写点

形状文字的编辑开始于：

- `startEdit()`

它会把 `editable.value` 设为 `true`，然后调用 `prosemirrorEditorRef.value.focus()` 聚焦编辑器。

回写函数是：

- `updateText(content: string, ignore = false)`

内部更新的是：

- `slidesStore.updateElement({ id, props: { text: _text } })`

所以形状文字回写的目标字段不是 `content`，而是：

- `elementInfo.text.content`

### 3.5 形状文字清空后的处理

形状文字被清空后，`checkEmptyText()` 会执行：

- `slidesStore.removeElementProps({ id, propName: 'text' })`

也就是说，空的形状文本不是保留一个空字符串，而是直接去掉整个 `text` 属性。

## 4. ProsemirrorEditor 这个封装层到底做了什么

对应文件：

- `src/views/components/element/ProsemirrorEditor.vue`

这是整条链路里最关键的桥接层。它把外部 HTML 文本、工具栏命令、选区状态、store 同步都串在了一起。

### 4.1 初始化入口

初始化发生在：

- `onMounted()`

内部调用：

- `initProsemirrorEditor((editorViewRef.value as Element), textContent.value, props)`

这一步会创建真正的 `EditorView`。

### 4.2 输入事件如何回流

核心函数是：

- `handleInput()`

它会比较：

- `props.value`
- `editorView.dom.innerHTML`

如果内容发生变化，就触发：

```ts
emit('update', {
  value: editorView.dom.innerHTML,
  ignore: isHanldeHistory,
})
```

这就是“编辑结果如何回到父组件”的真正出口。

### 4.3 聚焦、失焦和工具栏状态同步

相关函数包括：

- `handleFocus()`
- `handleBlur()`
- `handleClick()`
- `syncAttrsToStore()`

它们负责：

- 禁用全局快捷键
- 恢复全局快捷键
- 从当前选区读取文字属性
- 把当前富文本属性同步回 store，供工具栏显示

### 4.4 外部 value 变化时如何反向同步

`watch(textContent, ...)` 是反向同步入口。

当外部 `props.value` 变化且编辑器当前没有 focus 时，会执行：

- `createDocument(textContent.value)`
- `tr.replaceRangeWith(0, doc.content.size, ...)`

这表示：

- 外部 HTML 重新被解析成 ProseMirror 文档
- 当前编辑器内容被整体替换

### 4.5 工具栏命令如何进入 ProseMirror

`ProsemirrorEditor.vue` 通过事件总线监听：

- `EmitterEvents.RICH_TEXT_COMMAND`
- `EmitterEvents.SYNC_RICH_TEXT_ATTRS_TO_STORE`

命令入口函数是：

- `execCommand({ target, action })`

这里会根据 action 类型分发到不同实现，例如：

- `toggleMark(...)`
- `alignmentCommand(...)`
- `indentCommand(...)`
- `textIndentCommand(...)`
- `toggleList(...)`
- `setListStyle(...)`
- `replaceText(...)`

因此，工具栏不是直接操作 HTML，而是通过命令修改 ProseMirror state，再由 EditorView 反映到 DOM。

## 5. ProseMirror 实例是如何创建的

对应文件：

- `src/utils/prosemirror/index.ts`

这里有两个核心函数：

### 5.1 `createDocument(content)`

职责：把 HTML 字符串解析成 ProseMirror 文档。

调用链是：

1. 先拼成 `<div>${content}</div>`
2. 用浏览器 `DOMParser` 转成普通 DOM
3. 用 `DOMParser.fromSchema(schema)` 转成 ProseMirror doc

所以它的作用不是渲染，而是“把 HTML 变成 ProseMirror 能理解的结构”。

### 5.2 `initProsemirrorEditor(dom, content, props, pluginOptions)`

职责：

1. 调用 `createDocument(content)` 得到 doc
2. 调用 `buildPlugins(schema, pluginOptions)` 得到插件列表
3. 通过 `EditorState.create(...)` 创建 state
4. 通过 `new EditorView(dom, ...)` 创建编辑器实例

## 6. Schema 是谁定义的

### 6.1 入口文件

- `src/utils/prosemirror/schema/index.ts`

这里只是把：

- `nodes`
- `marks`

组合导出给 `Schema` 构造函数使用。

### 6.2 节点定义

- `src/utils/prosemirror/schema/nodes.ts`

这里定义了 ProseMirror 可以识别的块级结构，主要包括：

- `doc`
- `paragraph`
- `blockquote`
- `ordered_list`
- `bullet_list`
- `list_item`
- `text`

同时还定义了段落属性如何和 HTML 对应，例如：

- `text-align`
- `text-indent`
- `data-indent`

### 6.3 行内 mark 定义

- `src/utils/prosemirror/schema/marks.ts`

这里定义了行内样式和 HTML 的互转规则，主要包括：

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

因此，HTML 中的字体、字号、颜色、链接等信息，可以在进入编辑器时被解析为 ProseMirror mark，并在输出时再还原为 HTML 样式。

## 7. 插件层是怎么接进来的

对应文件：

- `src/utils/prosemirror/plugins/index.ts`

`buildPlugins(schema, options)` 当前会挂上：

- `buildInputRules(schema)`
- `keymap(buildKeymap(schema))`
- `keymap(baseKeymap)`
- `dropCursor()`
- `gapCursor()`
- `history()`
- `placeholderPlugin(...)`（可选）

这里解决的是编辑器体验层的问题：

- 输入规则
- 快捷键
- 光标行为
- 撤销重做
- 占位提示

## 8. 静态展示时为什么不走 ProseMirror

静态展示入口不是 `EditableElement.vue`，而是：

- 缩略图：`src/views/components/ThumbnailSlide/ThumbnailElement.vue`
- 放映页：`src/views/Screen/ScreenElement.vue`

这两个分发器都会把文本元素和形状元素交给 Base 组件：

- `src/views/components/element/TextElement/BaseTextElement.vue`
- `src/views/components/element/ShapeElement/BaseShapeElement.vue`

### 8.1 文本框静态输出点

`BaseTextElement.vue` 直接使用：

```vue
<div class="text ProseMirror-static" v-html="elementInfo.content"></div>
```

### 8.2 形状文字静态输出点

`BaseShapeElement.vue` 直接使用：

```vue
<div class="ProseMirror-static" v-html="text.content"></div>
```

这里没有：

- `EditorState.create(...)`
- `EditorView`
- `Schema`

因此它们只是静态 HTML 渲染，不是 ProseMirror 实例渲染。

## 9. 为什么静态态和编辑态看起来又很像

对应文件：

- `src/assets/styles/prosemirror.scss`
- `src/main.ts`

`main.ts` 全局引入了：

- `prosemirror-view/style/prosemirror.css`
- `@/assets/styles/prosemirror.scss`

而 `prosemirror.scss` 同时给下面两个类定义了共同样式：

- `.ProseMirror`
- `.ProseMirror-static`

共享样式包括：

- 段落 margin
- 列表缩进
- code 样式
- `sup` / `sub`
- `blockquote`
- `[data-indent]` 缩进规则

这就是为什么：

- 编辑态是 ProseMirror 管的 DOM
- 静态态只是 `v-html`

但两者看起来仍然很接近。

## 10. 数据的完整往返链路

### 10.1 文本框链路

```text
slidesStore 中的 elementInfo.content（HTML）
  -> TextElement/index.vue
  -> ProsemirrorEditor.vue
  -> initProsemirrorEditor()
  -> createDocument()
  -> Schema + Plugins + EditorState
  -> EditorView
  -> 用户编辑
  -> handleInput()
  -> emit('update', { value: editorView.dom.innerHTML })
  -> updateContent()
  -> slidesStore.updateElement({ props: { content } })
```

### 10.2 形状文字链路

```text
slidesStore 中的 elementInfo.text.content（HTML）
  -> ShapeElement/index.vue
  -> ProsemirrorEditor.vue
  -> initProsemirrorEditor()
  -> createDocument()
  -> EditorView
  -> 用户编辑
  -> handleInput()
  -> emit('update', { value: editorView.dom.innerHTML })
  -> updateText()
  -> slidesStore.updateElement({ props: { text: _text } })
```

### 10.3 静态链路

```text
slidesStore 中的 HTML
  -> ThumbnailElement / ScreenElement
  -> BaseTextElement / BaseShapeElement
  -> v-html
  -> .ProseMirror-static 样式
```

## 11. 用一句话收束

如果只看文件和函数调用链，这套系统的本质是：

- 编辑态通过 `EditableElement -> TextElement/ShapeElement -> ProsemirrorEditor -> initProsemirrorEditor -> EditorView` 建立富文本运行时
- 输出态通过 `BaseTextElement/BaseShapeElement -> v-html` 直接消费 store 中已经保存好的 HTML
- 两端之间的桥梁是 `editorView.dom.innerHTML`

所以 ProseMirror 在这套架构里扮演的是“编辑器内核”，不是“整页 PPT 渲染器”。