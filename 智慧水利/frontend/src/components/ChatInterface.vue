<template>
  <div class="chat-interface">
    <div class="chat-messages" ref="messagesContainer">
      <div v-if="messages.length === 0" class="welcome-tip">
        <el-icon :size="48" color="#2980b9"><ChatDotRound /></el-icon>
        <p>欢迎使用水利工程智能问答系统</p>
        <span>上传规范文档后，可通过文字或语音提问</span>
      </div>
      <div v-for="(msg, idx) in messages" :key="idx" class="message-item" :class="msg.role">
        <div class="message-avatar">
          <el-avatar :size="36" :style="{ background: msg.role === 'user' ? '#2980b9' : '#27ae60' }">
            {{ msg.role === 'user' ? '我' : 'AI' }}
          </el-avatar>
        </div>
        <div class="message-body">
          <!-- 用户消息 -->
          <div v-if="msg.role === 'user'" class="message-content" v-html="formatContent(msg.content)"></div>

          <!-- AI 回答：知识库相关时显示双栏 -->
          <template v-else>
            <div v-if="msg.relevant" class="relevance-badge">
              <el-tag type="success" size="small">已匹配知识库</el-tag>
            </div>
            <div v-else class="relevance-badge">
              <el-tag type="info" size="small">通用回答</el-tag>
            </div>

            <!-- RAG 增强回答 -->
            <div v-if="msg.ragAnswer" class="answer-block rag-block">
              <div class="answer-label">知识库增强回答</div>
              <div class="message-content rag-content" v-html="formatContent(msg.ragAnswer)"></div>
            </div>

            <!-- 纯 LLM 回答 -->
            <div v-if="msg.llmAnswer" class="answer-block llm-block">
              <div class="answer-label">AI 独立回答</div>
              <div class="message-content llm-content" v-html="formatContent(msg.llmAnswer)"></div>
            </div>

            <!-- 兼容旧格式 -->
            <div v-if="!msg.ragAnswer && !msg.llmAnswer && msg.content" class="message-content" v-html="formatContent(msg.content)"></div>

            <div class="message-actions">
              <el-button :icon="speakingIdx === idx ? 'Mute' : 'Microphone'"
                size="small" text circle
                @click="toggleSpeak(msg, idx)"
                title="语音播报" />
            </div>
            <div v-if="msg.contexts && msg.contexts.length > 0" class="message-sources">
              <el-collapse>
                <el-collapse-item :title="'查看引用来源（' + msg.contexts.length + ' 条）'">
                  <div v-for="(src, i) in msg.contexts" :key="i" class="source-item">
                    <div class="source-header">
                      <el-tag size="small" type="success">{{ src.filename || '来源 ' + (i + 1) }}</el-tag>
                      <span class="source-distance" v-if="src.distance !== undefined">相关度: {{ (100 - src.distance * 100).toFixed(0) }}%</span>
                    </div>
                    <div class="source-excerpt">{{ src.excerpt || src }}</div>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>
          </template>
          <div class="message-time">{{ formatTime(msg.timestamp) }}</div>
        </div>
      </div>
      <div v-if="loading" class="message-item assistant">
        <div class="message-avatar">
          <el-avatar :size="36" style="background: #27ae60">AI</el-avatar>
        </div>
        <div class="message-body">
          <div class="typing-indicator">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>
    </div>

    <!-- 模型切换栏 -->
    <div class="model-bar">
      <span class="model-label">当前模型：</span>
      <el-select v-model="currentProvider" @change="onQuickSwitch" size="small" style="width: 160px">
        <el-option label="Ollama (本地)" value="ollama" />
        <el-option label="DeepSeek" value="deepseek" />
        <el-option label="Kimi (Moonshot)" value="kimi" />
        <el-option label="离线模板" value="template" />
      </el-select>
      <el-button size="small" text @click="settingsRef?.open()" title="配置 API Key">
        <el-icon><Setting /></el-icon> API Key
      </el-button>
      <el-tag v-if="currentProvider === 'template'" type="warning" size="small" style="margin-left: 6px">无需 Key</el-tag>
      <el-tag v-else-if="currentProvider === 'ollama'" type="info" size="small" style="margin-left: 6px">需本地运行</el-tag>
      <el-tag v-else-if="!hasKeyForProvider" type="danger" size="small" style="margin-left: 6px">未配置 Key</el-tag>
      <el-tag v-else type="success" size="small" style="margin-left: 6px">已配置</el-tag>
      <el-switch v-model="streamMode" size="small" style="margin-left: 12px" active-text="流式" inactive-text="普通" />
    </div>

    <!-- 输入区域 -->
    <div class="chat-input-area">
      <el-button
        :type="listening ? 'danger' : 'default'"
        circle
        size="large"
        :class="{ recording: listening }"
        @click="startVoiceInput"
        title="语音输入"
        :disabled="listening"
      >
        <el-icon><Microphone /></el-icon>
      </el-button>
      <el-button
        v-if="listening"
        type="success"
        size="default"
        @click="finishVoiceInput"
        style="flex-shrink: 0;"
      >
        完成
      </el-button>
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="2"
        :placeholder="listening ? '正在聆听...' : '输入问题，按 Enter 发送'"
        resize="none"
        @keydown.enter.exact.prevent="sendMessage"
      />
      <el-button type="primary" :disabled="!inputText.trim() || loading" @click="sendMessage">
        <el-icon><Promotion /></el-icon> 发送
      </el-button>
    </div>

    <SettingsDialog ref="settingsRef" />
  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch, onMounted, onUnmounted } from 'vue'
