# External apps — independent UIs registered to Modoor

Modoor 作为**注册中心**：外部服务启动后 `POST /api/registry/services`，  
PC Brand / 外部应用的 Module 切换都从 `GET /api/registry/catalog` 取列表。

## Demos

| 服务 | 端口 | 模块 ID | 说明 |
|---|---|---|---|
| Board | 8771 | `board` | 便签板（服务端 HTML）；启动时自动注册 |
| Pulse | 8772 | `pulse` | Vue CSR；启动时自动注册 |

**不在** `modules/` 下放置桥接清单；Brand / catalog 只在服务成功 `POST /api/registry/services` 后出现。


均自带 **module 切换** + **Log out**（建议能力）。

## 启动

```bash
# 终端 1：Modoor
make dev

# 终端 2：两个外部服务
make external
# 或: python scripts/run_external_demos.py
```

打开 http://127.0.0.1:8765 登录后，Brand 里选 **Board** / **Pulse** 跳到外部应用。  
外部应用顶栏可切回其他 module，或 Log out 回 Modoor。

## Capability export (MODULE_CONTRACT)

External apps **optionally** register the same contract as in-repo modules:

```json
{
  "manifest": { "id": "...", "exports": { "tools": [...], "skills": [...] }, "ability": [...], "ui-web": { "kind": "external" } },
  "artifacts": {
    "tools": [{ "name": "...", "input_schema": {}, "invoke_url": "...", "risk": "low", ... }],
    "skills": [{ "id": "...", "tools": [...], "content": "# Skill..." }],
    "models": [{ "name": "...", "fields": [] }]
  }
}
```

- Only names in `manifest.exports.*` are L1.
- Hub: `GET /api/registry/exports`
- MCP: `catalog.list_capabilities` / `catalog.list_skills` / `external.call_tool`


| 变量 | 默认 |
|---|---|
| `MODOOR_URL` | `http://127.0.0.1:8765` |
| `MODOOR_API_KEY` | 与 `.env` 一致（注册鉴权） |
| `EXTERNAL_BOARD_PORT` | `8771` |
| `EXTERNAL_PULSE_PORT` | `8772` |
