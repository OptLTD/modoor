import type { RouteRecordRaw } from 'vue-router'
import ShipmentsView from './ShipmentsView.vue'

export const transportRoute: RouteRecordRaw = {
  path: '/web/transport',
  component: ShipmentsView,
  meta: { moduleId: 'transport' },
}
