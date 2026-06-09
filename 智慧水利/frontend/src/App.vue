<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <h1>水利工程智能问答系统</h1>
      <div class="header-right">
        <template v-if="isLoggedIn">
          <span class="user-name">{{ currentUser?.username }}</span>
          <el-button text size="small" @click="onLogout">退出</el-button>
        </template>
        <el-button v-else text size="small" @click="loginRef?.open()">登录</el-button>
      </div>
    </el-header>
    <el-main class="app-main">
      <router-view />
    </el-main>
    <LoginDialog ref="loginRef" />
  </el-container>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useAuth } from './composables/useAuth'
import LoginDialog from './components/LoginDialog.vue'

const { currentUser, isLoggedIn, logout, fetchUser } = useAuth()
const loginRef = ref(null)

function onLogout() {
  logout()
}

onMounted(() => {
  fetchUser()
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
}

.app-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-header {
  background: linear-gradient(135deg, #1a5276, #2980b9);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
  flex-shrink: 0;
  padding: 0 24px;
}

.app-header h1 {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 2px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-right .el-button {
  color: #fff;
}

.user-name {
  font-size: 13px;
  opacity: 0.9;
}

.app-main {
  flex: 1;
  overflow: hidden;
  padding: 0;
  background: #f0f2f5;
}
</style>