import { sendQuery, sendQueryStream } from '../api'
import { useConversation } from '../composables/useConversation'
import { ChatDotRound, Promotion, Microphone, Setting } from '@element-plus/icons-vue'
import SettingsDialog from './SettingsDialog.vue'

const {
  currentConversationId,
  currentMessages: messages,
  addMessage: persistMessage,
  createConversation: ensureConversation,
} = useConversation()

const STORAGE_KEY = 'water_llm_settings'

const inputText = ref('')
const loading = ref(false)
const listening = ref(false)
const speakingIdx = ref(-1)
const messagesContainer = ref(null)
const settingsRef = ref(null)
const currentProvider = ref('ollama')
const streamMode = ref(true)

function loadCurrentProvider() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const data = JSON.parse(raw)
      currentProvider.value = data.current_provider || 'ollama'
    }
  } catch { /* ignore */ }
}

const hasKeyForProvider = computed(() => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return currentProvider.value === 'ollama' || currentProvider.value === 'template'
    const data = JSON.parse(raw)
    const p = currentProvider.value
    if (p === 'ollama' || p === 'template') return true
    return !!data[p + '_key']
  } catch { return false }
})

function onQuickSwitch(provider) {
  currentProvider.value = provider
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    const data = raw ? JSON.parse(raw) : {}
    data.current_provider = provider
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  } catch { /* ignore */ }
}

// ========== Web Speech API: 语音识别 ==========
let recognition = null
let userWantsListening = false

function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  if (!SpeechRecognition) {
    console.warn('浏览器不支持语音识别')
    return
  }
  recognition = new SpeechRecognition()
  recognition.lang = 'zh-CN'
  recognition.continuous = true
  recognition.interimResults = true

  recognition.onresult = (event) => {
    let transcript = ''
    for (let i = 0; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript
    }
    inputText.value = transcript.trim()
  }

  recognition.onerror = () => {}

  recognition.onend = () => {
    if (userWantsListening) {
      setTimeout(() => {
        try { recognition.start() } catch { userWantsListening = false; listening.value = false }
      }, 50)
    } else {
      listening.value = false
    }
  }
}

function startVoiceInput() {
  if (!recognition) initSpeechRecognition()
  if (!recognition) {
    alert('您的浏览器不支持语音识别，请使用 Chrome 或 Edge 浏览器')
    return
  }
  inputText.value = ''
  userWantsListening = true
  listening.value = true
  try { recognition.start() } catch { userWantsListening = false; listening.value = false }
}

