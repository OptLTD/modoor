/** 轻量对话框：浏览器原生；后续可换自定义 UI */

export async function appAlert(message: string, _title = '提示'): Promise<void> {
  window.alert(message)
}

export async function appConfirm(
  message: string,
  _title = '确认',
  _opts?: { confirmText?: string; cancelText?: string },
): Promise<boolean> {
  return window.confirm(message)
}

export function appToast(message: string): void {
  // 暂无 toast 组件：控制台 + 短时 status
  console.info('[toast]', message)
}
