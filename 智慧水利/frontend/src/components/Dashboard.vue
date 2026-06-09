<template>
  <div class="dashboard">
    <!-- 左侧：会话列表 -->
    <div class="dashboard-sidebar">
      <div class="sidebar-header">
        <span>对话列表</span>
        <el-button :icon="Plus" size="small" circle @click="onNewConversation" title="新建对话" />
      </div>
      <div class="sidebar-list" v-loading="loadingConversations">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          class="sidebar-item"
          :class="{ active: conv.id === currentConversationId }"
          @click="onSelectConversation(conv.id)"
        >
          <div class="sidebar-item-main">
            <span class="sidebar-item-title">{{ conv.title }}</span>
            <span class="sidebar-item-meta">{{ conv.message_count || 0 }} 条消息</span>
          </div>
          <el-dropdown trigger="click" @command="(cmd) => onConvAction(cmd, conv)">
            <el-button :icon="MoreFilled" size="small" text @click.stop />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="rename">
                  <el-icon><Edit /></el-icon> 重命名
                </el-dropdown-item>
                <el-dropdown-item command="delete" divided>
                  <el-icon><Delete /></el-icon> 删除
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <div v-if="!loadingConversations && conversations.length === 0" class="sidebar-empty">
          暂无对话，点击 + 创建
        </div>
      </div>
    </div>

    <!-- 中间：主内容 -->
    <div class="dashboard-center">
      <div class="kpi-row">
        <div class="kpi-card">
          <div class="kpi-icon" style="background: #e8f5e9;">
            <el-icon :size="28" color="#27ae60"><Watermelon /></el-icon>
          </div>
          <div class="kpi-info">
            <span class="kpi-label">水库水位</span>
            <span class="kpi-value">{{ kpiValues.water_level.value }} <small>{{ kpiValues.water_level.unit }}</small></span>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon" style="background: #e3f2fd;">
            <el-icon :size="28" color="#2980b9"><Cloudy /></el-icon>
          </div>
          <div class="kpi-info">
            <span class="kpi-label">今日降雨量</span>
            <span class="kpi-value">{{ kpiValues.rainfall.value }} <small>{{ kpiValues.rainfall.unit }}</small></span>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon" style="background: #fff3e0;">
            <el-icon :size="28" color="#f39c12"><Warning /></el-icon>
          </div>
          <div class="kpi-info">
            <span class="kpi-label">预警状态</span>
            <span class="kpi-value status-normal">正常</span>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon" style="background: #fce4ec;">
            <el-icon :size="28" color="#e74c3c"><Document /></el-icon>
          </div>
          <div class="kpi-info">
            <span class="kpi-label">知识库文档</span>
            <span class="kpi-value">{{ docCount }} <small>份</small></span>
          </div>
        </div>
      </div>
      <div class="chart-toggle" @click="showChart = !showChart">
        <el-icon><DataAnalysis /></el-icon>
        <span>{{ showChart ? '收起监测图表' : '展开监测图表' }}</span>
        <el-icon><component :is="showChart ? 'ArrowUp' : 'ArrowDown'" /></el-icon>
      </div>
      <MonitoringChart v-show="showChart" />
      <div class="chat-section">
        <ChatInterface ref="chatRef" />
      </div>
    </div>

    <!-- 右侧：上传 + 信息 -->
    <div class="dashboard-right">
      <el-card shadow="never" class="upload-card">
        <template #header>
          <span>文档上传</span>
        </template>
        <FileUpload @uploaded="onUploaded" />
      </el-card>
      <el-card shadow="never" class="info-card">
        <template #header>
          <span>系统信息</span>
        </template>
        <div class="info-list">
          <div class="info-item">
            <span>后端状态</span>
            <el-tag :type="backendOnline ? 'success' : 'danger'" size="small">
              {{ backendOnline ? '在线' : '离线' }}
            </el-tag>
          </div>
          <div class="info-item">
            <span>LLM 模式</span>
            <el-tag :type="llmTagType" size="small">
              {{ llmLabel }}
            </el-tag>
          </div>
          <div class="info-item">
            <span>向量数据库</span>
            <el-tag type="info" size="small">ChromaDB</el-tag>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 重命名弹窗 -->
    <el-dialog v-model="renameVisible" title="重命名对话" width="360px" :close-on-click-modal="true">
      <el-input v-model="renameTitle" placeholder="输入新标题" @keydown.enter="onRenameConfirm" />
      <template #footer>
        <el-button @click="renameVisible = false">取消</el-button>
        <el-button type="primary" @click="onRenameConfirm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ChatInterface from './ChatInterface.vue'
