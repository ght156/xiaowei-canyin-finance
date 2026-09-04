<template>
  <div class="page home">
    <van-nav-bar :title="shopStore.currentName" @click-title="showShopPicker = true">
      <template #right>
        <van-icon name="replay" size="20" @click="loadOverview" />
      </template>
    </van-nav-bar>

    <div class="stat-card">
      <div class="stat-row">
        <div class="stat-item">
          <div class="stat-label">今日收入</div>
          <div class="stat-value amount-income">¥{{ ov.today?.income ?? '0.00' }}</div>
        </div>
        <div class="stat-item">
          <div class="stat-label">今日支出</div>
          <div class="stat-value amount-expense">¥{{ ov.today?.expense ?? '0.00' }}</div>
        </div>
        <div class="stat-item">
          <div class="stat-label">今日利润</div>
          <div class="stat-value">{{ ov.today?.profit ?? '0.00' }}</div>
        </div>
      </div>
    </div>

    <div class="entry-btns">
      <van-button type="success" size="large" round icon="plus" to="/entry/income" class="entry-btn">
        记收入
      </van-button>
      <van-button type="danger" size="large" round icon="minus" to="/entry/expense" class="entry-btn">
        记支出
      </van-button>
    </div>

    <van-cell-group inset title="本月概况" class="month-card">
      <van-cell title="本月收入" :value="'¥' + (ov.month?.income ?? '0.00')" />
      <van-cell title="本月支出" :value="'¥' + (ov.month?.expense ?? '0.00')" />
      <van-cell title="本月利润" :value="ov.month?.profit ?? '0.00'" />
      <van-cell title="利润率" :value="ov.month?.profit_rate ?? '—'" />
    </van-cell-group>

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
import { useShopStore } from '../stores/shops'

const shopStore = useShopStore()
const ov = ref({})
const showShopPicker = ref(false)

const shopColumns = computed(() => [
  { text: '全部店铺', value: 0 },
  ...shopStore.list.map((s) => ({ text: s.name, value: s.id }))
])

async function loadOverview() {
  const { data } = await api.get('/reports/overview', {
    params: shopStore.currentId ? { shop_id: shopStore.currentId } : {}
  })
  ov.value = data
}

function onShopConfirm({ selectedValue }) {
  shopStore.setCurrent(selectedValue)
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
  padding: 18px 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
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
  font-size: 13px;
  margin-bottom: 6px;
}
.stat-value {
  font-size: 20px;
  font-weight: 700;
}
.entry-btns {
  display: flex;
  gap: 12px;
  margin: 4px 12px 12px;
}
.entry-btn {
  flex: 1;
  height: 56px;
  font-size: 17px;
  font-weight: 600;
}
.month-card {
  margin-top: 4px;
}
</style>
