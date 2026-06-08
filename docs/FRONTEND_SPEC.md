# Me.Agent 前端规格设计

## 1. 前端目标

Me.Agent 前端负责提供一个低认知负担的图上交互界面，让用户可以：

* 创建和编辑节点；
* 查看局部图；
* 进入工作区；
* 与 Agent 对话；
* 查看本轮上下文；
* 审核 Agent 的图更新提案；
* 查看事件时间线；
* 管理节点脚本。

前端不应强迫用户理解复杂节点类型或边类型。默认只暴露：

* 节点；
* 边；
* 工作区；
* 候选关系；
* 更新提案；
* 局部图视野。

---

## 2. 技术栈

前端主语言为 Node.js 生态下的 TypeScript。

MVP 使用：

```text
Framework: Next.js
Language: TypeScript
UI: React
Graph Visualization: React Flow
Editor: TipTap
State Management: Zustand
Styling: Tailwind CSS
API Client: OpenAPI generated client or custom fetch wrapper
```

后续可根据需要引入：

```text
Cytoscape.js / Sigma.js
Monaco Editor
TanStack Query
shadcn/ui
Framer Motion
```

---

## 3. 信息架构

主要页面：

```text
/
├── Dashboard
├── Graph View
├── Nodes
│   └── Node Detail
├── Workspaces
│   └── Workspace View
├── Chat
├── Proposals
├── Timeline
└── Scripts
```

推荐路由：

```text
/                         Home Dashboard
/graph                    Global or current ego graph
/nodes/[nodeId]           Node Detail
/workspaces               Workspace list
/workspaces/[nodeId]      Workspace View
/chat/[sessionId]         Chat View
/proposals                Proposal Inbox
/timeline                 Event Log
/scripts/[scriptId]       Script Panel
```

---

## 4. 核心页面

## 4.1 Home Dashboard

Dashboard 是用户进入 Me.Agent 后的首页。

展示内容：

* 最近访问节点；
* 最近工作区；
* 最近对话；
* 待确认 proposal；
* Agent 建议；
* 今日新增节点；
* 高活跃节点。

核心操作：

* 新建节点；
* 新建对话；
* 进入最近工作区；
* 查看待确认 proposal；
* 查看最近图谱变化。

优先级：

1. 待确认 proposal；
2. 最近工作区；
3. 最近访问节点；
4. 最近对话；
5. Agent 建议。

---

## 4.2 Graph View

Graph View 是 Me.Agent 的核心视觉入口。

### 4.2.1 展示原则

默认不展示全局图，只展示当前节点附近的局部 ego graph，避免认知负担。

默认参数：

```text
depth = 2
limit = 50
hide_archived = true
show_candidate_edges = true
```

### 4.2.2 节点视觉

节点需要区分：

* 当前锚点；
* 普通节点；
* 工作区节点；
* 归档节点；
* 高活跃节点；
* Agent 新建议节点。

视觉建议：

* 当前锚点使用最明显的边框；
* 工作区节点使用特殊图标；
* 归档节点降低透明度；
* 高活跃节点略大；
* 新建议节点带小 badge。

### 4.2.3 边视觉

边需要体现：

* 普通边；
* 候选边；
* 边权强弱；
* 最近访问边。

视觉建议：

* 普通边使用实线；
* 候选边使用虚线或低透明度；
* 边权越高线条越粗；
* 最近访问边可短暂高亮。

### 4.2.4 交互能力

Graph View 应支持：

* 缩放；
* 拖拽；
* 聚焦节点；
* 展开一跳 / 二跳 / 三跳；
* 点击节点进入详情；
* 在两个节点之间创建边；
* 删除边；
* 确认候选边；
* 拒绝候选边；
* 以某节点为锚点重绘局部图；
* 按工作区过滤；
* 隐藏归档节点。

---

## 4.3 Node Detail

节点详情页用于查看和编辑单个节点。

展示内容：

* 标题；
* 正文；
* 摘要；
* 状态；
* 是否工作区；
* 访问次数；
* 最近访问时间；
* 相邻节点；
* 相关 episode；
* 关联脚本；
* 节点历史；
* Agent 建议。

核心操作：

* 编辑标题；
* 编辑正文；
* 归档节点；
* 升级为工作区；
* 新建相邻节点；
* 连接已有节点；
* 从当前节点发起对话；
* 查看局部图；
* 查看历史版本；
* 接受或拒绝 Agent 建议。