import FileUpload from './FileUpload.vue'
import MonitoringChart from './MonitoringChart.vue'
import { healthCheck } from '../api'
import { useConversation } from '../composables/useConversation'
import { useMonitoring } from '../composables/useMonitoring'
import { Watermelon, Cloudy, Warning, Document, Plus, MoreFilled, Edit, Delete, DataAnalysis, ArrowDown, ArrowUp } from '@element-plus/icons-vue'

const { kpiValues, fetchKpiValues } = useMonitoring()
const showChart = ref(false)

const STORAGE_KEY = 'water_llm_settings'
const docCount = ref(0)
const backendOnline = ref(false)
const llmProvider = ref('ollama')

const {
  conversations,
  currentConversationId,
  loadingConversations,
  fetchConversations,
  createConversation,
  selectConversation,
  deleteConversation,
  renameConversation,
  init: initConversations,
} = useConversation()

const MODEL_LABELS = {
  deepseek: 'DeepSeek AI',
  kimi: 'Kimi AI',
  ollama: 'Ollama 本地',
  template: '离线模板'
}

const llmLabel = computed(() => MODEL_LABELS[llmProvider.value] || 'Ollama 本地')

const llmTagType = computed(() => {
  if (llmProvider.value === 'template') return 'warning'
  if (llmProvider.value === 'ollama') return 'info'
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return 'danger'
    const data = JSON.parse(raw)
    return data[llmProvider.value + '_key'] ? 'success' : 'danger'
  } catch { return 'danger' }
})

function refreshLLMStatus() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const data = JSON.parse(raw)
      llmProvider.value = data.current_provider || 'ollama'
    }
  } catch { /* ignore */ }
}

let statusTimer = null

onMounted(async () => {
  refreshLLMStatus()
  statusTimer = setInterval(refreshLLMStatus, 500)
  try {
    await healthCheck()
    backendOnline.value = true
  } catch {
    backendOnline.value = false
  }
  // 初始化对话列表
  await initConversations()
  // 加载监测数据
  fetchKpiValues()
})

onUnmounted(() => {
  clearInterval(statusTimer)
})

function onUploaded(data) {
  docCount.value += 1
}

// ========== 对话管理 ==========

async function onNewConversation() {
  await createConversation()
  await fetchConversations()
}

async function onSelectConversation(convId) {
  await selectConversation(convId)
}

function onConvAction(cmd, conv) {
  if (cmd === 'rename') {
    renameTarget.value = conv.id
    renameTitle.value = conv.title
    renameVisible.value = true
  } else if (cmd === 'delete') {
    onDeleteConversation(conv)
  }
}

async function onDeleteConversation(conv) {
  try {
    await ElMessageBox.confirm(
      `确定要删除对话「${conv.title}」吗？删除后不可恢复。`,
      '删除确认',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteConversation(conv.id)
    await fetchConversations()
    ElMessage.success('对话已删除')
  } catch {
    // 用户取消
  }
}

const renameVisible = ref(false)
const renameTarget = ref(null)
const renameTitle = ref('')

async function onRenameConfirm() {
  if (!renameTitle.value.trim()) return
  await renameConversation(renameTarget.value, renameTitle.value.trim())
  await fetchConversations()
  renameVisible.value = false
  ElMessage.success('已重命名')
}
</script>

<style scoped>
.dashboard {
  display: flex;
  height: 100%;
  gap: 0;
}

/* 左侧边栏 */
.dashboard-sidebar {
  width: 260px;
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid #e8e8e8;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 600;
  color: #333;
  border-bottom: 1px solid #eee;
}

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.sidebar-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
  margin-bottom: 2px;
}

.sidebar-item:hover {
  background: #f5f7fa;
}

.sidebar-item.active {
  background: #e6f0fa;
}

.sidebar-item-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.sidebar-item-title {
  font-size: 13px;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-item-meta {
  font-size: 11px;
  color: #999;
}

.sidebar-empty {
  text-align: center;
  color: #ccc;
  font-size: 13px;
  padding: 24px;
}

/* 中间 */
.dashboard-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  min-width: 0;
  background: #f0f2f5;
}

.kpi-row {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

.kpi-card {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

.kpi-icon {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.kpi-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.kpi-label {
  font-size: 12px;
  color: #999;
}

.kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: #333;
}

.kpi-value small {
  font-size: 12px;
  font-weight: 400;
  color: #999;
}

.status-normal {
  color: #27ae60 !important;
  font-size: 18px !important;
}

.chart-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px;
  font-size: 12px;
  color: #2980b9;
  cursor: pointer;
  user-select: none;
  background: #e8f0fe;
  border-radius: 6px;
  transition: background 0.2s;
}

.chart-toggle:hover {
  background: #d0e2fb;
}

.chat-section {
  flex: 1;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
  overflow: hidden;
  min-height: 0;
}

/* 右侧 */
.dashboard-right {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 16px 16px 0;
  background: #f0f2f5;
}

.upload-card, .info-card {
  border-radius: 8px;
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: #666;
}
</style>
