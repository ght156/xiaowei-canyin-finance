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

/** 大额确认阈值（元）：超过需二次确认 */
export const LARGE_AMOUNT_YUAN = 5000

/**
 * "元"字符串 → 整数分。纯字符串解析，不走 JS 浮点运算。
 * "12.5" → 1250，"0.1" → 10
 */
export function yuanToCents(value) {
  const s = String(value ?? '0').trim()
  const neg = s.startsWith('-')
  const [int = '0', dec = ''] = (neg ? s.slice(1) : s).split('.')
  const dec2 = (dec + '00').slice(0, 2)
  const cents = Number(int || 0) * 100 + Number(dec2 || 0)
  return neg ? -cents : cents
}

/**
 * 统一金额格式化：接受整数分（number）或"元"字符串。
 * 返回 "¥1,280.00"，负数返回 "-¥120.00"。
 */
export function formatMoney(value) {
  const cents = typeof value === 'number' ? value : yuanToCents(value)
  const sign = cents < 0 ? '-' : ''
  const abs = Math.abs(Math.round(cents))
  const yuan = Math.floor(abs / 100)
  const fen = String(abs % 100).padStart(2, '0')
  const yuanStr = String(yuan).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return `${sign}¥${yuanStr}.${fen}`
}

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

/** "2026-09-04" → "9月4日 周五" */
export function formatDateCN(dateStr) {
  const d = dayjs(dateStr)
  if (!d.isValid()) return dateStr
  return `${d.month() + 1}月${d.date()}日 ${WEEKDAYS[d.day()]}`
}
