import { ref, computed } from 'vue'
import { login as apiLogin, register as apiRegister, getUserInfo } from '../api'

const currentUser = ref(null)
const authToken = ref(localStorage.getItem('water_auth_token') || '')

const isLoggedIn = computed(() => !!authToken.value && !!currentUser.value)

async function login(username, password) {
  const { data } = await apiLogin(username, password)
  authToken.value = data.access_token
  localStorage.setItem('water_auth_token', data.access_token)
  currentUser.value = { id: data.user_id, username: data.username }
  return data
}

async function register(username, password, dept = '') {
  const { data } = await apiRegister(username, password, dept)
  authToken.value = data.access_token
  localStorage.setItem('water_auth_token', data.access_token)
  currentUser.value = { id: data.user_id, username: data.username }
  return data
}

async function fetchUser() {
  if (!authToken.value) return
  try {
    const { data } = await getUserInfo()
    currentUser.value = data
  } catch {
    logout()
  }
}

function logout() {
  authToken.value = ''
  currentUser.value = null
  localStorage.removeItem('water_auth_token')
}

export function useAuth() {
  return {
    currentUser,
    authToken,
    isLoggedIn,
    login,
    register,
    logout,
    fetchUser,
  }
}