正文编辑器使用 TipTap，支持 Markdown-like 编辑体验。

---

## 4.4 Workspace View

工作区视图是某个 workspace 节点的局部操作台。

展示内容：

* 工作区简介；
* 入口摘要；
* 局部图；
* 相关节点列表；
* 最近活动；
* 开放问题；
* 任务候选；
* 文件和脚本；
* Agent 对话区。

核心操作：

* 进入工作区对话；
* 查看工作区局部图；
* 添加节点到工作区；
* 从多个节点生成子工作区；
* 查看工作区最近事件；
* 查看 Agent 整理建议。

Workspace View 应比普通节点页更偏“操作台”，而不是单纯内容页。

---

## 4.5 Chat View

Chat View 是用户和 Me.Agent 的主要交互入口。

展示内容：

* 对话消息；
* 当前锚点；
* 当前工作区；
* 本轮使用的上下文节点；
* Agent 生成的 proposal；
* 自动执行的低风险更新；
* 需要确认的高风险更新。

核心操作：

* 发送消息；
* 选择当前锚点；
* 切换工作区；
* 查看 used_context；
* 从回答中保存节点；
* 从回答中创建工作区；
* 接受 / 拒绝 proposal；
* 移除错误上下文节点；
* 继续基于某个节点追问。

### 4.5.1 used_context 展示

Agent 回答时应展示本轮使用了哪些节点。

展示字段：

```text
node title
include_level
activation_score
reason
```

用户应可以：

* 展开查看节点摘要；
* 从上下文中移除某个节点；
* 将某个上下文节点设为新的锚点；
* 打开节点详情。

---

## 4.6 Proposal Inbox

Proposal Inbox 集中展示待确认更新提案。

每个 proposal 展示：

* 操作类型；
* 影响节点；
* 修改前后；
* 理由；
* 置信度；
* 风险等级；
* 创建时间；
* 来源对话。

用户可以：

* 接受；
* 拒绝；
* 修改后接受；
* 延后；
* 永久忽略类似建议。

Proposal 类型包括：

```text
create_node
edit_node
archive_node
split_node
merge_node
create_edge
remove_edge
strengthen_edge
weaken_edge
create_workspace
promote_to_workspace
```

### 4.6.1 Proposal Detail

Proposal 详情页需要按操作类型展示不同内容。

对于 `split_node`，展示：

* 原节点；
* 拆分理由；
* 建议新节点；
* 新节点正文预览；
* 建议边；
* 原节点改写后的 overview。

对于 `create_edge`，展示：

* 源节点；
* 目标节点；
* 建议理由；
* 是否候选边；
* 初始权重。

对于 `promote_to_workspace`，展示：

* 目标节点；
* 升级理由；
* 当前相邻节点；
* 工作区初始摘要。

---

## 4.7 Timeline / Event Log

Timeline 展示图谱演化历史。

支持：

* 按时间查看；
* 按节点过滤；
* 按工作区过滤；
* 按事件类型过滤；
* 查看某个节点的历史版本；
* 查看 proposal 的接受 / 拒绝记录；
* 回滚到某个版本。

事件类型包括：

```text
NodeCreated
NodeEdited
NodeArchived
NodeSplit
NodeMerged
EdgeCreated
EdgeRemoved
EdgeStrengthened
EdgeWeakened
WorkspaceCreated
NodePromotedToWorkspace
EpisodeCreated
ProposalCreated
ProposalAccepted
ProposalRejected
ScriptExecuted
ContextAssembled
AgentResponseGenerated
```

---

## 4.8 Script Panel

Script Panel 展示节点脚本。

展示内容：

* 脚本名称；
* 脚本类型；
* 关联节点；
* 脚本代码；
* 权限等级；
* 最近运行结果；
* stdout / stderr；
* 执行历史。

脚本类型：

```text
read_script
transform_script
action_script
```

执行策略：

* read_script：用户确认后可执行；
* transform_script：沙盒执行；
* action_script：必须显式确认，并展示影响范围；
* 禁止默认执行系统命令；
* 所有脚本执行记录进入 event log。

---

## 5. 前端状态管理

建议使用 Zustand 管理客户端状态。

核心 store：

