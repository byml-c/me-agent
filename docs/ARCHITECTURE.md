# Me.Agent 后端与系统架构设计

## 1. 架构目标

Me.Agent 后端负责支撑一个以无向认知图为核心的个人 Agent Harness。系统需要同时支持：

* 图数据存储；
* 节点与边的 CRUD；
* 局部图查询；
* 差序格局式上下文组织；
* Agent 对话；
* Graph Writer 更新提案；
* Proposal 审核与执行；
* Event log；
* Embedding 检索；
* 节点脚本运行；
* 后续多模型、多工具扩展。

---

## 2. 技术栈

后端主语言为 Python。

MVP 推荐技术栈：

```text
API Framework: FastAPI
Data Validation: Pydantic
ORM: SQLAlchemy
Database: PostgreSQL
Migration: Alembic
Vector Search: pgvector
Cache: Redis optional
Task Queue: Celery / Dramatiq / RQ optional
LLM Orchestration: LangGraph / custom state machine
Testing: pytest
```

初期不建议过早引入复杂图数据库。无向图可以先用 PostgreSQL 的 edge table 实现，后续再根据查询瓶颈迁移到 Neo4j、Kuzu、FalkorDB 或 ArangoDB。

---

## 3. 总体数据流

核心执行流程：

```text
User Message
→ API Layer
→ Intent Router
→ Anchor Resolver
→ Context Reader
→ Context Assembler
→ LLM Reasoner
→ Graph Writer
→ Proposal Policy
→ Response Builder
→ Event Logger
→ Graph Store
```

其中：

* **Context Reader** 负责读图；
* **Context Assembler** 负责组装 LLM 上下文；
* **LLM Reasoner** 负责回答；
* **Graph Writer** 负责提出图更新；
* **Proposal Policy** 负责判断自动执行或等待确认；
* **Event Logger** 负责记录所有关键操作。

---

## 4. 后端模块划分

### 4.1 API Layer

负责对外提供 REST / WebSocket API。

主要职责：

* 鉴权；
* 请求校验；
* 调用 service；
* 返回统一响应；
* 支持 Chat 流式输出；
* 支持 Proposal 审核操作。

建议目录：

```text
backend/app/api/
├── routes_nodes.py
├── routes_edges.py
├── routes_chat.py
├── routes_workspaces.py
├── routes_proposals.py
├── routes_events.py
└── routes_scripts.py
```

### 4.2 Graph Store

负责节点、边、事件、proposal 的存储与查询。

核心表：

```text
nodes
edges
events
proposals
chat_sessions
chat_messages
node_embeddings
script_refs
```

MVP 中 Graph Store 可以基于 PostgreSQL 实现：

* `nodes` 表存节点；
* `edges` 表存无向边；
* `events` 表存 append-only event log；
* `node_embeddings` 表存 embedding；
* `proposals` 表存 Agent 更新提案。

### 4.3 Context Reader

Context Reader 负责根据当前请求生成局部图上下文。

输入：

```yaml
user_message: string
current_node_id: string | null
current_workspace_id: string | null
chat_session_id: string
token_budget: integer
```

输出：

```yaml
anchor_nodes:
  - node_id
context_nodes:
  - node_id
  - title
  - summary
  - distance
  - activation_score
  - include_level
context_edges:
  - edge_id
  - node_a_id
  - node_b_id
  - weight
context_summary: string
```

Context Reader 的核心任务不是单纯 top-k 检索，而是以当前锚点为中心，从无向图上做加权扩散。

### 4.4 Anchor Resolver

Anchor Resolver 负责确定本轮对话的当前锚点。

锚点优先级：

1. 用户显式指定的节点；
2. 当前打开的节点；
3. 当前工作区；
4. 最近活跃节点；
5. 语义检索匹配节点；
6. 新建临时对话节点。

### 4.5 Context Assembler

Context Assembler 负责将 Context Reader 的结果转为 LLM prompt。

组装策略：

* 当前锚点详细展开；
* 一跳节点中度摘要；
* 二跳节点短摘要；
* 远处节点只展示标题；
* 不注入归档节点全文；
* 不自动注入敏感节点；
* 脚本节点默认只展示接口；
* 原始 episode 按需拉取。

### 4.6 Agent Runtime

Agent Runtime 负责对话执行。

职责：

