<template>
  <div class="page settings">
    <van-nav-bar title="我的" />

    <van-cell-group inset class="block">
      <van-cell center>
        <template #title>
          <div class="user-line">
            <van-icon name="manager" size="28" />
            <span class="uname">{{ auth.username }}</span>
            <van-tag :type="roleTagType">{{ roleLabel(auth.user?.role) }}</van-tag>
          </div>
        </template>
      </van-cell>
    </van-cell-group>

    <!-- 店铺管理（仅管理员） -->
    <van-cell-group v-if="auth.isAdmin" inset title="店铺管理" class="block">
      <van-cell v-for="s in shops" :key="s.id" :title="s.name">
        <template #title>
          {{ s.name }}
          <van-tag v-if="s.status !== 'active'" type="danger" size="mini">已停用</van-tag>
        </template>
        <template #value>
          <van-button size="mini" :plain="s.status === 'active'" :type="s.status === 'active' ? 'danger' : 'primary'"
            @click="toggleShop(s)">
            {{ s.status === 'active' ? '停用' : '启用' }}
          </van-button>
          <van-button size="mini" type="danger" plain @click="deleteShop(s)">删除</van-button>
        </template>
      </van-cell>
      <van-cell title="新增店铺" icon="plus" clickable @click="addShop" />
    </van-cell-group>

    <!-- 分类管理（仅管理员） -->
    <van-cell-group v-if="auth.isAdmin" inset title="分类管理" class="block">
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
              <van-button size="mini" type="danger" plain @click="deleteCategory(c)">删除</van-button>
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
              <van-button size="mini" type="danger" plain @click="deleteCategory(c)">删除</van-button>
            </template>
          </van-cell>
          <van-cell title="新增收入分类" icon="plus" clickable @click="addCategory('income')" />
        </van-tab>
      </van-tabs>
    </van-cell-group>

    <!-- 用户管理（仅管理员） -->
    <van-cell-group v-if="auth.isAdmin" inset title="用户管理" class="block">
      <van-cell v-for="u in users" :key="u.id">
        <template #title>
          {{ u.username }}
          <van-tag :type="u.role === 'admin' ? 'primary' : u.role === 'owner' ? 'success' : 'default'" size="mini">
            {{ roleLabel(u.role) }}
          </van-tag>
          <van-tag v-if="u.status !== 'active'" type="danger" size="mini">已停用</van-tag>
        </template>
        <template #label>
          {{ userShopNames(u) }}
        </template>
        <template #value>
          <van-button v-if="u.role !== 'admin'" size="mini" plain @click="openUserShops(u)">授权店铺</van-button>
          <van-button size="mini" plain @click="resetPwd(u)">改密码</van-button>
          <van-button size="mini" :type="u.status === 'active' ? 'danger' : 'primary'" plain @click="toggleUser(u)">
            {{ u.status === 'active' ? '停用' : '启用' }}
          </van-button>
          <van-button v-if="u.id !== auth.user?.id" size="mini" type="danger" plain @click="deleteUser(u)">删除</van-button>
        </template>
      </van-cell>
      <van-cell title="新增用户" icon="plus" clickable @click="openUserForm" />
    </van-cell-group>

    <!-- 数据安全 -->
    <van-cell-group v-if="auth.isAdmin || auth.isOwner" inset title="数据安全" class="block">
      <van-cell title="立即备份" icon="records" is-link @click="backupNow" />
      <van-cell v-if="auth.isAdmin" title="备份记录" is-link :value="`${backups.length} 份`" @click="showBackups = true" />
      <van-cell title="回收站" is-link @click="openRecycle" />
      <van-cell v-if="auth.isAdmin" title="操作日志" is-link @click="openLogs" />
    </van-cell-group>

    <!-- 数据导出 -->
    <van-cell-group v-if="auth.isAdmin || auth.isOwner" inset title="数据导出" class="block">
      <van-field label="开始日期" readonly is-link :model-value="exportStart" @click="showExportStart = true" />
      <van-field label="结束日期" readonly is-link :model-value="exportEnd" @click="showExportEnd = true" />
      <van-cell title="导出 CSV（默认本月）">
        <template #value>
          <van-button type="primary" size="small" round :loading="exporting" @click="doExport">导 出</van-button>
        </template>
      </van-cell>
    </van-cell-group>

    <div class="block">
      <van-button block round type="danger" plain @click="logout">退出登录</van-button>
      <div class="ver">小微餐饮财务管理系统 v1.2</div>
    </div>

    <!-- 新增用户 -->
    <van-popup v-model:show="showUserForm" round position="bottom" :style="{ minHeight: '50%' }">
      <van-nav-bar title="新增用户" />
      <van-cell-group inset style="margin-top: 12px">
        <van-field v-model="userForm.username" label="用户名" placeholder="登录账号，如 xiaozhang" />
        <van-field v-model="userForm.password" label="初始密码" placeholder="至少 6 位" />
        <van-field label="角色" readonly is-link :model-value="roleLabel(userForm.role)" @click="showRolePick = true" />
      </van-cell-group>
      <van-cell-group v-if="userForm.role !== 'admin'" inset title="授权店铺（员工/店主必须勾选）" class="block">
        <van-checkbox-group v-model="userForm.shop_ids" direction="horizontal" class="shop-checks">
          <van-checkbox v-for="s in shops" :key="s.id" :name="s.id" shape="square">{{ s.name }}</van-checkbox>
        </van-checkbox-group>
      </van-cell-group>
      <div class="detail-btns">
        <van-button type="primary" block round :loading="saving" @click="submitUserForm">保 存</van-button>
      </div>
    </van-popup>

    <van-popup v-model:show="showRolePick" round position="bottom">
      <van-picker
        :columns="[{ text: '管理员', value: 'admin' }, { text: '店主', value: 'owner' }, { text: '员工', value: 'employee' }]"
        title="选择角色"
        @confirm="(v) => { userForm.role = v.selectedValues[0]; showRolePick = false }"
        @cancel="showRolePick = false"
      />
    </van-popup>

    <!-- 授权店铺 -->
    <van-popup v-model:show="showUserShops" round position="bottom" :style="{ minHeight: '40%' }">
      <van-nav-bar :title="`授权店铺：${userShopsTarget.username}`" />
      <van-cell-group inset style="margin-top: 12px">
        <van-checkbox-group v-model="userShopsSelected" direction="horizontal" class="shop-checks">
          <van-checkbox v-for="s in shops" :key="s.id" :name="s.id" shape="square">{{ s.name }}</van-checkbox>
        </van-checkbox-group>
      </van-cell-group>
      <div class="detail-btns">
        <van-button type="primary" block round :loading="saving" @click="saveUserShops">保 存</van-button>
      </div>
    </van-popup>

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
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showDialog, showToast } from 'vant'
import api from '../api'
import { useAuthStore } from '../stores/auth'
import { inputDialog } from '../utils/inputDialog'
import { dayjs, formatMoney, roleLabel } from '../utils/format'

