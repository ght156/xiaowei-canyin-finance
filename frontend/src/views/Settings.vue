<template>
  <div class="page settings">
    <van-nav-bar title="我的" />

    <van-cell-group inset class="block">
      <van-cell center>
        <template #title>
          <div class="user-line">
            <van-icon name="manager" size="28" />
            <span class="uname">{{ auth.username }}</span>
            <van-tag :type="auth.isAdmin ? 'primary' : 'success'">
              {{ auth.isAdmin ? '管理员' : '店主' }}
            </van-tag>
          </div>
        </template>
      </van-cell>
    </van-cell-group>

    <template v-if="auth.isAdmin">
      <!-- 店铺管理 -->
      <van-cell-group inset title="店铺管理" class="block">
        <van-cell v-for="s in shops" :key="s.id" :title="s.name" :value="s.status === 'active' ? '营业中' : '已停用'" is-link
          @click="toggleShop(s)" />
        <van-cell title="新增店铺" icon="plus" clickable @click="addShop" />
      </van-cell-group>

      <!-- 分类管理 -->
      <van-cell-group inset title="分类管理" class="block">
        <van-tabs v-model:active="catTab" shrink>
          <van-tab title="支出分类">
            <van-cell v-for="c in catList.expense" :key="c.id">
              <template #title>
                {{ c.name }}
                <van-tag v-if="c.status !== 'active'" type="danger" size="mini">已停用</van-tag>
              </template>
              <template #value>
                <van-button size="mini" plain @click="editCategory(c)">编辑</van-button>
                <van-button size="mini" :plain="c.status === 'active'" :type="c.status === 'active' ? 'danger' : 'primary'"
                  @click="toggleCategory(c)">
                  {{ c.status === 'active' ? '停用' : '启用' }}
                </van-button>
              </template>
            </van-cell>
            <van-cell title="新增支出分类" icon="plus" clickable @click="addCategory('expense')" />
          </van-tab>
          <van-tab title="收入分类">
            <van-cell v-for="c in catList.income" :key="c.id">
              <template #title>
                {{ c.name }}
                <van-tag v-if="c.status !== 'active'" type="danger" size="mini">已停用</van-tag>
              </template>
              <template #value>
                <van-button size="mini" plain @click="editCategory(c)">编辑</van-button>
                <van-button size="mini" :plain="c.status === 'active'" :type="c.status === 'active' ? 'danger' : 'primary'"
                  @click="toggleCategory(c)">
                  {{ c.status === 'active' ? '停用' : '启用' }}
                </van-button>
              </template>
            </van-cell>
            <van-cell title="新增收入分类" icon="plus" clickable @click="addCategory('income')" />
          </van-tab>
        </van-tabs>
      </van-cell-group>

      <!-- 用户管理 -->
      <van-cell-group inset title="用户管理" class="block">
        <van-cell v-for="u in users" :key="u.id" :title="u.username"
          :label="u.status === 'active' ? undefined : '已停用'"
          :value="u.role === 'admin' ? '管理员' : '店主'">
          <template #value>
            <van-button size="mini" plain @click="resetPwd(u)">改密码</van-button>
            <van-button size="mini" :type="u.status === 'active' ? 'danger' : 'primary'" plain @click="toggleUser(u)">
              {{ u.status === 'active' ? '停用' : '启用' }}
            </van-button>
          </template>
        </van-cell>
        <van-cell title="新增用户" icon="plus" clickable @click="addUser" />
      </van-cell-group>

      <!-- 数据安全 -->
      <van-cell-group inset title="数据安全" class="block">
        <van-cell title="立即备份" icon="records" is-link @click="backupNow" />
        <van-cell title="备份记录" is-link :value="`${backups.length} 份`" @click="showBackups = true" />
        <van-cell title="回收站" is-link @click="openRecycle" />
        <van-cell title="操作日志" is-link @click="openLogs" />
      </van-cell-group>

      <!-- 导出 -->
      <van-cell-group inset title="数据导出" class="block">
        <van-field label="开始日期" readonly is-link :model-value="exportStart" @click="showExportStart = true" />
        <van-field label="结束日期" readonly is-link :model-value="exportEnd" @click="showExportEnd = true" />
        <van-cell title="导出 CSV（本月默认）">
          <template #value>
            <van-button type="primary" size="small" round :loading="exporting" @click="doExport">导 出</van-button>
          </template>
        </van-cell>
      </van-cell-group>
    </template>

    <div class="block">
      <van-button block round type="danger" plain @click="logout">退出登录</van-button>
      <div class="ver">小微餐饮财务管理系统 v1.1</div>
    </div>

    <!-- 备份列表 -->
    <van-popup v-model:show="showBackups" round position="bottom" :style="{ minHeight: '40%' }">
      <van-nav-bar title="备份记录" />
      <van-cell v-for="b in backups" :key="b.id" :title="b.file_name"
        :label="`${fmtTime(b.created_at)} · ${backupTypeLabel(b.backup_type)}`">
        <template #value>
          <van-button size="mini" plain @click="downloadBackup(b)">下载</van-button>
          <van-button size="mini" type="warning" plain @click="restoreBackup(b)">恢复</van-button>
        </template>
      </van-cell>
      <van-empty v-if="!backups.length" description="暂无备份" />
    </van-popup>

    <!-- 回收站 -->
    <van-popup v-model:show="showRecycle" round position="bottom" :style="{ minHeight: '50%' }">
      <van-nav-bar title="回收站（已删除流水）" />
      <van-cell v-for="t in recycle" :key="t.id" :title="`${t.category_name} ${formatMoney(t.amount)}`"
        :label="`${t.biz_date} · ${t.shop_name} · 删除于 ${fmtTime(t.deleted_at)}`">
        <template #value>
          <van-button size="mini" type="primary" @click="restoreTx(t)">恢复</van-button>
        </template>
      </van-cell>
      <van-empty v-if="!recycle.length" description="回收站是空的" />
    </van-popup>

    <!-- 操作日志 -->
    <van-popup v-model:show="showLogs" round position="bottom" :style="{ minHeight: '60%' }">
      <van-nav-bar title="操作日志" />
      <div class="logs">
        <van-cell v-for="l in logs" :key="l.id" :title="logTitle(l)" :label="`${fmtTime(l.created_at)} · ${l.username}`" />
        <van-empty v-if="!logs.length" description="暂无日志" />
      </div>
    </van-popup>

    <!-- 导出日期选择 -->
    <van-popup v-model:show="showExportStart" round position="bottom">
      <van-date-picker v-model="exportStartParts" :min-date="minDate" :max-date="maxDate" title="开始日期"
        @confirm="(v) => { exportStart = v.selectedValues.join('-'); showExportStart = false }"
        @cancel="showExportStart = false" />
    </van-popup>
    <van-popup v-model:show="showExportEnd" round position="bottom">
      <van-date-picker v-model="exportEndParts" :min-date="minDate" :max-date="maxDate" title="结束日期"
        @confirm="(v) => { exportEnd = v.selectedValues.join('-'); showExportEnd = false }"
        @cancel="showExportEnd = false" />
    </van-popup>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showDialog, showToast } from 'vant'
