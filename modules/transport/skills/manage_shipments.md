# Skill: Manage transport shipments

## when_to_use
When the user wants to list or create shipments in Transport / TMS.

## steps
1. Call `transport.list_shipments` to see current shipments.
2. Call `transport.add_shipment` with `{ "ref_no", "origin", "destination" }`.

## tools
- transport.list_shipments
- transport.add_shipment

## confirmations
None (low risk writes).

## 禁忌 / 边界
- Do not invent shipments that were not returned by tools.
- Tables use prefix `tms_`.
