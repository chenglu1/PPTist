# Vercel 部署说明

这份文档对应当前仓库的实际部署形态：

- 前端：Vite 构建后的静态站点
- AI 后端：Vercel Python Function
- 大模型：通过 OpenAI-compatible API 调外部模型服务

当前仓库已经完成了 Vercel 适配，关键文件包括：

- `vercel.json`
- `requirements.txt`
- `api/index.py`
- `src/services/index.ts`
- `.python-version`

你不需要再手动改这些文件，只需要按下面步骤配置并部署。

---

## 1. 部署前先理解当前线上请求会怎么走

部署到 Vercel 后，前端和后端的访问关系如下：

- 浏览器访问你的 Vercel 域名，例如 `https://your-project.vercel.app`
- 前端 AI 接口走相对路径 `/api`
- Vercel 会把 `/api` 下的请求交给 Python Function
- Python Function 再去调用你配置的大模型 API

当前前端已经拆分了两类服务地址：

- AI 生成相关接口：走 `VITE_API_BASE_URL`
- 图片搜索接口：走 `VITE_IMAGE_SEARCH_BASE_URL`

如果你不额外配置 `VITE_IMAGE_SEARCH_BASE_URL`，图片搜索默认仍会走官方服务：

- `https://server.pptist.cn`

这意味着：

- AIPPT、大纲生成、AI 写作会走你自己的 Vercel 后端
- 图片搜索默认不需要你自己实现

---

## 2. 部署前准备

在开始之前，你需要准备好以下内容：

### 2.1 一个 Vercel 账号

建议直接用 GitHub 登录，这样后面可以直接关联仓库自动部署。

### 2.2 一个可用的大模型 Key

当前仓库推荐使用 OpenAI-compatible 模型提供方。

你现在这套后端已经按 BigModel 的接法适配过，推荐直接使用：

- `glm-4.7-flash`

你需要准备：

- `AGNO_OPENAI_API_KEY`
- `AGNO_OPENAI_BASE_URL`

如果你用的是 BigModel，对应值一般是：

```env
AGNO_OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
AGNO_DEFAULT_MODEL=glm-4.7-flash
```

### 2.3 代码已经推到 Git 仓库

推荐把当前项目推到 GitHub，然后在 Vercel 中直接 Import。

如果还没推送，先在本地完成：

```powershell
git status
git add .
git commit -m "chore: prepare vercel deployment"
git push
```

如果你不想现在提交全部内容，至少要保证下面这些文件已经在仓库里：

- `vercel.json`
- `requirements.txt`
- `api/index.py`
- `.python-version`

---

## 3. 本地部署前自检

正式上 Vercel 之前，建议你先在本地确认两件事：

### 3.1 前端生产构建能通过

在项目根目录运行：

```powershell
pnpm run build-only
```

当前仓库这一项已经验证通过。

### 3.2 本地 AI 后端能正常响应

在项目根目录运行：

```powershell
pnpm run dev:api
```

然后访问：

```text
http://127.0.0.1:8000/health
```

或者命令行测试：

```powershell
Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing
```

如果健康检查正常，再继续部署。

---

## 4. 在 Vercel 里创建项目

### 4.1 导入仓库

进入 Vercel 控制台后：

1. 点击 `Add New...`
2. 点击 `Project`
3. 选择你的 Git 仓库
4. 点击 `Import`

### 4.2 构建设置

这个仓库已经有 `vercel.json`，大部分配置会自动识别。

你只需要确认以下内容：

- Framework Preset：`Vite`
- Root Directory：项目根目录
- Build Command：保持默认，或填 `pnpm run build-only`
- Output Directory：`dist`

如果 Vercel 没自动识别到 `dist`，手动填上即可。

---

## 5. 配置环境变量

这是最关键的一步。

在 Vercel 项目设置里进入：

- `Settings`
- `Environment Variables`

至少添加以下变量。

### 5.1 前端环境变量

```env
VITE_API_BASE_URL=/api
```

作用：

- 让前端上线后把 AI 请求发送到同域名下的 `/api`

如果你希望图片搜索也走你自己的服务，再额外配置：

```env
VITE_IMAGE_SEARCH_BASE_URL=https://你的图片搜索服务域名
```

如果不配置，图片搜索默认仍会走：

- `https://server.pptist.cn`

### 5.2 后端环境变量

推荐直接填下面这组：

```env
AGNO_MODEL_PROVIDER=openai
AGNO_OPENAI_API_KEY=你的实际模型密钥
AGNO_OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
AGNO_DEFAULT_MODEL=glm-4.7-flash
AGNO_MODEL_ALIASES={"glm-4.7-flash":"glm-4.7-flash","doubao-seed-1.6-flash":"glm-4.7-flash","gemini-2.5-flash":"glm-4.7-flash","gemini-2.5-flash-lite":"glm-4.7-flash"}
AGNO_REQUEST_TIMEOUT=120
AGNO_MAX_RETRIES=2
AGNO_STREAM_CHUNK_SIZE=48
```

如果你有自己的前端域名，还建议把 CORS 也补上：

```env
AGNO_CORS_ORIGINS=https://你的正式域名
```

如果你暂时不确定，也可以先不配，当前后端代码对 CORS 已经比较宽松。

### 5.3 不要在 Vercel 上依赖本地 `.env`

注意：

- `agno_service/.env` 是本地开发文件
- 部署到 Vercel 时，以控制台里填写的环境变量为准

