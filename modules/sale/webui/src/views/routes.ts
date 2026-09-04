import type { RouteRecordRaw } from 'vue-router'
import ModuleShell from './ModuleShell.vue'
import TableWorkspace from './TableWorkspace.vue'

/** sale app：订单列表（模型固定 sale.order）。 */
export const saleRoute: RouteRecordRaw = {
  path: '/web/sale',
  component: ModuleShell,
  meta: { module: 'sale' },
  children: [
    {
      path: '',
      name: 'sale.orders',
      component: TableWorkspace,
      props: { model: 'sale.order' },
    },
  ],
}