import api from '../api'
import { useAuthStore } from '../stores/auth'
import { inputDialog } from '../utils/inputDialog'
import { dayjs, formatMoney } from '../utils/format'

const auth = useAuthStore()
const router = useRouter()

const shops = ref([])
const catList = ref({ income: [], expense: [] })
const users = ref([])
const backups = ref([])
const recycle = ref([])
const logs = ref([])
const catTab = ref('expense')

const minDate = new Date(2020, 0, 1)
const maxDate = new Date(dayjs().year() + 1, 11, 31)

const showBackups = ref(false)
const showRecycle = ref(false)
const showLogs = ref(false)
const showExportStart = ref(false)
const showExportEnd = ref(false)
const exporting = ref(false)

const exportStart = ref(dayjs().startOf('month').format('YYYY-MM-DD'))
const exportEnd = ref(dayjs().format('YYYY-MM-DD'))
const exportStartParts = ref(exportStart.value.split('-'))
const exportEndParts = ref(exportEnd.value.split('-'))

async function loadAll() {
  const [s, c] = await Promise.all([
    api.get('/shops?include_disabled=1'),
    api.get('/categories?include_disabled=1')
  ])
  shops.value = s.data
  catList.value = {
    income: c.data.filter((x) => x.type === 'income'),
    expense: c.data.filter((x) => x.type === 'expense')
  }
  if (auth.isAdmin) {
    const [u, b] = await Promise.all([api.get('/users'), api.get('/backups')])
    users.value = u.data
    backups.value = b.data
  }
}