* 处理用户消息；
* 调用 Context Reader；
* 调用 LLM；
* 支持流式响应；
* 调用 Graph Writer；
* 返回 assistant response 和 proposals；
* 记录上下文使用情况。

### 4.7 Graph Writer

Graph Writer 根据对话生成图更新 proposal。

它不直接执行高风险写入。

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

输出示例：

```json
{
  "operation": "split_node",
  "target_node_id": "node_123",
  "reason": "该节点已经包含上下文机制、节点更新机制和工作区生成三个独立主题。",
  "proposed_nodes": [
    {
      "title": "差序格局上下文",
      "body": "..."
    },
    {
      "title": "节点更新机制",
      "body": "..."
    },
    {
      "title": "工作区生成机制",
      "body": "..."
    }
  ],
  "risk_level": "high",
  "requires_confirmation": true
}
```

### 4.8 Proposal Policy

Proposal Policy 根据操作风险决定是否自动执行。

自动执行：

```text
update_access_count
update_last_accessed_at
create_episode_node
strengthen_existing_edge
create_candidate_edge
save_chat_summary
```

需要确认：

```text
edit_node_body
archive_node
split_node
merge_node
promote_to_workspace
execute_script
remove_edge
bulk_create_edges
```

### 4.9 Event Logger

所有重要操作写入 append-only event log。

Event 类型：

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

Event log 应不可直接修改，只能追加修正事件。

### 4.10 Embedding Service

负责节点、episode、消息的 embedding 生成和更新。

触发时机：

* 节点创建；
* 节点正文修改；
* episode 创建；
* 文件导入；
* 周期性重建。

### 4.11 Script Runtime

负责执行节点脚本。

MVP 中可以先实现受限 Python 脚本或 shell 禁用模式。

安全要求：

* 沙盒执行；
* 限制文件访问；
* 限制网络访问；
* 限制运行时间；
* 记录 stdout / stderr；
* 高风险操作需要用户确认。

---

## 5. 数据模型草案

### 5.1 Node

```python
class Node:
    id: str
    title: str
    body: str
    summary: str | None
    memory: dict
    is_workspace: bool
    status: str  # active | dense | archived
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime | None
    access_count: int
```

### 5.2 Edge

```python
class Edge:
    id: str
    node_a_id: str
    node_b_id: str
    weight: float
    access_count: int
    coactivation_count: int
    is_candidate: bool
    created_by: str  # user | agent | system
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime | None
```

无向边需要保证 `(node_a_id, node_b_id)` 的规范顺序，避免 A-B 和 B-A 重复存储。

### 5.3 Event

```python
class Event:
    id: str
    type: str
    actor: str  # user | agent | system
    payload: dict
    created_at: datetime
```

### 5.4 Proposal

```python
class Proposal:
    id: str
    operation: str
    target_ids: list[str]
    payload: dict
    reason: str
    confidence: float
    risk_level: str  # low | medium | high
    status: str  # pending | accepted | rejected | modified | expired
    created_at: datetime
    resolved_at: datetime | None
```

### 5.5 ChatSession

```python
class ChatSession:
    id: str
    title: str
    current_anchor_node_ids: list[str]
    current_workspace_id: str | None
    created_at: datetime
    updated_at: datetime
```

### 5.6 ChatMessage

```python
class ChatMessage:
    id: str
    session_id: str
    role: str  # user | assistant | system
    content: str
    context_node_ids: list[str]
    created_at: datetime
```

---

## 6. 上下文组织算法

### 6.1 图扩散

从锚点出发，在无向图上进行加权扩散。

候选节点分数：

```text
score(v) =
  α * semantic_relevance(query, v)
+ β * exp(-λ * graph_distance(anchor, v))
+ γ * path_edge_weight
+ δ * recency_score(v)
+ ε * access_score(v)
+ ζ * workspace_boost(v)
- η * archived_penalty(v)
```

### 6.2 上下文层级

按分数和距离分为：

```text
Level 0: 当前锚点，详细展开
Level 1: 强相邻节点，中等摘要
Level 2: 弱相邻或二跳节点，短摘要
Level 3: 远处候选节点，仅标题
```

### 6.3 边权更新

当两个节点共同进入上下文时：

```text
edge.coactivation_count += 1
edge.weight += learning_rate * coactivation_signal
```

当边长期未访问时：

```text
edge.weight *= exp(-decay_rate * elapsed_time)
```

---

## 7. API 草案

### 7.1 Nodes API

