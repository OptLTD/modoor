import type { RouteRecordRaw } from 'vue-router'
import VehiclesView from './VehiclesView.vue'

export const fleetRoute: RouteRecordRaw = {
  path: '/web/fleet',
  component: VehiclesView,
  meta: { moduleId: 'fleet' },
}
