import axios from 'axios'
import { showToast } from 'vant'
import router from '../router'

const api = axios.create({ baseURL: '/api', timeout: 15000 })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

/** 统一把后端/网络错误转成用户能看懂的中文提示 */
function humanizeError(err) {
  const status = err.response?.status
  if (status === 401) return '登录已失效，请重新登录'
  if (status === 403) return err.response?.data?.detail || '没有权限执行此操作'
  if (status === 404) return err.response?.data?.detail || '要查看的内容不存在或已被删除'
  if (status === 422) {
    const detail = err.response?.data?.detail
    if (typeof detail === 'string') return detail
    return '输入的内容有误，请检查金额和日期后重试'
  }
  if (status >= 500) return '系统暂时无法保存，请稍后重试'
  if (!status) return '网络连接失败，请稍后重试'
  return err.response?.data?.detail || '操作失败，请稍后重试'
}

api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    const status = err.response?.status
    const msg = humanizeError(err)
    if (status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (router.currentRoute.value.path !== '/login') router.replace('/login')
    }
    showToast(msg)
    return Promise.reject(err)
  }
)

export default api