function finishVoiceInput() {
  userWantsListening = false
  listening.value = false
  try { recognition.stop() } catch { /* ignore */ }
}

// ========== Web Speech API: 语音合成 (TTS) ==========
const synth = window.speechSynthesis

function getSpeakText(msg) {
  // 拼接所有可朗读的文本
  const parts = []
  if (msg.ragAnswer) parts.push('知识库增强回答：' + msg.ragAnswer)
  if (msg.llmAnswer) parts.push('AI独立回答：' + msg.llmAnswer)
  if (!msg.ragAnswer && !msg.llmAnswer && msg.content) parts.push(msg.content)
  return parts.join('\n\n')
}

function toggleSpeak(msg, idx) {
  if (speakingIdx.value === idx) {
    synth.cancel()
    speakingIdx.value = -1
    return
  }
  synth.cancel()
  const text = getSpeakText(msg)
  const cleanText = text.replace(/<br\/?>/g, '\n').replace(/<[^>]+>/g, '')
  const utterance = new SpeechSynthesisUtterance(cleanText)
  utterance.lang = 'zh-CN'
  utterance.rate = 1.0
  utterance.pitch = 1.0
  utterance.onend = () => { speakingIdx.value = -1 }
  utterance.onerror = () => { speakingIdx.value = -1 }
  speakingIdx.value = idx
  synth.speak(utterance)
}

// ========== 消息格式化 ==========
function formatContent(text) {
  if (!text) return ''
  // 高亮三段式标题
  let html = text
    .replace(/【结论】/g, '<span class="section-tag tag-conclusion">结论</span>')
    .replace(/【依据】/g, '<span class="section-tag tag-basis">依据</span>')
    .replace(/【建议】/g, '<span class="section-tag tag-suggest">建议</span>')
  html = html.replace(/\n/g, '<br/>')
  return html
}