```text
useGraphStore
useNodeStore
useWorkspaceStore
useChatStore
useProposalStore
useTimelineStore
useUIStore
```

### 5.1 Graph Store

维护：

* 当前 ego graph；
* 当前锚点；
* 节点布局；
* 展开深度；
* 过滤条件；
* 选中节点；
* hover 状态。

### 5.2 Chat Store

维护：

* 当前 session；
* 消息列表；
* 当前工作区；
* 当前锚点；
* streaming 状态；
* used_context；
* 本轮 proposals。

### 5.3 Proposal Store

维护：

* 待确认 proposal；
* proposal 详情；
* proposal 状态；
* 接受 / 拒绝结果。

---

## 6. API Client

前端通过 API client 与 FastAPI 通信。

建议封装：

```text
api.nodes
api.edges
api.chat
api.workspaces
api.proposals
api.events
api.scripts
```

Chat API 应支持流式输出。MVP 可以先用普通 HTTP response，后续改为 SSE 或 WebSocket。

---

## 7. 前端交互原则

### 7.1 局部优先

默认不展示全局图，只展示当前节点附近的局部视野。

### 7.2 Agent 透明

Agent 回答时应展示：

* 当前锚点；
* 使用了哪些节点；
* 是否生成了图更新；
* 哪些更新已自动执行；
* 哪些更新需要确认。

### 7.3 更新可控

用户应始终知道图发生了什么变化。

高风险操作不得静默执行。

### 7.4 降低类型负担

前端不应要求用户选择复杂节点类型或边类型。

默认只需要：

* 节点标题；
* 节点正文；
* 是否工作区；
* 是否归档。

### 7.5 候选关系弱展示

Agent 推断的候选边应以弱视觉形式显示，避免污染用户认知。

---

## 8. 推荐前端仓库结构

```text
frontend/
├── src/
│   ├── app/
│   │   ├── page.tsx
│   │   ├── graph/
│   │   ├── nodes/
│   │   ├── workspaces/
│   │   ├── chat/
│   │   ├── proposals/
│   │   ├── timeline/
│   │   └── scripts/
│   ├── components/
│   │   ├── layout/
│   │   ├── graph/
│   │   ├── node/
│   │   ├── chat/
│   │   ├── proposal/
│   │   └── common/
│   ├── features/
│   │   ├── graph/
│   │   ├── chat/
│   │   ├── nodes/
│   │   ├── workspaces/
│   │   ├── proposals/
│   │   └── timeline/
│   ├── api/
│   │   ├── client.ts
│   │   ├── nodes.ts
│   │   ├── edges.ts
│   │   ├── chat.ts
│   │   ├── proposals.ts
│   │   └── events.ts
│   ├── stores/
│   ├── hooks/
│   ├── types/
│   └── styles/
├── package.json
├── next.config.ts
└── tsconfig.json
```

---

## 9. 前端开发阶段

### Phase 0：技术验证

目标：

* 搭建 Next.js；
* 接入 Tailwind；
* 实现基础布局；
* 实现 React Flow 局部图 demo；
* 实现基础 API client；
* 实现节点详情页静态版。

### Phase 1：MVP 前端

目标：

* 实现 Dashboard；
* 实现 Graph View；
* 实现 Node Detail；
* 实现 Chat View；
* 实现 Proposal Inbox；
* 实现 Workspace View；
* 接入后端真实 API。

### Phase 2：图演化交互

目标：

* 支持候选边确认 / 拒绝；
* 支持节点拆分 proposal 预览；
* 支持节点升级工作区；
* 支持 used_context 展示；
* 支持 event timeline；
* 支持节点历史查看。

### Phase 3：脚本与高级视图

目标：

* 实现 Script Panel；
* 实现脚本运行确认弹窗；
* 实现图布局保存；
* 实现工作区内任务视图；
* 实现反思报告页面。

---

## 10. 前端验收标准

* 用户可以创建、编辑、归档节点；
* 用户可以查看二跳局部图；
* 用户可以确认或拒绝候选边；
* 用户可以在 Chat View 中选择当前锚点；
* Agent 回答后可以展示 used_context；
* Proposal Inbox 可以展示、接受、拒绝 proposal；
* Workspace View 可以展示工作区局部图和相关节点；
* Timeline 可以展示 event log；
* 高风险操作前端必须展示确认步骤。
