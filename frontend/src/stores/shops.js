import { defineStore } from 'pinia'
import api from '../api'

export const useShopStore = defineStore('shops', {
  state: () => ({
    list: [],
    // 0 表示"全部店铺"；记账页强制要求具体店铺
    currentId: Number(localStorage.getItem('shopId') || 0)
  }),
  getters: {
    currentName: (s) => {
      if (!s.currentId) return '全部店铺'
      return s.list.find((x) => x.id === s.currentId)?.name || '全部店铺'
    }
  },
  actions: {
    async load() {
      const { data } = await api.get('/shops')
      this.list = data
      if (this.currentId && !data.some((s) => s.id === this.currentId)) this.currentId = 0
    },
    setCurrent(id) {
      this.currentId = id
      localStorage.setItem('shopId', String(id))
    }
  }
})
