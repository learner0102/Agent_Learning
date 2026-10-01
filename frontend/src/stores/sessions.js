// frontend/src/stores/sessions.js
import { defineStore } from 'pinia'
import api from '../api'

export const useSessionsStore = defineStore('sessions', {
  state: () => ({
    list: [],          // [{ id, title, created_at, updated_at }]
    currentId: null,   // 当前打开的会话 id
    loading: false,
  }),
  getters: {
    current: (s) => s.list.find((x) => x.id === s.currentId) || null,
  },
  actions: {
    async fetchList() {
      this.loading = true
      try {
        const { data } = await api.get('/sessions')
        this.list = data
      } finally {
        this.loading = false
      }
    },

    async create(title = '新会话') {
      const { data } = await api.post('/sessions', { title })
      this.list.unshift(data)
      this.currentId = data.id
      return data
    },

    async remove(id) {
      await api.delete(`/sessions/${id}`)
      this.list = this.list.filter((s) => s.id !== id)
      if (this.currentId === id) {
        this.currentId = this.list[0]?.id || null
      }
    },

    async rename(id, title) {
      await api.patch(`/sessions/${id}`, { title })
      const s = this.list.find((x) => x.id === id)
      if (s) s.title = title
    },

    // 本地更新（聊天后，后端返回的 session_id 可能是新建的）
    upsertLocal(session) {
      const idx = this.list.findIndex((x) => x.id === session.id)
      if (idx >= 0) {
        this.list[idx] = { ...this.list[idx], ...session }
      } else {
        this.list.unshift(session)
      }
    },

    // 把某个会话置顶（最近使用）
    bumpToTop(id) {
      const idx = this.list.findIndex((x) => x.id === id)
      if (idx > 0) {
        const [s] = this.list.splice(idx, 1)
        this.list.unshift(s)
      }
    },

    // 聊天后调用：更新会话标题 + 置顶 + 刷新时间
    async refreshOne(id) {
      // 后端没有单查接口，直接重新拉列表最简单
      await this.fetchList()
      this.bumpToTop(id)
    },
  },
})