import { useInputDialogStore } from '../stores/inputDialog'

/**
 * Promise 风格的输入对话框。
 * 返回 { value } 或 null（取消）。
 */
export function inputDialog(opts) {
  return useInputDialogStore().open(opts)
}
