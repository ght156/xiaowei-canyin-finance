<template>
  <div class="page reports">
    <van-nav-bar :title="shopStore.currentName + ' · 经营分析'" @click-title="showShopPicker = true" />

    <van-tabs v-model:active="mode" @change="loadAll" shrink>
      <van-tab title="按日" name="day" />
      <van-tab title="按月" name="month" />
      <van-tab title="自定义区间" name="range" />
    </van-tabs>

    <!-- 日期选择行 -->
    <van-cell-group inset class="picker-row">
      <van-field
        v-if="mode === 'day'"
        label="日期"
        readonly
        is-link
        :model-value="day"
        @click="openDayPicker = true"
      />
      <van-field
        v-if="mode === 'month'"
        label="月份"
        readonly
        is-link
        :model-value="month"
        @click="openMonthPicker = true"
      />
      <template v-if="mode === 'range'">
        <van-field label="开始" readonly is-link :model-value="start" @click="openStartPicker = true" />
        <van-field label="结束" readonly is-link :model-value="end" @click="openEndPicker = true" />
      </template>
    </van-cell-group>

    <!-- 汇总卡片 -->
    <div class="summary-card" v-if="summary">
      <div class="summary-main">
        <div>
          <div class="s-label">收入</div>
          <div class="s-value amount-income">{{ formatMoney(summary.income) }}</div>
        </div>
        <div>
          <div class="s-label">支出</div>
          <div class="s-value amount-expense">{{ formatMoney(summary.expense) }}</div>
        </div>
        <div>
          <div class="s-label">利润</div>
          <div class="s-value">{{ formatMoney(summary.profit) }}</div>
        </div>
      </div>
      <div class="summary-rate">利润率：{{ summary.profit_rate ?? '—' }}</div>
      <div class="summary-metrics" v-if="mode !== 'day' && summary.business_days > 0">
        本期营业 {{ summary.business_days }} 天
        · 日均收入 {{ formatMoney(summary.avg_daily_income ?? '0.00') }}
        · 日均利润 {{ formatMoney(summary.avg_daily_profit ?? '0.00') }}
      </div>
    </div>

    <!-- 分店铺（全部店铺时显示） -->
    <van-cell-group v-if="summary && summary.by_shop.length > 1" inset title="分店铺利润" class="block">
      <van-cell
        v-for="s in summary.by_shop"
        :key="s.shop_id"
        :title="s.shop_name"
        :value="'利润 ' + formatMoney(s.profit)"
        :label="`收入 ${formatMoney(s.income)} · 支出 ${formatMoney(s.expense)}`"
      />
    </van-cell-group>

    <!-- 趋势图 -->
    <div class="chart-card block" v-if="trend.length">
      <div class="chart-title">收入 / 支出趋势</div>
      <div ref="trendChart" class="chart"></div>
    </div>

    <!-- 支出构成：文字为主，饼图为辅 -->
    <div class="chart-card block" v-if="expenseCats.length">
      <div class="chart-title">支出构成</div>
      <div class="expense-list">
        <div class="expense-row" v-for="c in expenseCats" :key="c.category_id">
          <span class="e-name">{{ c.category_name }}</span>
          <span class="e-amount">{{ formatMoney(c.amount) }}</span>
          <span class="e-pct">{{ c.percentage ?? '—' }}</span>
        </div>
      </div>
      <div ref="pieChart" class="chart"></div>
    </div>

    <van-empty v-if="loaded && !summary" description="暂无数据" />

    <!-- 各种日期选择器 -->
    <van-popup v-model:show="showShopPicker" round position="bottom">
      <van-picker :columns="shopColumns" title="选择店铺" @confirm="onShopConfirm" @cancel="showShopPicker = false" />
    </van-popup>
    <van-popup v-model:show="openDayPicker" round position="bottom">
      <van-date-picker v-model="dayParts" :min-date="minDate" :max-date="maxDate" title="选择日期"
        @confirm="(v) => { day = v.selectedValues.join('-'); openDayPicker = false; loadAll() }"
        @cancel="openDayPicker = false" />
    </van-popup>
    <van-popup v-model:show="openMonthPicker" round position="bottom">
      <van-date-picker v-model="monthParts" :columns-type="['year', 'month']" :min-date="minDate" :max-date="maxDate"
        title="选择月份"
        @confirm="(v) => { month = v.selectedValues.join('-'); openMonthPicker = false; loadAll() }"
        @cancel="openMonthPicker = false" />
    </van-popup>
    <van-popup v-model:show="openStartPicker" round position="bottom">
      <van-date-picker v-model="startParts" :min-date="minDate" :max-date="maxDate" title="开始日期"
        @confirm="(v) => { start = v.selectedValues.join('-'); openStartPicker = false; loadAll() }"
        @cancel="openStartPicker = false" />
    </van-popup>
    <van-popup v-model:show="openEndPicker" round position="bottom">
      <van-date-picker v-model="endParts" :min-date="minDate" :max-date="maxDate" title="结束日期"
        @confirm="(v) => { end = v.selectedValues.join('-'); openEndPicker = false; loadAll() }"
        @cancel="openEndPicker = false" />
    </van-popup>
  </div>