const auth = useAuthStore()
const router = useRouter()
const roleTagType = computed(() =>
  auth.user?.role === 'admin' ? 'primary' : auth.user?.role === 'owner' ? 'success' : 'default'
)

const shops = ref([])
const catList = ref({ income: [], expense: [] })
const users = ref([])
const backups = ref([])
const recycle = ref([])
const logs = ref([])
const catTab = ref('expense')
const saving = ref(false)

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

// 新增用户 / 授权店铺
const showUserForm = ref(false)
const showRolePick = ref(false)
const userForm = ref({ username: '', password: '', role: 'employee', shop_ids: [] })
const showUserShops = ref(false)
const userShopsTarget = ref({ id: 0, username: '' })
const userShopsSelected = ref([])

const shopNameMap = computed(() => Object.fromEntries(shops.value.map((s) => [s.id, s.name])))
const userShopNames = (u) => {
  if (u.role === 'admin') return '默认拥有全部店铺'
  if (!u.shop_ids?.length) return '未授权店铺'
  return u.shop_ids.map((id) => shopNameMap.value[id] || `#${id}`).join('、')
}

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

// ---------- 新增用户 / 授权店铺 ----------
function openUserForm() {
  userForm.value = { username: '', password: '', role: 'employee', shop_ids: [...shops.value.map((s) => s.id)] }
  showUserForm.value = true
}

