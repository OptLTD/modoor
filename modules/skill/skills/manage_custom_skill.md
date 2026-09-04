---
id: skill.manage_custom_skill
title: Manage custom skills
summary: List module (read-only) and custom skills; create/update/delete only custom ones.
when_to_use: |
  User wants to browse Skill Catalog, author a tenant custom skill SOP, or remove a custom skill.
  Module-exported skills (source=module) are view-only.
tools:
  - skill.list_skills
  - skill.get_skill
  - skill.create_skill
  - skill.update_skill
  - skill.delete_skill
confirmations:
  - step: delete
    tool: skill.delete_skill
    reason: Deleting a custom skill is destructive; requires confirmation_token.
---

# Skill: Manage custom skills

## Steps

1. **Browse**: `skill.list_skills(source=..., q=...)`
   - `source=module` → skills shipped under `modules/*/skills/*.md` (**readonly**).
   - `source=custom` → tenant custom skills (editable).
2. **Read**: `skill.get_skill(skill_id=...)` — returns markdown + metadata.
   - Module ids look like `wiki.manage_page`.
   - Custom ids look like `custom.my_sop`.
3. **Create** (custom only): `skill.create_skill(skill_key, title, summary, when_to_use, content, tools, confirmations, boundaries)`.
4. **Update** (custom only): `skill.update_skill` with `skill_id` / `record_id` / `skill_key`.
5. **Delete** (custom only, high risk):
   - Call `skill.delete_skill` once → expect `needs_confirmation`.
   - After human approval, call again with the same args + `confirmation_token`.

## 禁忌 / 边界

- **Never** update or delete `source=module` / `readonly=true` skills — they live in the repo.
- Do not invent SQL or bypass MCP.
- Custom `skill_key` must be lowercase `[a-z][a-z0-9_]*`.
- Skill content should reference only exported tools (or depends), not private APIs.
