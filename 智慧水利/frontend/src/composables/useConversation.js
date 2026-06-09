import { ref, computed } from 'vue'
import {
  fetchConversations as apiFetchConversations,
  createConversation as apiCreateConversation,
  getConversation as apiGetConversation,
  updateConversation as apiUpdateConversation,
  deleteConversation as apiDeleteConversation,
  addMessage as apiAddMessage,
} from '../api'

// 全局单例状态（所有导入组件共享）
const conversations = ref([])
const currentConversationId = ref(null)
const currentMessages = ref([])
const loadingConversations = ref(false)

export function useConversation() {
  async function fetchConversations() {
    loadingConversations.value = true
    try {
      const { data } = await apiFetchConversations()
      conversations.value = data || []
    } catch {
      conversations.value = []
    } finally {
      loadingConversations.value = false
    }
  }

  async function createConversation(title = '新会话') {
    try {
      const { data } = await apiCreateConversation(title)
      conversations.value.unshift({
        id: data.id,
        session_id: data.session_id,
        title: data.title,
        created_at: data.created_at,
        updated_at: data.created_at,
        message_count: 0,
      })
      currentConversationId.value = data.id
      currentMessages.value = []
      return data
    } catch {
      return null
    }
  }

  async function selectConversation(convId) {
    if (convId === currentConversationId.value) return
    currentConversationId.value = convId
    try {
      const { data } = await apiGetConversation(convId)
      currentMessages.value = (data.messages || []).map(m => ({
        role: m.role,
        content: m.content,
        timestamp: m.created_at ? new Date(m.created_at).getTime() : Date.now(),
        // 尝试从保存的 content 中解析双路回答结构
        ragAnswer: extractRagAnswer(m.content),
        llmAnswer: extractLlmAnswer(m.content),
        relevant: !!(m.content && m.content.includes('【知识库增强回答】')),
      }))
    } catch {
      currentMessages.value = []
    }
  }

  async function deleteConversation(convId) {
    try {
      await apiDeleteConversation(convId)
      conversations.value = conversations.value.filter(c => c.id !== convId)
      if (currentConversationId.value === convId) {
        currentConversationId.value = null
        currentMessages.value = []
      }
    } catch {
      // ignore
    }
  }

  async function renameConversation(convId, title) {
    try {
      await apiUpdateConversation(convId, title)
      const conv = conversations.value.find(c => c.id === convId)
      if (conv) conv.title = title
    } catch {
      // ignore
    }
  }

  async function addMessage(convId, role, content) {
    try {
      await apiAddMessage(convId, role, content)
      // 更新本地 message_count
      const conv = conversations.value.find(c => c.id === convId)
      if (conv) conv.message_count = (conv.message_count || 0) + 1
    } catch {
      // 静默失败，不影响主流程
    }
  }

  // 初始化：自动创建或加载最近的对话
  async function init() {
    await fetchConversations()
    if (conversations.value.length > 0) {
      await selectConversation(conversations.value[0].id)
    } else {
      await createConversation()
    }
  }

  return {
    conversations,
    currentConversationId,
    currentMessages,
    loadingConversations,
    fetchConversations,
    createConversation,
    selectConversation,
    deleteConversation,
    renameConversation,
    addMessage,
    init,
  }
}

// 从保存的 AI 消息内容中提取 RAG 回答
function extractRagAnswer(content) {
  if (!content) return ''
  const match = content.match(/【知识库增强回答】\n([\s\S]*?)(?=【AI 独立回答】|$)/)
  return match ? match[1].trim() : ''
}

// 从保存的 AI 消息内容中提取 LLM 回答
function extractLlmAnswer(content) {
  if (!content) return ''
  const match = content.match(/【AI 独立回答】\n([\s\S]*?)$/)
  return match ? match[1].trim() : ''
}
