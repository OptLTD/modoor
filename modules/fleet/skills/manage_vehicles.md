# Skill: Manage fleet vehicles

## when_to_use
When the user wants to list or register vehicles in Fleet / VMS.

## steps
1. Call `fleet.list_vehicles` to see current vehicles.
2. Call `fleet.add_vehicle` with `{ "plate_no": "...", "model": "..." }` to register.

## tools
- fleet.list_vehicles
- fleet.add_vehicle

## confirmations
None (low risk writes).

## 禁忌 / 边界
- Do not invent vehicles that were not returned by tools.
- Tables use prefix `vms_`.