</template>

<script setup>
import { computed, nextTick, onActivated, onUnmounted, ref } from 'vue'
import * as echarts from 'echarts'
import api from '../api'
import { dayjs, formatMoney } from '../utils/format'
import { useShopStore } from '../stores/shops'

const shopStore = useShopStore()

const mode = ref('month')
const summary = ref(null)
const trend = ref([])
const expenseCats = ref([])
const loaded = ref(false)

const minDate = new Date(2020, 0, 1)
const maxDate = new Date(dayjs().year() + 1, 11, 31)

const day = ref(dayjs().format('YYYY-MM-DD'))
const month = ref(dayjs().format('YYYY-MM'))
const start = ref(dayjs().startOf('month').format('YYYY-MM-DD'))
const end = ref(dayjs().format('YYYY-MM-DD'))

const dayParts = ref(day.value.split('-'))
const monthParts = ref(month.value.split('-'))
const startParts = ref(start.value.split('-'))
const endParts = ref(end.value.split('-'))

const openDayPicker = ref(false)
const openMonthPicker = ref(false)
const openStartPicker = ref(false)
const openEndPicker = ref(false)
const showShopPicker = ref(false)

const shopColumns = computed(() => [
  { text: '全部店铺', value: 0 },
  ...shopStore.list.map((s) => ({ text: s.name, value: s.id }))
])

function onShopConfirm({ selectedValue }) {
  shopStore.setCurrent(selectedValue)
  showShopPicker.value = false
  loadAll()
}

function rangeParams() {
  const p = {}
  if (shopStore.currentId) p.shop_id = shopStore.currentId
  return p
}

async function loadAll() {
  loaded.value = false
  const p = rangeParams()
  try {
    if (mode.value === 'day') {
      const { data } = await api.get('/reports/daily', { params: { ...p, date: day.value } })
      summary.value = data
      const t = await api.get('/reports/trend', {
        params: { ...p, start: day.value, end: day.value }
      })
      trend.value = t.data
    } else if (mode.value === 'month') {
      const [y, m] = month.value.split('-').map(Number)
      const s = `${month.value}-01`
      const e = dayjs(new Date(y, m, 0)).format('YYYY-MM-DD')
      const { data } = await api.get('/reports/monthly', { params: { ...p, month: month.value } })
      summary.value = data
      const t = await api.get('/reports/trend', { params: { ...p, start: s, end: e } })
      trend.value = t.data
    } else {
      const { data } = await api.get('/reports/range', {
        params: { ...p, start: start.value, end: end.value }
      })
      summary.value = data
      const t = await api.get('/reports/trend', {
        params: { ...p, start: start.value, end: end.value }
      })
      trend.value = t.data
    }
    const ec = await api.get('/reports/expense-categories', {
      params:
        mode.value === 'day'
          ? { ...p, start: day.value, end: day.value }
          : mode.value === 'month'
            ? { ...p, start: `${month.value}-01`, end: monthEndOf() }
            : { ...p, start: start.value, end: end.value }
    })
    expenseCats.value = ec.data
    await nextTick()
    renderTrend()
    renderPie()
  } finally {
    loaded.value = true
  }
}

