---
id: base.manage_rbac
title: Manage apps, users, and roles
summary: Create apps/users/roles and assign roles under the current tenant.
when_to_use: |
  User wants to set up applications, accounts, or RBAC (roles / assignments).
tools:
  - base.create_app
  - base.list_apps
  - base.create_user
  - base.list_users
  - base.create_role
  - base.list_roles
  - base.assign_role
  - base.list_user_roles
  - base.revoke_role
  - base.delete_app
  - base.delete_user
  - base.delete_role
confirmations:
  - tool: base.delete_app
  - tool: base.delete_user
  - tool: base.delete_role
  - tool: base.revoke_role
---

# Skill: Manage base RBAC

## Concepts

- **App**: application under a tenant (`code` unique per tenant).
- **User**: account under a tenant (`username` unique per tenant).
- **Role**: permission bundle; optional `app_id` makes it app-scoped; omit `app_id` for tenant-wide.
- **Assignment**: user ids stored as JSON on `role.users`; ability codes as `role.nodes`.

## Typical flow

1. `base.create_app(code="crm", name="CRM")`
2. `base.create_user(username="alice", realname="Alice")`
3. `base.create_role(code="admin", name="Admin", app_id=<app.id>)` or without app_id
4. `base.assign_role(user_id=..., role_id=...)`
5. Verify with `base.list_user_roles(user_id=...)`

## 禁忌

- Do not invent SQL or bypass MCP.
- Deletes / revoke require `needs_confirmation` then resubmit with token.
- Cannot delete an app while roles still reference it — delete or reassign roles first.