```text
POST   /nodes
GET    /nodes/{id}
PATCH  /nodes/{id}
POST   /nodes/{id}/archive
GET    /nodes/{id}/neighbors
GET    /nodes/{id}/history
GET    /nodes/{id}/ego-graph?depth=2&limit=50
```

### 7.2 Edges API

```text
POST   /edges
DELETE /edges/{id}
PATCH  /edges/{id}
```

### 7.3 Chat API

```text
POST   /chat
GET    /chat/sessions/{id}
POST   /chat/sessions/{id}/messages
```

Request:

```json
{
  "session_id": "chat_001",
  "message": "帮我整理一下 Me.Agent 的上下文机制",
  "anchor_node_ids": ["node_me_agent"],
  "workspace_id": "node_me_agent",
  "options": {
    "allow_proposals": true,
    "context_budget": 12000
  }
}
```

Response:

```json
{
  "assistant_message": "可以。当前上下文机制可以整理为...",
  "used_context": {
    "anchor_nodes": ["node_me_agent"],
    "context_nodes": [
      {
        "id": "node_context_reader",
        "title": "差序格局上下文",
        "include_level": 0,
        "activation_score": 0.93
      }
    ]
  },
  "proposals": [
    {
      "id": "proposal_001",
      "operation": "create_node",
      "title": "Context Reader 设计",
      "risk_level": "medium",
      "requires_confirmation": true
    }
  ]
}
```

### 7.4 Workspaces API

```text
GET    /workspaces
POST   /workspaces
GET    /workspaces/{id}
```

### 7.5 Proposals API

```text
GET    /proposals
GET    /proposals/{id}
POST   /proposals/{id}/accept
POST   /proposals/{id}/reject
PATCH  /proposals/{id}
```

### 7.6 Events API

```text
GET    /events
GET    /events/{id}
```

### 7.7 Scripts API

```text
POST   /scripts/{id}/run
```

---

## 8. 推荐后端仓库结构

```text
backend/
├── app/
│   ├── api/
│   │   ├── routes_nodes.py
│   │   ├── routes_edges.py
│   │   ├── routes_chat.py
│   │   ├── routes_workspaces.py
│   │   ├── routes_proposals.py
│   │   ├── routes_events.py
│   │   └── routes_scripts.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── logging.py
│   ├── db/
│   │   ├── session.py
│   │   └── migrations/
│   ├── models/
│   │   ├── node.py
│   │   ├── edge.py
│   │   ├── event.py
│   │   ├── proposal.py
│   │   └── chat.py
│   ├── schemas/
│   ├── services/
│   │   ├── graph_store/
│   │   ├── context_reader/
│   │   ├── context_assembler/
│   │   ├── agent_runtime/
│   │   ├── graph_writer/
│   │   ├── proposal_policy/
│   │   ├── embedding_service/
│   │   └── script_runtime/
│   ├── workers/
│   └── main.py
├── tests/
├── alembic/
└── pyproject.toml
```

---

## 9. 开发阶段规划

### Phase 0：技术验证

目标：

* 搭建 FastAPI 后端；
* 实现 Node / Edge 基础 CRUD；
* 实现局部 ego graph 查询；
* 实现基础 Chat API；
* 实现基本 event log。

### Phase 1：MVP 后端

目标：

* 实现差序格局上下文；
* 实现 Context Reader；
* 实现 Context Assembler；
* 实现 Graph Writer proposal；
* 实现 Proposal Policy；
* 实现 workspace 节点；
* 实现 PostgreSQL + pgvector。

### Phase 2：图演化

目标：

* 实现节点拆分；
* 实现节点聚合为工作区；
* 实现候选边机制；
* 实现边权自动强化和衰减；
* 实现节点状态 dense / archived；
* 实现基础反思报告。

### Phase 3：脚本与工具

目标：

* 支持节点脚本；
* 支持沙盒执行；
* 支持文件节点；
* 支持外部数据导入；
* 支持插件式工具接口。

---

## 10. 后端验收标准

* Node / Edge CRUD 可用；
* 无向边不会重复存储；
* 能查询二跳 ego graph；
* Chat API 能返回 assistant message；
* Chat API 能返回 used_context；
* Graph Writer 能生成 proposal；
* 高风险 proposal 不会自动执行；
* 所有关键操作写入 event log；
* 节点创建和更新后可生成 embedding；
* 基础单元测试覆盖核心 service。