function monthEndOf() {
  const [y, m] = month.value.split('-').map(Number)
  return dayjs(new Date(y, m, 0)).format('YYYY-MM-DD')
}

const trendChart = ref(null)
const pieChart = ref(null)

// 图表实例复用：同一 DOM 不重复 init，切换日期/店铺只 setOption
function getChart(dom) {
  if (!dom) return null
  return echarts.getInstanceByDom(dom) || echarts.init(dom)
}

function renderTrend() {
  const chart = getChart(trendChart.value)
  if (!chart || !trend.value.length) return
  chart.setOption({
    grid: { left: 40, right: 12, top: 30, bottom: 24 },
    tooltip: { trigger: 'axis' },
    legend: { data: ['收入', '支出'], top: 0 },
    xAxis: { type: 'category', data: trend.value.map((t) => t.date.slice(5)) },
    yAxis: { type: 'value' },
    series: [
      { name: '收入', type: 'bar', data: trend.value.map((t) => Number(t.income)), itemStyle: { color: '#07c160' } },
      { name: '支出', type: 'bar', data: trend.value.map((t) => Number(t.expense)), itemStyle: { color: '#ee0a24' } }
    ]
  }, { notMerge: true })
}

function renderPie() {
  const chart = getChart(pieChart.value)
  if (!chart || !expenseCats.value.length) return
  chart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c}元（{d}%）' },
    legend: { orient: 'vertical', right: 0, top: 'middle', type: 'scroll' },
    series: [
      {
        type: 'pie',
        radius: ['35%', '65%'],
        center: ['35%', '50%'],
        data: expenseCats.value.map((c) => ({ name: c.category_name, value: Number(c.amount) })),
        label: { show: false }
      }
    ]
  }, { notMerge: true })
}

function handleResize() {
  trendChart.value && echarts.getInstanceByDom(trendChart.value)?.resize()
  pieChart.value && echarts.getInstanceByDom(pieChart.value)?.resize()
}

window.addEventListener('resize', handleResize)
onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart.value && echarts.getInstanceByDom(trendChart.value)?.dispose()
  pieChart.value && echarts.getInstanceByDom(pieChart.value)?.dispose()
})

onActivated(async () => {
  await shopStore.load()
  loadAll()
})
</script>

<style scoped>
.picker-row {
  margin-top: 10px;
}
.block {
  margin-top: 12px;
}
.summary-card {
  margin: 12px;
  border-radius: 12px;
  background: #fff;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}
.summary-main {
  display: flex;
  text-align: center;
}
.summary-main > div {
  flex: 1;
}
.s-label {
  color: #999;
  font-size: 13px;
}
.s-value {
  font-size: 21px;
  font-weight: 700;
  margin-top: 4px;
}
.summary-rate {
  text-align: center;
  color: #666;
  margin-top: 12px;
  font-size: 14px;
}
.summary-metrics {
  text-align: center;
  color: #1989fa;
  background: #e8f7ff;
  border-radius: 8px;
  margin-top: 10px;
  padding: 8px;
  font-size: 13px;
}
.chart-card {
  margin: 12px;
  border-radius: 12px;
  background: #fff;
  padding: 12px;
}
.chart-title {
  font-weight: 600;
  margin-bottom: 8px;
}
.expense-list {
  margin-bottom: 8px;
}
.expense-row {
  display: flex;
  align-items: center;
  padding: 8px 4px;
  border-bottom: 1px solid #f5f5f5;
  font-size: 14px;
}
.expense-row:last-child {
  border-bottom: none;
}
.e-name {
  flex: 1;
  font-weight: 500;
}
.e-amount {
  color: #333;
  font-weight: 600;
  margin-right: 12px;
}
.e-pct {
  color: #999;
  width: 56px;
  text-align: right;
}
.chart {
  width: 100%;
  height: 240px;
}
</style>
