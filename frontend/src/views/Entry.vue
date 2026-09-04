<template>
  <div class="page entry">
    <van-nav-bar
      :title="isIncome ? '记收入' : '记支出'"
      left-text="取消"
      left-arrow
      @click-left="router.back()"
    />

    <van-cell-group inset class="block">
      <van-field
        ref="amountField"
        v-model="form.amount"
        type="text"
        inputmode="decimal"
        label="金额（元）"
        placeholder="0.00"
        required
        class="amount-field"
      />
      <van-field label="店铺" required readonly :model-value="entryShopName" is-link @click="showShopPicker = true" />
    </van-cell-group>

    <van-cell-group inset title="分类" class="block">
      <van-grid :column-num="4" :border="false" clickable>
        <van-grid-item v-for="c in categories" :key="c.id" @click="form.category_id = c.id">
          <div class="cat-item" :class="{ active: form.category_id === c.id }">{{ c.name }}</div>
        </van-grid-item>
      </van-grid>
    </van-cell-group>

    <van-cell-group inset title="支付方式" class="block">
      <van-radio-group v-model="form.payment_method" direction="horizontal" class="pay-group">
        <van-radio v-for="p in PAYMENTS" :key="p.value" :name="p.value">{{ p.label }}</van-radio>
      </van-radio-group>
    </van-cell-group>

    <van-cell-group inset class="block">
      <van-field label="日期" readonly required :model-value="form.biz_date" is-link @click="showDatePicker = true" />
      <van-field
        v-model="form.remark"
        label="备注"
        type="textarea"
        rows="1"
        autosize
        maxlength="200"
        placeholder="选填，如：张三面条钱"
      />
    </van-cell-group>

    <div class="save-btn">
      <van-button type="primary" block size="large" round :loading="saving" @click="save">
        保 存
      </van-button>
    </div>

    <van-popup v-model:show="showShopPicker" round position="bottom">
      <van-picker :columns="shopColumns" title="选择店铺" @confirm="onShopConfirm" @cancel="showShopPicker = false" />
    </van-popup>

    <van-popup v-model:show="showDatePicker" round position="bottom">
      <van-date-picker
        v-model="dateParts"
        :min-date="minDate"
        :max-date="maxDate"
        title="选择日期"
        @confirm="onDateConfirm"
        @cancel="showDatePicker = false"
      />
    </van-popup>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import api from '../api'
import { PAYMENTS, dayjs, formatMoney, LARGE_AMOUNT_YUAN, today, yuanToCents } from '../utils/format'
import { useShopStore } from '../stores/shops'

const route = useRoute()
const router = useRouter()
const shopStore = useShopStore()

const isIncome = computed(() => route.params.type === 'income')
const txType = computed(() => (isIncome.value ? 'income' : 'expense'))

const amountField = ref()
const categories = ref([])
const saving = ref(false)
const showShopPicker = ref(false)
const showDatePicker = ref(false)

const form = reactive({
  amount: '',
  category_id: null,
  payment_method: localStorage.getItem('lastPayment') || 'cash',
  biz_date: dayjs().format('YYYY-MM-DD'),
  remark: '',
  shop_id: null
})

const dateParts = ref(dayjs().format('YYYY-MM-DD').split('-'))
const minDate = new Date(2020, 0, 1)
const maxDate = new Date(dayjs().year() + 1, 11, 31)

const shopColumns = computed(() => shopStore.list.map((s) => ({ text: s.name, value: s.id })))
const entryShopName = computed(
  () => shopStore.list.find((s) => s.id === form.shop_id)?.name || '请选择'
)

function onShopConfirm({ selectedValue }) {
  form.shop_id = selectedValue
  showShopPicker.value = false
}

function onDateConfirm({ selectedValues }) {
  form.biz_date = selectedValues.join('-')
  showDatePicker.value = false
}

async function loadCategories() {
  const { data } = await api.get('/categories', { params: { type: txType.value } })
  categories.value = data
  if (data.length && !data.some((c) => c.id === form.category_id)) {
    form.category_id = data[0].id
  }
}

async function save() {
  if (!form.amount || Number(form.amount) <= 0) return showToast('请输入正确的金额')
  if (!form.shop_id) return showToast('请选择店铺')
  if (!form.category_id) return showToast('请选择分类')

  // 大额二次确认（阈值见 LARGE_AMOUNT_YUAN），防多打一个 0
  if (yuanToCents(form.amount) >= LARGE_AMOUNT_YUAN * 100) {
    try {
      await showConfirmDialog({
        title: '大额确认',
        message: `本笔金额为 ${formatMoney(form.amount)}，金额较大，确认无误吗？`,
        confirmButtonText: '确认无误',
        cancelButtonText: '再改改'
      })
    } catch {
      return
    }
  }

  // 未来日期提醒：允许补记/预记，但要确认
  if (form.biz_date > today()) {
    try {
      await showConfirmDialog({
        title: '日期提醒',
        message: '当前选择的是未来日期，确认保存吗？',
        confirmButtonText: '确认保存',
        cancelButtonText: '再改改'
      })
    } catch {
      return
    }
  }

  saving.value = true
  let respData
  try {
    const { data } = await api.post('/transactions', {
      shop_id: form.shop_id,
      type: txType.value,
      category_id: form.category_id,
      amount: String(form.amount),
      payment_method: form.payment_method,
      biz_date: form.biz_date,
      remark: form.remark || null
    })
    respData = data
    localStorage.setItem('lastPayment', form.payment_method)
  } finally {
    saving.value = false
  }

  if (respData?.duplicate_warning) {
    showToast('检测到刚记过一笔相同流水，请注意是否重复')
  }

  // 记账成功后支持连续记账：保留店铺/支付方式/日期，清空金额与备注
  const goOn = await showConfirmDialog({
    title: '记账成功',
    message: `已保存 ${formatMoney(respData?.amount ?? form.amount)}`,
    confirmButtonText: '再记一笔',
    cancelButtonText: '返回首页'
  })
    .then(() => true)
    .catch(() => false)

  if (goOn) {
    form.amount = ''
    form.remark = ''
    nextTick(() => amountField.value?.focus())
  } else {
    router.replace('/')
  }
}

onMounted(async () => {
  form.shop_id = shopStore.currentId || shopStore.list[0]?.id || null
  if (!shopStore.list.length) await shopStore.load()
  if (!form.shop_id) form.shop_id = shopStore.list[0]?.id || null
  await loadCategories()
  nextTick(() => amountField.value?.focus())
})
</script>

<style scoped>
.block {
  margin-top: 12px;
}
.amount-field :deep(input) {
  font-size: 26px;
  font-weight: 700;
}
.cat-item {
  width: 100%;
  padding: 10px 2px;
  border-radius: 8px;
  background: #f7f8fa;
  font-size: 14px;
  text-align: center;
  border: 2px solid transparent;
}
.cat-item.active {
  background: #e8f7ff;
  border-color: #1989fa;
  color: #1989fa;
  font-weight: 600;
}
.pay-group {
  padding: 10px 16px;
  flex-wrap: wrap;
  row-gap: 10px;
}
.save-btn {
  margin: 24px 16px;
}
</style>
