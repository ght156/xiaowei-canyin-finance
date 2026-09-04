<template>
  <div class="page tx">
    <van-nav-bar title="流水" />

    <van-dropdown-menu>
      <van-dropdown-item v-model="filters.shop_id" :options="shopOptions" @change="reload" />
      <van-dropdown-item v-model="filters.type" :options="typeOptions" @change="onTypeChange" />
      <van-dropdown-item v-model="filters.category_id" :options="categoryOptions" @change="reload" />
      <van-dropdown-item v-model="filters.range" :options="rangeOptions" @change="onRangeChange" />
    </van-dropdown-menu>

    <!-- 自定义日期区间 -->
    <van-calendar
      v-model:show="showRangePicker"
      type="range"
      :min-date="new Date(2020, 0, 1)"
      :max-date="new Date(dayjs().year() + 1, 11, 31)"
      @confirm="onCustomRange"
      :allow-same-day="true"
    />

    <van-list
      v-model:loading="loading"
      :finished="finished"
      finished-text="没有更多了"
      @load="loadPage"
      class="tx-list"
    >
      <template v-for="group in groups" :key="group.date">
        <div class="date-head">
          <span>{{ group.title }}</span>
          <span class="date-sum">
            收入 <b class="amount-income">{{ formatMoney(group.incomeCents) }}</b>
            · 支出 <b class="amount-expense">{{ formatMoney(group.expenseCents) }}</b>
          </span>
        </div>
        <van-cell
          v-for="tx in group.items"
          :key="tx.id"
          clickable
          @click="openDetail(tx)"
        >
          <template #title>
            <span class="tx-cat">{{ tx.category_name }}</span>
            <span class="tx-remark">{{ tx.remark || '' }}</span>
          </template>
          <template #value>
            <span :class="tx.type === 'income' ? 'amount-income' : 'amount-expense'">
              {{ tx.type === 'income' ? '+' : '-' }}{{ formatMoney(tx.amount) }}
            </span>
          </template>
          <template #label>
            {{ tx.shop_name }} · {{ paymentLabel(tx.payment_method) }}
            <van-tag v-if="tx.deleted_at" type="danger" size="mini">已删除</van-tag>
          </template>
        </van-cell>
      </template>
    </van-list>

    <!-- 详情 / 编辑 -->
    <van-popup v-model:show="showDetail" round position="bottom" :style="{ minHeight: '40%' }">
      <div v-if="current" class="detail">
        <van-nav-bar :title="typeLabel(current.type) + '详情'" />
        <van-cell-group inset>
          <van-cell title="金额" :value="formatMoney(current.amount)" />
          <van-cell title="分类" :value="current.category_name" />
          <van-cell title="店铺" :value="current.shop_name" />
          <van-cell title="支付方式" :value="paymentLabel(current.payment_method)" />
          <van-cell title="日期" :value="current.biz_date" />
          <van-cell title="备注" :value="current.remark || '—'" />
          <van-cell title="创建人" :value="current.created_by_name" />
          <van-cell title="记录时间" :value="fmtTime(current.created_at)" />
        </van-cell-group>

        <template v-if="auth.isAdmin && !current.deleted_at">
          <div class="detail-btns">
            <van-button type="primary" block round @click="startEdit">编 辑</van-button>
            <van-button type="danger" block round plain @click="onDelete">删 除</van-button>
          </div>
        </template>
      </div>
    </van-popup>

    <!-- 编辑表单 -->
    <van-popup v-model:show="showEdit" round position="bottom" :style="{ minHeight: '50%' }">
      <div v-if="editForm" class="detail">
        <van-nav-bar title="编辑流水" />
        <van-cell-group inset style="margin-top:12px">
          <van-field v-model="editForm.amount" type="text" inputmode="decimal" label="金额（元）" />
          <van-field label="分类" readonly is-link :model-value="editCategoryName" @click="showEditCat = true" />
          <van-field label="支付方式" readonly is-link :model-value="paymentLabel(editForm.payment_method)" @click="showEditPay = true" />
          <van-field label="日期" readonly is-link :model-value="editForm.biz_date" @click="showEditDate = true" />
          <van-field v-model="editForm.remark" label="备注" maxlength="200" />
        </van-cell-group>
        <div class="detail-btns">
          <van-button type="primary" block round :loading="saving" @click="saveEdit">保 存</van-button>
        </div>
      </div>
    </van-popup>

    <van-popup v-model:show="showEditCat" round position="bottom">
      <van-picker
        :columns="editCategoryOptions"
        title="选择分类（仅启用中的分类）"
        @confirm="(v) => { editForm.category_id = v.selectedValues[0]; showEditCat = false }"
        @cancel="showEditCat = false"
      />
    </van-popup>
    <van-popup v-model:show="showEditPay" round position="bottom">
      <van-picker
        :columns="PAYMENTS.map(p => ({ text: p.label, value: p.value }))"
        title="支付方式"
        @confirm="(v) => { editForm.payment_method = v.selectedValues[0]; showEditPay = false }"
        @cancel="showEditPay = false"
      />
    </van-popup>
    <van-popup v-model:show="showEditDate" round position="bottom">
      <van-date-picker
        v-model="editDateParts"
        :min-date="new Date(2020, 0, 1)"
        :max-date="new Date(dayjs().year() + 1, 11, 31)"
        title="选择日期"
        @confirm="onEditDateConfirm"
        @cancel="showEditDate = false"
      />
    </van-popup>
  </div>
