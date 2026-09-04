import { defineStore } from 'pinia'

/**
 * 全局输入对话框状态，由 App.vue 中的 <van-dialog> 渲染。
 * open() 返回 Promise<{ value } | null>（取消时 resolve null）。
 */
export const useInputDialogStore = defineStore('inputDialog', {
  state: () => ({
    show: false,
    title: '',
    placeholder: '',
    message: '',
    initialValue: '',
    value: '',
    _resolve: null
  }),
  actions: {
    open(opts = {}) {
      this.title = opts.title || ''
      this.placeholder = opts.placeholder || ''
      this.message = opts.message || ''
      this.initialValue = opts.initialValue || ''
      this.value = opts.initialValue || ''
      this.show = true
      return new Promise((resolve) => {
        this._resolve = resolve
      })
    },
    confirm() {
      this.show = false
      this._resolve?.({ value: this.value })
      this._resolve = null
    },
    cancel() {
      this.show = false
      this._resolve?.(null)
      this._resolve = null
    }
  }
})
