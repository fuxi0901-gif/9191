<template>
  <el-dialog v-model="visible" :title="isLogin ? '登录' : '注册'" width="400px" :close-on-click-modal="false">
    <el-form label-position="top" @keydown.enter="onSubmit">
      <el-form-item label="用户名">
        <el-input v-model="username" placeholder="请输入用户名" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input v-model="password" type="password" show-password placeholder="请输入密码" />
      </el-form-item>
      <el-form-item v-if="!isLogin" label="部门">
        <el-input v-model="dept" placeholder="请输入部门（选填）" />
      </el-form-item>
    </el-form>

    <template #footer>
      <div style="display: flex; justify-content: space-between; width: 100%">
        <el-button text type="primary" @click="isLogin = !isLogin">
          {{ isLogin ? '没有账号？去注册' : '已有账号？去登录' }}
        </el-button>
        <div>
          <el-button @click="visible = false">取消</el-button>
          <el-button type="primary" :loading="loading" @click="onSubmit">
            {{ isLogin ? '登录' : '注册' }}
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuth } from '../composables/useAuth'

const { login, register } = useAuth()

const visible = ref(false)
const isLogin = ref(true)
const loading = ref(false)
const username = ref('')
const password = ref('')
const dept = ref('')

function open() {
  isLogin.value = true
  username.value = ''
  password.value = ''
  dept.value = ''
  visible.value = true
}

async function onSubmit() {
  if (!username.value.trim() || !password.value.trim()) {
    ElMessage.warning('请填写用户名和密码')
    return
  }
  loading.value = true
  try {
    if (isLogin.value) {
      await login(username.value.trim(), password.value)
      ElMessage.success('登录成功')
    } else {
      await register(username.value.trim(), password.value, dept.value.trim())
      ElMessage.success('注册成功')
    }
    visible.value = false
  } catch (e) {
    const msg = e.response?.data?.detail || '操作失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

defineExpose({ open, visible })
</script>