不要把真实密钥硬编码进仓库。

---

## 6. 开始部署

环境变量配置完成后：

1. 点击 `Deploy`
2. 等待 Vercel 完成安装依赖、构建前端、打包 Python Function
3. 构建成功后，打开分配的域名

如果你后续继续推送代码，Vercel 会自动重新部署。

---

## 7. 部署完成后的验证顺序

推荐按下面顺序验证，这样最容易定位问题。

### 7.1 验证后端健康检查

先访问：

```text
https://你的域名/api/health
```

正常情况下应返回类似：

```json
{
  "status": "ok",
  "provider": "openai",
  "model": "glm-4.7-flash"
}
```

如果这一步失败，先不要去测前端页面。

### 7.2 验证前端页面是否能打开

访问首页，确认页面能正常加载，没有白屏。

### 7.3 验证 AI 大纲生成

在 AIPPT 对话框里输入一个主题，点击生成大纲。

重点看两点：

- 是否有流式输出
- 是否最终生成可编辑大纲

### 7.4 验证 AI 生成 PPT

确认大纲没问题后，再点生成 PPT。

重点看：

- 是否开始逐页生成
- 是否最终插入到编辑器中

### 7.5 验证 AI 写作

选中一段文字，触发 AI 写作，确认能返回文本流。

---

## 8. 常见问题与处理方式

### 8.1 打开首页没问题，但 AI 一调用就报错

优先检查：

- `VITE_API_BASE_URL` 是否填成了 `/api`
- `AGNO_OPENAI_API_KEY` 是否填写正确
- `AGNO_OPENAI_BASE_URL` 是否填写正确
- `AGNO_DEFAULT_MODEL` 是否与供应商支持的模型名一致

### 8.2 `/api/health` 返回 500

通常说明后端函数已启动，但运行时配置不对。

优先检查：

- 环境变量是否漏填
- `AGNO_MODEL_PROVIDER` 是否为 `openai`
- `AGNO_OPENAI_API_KEY` 是否为空

### 8.3 页面能打开，但 AIPPT 一直没有内容

优先检查：

- Vercel Function 日志里是否有超时
- 模型供应商是否限流
- 大纲接口是否能先正常返回

建议先测：

- `/api/health`
- AIPPT 大纲生成
- 再测完整 PPT 生成

### 8.4 流式输出在 Vercel 上不稳定

Vercel Python Function 支持流式响应，但你仍然要注意两个现实限制：

- 模型响应太慢时，可能碰到函数执行时长限制
- 大模型供应商本身限流时，前端会表现为生成慢、失败或中断

如果后续你发现完整 PPT 生成经常超时，建议把 AI 后端迁到更适合长连接和长耗时任务的运行环境，例如：

- Cloudflare
- Railway
- Render
- 自己的云服务器

然后仅把前端静态站点放在 Vercel。

### 8.5 图片搜索不可用

这是因为当前你自建的后端没有实现：

- `/tools/img_search`

当前仓库已经做了兼容：

- 如果不配置 `VITE_IMAGE_SEARCH_BASE_URL`，图片搜索仍默认走官方服务

如果你想完全自托管图片搜索，需要后续再单独实现这一条接口。

---

## 9. 推荐的最小可用配置

如果你只是想先尽快把线上版本跑起来，最小配置只需要填这些：

```env
VITE_API_BASE_URL=/api
AGNO_MODEL_PROVIDER=openai
AGNO_OPENAI_API_KEY=你的实际模型密钥
AGNO_OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
AGNO_DEFAULT_MODEL=glm-4.7-flash
AGNO_MODEL_ALIASES={"glm-4.7-flash":"glm-4.7-flash","doubao-seed-1.6-flash":"glm-4.7-flash","gemini-2.5-flash":"glm-4.7-flash","gemini-2.5-flash-lite":"glm-4.7-flash"}
```

这组变量足够把：

- AIPPT 大纲生成
- AIPPT 幻灯片生成
- AI 写作

跑起来。

---

## 10. 一条最短操作路径

如果你只想照着做，不想看解释，直接按下面顺序执行：

1. 把当前代码推到 GitHub。
2. 登录 Vercel，Import 这个仓库。
3. 确认 `Framework Preset = Vite`。
4. 确认 `Output Directory = dist`。
5. 在 `Environment Variables` 中填写：
   - `VITE_API_BASE_URL=/api`
   - `AGNO_MODEL_PROVIDER=openai`
   - `AGNO_OPENAI_API_KEY=你的密钥`
   - `AGNO_OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/`
   - `AGNO_DEFAULT_MODEL=glm-4.7-flash`
   - `AGNO_MODEL_ALIASES={"glm-4.7-flash":"glm-4.7-flash","doubao-seed-1.6-flash":"glm-4.7-flash","gemini-2.5-flash":"glm-4.7-flash","gemini-2.5-flash-lite":"glm-4.7-flash"}`
6. 点击 `Deploy`。
7. 部署成功后打开：`https://你的域名/api/health`。
8. 如果健康检查通过，再打开前端页面测试 AIPPT。

---

## 11. 建议的后续优化

当你完成第一版部署后，建议再做下面几项：

- 绑定自己的正式域名
- 为生产环境和预览环境分别配置不同的模型 Key
- 接入自己的图片搜索服务
- 为大模型请求增加更明确的重试和降级策略
- 如果 AI 生成耗时过长，把后端从 Vercel 迁到更适合长耗时流式任务的平台
