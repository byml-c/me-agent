---
name: me-agent-graph-cli
description: Use this skill when an agent needs to directly inspect, search, create, edit, connect, or enrich the Me.Agent graph through backend/app/cli.py. Trigger for operating graph nodes, workspaces, edges, node databases, node files, node scripts, memory attachments, or using the Me.Agent graph as an agent knowledge base without proposal review.
---

# Me.Agent Graph CLI

Use `me-agent` as the direct graph knowledge-base interface.

## Invocation

Preferred code-agent invocation:

```bash
me-agent nodes search "current topic"
```

`backend/app/cli.py` reads `ME_AGENT_API_URL` or `SERVER_URL` as the default backend URL. The local wrapper should point at the shared backend:

```bash
#!/usr/bin/env sh
export SERVER_URL=http://localhost:11001
exec "$HOME/projects/me-agent/.venv/bin/python" "$HOME/projects/me-agent/backend/app/cli.py" "$@"
```

Non-interactive commands emit JSON. Parse JSON output; do not scrape text.

Global options must appear before the subcommand:

- `--api-url http://localhost:11001`: explicit HTTP backend.
- `--no-seed`: local SQLite only; skip initial seed nodes.

## Agent Workflow

When asked to work in a current topic or workspace:

1. Find the relevant workspace or anchor node with `nodes search`.
2. Inspect local context with `nodes ego-graph`, `nodes neighbors`, and `nodes show`.
3. Directly create/update nodes, edges, databases, files, or scripts as needed.
4. Verify with `nodes show`, `nodes databases list`, `nodes files list`, or `nodes scripts list`.

Do not route these changes through `proposals`; this CLI is the no-review agent editing path.

## Search And Explore

```bash
me-agent nodes search "视觉 触觉" --limit 10
me-agent nodes search "GelSight" --workspace-id <workspace_id> --depth 3
me-agent nodes search "dataset" --with-database "GelSight"
me-agent nodes show <node_id>
me-agent nodes neighbors <node_id>
me-agent nodes ego-graph <node_id> --depth 2 --limit 50
me-agent workspaces list
me-agent workspaces show <workspace_id>
```

## Nodes And Edges

```bash
me-agent nodes create --title "新主题" --body "正文" --summary "摘要"
me-agent nodes update <node_id> --title "新标题"
me-agent nodes update <node_id> --body "新正文" --summary "新摘要"
me-agent nodes update <node_id> --workspace
me-agent nodes archive <node_id>

me-agent edges create <source_node_id> <target_node_id> --weight 1.0
me-agent edges update <edge_id> --weight 0.8
me-agent edges delete <edge_id>
```

## Node Databases

Use databases for structured knowledge entries attached to a node.

```bash
me-agent nodes databases list <node_id>
me-agent nodes databases add <node_id> --name "实验数据库" --description "用途" --content "文本资料"
me-agent nodes databases add <node_id> --name "数据文件" --kind file --path /path/to/data.csv
me-agent nodes databases add <node_id> --name "长资料" --content-file /path/to/notes.md
me-agent nodes databases update <node_id> <database_id> --description "新的描述"
me-agent nodes databases delete <node_id> <database_id>
```

Search nodes by attached database:

```bash
me-agent nodes search "当前话题" --with-database "数据库关键词"
```

## Node Files

Use files for file attachments visible to node scripts.

```bash
me-agent nodes files list <node_id>
me-agent nodes files add <node_id> --name "config.yaml" --path /path/to/config.yaml
me-agent nodes files add <node_id> --name "notes.md" --content-file /path/to/notes.md
me-agent nodes files delete <node_id> <file_attachment_id>
```

## Node Scripts

Use scripts for Python automations attached to a node. The runtime prepends `from utils import *`, so scripts can call the helpers below without imports.

Available variables:

- `NODE_ID`: current node id as a string.
- `SCRIPT_ARGS`: dict built from `nodes scripts run ... --arg key=value`.
- `NODE_DATABASES`: list of database attachments from the current node. Each item is a dict with fields such as `id`, `entry_id`, `kind`, `name`, `description`, `content`, `summary`, `path`, `media_type`, and `download_url`.
- `NODE_FILES`: list of file attachments from the current node. Each item is a dict with fields such as `id`, `file_id`, `name`, `path`, `description`, `content`, `summary`, `media_type`, and `download_url`.
- `TRIGGER`: trigger name, usually `manual_run`, `enter`, `manual_enter`, `ai_switch`, or `schedule`.
- `SCRIPTS_DIR`: `pathlib.Path` for the repo-level script runtime directory.

Available helper functions:

- `open_app(app, args=None, once=True, cwd=None)`: non-blocking desktop/process launcher. `app` is an executable name or path. `args` may be a string or list. `$HOME`, environment variables, and `~` are expanded. `cwd` is resolved before launch. With `once=True`, an already-running process with the same command and cwd is reused. Returns a dict like `{"ok": true, "created": true, "pid": 123, "command": [...], "cwd": "..."}` or an error dict.
- `list_node_files()`: returns `NODE_FILES`.
- `get_node_file(file_id=None, name=None)`: returns the first file attachment matching `file_id` or exact `name`, otherwise `None`.
- `log(value)`: prints JSON for dict/list values, or plain text for other values. Output is captured in the script run log.

Script run behavior:

- `nodes scripts run` starts the script in the background and returns `status: "started"` plus `pid`, `log_path`, and `script_path`.
- The script body is written under the repo `scripts/` directory and executed with Python.
- Runtime output is written to the JSON file at `log_path`; inspect that file when the command returns before the script finishes.

Example script:

```python
target = SCRIPT_ARGS.get("path") or "$HOME/project"
result = open_app("code", [target], once=True, cwd=target)
log({
    "node_id": NODE_ID,
    "trigger": TRIGGER,
    "opened": result,
    "databases": [item.get("name") for item in NODE_DATABASES],
})
```

```bash
me-agent nodes scripts list <node_id>
me-agent nodes scripts add <node_id> --name "打开项目" --description "进入节点时打开编辑器" --code 'open_app("code", ["."], cwd="$HOME/project")' --trigger-on-enter
me-agent nodes scripts add <node_id> --name "整理数据" --code-file /path/to/script.py
me-agent nodes scripts update <node_id> <script_id> --description "新的脚本说明"
me-agent nodes scripts update <node_id> <script_id> --code-file /path/to/new_script.py
me-agent nodes scripts delete <node_id> <script_id>
me-agent nodes scripts run <node_id> <script_id> --arg key=value
```

## Raw Memory

Use raw memory only when the higher-level database/file/script commands are insufficient.

```bash
me-agent nodes memory show <node_id>
me-agent nodes memory update <node_id> --memory '{"attachments":{"databases":[],"files":[],"scripts":[]}}'
me-agent nodes memory update <node_id> --file /path/to/memory.json
```

## Chat Context

Use chat when natural-language synthesis is useful, but remember direct CLI edits above are the no-review write path.

```bash
me-agent chat "总结这个节点并补充下一步" --anchor <node_id>
me-agent chat "围绕这个工作区整理行动项" --workspace-id <workspace_id>
```

## Error Handling

- `failed to connect to backend`: report the issue to users.
- `node not found`, `script not found`, or `database attachment not found`: re-run the relevant `list` or `search` command and retry with current ids.
- `unrecognized arguments`: keep global options before the subcommand and check the command shape.
- If `me-agent` prints usage even though arguments were supplied, check that the wrapper ends with `"$@"`.