</template>

<script setup>
import { computed, onActivated, reactive, ref } from 'vue'
import { showConfirmDialog, showDialog, showToast } from 'vant'
import api from '../api'
import { useAuthStore } from '../stores/auth'
import { useShopStore } from '../stores/shops'
import {
  PAYMENTS, dayjs, formatDateCN, formatMoney, paymentLabel, typeLabel, yuanToCents
} from '../utils/format'

const auth = useAuthStore()
const shopStore = useShopStore()

const items = ref([])
const loading = ref(false)
const finished = ref(false)
const page = ref(1)
const total = ref(0)
const saving = ref(false)

const filters = reactive({
  shop_id: 0,
  type: 'all',
  category_id: 0,
  range: 'month',
  start: '',
  end: ''
})

const shopOptions = computed(() => [
  { text: '全部店铺', value: 0 },
  ...shopStore.list.map((s) => ({ text: s.name, value: s.id }))
])
const typeOptions = [
  { text: '全部类型', value: 'all' },
  { text: '收入', value: 'income' },
  { text: '支出', value: 'expense' }
]
const categoryOptions = computed(() => {
  const opts = [{ text: '全部分类', value: 0 }]
  cats.value
    .filter((c) => filters.type === 'all' || c.type === filters.type)
    .forEach((c) => opts.push({ text: c.name, value: c.id }))
  return opts
})
const cats = ref([])

const rangeOptions = [
  { text: '今天', value: 'today' },
  { text: '近7天', value: 'week' },
  { text: '本月', value: 'month' },
  { text: '上月', value: 'lastMonth' },
  { text: '自定义', value: 'custom' },
  { text: '全部', value: 'all' }
]

function applyRange() {
  const r = filters.range
  if (r === 'today') {
    filters.start = dayjs().format('YYYY-MM-DD')
    filters.end = filters.start
  } else if (r === 'week') {
    filters.start = dayjs().subtract(6, 'day').format('YYYY-MM-DD')
    filters.end = dayjs().format('YYYY-MM-DD')
  } else if (r === 'month') {
    filters.start = dayjs().startOf('month').format('YYYY-MM-DD')
    filters.end = dayjs().format('YYYY-MM-DD')
  } else if (r === 'lastMonth') {
    filters.start = dayjs().subtract(1, 'month').startOf('month').format('YYYY-MM-DD')
    filters.end = dayjs().subtract(1, 'month').endOf('month').format('YYYY-MM-DD')
  } else if (r === 'all') {
    filters.start = ''
    filters.end = ''
  }
}

const showRangePicker = ref(false)
function onRangeChange(v) {
  if (v === 'custom') {
    showRangePicker.value = true
    return
  }
  applyRange()
  reload()
}

/** 类型切换后必须清空旧分类筛选，避免"收入 × 支出分类"这种空结果组合 */
function onTypeChange() {
  if (filters.category_id) {
    filters.category_id = 0
  }
  reload()
}

function onCustomRange([s, e]) {
  filters.start = dayjs(s).format('YYYY-MM-DD')
  filters.end = dayjs(e).format('YYYY-MM-DD')
  showRangePicker.value = false
  reload()
}

/** 按日分组；合计用整数分相加，不走浮点 */
const groups = computed(() => {
  const map = new Map()
  for (const tx of items.value) {
    const d = tx.biz_date
    if (!map.has(d)) map.set(d, { date: d, title: formatDateCN(d), items: [], incomeCents: 0, expenseCents: 0 })
    const g = map.get(d)
    g.items.push(tx)
    if (tx.type === 'income') g.incomeCents += yuanToCents(tx.amount)
    else g.expenseCents += yuanToCents(tx.amount)
  }
  return [...map.values()]
})

