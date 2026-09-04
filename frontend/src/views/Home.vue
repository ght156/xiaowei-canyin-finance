<template>
  <div class="page home">
    <van-nav-bar :title="shopStore.currentName" @click-title="showShopPicker = true">
      <template #right>
        <van-icon name="replay" size="20" @click="loadOverview" />
      </template>
    </van-nav-bar>

    <!-- 员工首页：只有营业额与笔数，不显示利润 -->
    <template v-if="auth.isEmployee">
      <div class="stat-card">
        <div class="stat-label">今日营业额</div>
        <div class="emp-income">{{ formatMoney(emp.income ?? '0.00') }}</div>
        <div class="emp-sub">
          今日已记 <b>{{ emp.count ?? 0 }}</b> 笔
          <template v-if="emp.expense"> · 今日支出 {{ formatMoney(emp.expense) }}</template>
        </div>
      </div>
    </template>

    <!-- 管理员/店主首页 -->
    <template v-else>
      <div class="stat-card">
        <div class="stat-row">
          <div class="stat-item">
            <div class="stat-label">今日收入</div>
            <div class="stat-value amount-income">{{ formatMoney(ov.today?.income ?? '0.00') }}</div>
          </div>
          <div class="stat-item">
            <div class="stat-label">今日支出</div>
            <div class="stat-value amount-expense">{{ formatMoney(ov.today?.expense ?? '0.00') }}</div>
          </div>
        </div>
        <div class="profit-line">
          <span class="stat-label">今日利润</span>
          <span class="profit-value">{{ formatMoney(ov.today?.profit ?? '0.00') }}</span>
        </div>
        <div class="compare-line" v-if="yesterdayLoaded">
          昨日收入 {{ formatMoney(ov.yesterday?.income ?? '0.00') }}
          <span :class="diffClass">{{ diffText }}</span>
        </div>
      </div>

      <van-cell-group inset title="本月概况" class="month-card">
        <van-cell title="本月收入" :value="formatMoney(ov.month?.income ?? '0.00')" />
        <van-cell title="本月支出" :value="formatMoney(ov.month?.expense ?? '0.00')" />
        <van-cell title="本月利润" :value="formatMoney(ov.month?.profit ?? '0.00')" />
        <van-cell title="利润率" :value="ov.month?.profit_rate ?? '—'" />
      </van-cell-group>
    </template>

    <div class="entry-btns">
      <van-button type="success" size="large" round icon="plus" to="/entry/income" class="entry-btn">
        记收入
      </van-button>
      <van-button type="danger" size="large" round icon="minus" to="/entry/expense" class="entry-btn">
        记支出
      </van-button>
    </div>

    <!-- 店铺切换 -->
    <van-popup v-model:show="showShopPicker" round position="bottom">
      <van-picker
        :columns="shopColumns"
        @confirm="onShopConfirm"
        @cancel="showShopPicker = false"
        title="选择店铺"
      />
    </van-popup>
  </div>
</template>

<script setup>
import { computed, onActivated, ref } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'
import { useShopStore } from '../stores/shops'
import { formatMoney, yuanToCents } from '../utils/format'

const auth = useAuthStore()
const shopStore = useShopStore()
const ov = ref({})
const emp = ref({})
const showShopPicker = ref(false)
const yesterdayLoaded = ref(false)

const shopColumns = computed(() => [
  ...(auth.isEmployee ? [] : [{ text: '全部店铺', value: 0 }]),
  ...shopStore.list.map((s) => ({ text: s.name, value: s.id }))
])

const diffCents = computed(
  () => yuanToCents(ov.value.today?.income ?? '0') - yuanToCents(ov.value.yesterday?.income ?? '0')
)
const diffText = computed(() => {
  const c = diffCents.value
  if (c > 0) return `比昨日 +${formatMoney(c)}`
  if (c < 0) return `比昨日 ${formatMoney(c)}`
  return '与昨日持平'
})
const diffClass = computed(() =>
  diffCents.value > 0 ? 'diff-up' : diffCents.value < 0 ? 'diff-down' : 'diff-flat'
)

async function loadOverview() {
  if (auth.isEmployee) {
    // 员工：仅当前店铺的今日营业额与笔数；后端不返回利润
    const params = shopStore.currentId ? { shop_id: shopStore.currentId } : {}
    const { data } = await api.get('/reports/employee-summary', { params })
    emp.value = data
    if (data.shop_id) shopStore.setCurrent(data.shop_id)
    return
  }
  const { data } = await api.get('/reports/overview', {
    params: shopStore.currentId ? { shop_id: shopStore.currentId } : {}
  })
  ov.value = data
  yesterdayLoaded.value = true
}

function onShopConfirm({ selectedValues }) {
  shopStore.setCurrent(selectedValues[0])
  showShopPicker.value = false
  loadOverview()
}

onActivated(async () => {
  await shopStore.load()
  loadOverview()
})
</script>

<style scoped>
.stat-card {
  margin: 12px;
  border-radius: 12px;
  background: #fff;
  padding: 20px 8px 14px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  text-align: center;
}
.emp-income {
  font-size: 40px;
  font-weight: 800;
  color: #07c160;
  margin: 8px 0;
}
.emp-sub {
  color: #666;
  font-size: 15px;
}
.emp-sub b {
  color: #1989fa;
}
.stat-row {
  display: flex;
  text-align: center;
}
.stat-item {
  flex: 1;
}
.stat-label {
  color: #999;
  font-size: 14px;
  margin-bottom: 6px;
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
}
.profit-line {
  text-align: center;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed #eee;
}
.profit-value {
  font-size: 30px;
  font-weight: 800;
  margin-left: 10px;
}
.compare-line {
  text-align: center;
  color: #999;
  font-size: 13px;
  margin-top: 8px;
}
.diff-up {
  color: #07c160;
  margin-left: 6px;
}
.diff-down {
  color: #ee0a24;
  margin-left: 6px;
}
.diff-flat {
  margin-left: 6px;
}
.entry-btns {
  display: flex;
  gap: 12px;
  margin: 4px 12px 12px;
}
.entry-btn {
  flex: 1;
  height: 60px;
  font-size: 19px;
  font-weight: 700;
}
.month-card {
  margin-top: 4px;
}
</style>
