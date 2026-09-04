import dayjs from 'dayjs'

export { dayjs }

export const PAYMENTS = [
  { value: 'cash', label: '现金' },
  { value: 'wechat', label: '微信' },
  { value: 'alipay', label: '支付宝' },
  { value: 'card', label: '刷卡' },
  { value: 'other', label: '其他' }
]

export const paymentLabel = (v) => PAYMENTS.find((p) => p.value === v)?.label || v
export const typeLabel = (v) => (v === 'income' ? '收入' : '支出')
export const today = () => dayjs().format('YYYY-MM-DD')
export const monthStart = () => dayjs().format('YYYY-MM') + '-01'
export const monthEnd = () => dayjs().endOf('month').format('YYYY-MM-DD')
