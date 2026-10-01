// frontend/src/api/index.js
import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,   // 本地模型推理慢，给 2 分钟
})

// 请求拦截：自动带 token
api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// 响应拦截：401 自动跳登录
api.interceptors.response.use(
  (r) => r,
  (err) => {
    const status = err.response?.status
    if (status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      ElMessage.error('登录已过期，请重新登录')
      // 避免循环跳转
      if (location.pathname !== '/login') {
        location.href = '/login'
      }
    } else if (status === 404) {
      ElMessage.error(err.response?.data?.detail || '资源不存在')
    } else if (status >= 500) {
      ElMessage.error(err.response?.data?.detail || '服务器错误')
    }
    return Promise.reject(err)
  }
)

export default api