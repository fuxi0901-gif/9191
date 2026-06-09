import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' }
})

// 请求拦截器：自动附加 JWT Token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('water_auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const msg = error.response?.data?.detail || error.message || '请求失败'
    if (error.response?.status !== 401) {
      ElMessage.error(msg)
    }
    return Promise.reject(error)
  }
)

export function uploadFile(file) {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000
  })
}

export function sendQuery(query, topK = 3, llmConfig = null, convId = null) {
  const body = { query, top_k: topK }
  if (llmConfig) {
    body.llm_config = llmConfig
  }
  if (convId) {
    body.conversation_id = convId
  }
  return api.post('/query/', body)
}

/** 流式查询：接受预构建的 body 对象或各参数，返回 fetch Response */
export function sendQueryStream(bodyOrQuery, topK = 3, llmConfig = null, convId = null) {
  let body
  if (typeof bodyOrQuery === 'object' && bodyOrQuery !== null && bodyOrQuery.query) {
    body = { ...bodyOrQuery }
  } else {
    body = { query: bodyOrQuery, top_k: topK }
    if (llmConfig) body.llm_config = llmConfig
    if (convId) body.conversation_id = convId
  }
  return fetch('/api/query/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
}

export function testLLM(config) {
  return api.post('/test-llm/', config, { timeout: 20000 })
}

export function healthCheck() {
  return api.get('/')
}

export function systemStatus() {
  return api.get('/status/')
}

// ========== 对话管理 API ==========

export function fetchConversations() {
  return api.get('/conversations/')
}

export function createConversation(title = '新会话') {
  return api.post('/conversations/', { title })
}

export function getConversation(convId) {
  return api.get(`/conversations/${convId}`)
}

export function updateConversation(convId, title) {
  return api.put(`/conversations/${convId}`, { title })
}

export function deleteConversation(convId) {
  return api.delete(`/conversations/${convId}`)
}

export function addMessage(convId, role, content) {
  return api.post('/messages/', { conversation_id: convId, role, content })
}

// ========== 用户认证 API ==========

export function login(username, password) {
  return api.post('/login/', { username, password })
}

export function register(username, password, dept = '') {
  return api.post('/register/', { username, password, dept })
}

export function getUserInfo() {
  return api.get('/users/me/')
}

export default api
