<template>
  <router-view v-slot="{ Component }">
    <keep-alive include="Home,Transactions,Reports">
      <component :is="Component" />
    </keep-alive>
  </router-view>
  <van-tabbar route v-if="showTabbar">
    <van-tabbar-item replace to="/" icon="wap-home-o">首页</van-tabbar-item>
    <van-tabbar-item replace to="/transactions" icon="bill-o">流水</van-tabbar-item>
    <van-tabbar-item v-if="!auth.isEmployee" replace to="/reports" icon="chart-trending-o">分析</van-tabbar-item>
    <van-tabbar-item replace to="/settings" icon="user-o">我的</van-tabbar-item>
  </van-tabbar>

  <!-- 全局输入对话框（Vant 无函数式输入框，用 store 驱动） -->
  <van-dialog
    v-model:show="dlg.show"
    :title="dlg.title"
    :show-cancel-button="true"
    @confirm="dlg.confirm"
    @cancel="dlg.cancel"
  >
    <div v-if="dlg.message" class="dlg-msg">{{ dlg.message }}</div>
    <van-field v-model="dlg.value" :placeholder="dlg.placeholder" />
  </van-dialog>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useInputDialogStore } from './stores/inputDialog'

const route = useRoute()
const auth = useAuthStore()
const dlg = useInputDialogStore()

const showTabbar = computed(
  () =>
    auth.isLoggedIn &&
    route.path !== '/login' &&
    !route.path.startsWith('/entry/')
)
</script>

<style>
body {
  background: #f7f8fa;
  font-size: 15px;
}
#app {
  max-width: 640px;
  margin: 0 auto;
  min-height: 100vh;
}
.page {
  padding-bottom: 60px;
}
.amount-income {
  color: #07c160;
}
.amount-expense {
  color: #ee0a24;
}
</style>
