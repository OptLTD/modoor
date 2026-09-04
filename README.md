# Modoor — AI Capability Layer (Phase 0)

按 Odoo **Module** 理念重做的能力层：对外发布 **Skill + MCP**，供外部 AI 调用。  
**与 Odoo 无运行时关系。**

当前能力：`base`（app/user/role）、`sale`（create→confirm）、`wiki`（页面 CRUD）；鉴权为 API Key → ctx。  
外部应用 demo：`external/board`、`external/pulse`（经 Modoor 注册中心发现）。

整合层包结构：

```text
modoor/
  core/       # settings / ctx / db / errors / security
  runtime/    # auth / audit / confirmation / tool runner / MCP
  platform/   # module 启停 / loader / 外部服务注册 / bootstrap
  web/        # PC Shell
```

设计文档见 [`docs/`](./docs/)，实现约定见 [`docs/PHASE0.md`](./docs/PHASE0.md)。

## 快速开始

```bash
cd /path/to/modoor-app
make dev                 # 建表 + 初始化 + 启动 Web：http://127.0.0.1:8765
# 默认账号 admin / admin123
# make mcp               # MCP（stdio）
# make test
```

等价手工步骤：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

# 冒烟：直接跑销售链（不经 MCP 宿主）
python -m tests.smoke_sale_flow

# 启动 MCP（stdio，供 Cursor 等连接）
modoor-mcp
# 或: python -m modoor
```

本地默认 SQLite（`DATABASE_URL=sqlite:///./modoor.db`）。

## Cursor 接入

在 MCP 配置中增加（路径改成你的仓库绝对路径）：

```json
{
  "mcpServers": {
    "modoor": {
      "command": "/path/to/modoor-app/.venv/bin/modoor-mcp",
      "env": {
        "MODOOR_API_KEY": "dev-key-change-me",
        "MODOOR_TENANT": "demo",
        "MODOOR_USER_ID": "user-1",
        "MODOOR_CONFIRM_SECRET": "dev-confirm-secret-change-me",
        "DATABASE_URL": "sqlite:////path/to/modoor-app/modoor.db"
      }
    }
  }
}
```

Skill 文档路径：`modules/sale/skills/create_and_confirm_order.md`  
也可经 MCP resource：`skill://sale/create_and_confirm_order`，或 tool `catalog.list_skills`。

更细说明见 [`docs/INTEGRATION.md`](./docs/INTEGRATION.md)。

## ctx

| 字段 | 必填 | 来源（Phase 0） |
|---|---|---|
| `tenant` | 是 | `MODOOR_TENANT` |
| `user_id` | 是 | `MODOOR_USER_ID` |
| `team_id` | 否 | `MODOOR_TEAM_ID` |

进程启动时校验 `MODOOR_API_KEY`；当前一进程绑定一套 ctx。
