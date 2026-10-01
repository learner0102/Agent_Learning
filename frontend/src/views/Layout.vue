<!-- frontend/src/views/Layout.vue -->
<template>
  <div class="layout">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="brand">
          <div class="logo">R</div>
          <span>RAG Agent</span>
        </div>
        <el-button type="primary" size="small" :icon="Plus" circle @click="newSession" />
      </div>

      <div class="session-list">
        <el-empty v-if="!sessions.loading && sessions.list.length === 0"
                  description="还没有会话" :image-size="60" />
        <div v-for="s in sessions.list" :key="s.id"
             class="session-item"
             :class="{ active: s.id === sessions.currentId }"
             @click="openSession(s.id)">
          <span class="title">{{ s.title }}</span>
          <el-icon class="del" @click.stop="delSession(s)"><Delete /></el-icon>
        </div>
      </div>

      <div class="sidebar-footer">
        <el-dropdown trigger="click" @command="onCommand">
          <div class="user">
            <div class="avatar">{{ initial }}</div>
            <div class="meta">
              <div class="name">{{ auth.user?.nickname || auth.user?.username }}</div>
              <div class="sub">@{{ auth.user?.username }}</div>
            </div>
            <el-icon><ArrowDown /></el-icon>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="documents">
                <el-icon><Document /></el-icon> 我的知识库
              </el-dropdown-item>
              <el-dropdown-item command="settings">
                <el-icon><Setting /></el-icon> 设置
              </el-dropdown-item>
              <el-dropdown-item command="refresh">
                <el-icon><Refresh /></el-icon> 刷新会话列表
              </el-dropdown-item>
              <el-dropdown-item command="logout" divided>
                <el-icon><SwitchButton /></el-icon> 退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </aside>

    <!-- 主区 -->
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete, ArrowDown, Refresh, SwitchButton, Document, Setting } from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'
import { useSessionsStore } from '../stores/sessions'
import { useRoute, useRouter } from 'vue-router'
const route = useRoute()
const auth = useAuthStore()
const sessions = useSessionsStore()
const router = useRouter()

const initial = computed(() =>
  (auth.user?.nickname || auth.user?.username || '?').charAt(0).toUpperCase()
)

onMounted(async () => {
  try {
    await sessions.fetchList()
  } catch (e) {
    ElMessage.error('加载会话列表失败')
  }
})

function newSession() {
  try {
    sessions.currentId = null
    router.push('/chat')
  } catch (e) {
    ElMessage.error('新建会话失败')
  }
}

function openSession(id) {
  if (id === sessions.currentId) return
  router.push(`/chat/${id}`)
}

async function delSession(s) {
  try {
    await ElMessageBox.confirm(`确定删除会话「${s.title}」？`, '提示', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    })
    const wasCurrent = s.id === sessions.currentId
    await sessions.remove(s.id)
    ElMessage.success('已删除')
    if (wasCurrent) {
      // remove 后 currentId 已指向剩余第一个，或用 null
      router.push(sessions.currentId ? `/chat/${sessions.currentId}` : '/chat')
    }
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

async function onCommand(cmd) {
  if (cmd === 'logout') {
    try {
      await ElMessageBox.confirm('确定退出登录？', '提示', { type: 'warning' })
      auth.logout()
      router.push('/login')
    } catch {}
  } else if (cmd === 'refresh') {
    await sessions.fetchList()
    ElMessage.success('已刷新')
  }
  else if (cmd === 'documents') {
    const from = route.params.sessionId || route.query.from || ''
    router.push({ path: '/documents', query: { from } })
  }
  else if (cmd === 'settings') {
    router.push('/settings')
  }
}
</script>

<style scoped>
.layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* ---------- 侧边栏 ---------- */
.sidebar {
  width: 260px;
  background: #fafbfc;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #e5e7eb;
}
.brand { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.logo {
  width: 28px; height: 28px; border-radius: 8px;
  background: #1a73e8; color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  margin-bottom: 4px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  color: #4b5563;
  transition: background 0.15s;
}
.session-item:hover { background: #eef2f7; }
.session-item.active { background: #e0edff; color: #1a73e8; font-weight: 500; }
.session-item .title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.session-item .del {
  opacity: 0;
  color: #9ca3af;
  transition: opacity 0.15s;
}
.session-item:hover .del { opacity: 1; }
.session-item .del:hover { color: #ef4444; }

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid #e5e7eb;
}
.user {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}
.user:hover { background: #eef2f7; }
.avatar {
  width: 32px; height: 32px; border-radius: 50%;
  background: #1a73e8; color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-weight: 600;
  flex-shrink: 0;
}
.meta { flex: 1; min-width: 0; }
.meta .name {
  font-size: 13px; font-weight: 500; color: #1f2329;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.meta .sub { font-size: 11px; color: #9ca3af; }

/* ---------- 主区 ---------- */
.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: #fff;
}
</style>