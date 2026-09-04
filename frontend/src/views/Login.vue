<template>
  <div class="login-page">
    <div class="login-title">
      <div class="logo">🍲</div>
      <h2>小微餐饮记账</h2>
      <p>简单记账 · 自动算利润 · 安全备份</p>
    </div>
    <van-form @submit="onSubmit" class="login-form">
      <van-cell-group inset>
        <van-field
          v-model="form.username"
          name="username"
          label="账号"
          placeholder="请输入账号"
          :rules="[{ required: true, message: '请输入账号' }]"
        />
        <van-field
          v-model="form.password"
          type="password"
          name="password"
          label="密码"
          placeholder="请输入密码"
          :rules="[{ required: true, message: '请输入密码' }]"
        />
      </van-cell-group>
      <div class="login-btn">
        <van-button round block type="primary" native-type="submit" :loading="loading" size="large">
          登 录
        </van-button>
      </div>
    </van-form>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { useAuthStore } from '../stores/auth'
import { useShopStore } from '../stores/shops'

const router = useRouter()
const auth = useAuthStore()
const shopStore = useShopStore()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

async function onSubmit() {
  loading.value = true
  try {
    const { data } = await api.post('/auth/login', form)
    auth.setAuth(data.access_token, data.user)
    shopStore.currentId = 0
    shopStore.load()
    router.replace('/')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: linear-gradient(180deg, #ffe1e1 0%, #f7f8fa 40%);
}
.login-title {
  text-align: center;
  margin-bottom: 32px;
}
.logo {
  font-size: 56px;
}
.login-title h2 {
  margin: 8px 0 4px;
}
.login-title p {
  color: #999;
  font-size: 13px;
}
.login-btn {
  margin: 24px 16px;
}
</style>
