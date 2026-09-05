import type { RouteRecordRaw } from 'vue-router'
import ModuleShell from './ModuleShell.vue'
import CatalogView from './CatalogView.vue'
import DetailView from './DetailView.vue'
import EditView from './EditView.vue'

/** skill：壳挂 /web/skill，子路由由本模块切换。 */
export const skillRoute: RouteRecordRaw = {
  path: '/web/skill',
  component: ModuleShell,
  meta: { module: 'skill' },
  children: [
    { path: '', name: 'skill.catalog', component: CatalogView },
    { path: 'new', name: 'skill.new', component: EditView },
    { path: ':id/edit', name: 'skill.edit', component: EditView },
    { path: ':id', name: 'skill.detail', component: DetailView },
  ],
}
