import axios from 'axios'
import { showToast } from 'vant'
import router from '../router'

const api = axios.create({ baseURL: '/api', timeout: 15000 })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    const status = err.response?.status
    if (status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (router.currentRoute.value.path !== '/login') router.replace('/login')
    }
    let detail = err.response?.data?.detail
    if (Array.isArray(detail)) detail = detail[0]?.msg || '输入有误'
    showToast(detail || '网络异常，请稍后重试')
    return Promise.reject(err)
  }
)

export default api
