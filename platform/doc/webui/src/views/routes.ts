import type { RouteRecordRaw } from 'vue-router'
import ModuleShell from './ModuleShell.vue'
import FolderView from './FolderView.vue'
import PreviewView from './PreviewView.vue'

/** doc：/web/doc 文件夹列表；/web/doc/:id 按类型预览 */
export const docRoute: RouteRecordRaw = {
  path: '/web/doc',
  component: ModuleShell,
  meta: { module: 'doc' },
  children: [
    { path: '', name: 'doc.folder', component: FolderView },
    { path: ':id', name: 'doc.preview', component: PreviewView },
  ],
}
