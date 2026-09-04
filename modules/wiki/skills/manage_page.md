---
id: wiki.manage_page
title: Manage wiki projects and pages
summary: Create projects and hierarchical pages; body is BlockNote JSON; delete requires confirmation.
when_to_use: |
  User wants to organize docs in wiki projects / page trees, or edit page content.
tools:
  - wiki.create_project
  - wiki.list_projects
  - wiki.create_page
  - wiki.update_page
  - wiki.get_page
  - wiki.list_pages
  - wiki.delete_page
confirmations:
  - step: delete
    tool: wiki.delete_page
    reason: Deleting a page is destructive; requires confirmation_token.
---

# Skill: Manage wiki page

## Steps

1. **List projects**: `wiki.list_projects` — pick a `project_id` (or create one).
2. **Create project**: `wiki.create_project(name, description?)` — returns `project` + `home_page`.
3. **Create page**: `wiki.create_page(project_id, title, body?, parent_id?)` — `body` is BlockNote JSON array; omit for empty doc.
4. **Update**: `wiki.update_page(page_id, title?, body?)`.
5. **Read**: `wiki.get_page(page_id)`.
6. **List**: `wiki.list_pages(project_id?, q?, limit?)`.
7. **Delete** (high risk; cannot delete project home page):
   - Call `wiki.delete_page(page_id)` → `needs_confirmation`.
   - Resubmit with `confirmation_token`.

## 禁忌 / 边界

- Identify pages/projects by **id** only (no slug).
- Do not invent SQL or bypass MCP.
- Do not delete without confirmation.