async function submitUserForm() {
  const f = userForm.value
  if (!f.username.trim()) return showToast('请输入用户名')
  if (f.password.length < 6) return showToast('密码至少 6 位')
  if (f.role !== 'admin' && !f.shop_ids.length) return showToast('请至少勾选一个授权店铺')
  saving.value = true
  try {
    await api.post('/users', {
      username: f.username.trim(),
      password: f.password,
      role: f.role,
      shop_ids: f.role === 'admin' ? [] : f.shop_ids
    })
    showToast('用户已创建')
    showUserForm.value = false
    loadAll()
  } finally {
    saving.value = false
  }
}

function openUserShops(u) {
  if (u.role === 'admin') return showToast('管理员默认拥有全部店铺权限')
  userShopsTarget.value = { id: u.id, username: u.username }
  userShopsSelected.value = [...(u.shop_ids || [])]
  showUserShops.value = true
}

async function saveUserShops() {
  saving.value = true
  try {
    await api.put(`/users/${userShopsTarget.value.id}/shops`, { shop_ids: userShopsSelected.value })
    showToast('授权已更新，立即生效')
    showUserShops.value = false
    loadAll()
  } finally {
    saving.value = false
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

async function deleteShop(s) {
  try {
    await showConfirmDialog({
      title: '确认删除店铺',
      message: `删除后「${s.name}」将不再出现在选择列表，历史流水与统计仍保留店名。确定删除吗？`,
      confirmButtonText: '删除',
      confirmButtonColor: '#ee0a24'
    })
    await api.delete(`/shops/${s.id}`)
    showToast('已删除，历史记录仍保留')
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

async function deleteCategory(c) {
  try {
    await showConfirmDialog({
      title: '确认删除分类',
      message: `删除后「${c.name}」不能再用于记账，历史流水的分类名仍保留。确定删除吗？`,
      confirmButtonText: '删除',
      confirmButtonColor: '#ee0a24'
    })
    await api.delete(`/categories/${c.id}`)
    showToast('已删除，历史记录仍保留')
    loadAll()
  } catch { /* 取消 */ }
}

// ---------- 用户 ----------
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

async function deleteUser(u) {
  try {
    await showConfirmDialog({
      title: '确认删除用户',
      message: `删除后「${u.username}」将无法登录，其历史流水仍保留创建人名字。确定删除吗？`,
      confirmButtonText: '删除',
      confirmButtonColor: '#ee0a24'
    })
    await api.delete(`/users/${u.id}`)
    showToast('已删除，历史记录仍保留')
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
  create: '新增', update: '修改', update_shops: '调整店铺授权', soft_delete: '删除', restore: '恢复',
  login: '登录', backup: '备份', restore_backup: '恢复备份'
}
function logTitle(l) {
  if (l.action === 'update_shops') {
    return `${l.username} 调整了店铺授权（${(l.before_data?.shops || []).join('、') || '无'} → ${(l.after_data?.shops || []).join('、') || '无'}）`
  }
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
.shop-checks {
  padding: 12px 16px;
  flex-wrap: wrap;
  gap: 12px;
}
.detail-btns {
  display: flex;
  gap: 12px;
  margin: 16px;
}
.detail-btns .van-button {
  flex: 1;
}
:deep(.van-cell__value) {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 6px;
}
:deep(.van-cell__value .van-button + .van-button) {
  margin-left: 0;
}
</style>