// ---------- 店铺 ----------
async function addShop() {
  try {
    const { value } = await inputDialog({ title: '新增店铺', placeholder: '请输入店铺名称' })
    if (!value?.trim()) return
    await api.post('/shops', { name: value.trim() })
    showToast('已添加')
    loadAll()
  } catch { /* 取消 */ }
}

async function toggleShop(s) {
  const action = s.status === 'active' ? '停用' : '启用'
  try {
    await showConfirmDialog({ title: `确认${action}`, message: `确定${action}店铺「${s.name}」吗？` })
    await api.put(`/shops/${s.id}`, { status: s.status === 'active' ? 'disabled' : 'active' })
    showToast(`已${action}`)
    loadAll()
  } catch { /* 取消 */ }
}

// ---------- 分类 ----------
async function addCategory(type) {
  try {
    const { value } = await inputDialog({ title: type === 'income' ? '新增收入分类' : '新增支出分类', placeholder: '请输入分类名称' })
    if (!value?.trim()) return
    await api.post('/categories', { type, name: value.trim() })
    showToast('已添加')
    loadAll()
  } catch { /* 取消 */ }
}

async function editCategory(c) {
  try {
    const { value } = await inputDialog({ title: '编辑分类', initialValue: c.name, message: '修改分类名称' })
    if (!value?.trim() || value.trim() === c.name) return
    await api.put(`/categories/${c.id}`, { name: value.trim() })
    showToast('已修改')
    loadAll()
  } catch { /* 取消 */ }
}

async function toggleCategory(c) {
  const action = c.status === 'active' ? '停用' : '启用'
  try {
    await showConfirmDialog({ title: `确认${action}`, message: `确定${action}分类「${c.name}」吗？` })
    await api.put(`/categories/${c.id}`, { status: c.status === 'active' ? 'disabled' : 'active' })
    showToast(`已${action}`)
    loadAll()
  } catch { /* 取消 */ }
}

// ---------- 用户 ----------
async function addUser() {
  try {
    const { value } = await inputDialog({ title: '新增用户', placeholder: '格式：用户名/密码/角色(admin或owner)' })
    if (!value) return
    const [username, password, role] = value.split('/').map((x) => x?.trim())
    if (!username || !password) return showToast('格式：用户名/密码/角色')
    await api.post('/users', { username, password, role: role === 'admin' ? 'admin' : 'owner' })
    showToast('已添加')
    loadAll()
  } catch { /* 取消 */ }
}

async function resetPwd(u) {
  try {
    const { value } = await inputDialog({ title: `重置「${u.username}」的密码`, placeholder: '新密码（至少6位）' })
    if (!value) return
    if (value.length < 6) return showToast('密码至少6位')
    await api.put(`/users/${u.id}`, { password: value })
    showToast('已重置')
  } catch { /* 取消 */ }
}

async function toggleUser(u) {
  const action = u.status === 'active' ? '停用' : '启用'
  try {
    await showConfirmDialog({ title: `确认${action}`, message: `确定${action}用户「${u.username}」吗？` })
    await api.put(`/users/${u.id}`, { status: u.status === 'active' ? 'disabled' : 'active' })
    showToast(`已${action}`)
    loadAll()
  } catch { /* 取消 */ }
}