async function loadPage() {
  if (page.value === 1) items.value = []
  const params = {
    page: page.value,
    page_size: 20
  }
  if (filters.shop_id) params.shop_id = filters.shop_id
  if (filters.type !== 'all') params.type = filters.type
  if (filters.category_id) params.category_id = filters.category_id
  if (filters.start) params.start_date = filters.start
  if (filters.end) params.end_date = filters.end

  const { data } = await api.get('/transactions', { params })
  items.value.push(...data.items)
  total.value = data.total
  page.value += 1
  loading.value = false
  finished.value = items.value.length >= data.total
}

function reload() {
  page.value = 1
  finished.value = false
  loading.value = true
  items.value = []
  loadPage()
}

// ---- 详情 ----
const showDetail = ref(false)
const current = ref(null)
function openDetail(tx) {
  current.value = tx
  showDetail.value = true
}

// ---- 编辑 ----
const showEdit = ref(false)
const showEditCat = ref(false)
const showEditPay = ref(false)
const showEditDate = ref(false)
const editForm = ref(null)
const editDateParts = ref([])

// 只能换成启用中的分类；原分类若已停用则保留在列表里作为当前值
const editCategoryOptions = computed(() => {
  if (!current.value) return []
  const sameType = cats.value.filter((c) => c.type === current.value.type)
  const options = sameType.filter((c) => c.status === 'active')
  const cur = sameType.find((c) => c.id === current.value.category_id)
  if (cur && cur.status !== 'active') options.unshift(cur)
  return options.map((c) => ({ text: c.status === 'active' ? c.name : `${c.name}（已停用）`, value: c.id }))
})
const editCategoryName = computed(
  () => cats.value.find((c) => c.id === editForm.value?.category_id)?.name || ''
)

function startEdit() {
  editForm.value = {
    id: current.value.id,
    category_id: current.value.category_id,
    amount: current.value.amount,
    payment_method: current.value.payment_method,
    biz_date: current.value.biz_date,
    remark: current.value.remark || ''
  }
  showEditDate.value = false
  showEdit.value = true
}

function onEditDateConfirm({ selectedValues }) {
  editForm.value.biz_date = selectedValues.join('-')
  showEditDate.value = false
}

async function saveEdit() {
  if (!editForm.value) return
  saving.value = true
  try {
    const body = {
      category_id: editForm.value.category_id,
      amount: String(editForm.value.amount),
      payment_method: editForm.value.payment_method,
      biz_date: editForm.value.biz_date,
      remark: editForm.value.remark
    }
    const { data } = await api.put(`/transactions/${editForm.value.id}`, body)
    Object.assign(current.value, data)
    const idx = items.value.findIndex((t) => t.id === data.id)
    if (idx >= 0) items.value[idx] = data
    showEdit.value = false
    showDetail.value = false
    showDialog({ message: '修改成功，已记录审计日志' })
  } catch (err) {
    // 流水已在别处被删除：从本地列表移除并刷新，避免一直点一条"幽灵流水"
    if (err?.response?.status === 404) {
      showToast('这笔流水已被删除，列表已刷新')
      items.value = items.value.filter((t) => t.id !== editForm.value.id)
      showEdit.value = false
      showDetail.value = false
      reload()
    }
  } finally {
    saving.value = false
  }
}

async function onDelete() {
  showConfirmDialog({
    title: '确认删除',
    message: `确定删除这笔${typeLabel(current.value.type)}（${formatMoney(current.value.amount)}）吗？\n删除后可在回收站恢复。`
  }).then(async () => {
    await api.delete(`/transactions/${current.value.id}`)
    showDetail.value = false
    showToast('已移入回收站')
    reload()
  }).catch(() => {})
}

function fmtTime(s) {
  return s ? dayjs(s).format('YYYY-MM-DD HH:mm') : ''
}

onActivated(async () => {
  await shopStore.load()
  if (!cats.value.length) {
    cats.value = await api.get('/categories?include_disabled=1').then((r) => r.data)
  }
  // 每次回到流水页都刷新：别处删除/恢复过流水后，本地列表不能停留在旧数据
  reload()
})
</script>

<style scoped>
.tx-list {
  margin-top: 8px;
}
.date-head {
  padding: 8px 16px 4px;
  color: #999;
  font-size: 13px;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}
.date-sum {
  color: #666;
  white-space: nowrap;
}
.date-sum b {
  font-weight: 600;
}
.tx-cat {
  font-weight: 600;
  margin-right: 8px;
}
.tx-remark {
  color: #999;
  font-size: 13px;
}
.detail {
  padding-bottom: 24px;
}
.detail-btns {
  display: flex;
  gap: 12px;
  margin: 16px;
}
.detail-btns .van-button {
  flex: 1;
}
</style>
