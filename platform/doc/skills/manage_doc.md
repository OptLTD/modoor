---
id: doc.manage_assets
title: Manage doc assets (unstructured materials)
summary: Search and read tagged files in the doc warehouse; update tags; delete requires confirmation.
when_to_use: |
  User wants AI to find / read existing materials (policies, manuals, sheets, slides)
  stored in the doc module, or to retag / remove an asset.
tools:
  - doc.search_assets
  - doc.list_assets
  - doc.get_asset
  - doc.get_asset_text
  - doc.update_asset
  - doc.delete_asset
confirmations:
  - step: delete
    tool: doc.delete_asset
    reason: Deleting an asset removes the stored blob; requires confirmation_token.
---

# Skill: Manage doc assets

## Steps

1. **Search**: `doc.search_assets(q?, tag?, limit?)` — keyword matches title / filename / tags / extracted text.
2. **List**: `doc.list_assets(tag?, limit?)` — recent assets.
3. **Meta**: `doc.get_asset(asset_id)` — metadata + truncated text.
4. **Read for AI**: `doc.get_asset_text(asset_id)` — full extracted text.
   - Upload is async: if `text_status` is `pending` / `running`, wait and retry.
   - If `text_status` is `failed`, say extraction failed (`text_error`); do not invent contents.
5. **Update**: `doc.update_asset(asset_id, title?, tags?, note?)`.
6. **Delete** (high risk):
   - Call `doc.delete_asset(asset_id)` → `needs_confirmation`.
   - Resubmit with `confirmation_token`.

## 禁忌 / 边界

- Identify assets by **id** only.
- Prefer `get_asset_text` when answering from document contents.
- If `text_status` is pending/running, wait; if failed or empty, do not invent file contents.
- Do not delete without confirmation.
