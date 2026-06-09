<template>
  <el-dialog v-model="visible" title="LLM 模型设置" width="520px" :close-on-click-modal="false">
    <el-form label-position="top" size="default">
      <el-form-item label="LLM 供应商">
        <el-select v-model="form.provider" @change="onProviderChange" style="width: 100%">
          <el-option label="Ollama (本地部署，优先)" value="ollama" />
          <el-option label="DeepSeek" value="deepseek" />
          <el-option label="Kimi (Moonshot)" value="kimi" />
          <el-option label="离线模板模式" value="template" />
        </el-select>
      </el-form-item>

      <template v-if="form.provider !== 'template' && form.provider !== 'ollama'">
        <el-form-item label="API Key">
          <el-input v-model="form.api_key" type="password" show-password
            :placeholder="'sk-xxxxxxxxxxxxxxxx'" />
        </el-form-item>
      </template>

      <template v-if="form.provider === 'ollama'">
        <el-form-item label="Ollama 地址">
          <el-input v-model="form.api_base" placeholder="http://localhost:11434" />
        </el-form-item>
        <el-form-item label="模型名称">
          <el-input v-model="form.model" placeholder="qwen2:7b" />
        </el-form-item>
      </template>

      <template v-if="form.provider === 'deepseek' || form.provider === 'kimi'">
        <el-form-item label="API 地址">
          <el-input v-model="form.api_base" :placeholder="defaultApiBase" />
        </el-form-item>
        <el-form-item label="模型名称">
          <el-input v-model="form.model" :placeholder="defaultModel" />
        </el-form-item>
      </template>
    </el-form>

    <template #footer>
      <div style="display: flex; justify-content: space-between; width: 100%">
        <el-button @click="testConnection" :loading="testing">
          <el-icon><Connection /></el-icon> 测试连接
        </el-button>
        <div>
          <el-button @click="visible = false">取消</el-button>
          <el-button type="primary" @click="saveSettings">保存</el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Connection } from '@element-plus/icons-vue'

// ===== localStorage key & per-provider 默认值 =====
const STORAGE_KEY = 'water_llm_settings'

const DEFAULTS = {
  deepseek: { api_base: 'https://api.deepseek.com', model: 'deepseek-chat' },
  kimi:     { api_base: 'https://api.moonshot.cn',  model: 'moonshot-v1-8k' },
  ollama:   { api_base: 'http://localhost:11434',    model: 'qwen2:7b' },
  template: { api_base: '', model: '' }
}

const PROVIDERS = ['deepseek', 'kimi', 'ollama', 'template']

// ===== 全量存储 =====
function loadAll() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch { return {} }
}

function saveAll(obj) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(obj))
}

// ===== 对话框状态 =====
const visible = ref(false)
const testing = ref(false)

const form = reactive({
  provider: 'ollama',
  api_key: '',
  api_base: '',
  model: ''
})

const defaultApiBase = computed(() => DEFAULTS[form.provider]?.api_base || '')
const defaultModel = computed(() => DEFAULTS[form.provider]?.model || '')

function onProviderChange(provider) {
  const all = loadAll()
  const prefix = provider + '_'
  form.api_key = all[prefix + 'key'] || ''
  form.api_base = all[prefix + 'base'] || DEFAULTS[provider]?.api_base || ''
  form.model = all[prefix + 'model'] || DEFAULTS[provider]?.model || ''
}

function open() {
  const all = loadAll()
  const cur = all.current_provider || 'ollama'
  form.provider = cur
  const prefix = cur + '_'
  form.api_key = all[prefix + 'key'] || ''
  form.api_base = all[prefix + 'base'] || DEFAULTS[cur]?.api_base || ''
  form.model = all[prefix + 'model'] || DEFAULTS[cur]?.model || ''
  visible.value = true
}

function saveSettings() {
  const all = loadAll()
  const p = form.provider
  all.current_provider = p
  if (p !== 'template' && p !== 'ollama') {
    all[p + '_key'] = form.api_key
  }
  all[p + '_base'] = form.api_base || DEFAULTS[p]?.api_base || ''
  all[p + '_model'] = form.model || DEFAULTS[p]?.model || ''
  saveAll(all)
  visible.value = false
  ElMessage.success('设置已保存')
}

// ===== 外部调用: 获取当前有效 LLM 配置 =====
function getConfig() {
  const all = loadAll()
  const p = all.current_provider || 'ollama'
  if (p === 'template') return null
  if (p === 'ollama') {
    return {
      provider: 'ollama',
      api_key: '',
      api_base: all.ollama_base || DEFAULTS.ollama.api_base,
      model: all.ollama_model || DEFAULTS.ollama.model
    }
  }
  const key = all[p + '_key']
  if (key) {
    return {
      provider: p,
      api_key: key,
      api_base: all[p + '_base'] || DEFAULTS[p].api_base,
      model: all[p + '_model'] || DEFAULTS[p].model
    }
  }
  return null
}

// ===== 测试连接 =====
async function testConnection() {
  if (form.provider === 'template') {
    ElMessage.info('离线模式无需测试')
    return
  }
  if (form.provider !== 'ollama' && !form.api_key) {
    ElMessage.warning('请先填写 API Key')
    return
  }
  testing.value = true
  try {
    const api = await import('../api')
    const { data } = await api.testLLM({
      provider: form.provider,
      api_key: form.api_key,
      api_base: form.api_base || DEFAULTS[form.provider]?.api_base,
      model: form.model || DEFAULTS[form.provider]?.model
    })
    if (data && data.success) {
      ElMessage.success('连接成功！')
    } else {
      ElMessage.error(data?.message || '连接失败')
    }
  } catch (e) {
    ElMessage.error('连接失败：' + (e.response?.data?.detail || e.message))
  } finally {
    testing.value = false
  }
}

defineExpose({ open, getConfig, visible })
</script>