function formatTime(ts) {
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function scrollToBottom() {
  nextTick(() => {
    const el = messagesContainer.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

// ========== 消息发送 ==========
async function sendMessage() {
  const query = inputText.value.trim()
  if (!query || loading.value) return

  // 确保存在对话
  if (!currentConversationId.value) {
    await ensureConversation()
  }

  messages.value.push({ role: 'user', content: query, timestamp: Date.now() })
  inputText.value = ''
  loading.value = true
  scrollToBottom()

  try {
    const cfg = settingsRef.value?.getConfig() || null
    const convId = currentConversationId.value

    // 持久化用户消息
    if (convId) {
      persistMessage(convId, 'user', query).catch(() => {})
    }

    if (streamMode.value) {
      await sendMessageStream(query, cfg, convId)
    } else {
      await sendMessageNormal(query, cfg, convId)
    }
  } catch (e) {
    console.error('sendMessage error:', e)
    const errMsg = e?.message || e?.toString() || '未知错误'
    messages.value.push({
      role: 'assistant',
      content: `抱歉，请求失败：${errMsg}`,
      contexts: [],
      timestamp: Date.now()
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

/** 普通模式（非流式） */
async function sendMessageNormal(query, cfg, convId) {
  const { data } = await sendQuery(query, 3, cfg, convId)
  messages.value.push({
    role: 'assistant',
    relevant: data.relevant || false,
    ragAnswer: data.rag_answer || null,
    llmAnswer: data.llm_answer || data.answer || '未获取到回答',
    contexts: data.contexts || [],
    timestamp: Date.now()
  })
}

/** 流式模式（SSE） */
async function sendMessageStream(query, cfg, convId) {
  const body = { query, top_k: 3 }
  if (cfg) body.llm_config = cfg
  if (convId) body.conversation_id = convId
  const response = await sendQueryStream(body)
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }

  if (!response.body) {
    throw new Error('响应体为空')
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  // 在消息列表中预留位置
  const msgIdx = messages.value.length
  messages.value.push({
    role: 'assistant',
    relevant: false,
    ragAnswer: '',
    llmAnswer: '',
    contexts: [],
    timestamp: Date.now()
  })

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''  // 保留未完成的行

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const dataStr = line.slice(6)
        let event
        try {
          event = JSON.parse(dataStr)
        } catch {
          continue
        }

        switch (event.type) {
          case 'meta':
            messages.value[msgIdx].relevant = event.relevant
            messages.value[msgIdx].contexts = event.contexts || []
            break
          case 'rag_token':
            messages.value[msgIdx].ragAnswer += event.data
            break
          case 'llm_token':
            messages.value[msgIdx].llmAnswer += event.data
            break
          case 'done':
            break
        }
      }
      scrollToBottom()
    }
  } finally {
    reader.releaseLock()
  }
}

onMounted(() => {
  loadCurrentProvider()
  initSpeechRecognition()
})

const checkSettingsClosed = () => {
  if (settingsRef.value && settingsRef.value.visible === false) {
    loadCurrentProvider()
  }
}
const pollTimer = setInterval(checkSettingsClosed, 500)

onUnmounted(() => {
  clearInterval(pollTimer)
  if (recognition) recognition.abort()
  synth.cancel()
})

watch(messages, () => scrollToBottom(), { deep: true })
</script>

<style scoped>
.chat-interface {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.welcome-tip {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
  gap: 12px;
}

.welcome-tip p {
  font-size: 18px;
  font-weight: 500;
  color: #333;
}

.message-item {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.message-item.user { flex-direction: row-reverse; }

.message-body { max-width: 70%; }

.message-content {
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  word-break: break-word;
}

.user .message-content {
  background: #2980b9;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.assistant .message-content {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-bottom-left-radius: 4px;
}

.relevance-badge {
  margin-bottom: 6px;
}

.answer-block {
  margin-bottom: 10px;
}

.answer-label {
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
  font-weight: 500;
}

.rag-block .rag-content {
  border-left: 3px solid #27ae60;
}

.llm-block .llm-content {
  border-left: 3px solid #2980b9;
}

.rag-block .answer-label { color: #27ae60; }
.llm-block .answer-label { color: #2980b9; }

.message-actions {
  margin-top: 4px;
  text-align: right;
}

.message-sources {
  margin-top: 8px;
  font-size: 12px;
}

.message-sources :deep(.el-collapse-item__header) {
  font-size: 12px;
  color: #888;
}

.source-item {
  margin-bottom: 10px;
  padding: 8px 10px;
  background: #f9fafb;
  border-radius: 6px;
  border: 1px solid #eee;
}

.source-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.source-distance {
  font-size: 11px;
  color: #999;
}

.source-excerpt {
  font-size: 12px;
  color: #555;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.section-tag {
  display: inline-block;
  font-weight: 700;
  font-size: 13px;
  padding: 1px 8px;
  border-radius: 3px;
  margin: 8px 0 4px 0;
}
.tag-conclusion { background: #e3f2fd; color: #1565c0; }
.tag-basis      { background: #fff3e0; color: #e65100; }
.tag-suggest    { background: #e8f5e9; color: #2e7d32; }

.message-time {
  font-size: 11px;
  color: #bbb;
  margin-top: 4px;
  text-align: right;
}

.user .message-time { text-align: left; }

.model-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 20px;
  background: #fafafa;
  border-top: 1px solid #e8e8e8;
  font-size: 13px;
}

.model-label {
  color: #888;
  white-space: nowrap;
}

.chat-input-area {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  background: #fff;
  border-top: 1px solid #e8e8e8;
  align-items: flex-end;
}

.chat-input-area .el-button { flex-shrink: 0; }

.chat-input-area .el-button.recording {
  animation: pulse 1.2s infinite;
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(245, 34, 45, 0.4); }
  50% { box-shadow: 0 0 0 12px rgba(245, 34, 45, 0); }
}

.typing-indicator {
  padding: 12px 16px;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 12px;
  display: flex;
  gap: 4px;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #999;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
  30% { opacity: 1; transform: scale(1); }
}
</style>
