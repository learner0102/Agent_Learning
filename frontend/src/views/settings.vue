<!-- frontend/src/views/Settings.vue -->
<template>
  <div class="settings-page">
    <header class="page-header">
      <el-button text :icon="ArrowLeft" @click="goBack" class="back-btn">
        返回聊天
      </el-button>
      <h2>设置</h2>
      <p class="subtitle">管理你的账户、长期记忆和知识库</p>
    </header>

    <!-- 统计卡片 -->
    <section class="stats">
      <div class="stat-card">
        <div class="num">{{ info.sessions }}</div>
        <div class="label">会话</div>
      </div>
      <div class="stat-card">
        <div class="num">{{ info.messages }}</div>
        <div class="label">消息</div>
      </div>
      <div class="stat-card">
        <div class="num">{{ info.documents }}</div>
        <div class="label">知识库文件</div>
      </div>
      <div class="stat-card">
        <div class="num">{{ info.long_term_memories }}</div>
        <div class="label">长期记忆</div>
      </div>
    </section>

    <!-- 长期记忆 -->
    <section class="block">
      <div class="block-header">
        <h3>长期记忆</h3>
        <el-button
          v-if="memories.length > 0"
          type="danger" text size="small" :icon="Delete"
          @click="clearAllMemory"
        >
          清空全部
        </el-button>
      </div>

      <p class="hint">
        Agent 会根据语义相似度检索这些记忆。清空只影响长期记忆，不影响会话历史。
      </p>

      <el-empty
        v-if="!memoriesLoading && memories.length === 0"
        description="暂无长期记忆"
        :image-size="80"
      />

      <el-table
        v-else
        :data="memories"
        v-loading="memoriesLoading"
        style="margin-top: 12px"
      >
        <el-table-column prop="memory_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="typeTag(row.memory_type)">
              {{ row.memory_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="内容" min-width="300">
          <template #default="{ row }">
            <div class="mem-content">{{ row.content }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="importance" label="重要度" width="90">
          <template #default="{ row }">
            <span class="imp">{{ row.importance.toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="时间" width="170">
          <template #default="{ row }">
            <span class="time">{{ formatTime(row.create_time) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="right">
          <template #default="{ row }">
            <el-button
              type="danger" text size="small" :icon="Delete"
              @click="delMemory(row)"
            />
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- 危险操作 -->
    <section class="block danger-block">
      <h3>危险操作</h3>
      <p class="hint">这些操作不可撤销，请谨慎使用。</p>
      <div class="danger-actions">
        <el-button type="danger" plain :icon="Warning" @click="clearAllMemory">
          清空长期记忆
        </el-button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Delete, Warning } from '@element-plus/icons-vue'
import api from '../api'

const router = useRouter()

const info = ref({
  sessions: 0, messages: 0, documents: 0, long_term_memories: 0,
})
const memories = ref([])
const memoriesLoading = ref(false)

async function fetchInfo() {
  try {
    const { data } = await api.get('/settings/info')
    info.value = data
  } catch (e) {
    ElMessage.error('加载统计信息失败')
  }
}

async function fetchMemories() {
  memoriesLoading.value = true
  try {
    const { data } = await api.get('/settings/memory')
    memories.value = data
  } catch (e) {
    ElMessage.error('加载长期记忆失败')
  } finally {
    memoriesLoading.value = false
  }
}

async function delMemory(row) {
  try {
    await ElMessageBox.confirm('确定删除这条记忆？', '提示', { type: 'warning' })
    await api.delete(`/settings/memory/${row.idx}`)
    ElMessage.success('已删除')
    await fetchMemories()
    await fetchInfo()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

async function clearAllMemory() {
  if (memories.value.length === 0) {
    return ElMessage.info('当前没有长期记忆')
  }
  try {
    await ElMessageBox.confirm(
      `确定清空全部 ${memories.value.length} 条长期记忆？此操作不可撤销。`,
      '警告',
      { type: 'warning', confirmButtonText: '确定清空', cancelButtonText: '取消' }
    )
    await api.delete('/settings/memory')
    ElMessage.success('已清空')
    await fetchMemories()
    await fetchInfo()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('清空失败')
  }
}

function typeTag(t) {
  return { semantic: 'success', episodic: 'primary', working: 'info' }[t] || 'info'
}

function formatTime(iso) {
  if (!iso) return '-'
  try { return new Date(iso).toLocaleString('zh-CN', { hour12: false }) }
  catch { return iso }
}

function goBack() {
  router.push('/chat')
}

onMounted(() => {
  fetchInfo()
  fetchMemories()
})
</script>

<style scoped>
.settings-page {
  padding: 32px 40px;
  max-width: 1000px;
  margin: 0 auto;
}
.page-header { margin-bottom: 24px; }
.page-header h2 { margin: 8px 0 6px; font-size: 20px; }
.page-header .subtitle { margin: 0; color: #8a919f; font-size: 13px; }
.back-btn { padding-left: 0; color: #4b5563; }
.back-btn:hover { color: #1a73e8; }

.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 32px;
}
.stat-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 20px;
  text-align: center;
}
.stat-card .num { font-size: 28px; font-weight: 600; color: #1a73e8; }
.stat-card .label { font-size: 13px; color: #8a919f; margin-top: 4px; }

.block {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 20px 24px;
  margin-bottom: 20px;
}
.block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.block h3 { margin: 0 0 4px; font-size: 16px; }
.hint { color: #8a919f; font-size: 13px; margin: 4px 0 12px; }

.mem-content {
  font-size: 13px;
  line-height: 1.5;
  max-height: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}
.imp { color: #1a73e8; font-weight: 500; }
.time { color: #8a919f; font-size: 12px; }

.danger-block { border-color: #fecaca; }
.danger-block h3 { color: #dc2626; }
.danger-actions { margin-top: 12px; }
</style>