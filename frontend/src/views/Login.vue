<!-- frontend/src/views/Login.vue -->
<template>
  <div class="login-page">
    <el-card class="login-card" shadow="always">
      <div class="brand">
        <div class="logo">R</div>
        <h1>RAG Agent</h1>
        <p class="subtitle">LangGraph · RAG · 分层记忆</p>
      </div>

      <el-tabs v-model="tab" stretch>
        <el-tab-pane label="登录" name="login">
          <el-form :model="loginForm" @submit.prevent="doLogin">
            <el-form-item>
              <el-input v-model="loginForm.username" placeholder="用户名" size="large" />
            </el-form-item>
            <el-form-item>
              <el-input v-model="loginForm.password" type="password" placeholder="密码"
                        size="large" show-password @keyup.enter="doLogin" />
            </el-form-item>
            <el-button type="primary" size="large" style="width:100%"
                       :loading="loading" @click="doLogin">
              登录
            </el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="注册" name="register">
          <el-form :model="regForm" @submit.prevent="doRegister">
            <el-form-item>
              <el-input v-model="regForm.username" placeholder="用户名（3-32 字符）" size="large" />
            </el-form-item>
            <el-form-item>
              <el-input v-model="regForm.nickname" placeholder="昵称（可选）" size="large" />
            </el-form-item>
            <el-form-item>
              <el-input v-model="regForm.password" type="password" placeholder="密码（至少 6 位）"
                        size="large" show-password @keyup.enter="doRegister" />
            </el-form-item>
            <el-button type="primary" size="large" style="width:100%"
                       :loading="loading" @click="doRegister">
              注册并登录
            </el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const tab = ref('login')
const loading = ref(false)
const loginForm = ref({ username: '', password: '' })
const regForm = ref({ username: '', password: '', nickname: '' })

async function doLogin() {
  if (!loginForm.value.username || !loginForm.value.password) {
    return ElMessage.warning('请填写用户名和密码')
  }
  loading.value = true
  try {
    await auth.login(loginForm.value.username, loginForm.value.password)
    ElMessage.success('登录成功')
    router.push(route.query.redirect || '/')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

async function doRegister() {
  if (!regForm.value.username || !regForm.value.password) {
    return ElMessage.warning('请填写用户名和密码')
  }
  if (regForm.value.username.length < 3) return ElMessage.warning('用户名至少 3 字符')
  if (regForm.value.password.length < 6) return ElMessage.warning('密码至少 6 位')
  loading.value = true
  try {
    await auth.register(regForm.value.username, regForm.value.password, regForm.value.nickname)
    ElMessage.success('注册成功')
    router.push('/')
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e0e7ff 0%, #f5f7fa 100%);
}
.login-card {
  width: 400px;
  padding: 8px;
}
.brand { text-align: center; margin-bottom: 24px; }
.logo {
  width: 56px; height: 56px; margin: 0 auto 12px;
  border-radius: 14px; background: #1a73e8; color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 28px; font-weight: 700;
}
.brand h1 { margin: 0; font-size: 22px; }
.subtitle { color: #8a919f; font-size: 13px; margin: 4px 0 0; }
</style>