// ---------- 备份 ----------
async function backupNow() {
  try {
    await showConfirmDialog({ title: '确认备份', message: '将立即创建一份数据库备份，继续吗？' })
    const { data } = await api.post('/backups')
    showToast('备份完成')
    backups.value = [data, ...backups.value]
  } catch { /* 取消 */ }
}

async function restoreBackup(b) {
  try {
    await showConfirmDialog({
      title: '⚠️ 高危操作',
      message: `恢复备份会将系统恢复到指定时间点，此后的数据可能丢失！\n（恢复前会自动创建一份安全备份）\n确定用「${b.file_name}」恢复吗？`,
      confirmButtonText: '仍然恢复',
      confirmButtonColor: '#ee0a24'
    })
    await api.post(`/backups/${b.file_name}/restore`)
    showDialog({ message: '恢复完成，系统已切回备份时间点的数据，页面即将刷新。' })
    setTimeout(() => window.location.reload(), 1600)
  } catch { /* 取消 */ }
}

function backupTypeLabel(t) {
  return { auto: '自动', manual: '手动', pre_restore: '恢复前安全备份' }[t] || t
}

async function downloadBackup(b) {
  const resp = await api.get(`/backups/${b.file_name}/download`, { responseType: 'blob' })
  const url = URL.createObjectURL(resp.data)
  const a = document.createElement('a')
  a.href = url
  a.download = b.file_name
  a.click()
  URL.revokeObjectURL(url)
  showToast('已开始下载，建议保存到电脑或网盘留存')
}

// ---------- 回收站 ----------
async function openRecycle() {
  const { data } = await api.get('/transactions', { params: { deleted_only: 1, page_size: 100 } })
  recycle.value = data.items
  showRecycle.value = true
}

async function restoreTx(t) {
  await api.post(`/transactions/${t.id}/restore`)
  showToast('已恢复')
  recycle.value = recycle.value.filter((x) => x.id !== t.id)
}

// ---------- 日志 ----------
async function openLogs() {
  const { data } = await api.get('/audit-logs', { params: { page_size: 50 } })
  logs.value = data.items
  showLogs.value = true
}

const ACTION_LABELS = {
  create: '新增', update: '修改', soft_delete: '删除', restore: '恢复',
  login: '登录', backup: '备份', restore_backup: '恢复备份'
}
function logTitle(l) {
  return `${l.username} ${ACTION_LABELS[l.action] || l.action}了 ${l.entity_type}${l.entity_id ? '#' + l.entity_id : ''}`
}

// ---------- 导出 ----------
async function doExport() {
  exporting.value = true
  try {
    const resp = await api.get('/export', {
      params: { start: exportStart.value, end: exportEnd.value },
      responseType: 'blob'
    })
    const url = URL.createObjectURL(resp.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `流水_${exportStart.value}_${exportEnd.value}.csv`
    a.click()
    URL.revokeObjectURL(url)
    showToast('已导出')
  } finally {
    exporting.value = false
  }
}

function logout() {
  showConfirmDialog({ title: '退出登录', message: '确定要退出吗？' }).then(() => {
    auth.logout()
    router.replace('/login')
  }).catch(() => {})
}

function fmtTime(s) {
  return s ? dayjs(s).format('YYYY-MM-DD HH:mm') : ''
}

onMounted(loadAll)
</script>

<style scoped>
.block {
  margin-top: 12px;
}
.user-line {
  display: flex;
  align-items: center;
  gap: 8px;
}
.uname {
  font-weight: 600;
}
.logs {
  max-height: 60vh;
  overflow: auto;
}
.ver {
  text-align: center;
  color: #bbb;
  font-size: 12px;
  margin: 16px 0;
}
.van-button + .van-button {
  margin-left: 6px;
}
</style>
