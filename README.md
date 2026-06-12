# Me.Agent

Me.Agent 是一个以“个人认知图谱”为核心的本地个人 Agent。它把聊天、长期记忆、任务线索、文件材料和图谱节点放在同一个工作台里，让你可以围绕自己的工作、生活、研究和项目持续沉淀上下文。

这个项目目前是 MVP，更适合在自己的电脑上运行。数据默认保存在本地 SQLite 数据库中，模型调用通过 OpenAI 兼容接口完成。

## 你可以用它做什么

- 和 Agent 对话，让它读取当前图谱上下文并生成回答。
- 把想法、任务、项目、资料整理成节点，形成可浏览的个人知识图谱。
- 在工作区中同时查看局部图谱、节点内容和聊天上下文。
- 审核 Agent 提出的高风险图谱更新，确认后再写入长期记忆。
- 查看事件时间线，追踪图谱和记忆的演化过程。

## 适合谁

Me.Agent 适合想把个人知识管理、任务管理和 AI 对话放到同一个长期上下文里的用户。它不是一个云端 SaaS，也不会开箱即用地同步到多台设备；默认形态是本地运行、本地保存数据。

## 准备工作

你需要先安装：

- Python 3.12 或更新版本
- Node.js 18 或更新版本
- 一个 OpenAI 兼容的模型 API Key

模型服务可以是 OpenAI，也可以是任何兼容 OpenAI Chat Completions 接口的服务。

## 配置模型

在项目根目录创建 `.env` 文件：

```text
OPENAI_API_KEY=你的 API Key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_BASE_MODEL=gpt-4.1-mini
```

如果你使用其他兼容服务，把 `OPENAI_BASE_URL` 和 `OPENAI_BASE_MODEL` 改成对应的地址和模型名即可。

默认数据库会保存在 `data/me_agent.sqlite3`。如果想换位置，可以额外设置：

```text
ME_AGENT_DB=/path/to/me_agent.sqlite3
```

上传文件默认复制到本地 `data/uploads`，SQLite 只保存文件元数据、摘要、文本抽取结果和下载路径。如果想换文件存储目录，可以设置：

```text
ME_AGENT_FILE_STORAGE=/path/to/uploads
```

## 启动后端

推荐使用一键启动脚本同时启动前后端：

```bash
python scripts/start_dev.py
```

默认端口：

```text
前端：http://127.0.0.1:11100
后端：http://127.0.0.1:11101
```

你也可以通过参数指定端口：

```bash
python scripts/start_dev.py --frontend-port 3000 --backend-port 8000
```

脚本会自动把前端的 `NEXT_PUBLIC_API_BASE_URL` 指向后端地址，并配置后端 CORS。

如果需要手动启动，可以按下面的步骤分别启动。

在项目根目录运行：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn backend.app.main:app --reload --port 8000
```

启动后，后端 API 默认运行在：

```text
http://localhost:8000
```

你可以打开下面的地址检查服务是否正常：

```text
http://localhost:8000/health
```

## 启动界面

另开一个终端，进入前端目录：

```bash
cd frontend
npm install
npm run dev
```

然后在浏览器打开：

```text
http://localhost:3000
```

如果你的后端不在 `http://localhost:8000`，启动前端前设置：

```bash
NEXT_PUBLIC_API_BASE_URL=http://你的后端地址 npm run dev
```

## 基本使用方式

第一次启动时，Me.Agent 会自动创建几个初始工作区，例如工作、生活和 Me.Agent 设计。你可以从首页进入图谱工作台，也可以直接开始一次聊天。

建议的使用方式：

1. 先把一个真实主题写成节点，例如一个项目、一次会议、一个长期目标。
2. 在工作区里围绕这个节点和 Agent 对话。
3. 当 Agent 提出需要写入图谱的更新时，到 Proposals 页面确认或拒绝。
4. 定期查看 Graph 和 Timeline，整理长期上下文。

## 命令行用法

如果你更喜欢命令行，也可以使用内置 CLI：

```bash
me-agent chat "记录一个 todo：整理本周项目进展" --no-proposals
me-agent nodes list --json
me-agent proposals list --json
```

默认 CLI 直接访问本地 SQLite。Codex 等外部智能体需要连接正在运行的后端时，可以使用 HTTP 模式，这样它和浏览器里的对话框共享同一个 Python 服务、会话和图节点 API：

```bash
me-agent --api-url http://localhost:8000 chat "读取当前项目节点并更新摘要" --anchor node_xxx --json
me-agent --api-url http://localhost:8000 nodes show node_xxx --json
me-agent --api-url http://localhost:8000 proposals list --json
```

## 节点知识库和文件

节点编辑页的知识库支持文本条目和上传文件。文本文件会抽取正文用于编辑和检索；图片、PDF、压缩包等非纯文本文件会保存原文件，并在编辑页只展示摘要和元数据，需要完整内容时通过下载链接访问。

Agent 可以直接更新已有节点的正文和摘要，也可以直接把较冷的长期事实写入统一知识库；创建边、删除节点、归档等图结构变化仍会进入 Proposals，由你审核后再写入。

## 数据和隐私

Me.Agent 默认把数据保存在你本机的 SQLite 数据库中。聊天内容、节点内容和事件日志会作为本地数据持久化。

需要注意：

- 模型请求会发送到你配置的 `OPENAI_BASE_URL`。
- 不要把包含真实 API Key 的 `.env` 文件提交到公开仓库。
- 如果你部署到远程服务器，请自行处理鉴权、HTTPS、数据库备份和访问控制。

## 当前限制

- 目前主要面向本地个人使用，不是多人协作系统。
- 图谱结构和 Agent 行为仍在快速迭代，建议定期备份本地数据库。
