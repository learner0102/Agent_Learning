<!-- frontend/src/views/Documents.vue -->
<template>
  <div class="doc-page">
    <header class="doc-header">
      <el-button text :icon="ArrowLeft" @click="goBack" class="back-btn">
        返回聊天
      </el-button>
      <h2>我的知识库</h2>
      <p class="subtitle">上传 .txt / .md 文件，Agent 回答时会优先检索</p>
    </header>

    <div class="upload-area">
      <el-upload
        :action="uploadUrl"
        :headers="uploadHeaders"
        :show-file-list="false"
        :before-upload="beforeUpload"
        :on-success="onSuccess"
        :on-error="onError"
        accept=".txt,.md"
      >
        <el-button type="primary" :icon="Upload" :loading="uploading">
          上传文件
        </el-button>
        <template #tip>
          <div class="el-upload__tip">
            支持 .txt / .md，单文件建议 &lt; 1MB
          </div>
        </template>
      </el-upload>
    </div>

    <el-table :data="list" v-loading="loading" style="margin-top: 24px">
      <el-table-column prop="filename" label="文件名" min-width="240" />
      <el-table-column prop="size" label="大小" width="120">
        <template #default="{ row }">{{ formatSize(row.size) }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">
            {{ statusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="上传时间" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" align="right">
        <template #default="{ row }">
          <el-button
            type="danger" size="small" text :icon="Delete"
            @click="del(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && list.length === 0" description="还没有上传任何文件" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Delete, ArrowLeft } from '@element-plus/icons-vue'
import api from '../api'

const uploadUrl = '/api/documents/upload'
const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
}))

const list = ref([])
const loading = ref(false)
const uploading = ref(false)

import { useRoute, useRouter } from 'vue-router'
const route = useRoute()
const router = useRouter()

function goBack() {
  const from = route.query.from
  if (from) {
    router.push(`/chat/${from}`)
  } else {
    // 没有来源：回上一次页面，或兜底到 /chat
    if (window.history.length > 1) {
      router.back()
    } else {
      router.push('/chat')
    }
  }
}
async function fetchList() {
  loading.value = true
  try {
    const { data } = await api.get('/documents')
    list.value = data
  } catch (e) {
    ElMessage.error('加载文档列表失败')
  } finally {
    loading.value = false
  }
}

function beforeUpload(file) {
  const okExt = /\.(txt|md)$/i.test(file.name)
  if (!okExt) {
    ElMessage.error('只支持 .txt / .md 文件')
    return false
  }
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.error('文件不能超过 5MB')
    return false
  }
  uploading.value = true
  return true
}

function onSuccess(resp) {
  uploading.value = false
  ElMessage.success(`已上传：${resp.filename}`)
  fetchList()
}

function onError(err) {
  uploading.value = false
  let msg = '上传失败'
  try {
    msg = JSON.parse(err.message)?.detail || msg
  } catch {}
  ElMessage.error(msg)
}

async function del(row) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.filename}」？`, '提示', {
      type: 'warning',
    })
    await api.delete(`/documents/${row.id}`)
    ElMessage.success('已删除')
    fetchList()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

function formatTime(iso) {
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}

function statusType(s) {
  return { pending: 'warning', indexed: 'success', failed: 'danger' }[s] || 'info'
}

function statusText(s) {
  return { pending: '待索引', indexed: '已索引', failed: '失败' }[s] || s
}

onMounted(fetchList)
</script>

<style scoped>
.doc-page {
  padding: 32px 40px;
  max-width: 1000px;
  margin: 0 auto;
}
.doc-header h2 { margin: 0 0 6px; font-size: 20px; }
.doc-header .subtitle { margin: 0 0 24px; color: #8a919f; font-size: 13px; }
.upload-area { margin-bottom: 8px; }
.back-btn {
  margin-bottom: 12px;
  padding-left: 0;
  color: #4b5563;
}
.back-btn:hover { color: #1a73e8; }
</style>