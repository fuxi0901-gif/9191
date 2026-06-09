<template>
  <el-upload
    class="file-upload"
    drag
    :http-request="handleUpload"
    :accept="'.pdf,.docx,.txt'"
    :show-file-list="true"
    :limit="10"
    :on-exceed="onExceed"
  >
    <el-icon :size="40" color="#2980b9"><UploadFilled /></el-icon>
    <div class="upload-text">
      <p>点击或拖拽上传水利规范文档</p>
      <span>支持 PDF、DOCX、TXT 格式，单个文件不超过 20MB</span>
    </div>
  </el-upload>
</template>

<script setup>
import { UploadFilled } from '@element-plus/icons-vue'
import { uploadFile } from '../api'
import { ElMessage } from 'element-plus'

const emit = defineEmits(['uploaded'])

async function handleUpload({ file }) {
  if (file.size > 20 * 1024 * 1024) {
    ElMessage.warning('文件大小不能超过 20MB')
    return
  }
  try {
    const { data } = await uploadFile(file)
    ElMessage.success(`文档 "${data.filename}" 上传成功，共处理 ${data.chunks_stored} 个文本块`)
    emit('uploaded', data)
  } catch {
    // 错误已在拦截器处理
  }
}

function onExceed() {
  ElMessage.warning('上传文件数量已达上限')
}
</script>

<style scoped>
.file-upload {
  width: 100%;
}

.upload-text p {
  font-size: 14px;
  color: #333;
  margin: 8px 0 4px;
}

.upload-text span {
  font-size: 12px;
  color: #999;
}
</style>
