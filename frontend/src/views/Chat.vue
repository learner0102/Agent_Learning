<!-- frontend/src/views/Chat.vue -->
<template>
  <div class="chat-page">
    <!-- ============ 空状态：没有选中会话 ============ -->
        <div v-if="messages.length === 0 && !sending" class="empty">
      <div class="logo">R</div>
      <h2>开始新的对话</h2>
      <p>在下方输入框直接提问，会自动创建会话</p>

      <div class="quick-input">
        <el-input
          v-model="draft"
          type="textarea"
          :rows="2"
          placeholder="输入问题，Enter 发送，Shift+Enter 换行"
          resize="none"
          @keydown="onKeydown"
        />
        <el-button type="primary" :icon="Promotion"
                   :disabled="!draft.trim()" :loading="sending"
                   @click="send">
          发送
        </el-button>
      </div>
    </div>

    <!-- ============ 正常会话 ============ -->
    <template v-else>
      <header class="chat-header">
        <div class="title-wrap">
          <h3>{{ currentSession?.title || '会话' }}</h3>
          <span class="session-id">{{ sessionId }}</span>
        </div>
      </header>

      <div ref="bodyRef" class="chat-body">
        <div v-if="loadingHistory" class="loading-history">
          <el-icon class="is-loading"><Loading /></el-icon>
          加载历史…
        </div>

        <template v-else>
          <div v-for="(m, i) in messages" :key="i" class="msg-row" :class="m.role">
            <div class="avatar" :class="m.role">
              {{ m.role === 'user' ? 'U' : 'R' }}
            </div>
            <div class="bubble-wrap">
              <div v-if="m.role === 'user'" class="bubble user">
                {{ m.content }}
              </div>
              <template v-else>
                <div v-if="m.content" class="bubble bot markdown" v-html="renderMd(m.content)" />
                <div v-else class="bubble bot thinking">
                  <span class="dot" /><span class="dot" /><span class="dot" />
                </div>
              </template>
            </div>
          </div>


        </template>
      </div>

      <footer class="chat-footer">
        <el-input
          v-model="draft"
          type="textarea"
          :rows="2"
          placeholder="输入问题，Enter 发送，Shift+Enter 换行"
          resize="none"
          :disabled="sending"
          @keydown="onKeydown"
        />
        <el-button type="primary" :icon="Promotion"
                   :disabled="!draft.trim() || sending"
                   :loading="sending"
                   @click="send">
          发送
        </el-button>
      </footer>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Promotion, Loading } from '@element-plus/icons-vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.css'
import api from '../api'
import { useSessionsStore } from '../stores/sessions'

const route = useRoute()
const router = useRouter()
const sessions = useSessionsStore()

const sessionId = computed(() => route.params.sessionId || null)
const currentSession = computed(() => sessions.current)

const messages = ref([])      // [{ role: 'user'|'assistant', content, meta? }]
const draft = ref('')
const sending = ref(false)
const loadingHistory = ref(false)
const streamingMsg = ref(null)
const bodyRef = ref(null)

// ---------- Markdown 渲染 ----------
marked.setOptions({
  breaks: true,
  highlight(code, lang) {
    const l = hljs.getLanguage(lang) ? lang : 'plaintext'
    return hljs.highlight(code, { language: l }).value
  },
})
function renderMd(text) {
  return marked.parse(text || '')
}

// ---------- 滚动到底 ----------
async function scrollBottom() {
  await nextTick()
  const el = bodyRef.value
  if (!el) return

  // 立即滚
  el.scrollTop = el.scrollHeight

  // 等 Markdown / 代码高亮 / 图片渲染完，再滚一次
  requestAnimationFrame(() => {
    el.scrollTop = el.scrollHeight
  })
}

// ---------- 加载历史 ----------
async function loadHistory() {
  if (!sessionId.value) {
    messages.value = []
    return
  }
  loadingHistory.value = true
  try {
    const { data } = await api.get(`/sessions/${sessionId.value}/messages`)
    messages.value = data.map((m) => ({
      role: m.role,
      content: m.content,
      meta: m.role === 'assistant' && m.steps
        ? `⏱️ 步骤 ${m.steps} · 🛠️ 工具 ${m.tool_calls} 次`
        : null,
    }))
    await scrollBottom()
  } catch (e) {
    ElMessage.error('加载历史失败')
  } finally {
    loadingHistory.value = false
  }
}

// 会话切换时
watch(sessionId, async (id) => {
  sessions.currentId = id
  if (id) sessions.bumpToTop(id)
  await loadHistory()
}, { immediate: true })

// ---------- 发送 ----------
function onKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

async function send() {
  const text = draft.value.trim()
  if (!text || sending.value) return

  // 1. 立即显示用户消息 + 打字机
  messages.value.push({ role: 'user', content: text })
  draft.value = ''
  sending.value = true
  await scrollBottom()

  // 2. 准备一个"空的助手消息"，逐块往里 append
  const assistantMsg = reactive({
    role: 'assistant',
    content: '',
    meta: null,
  })
  messages.value.push(assistantMsg)

  try {
    const token = localStorage.getItem('token')
    const resp = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        message: text,
        session_id: sessionId.value,
      }),
    })

    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}: ${await resp.text()}`)
    }

    // 3. 逐块读 SSE
    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let newSessionId = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // SSE 以 \n\n 分隔事件
      const events = buffer.split('\n\n')
      buffer = events.pop() || ''

      for (const evt of events) {
        const lines = evt.split('\n')
        let eventName = 'message'
        let dataStr = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) eventName = line.slice(7).trim()
          else if (line.startsWith('data: ')) dataStr += line.slice(6)
        }
        if (!dataStr) continue

        let payload
        try { payload = JSON.parse(dataStr) } catch { continue }

        if (eventName === 'session') {
          newSessionId = payload.session_id
        } else if (eventName === 'delta') {
          assistantMsg.content += payload.text
          await scrollBottom()
        } else if (eventName === 'done') {
          newSessionId = payload.session_id
          assistantMsg.meta =
            `⏱️ 步骤 ${payload.steps} · 🛠️ 工具 ${payload.tool_calls} 次` +
            (payload.auto_saved ? ' · 💾 已自动记忆' : '')
          await scrollBottom()
        } else if (eventName === 'error') {
          assistantMsg.content = '⚠️ ' + (payload.message || '未知错误')
        }
      }
    }

    // 4. 新会话：跳 URL + 刷新列表
    if (!sessionId.value && newSessionId) {
      await sessions.fetchList()
      router.replace(`/chat/${newSessionId}`)
    } else if (sessionId.value) {
      await sessions.refreshOne(sessionId.value)
    }
  } catch (e) {
    assistantMsg.content = '⚠️ ' + (e.message || '发送失败')
    ElMessage.error(e.message || '发送失败')
  } finally {
    sending.value = false
  }
}


onMounted(() => {
  // 若 URL 里没有 sessionId，说明是新对话，等用户输入
})
</script>

<style scoped>
.chat-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* ---------- 空状态 ---------- */
.empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.empty .logo {
  width: 64px; height: 64px; border-radius: 16px;
  background: #1a73e8; color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 32px; font-weight: 700;
  margin-bottom: 16px;
}
.empty h2 { color: #1f2329; margin: 0 0 8px; }
.empty p { margin: 0 0 24px; font-size: 14px; color: #8a919f; }

.quick-input {
  width: 100%;
  max-width: 640px;
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

/* ---------- 会话头 ---------- */
.chat-header {
  padding: 12px 24px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  flex-shrink: 0;
}
.title-wrap { display: flex; align-items: baseline; gap: 12px; min-width: 0; }
.chat-header h3 {
  margin: 0; font-size: 15px; font-weight: 600;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.session-id { font-size: 11px; color: #c0c4cc; font-family: monospace; }

/* ---------- 消息区 ---------- */
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: #fafbfc;
}
.loading-history {
  display: flex; align-items: center; gap: 6px;
  color: #8a919f; font-size: 13px; justify-content: center;
  padding: 40px 0;
}

.msg-row {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  align-items: flex-start;
}
.msg-row.user { flex-direction: row-reverse; }

.avatar {
  width: 32px; height: 32px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-weight: 600; font-size: 13px; flex-shrink: 0;
}
.avatar.user { background: #dbeafe; color: #1a73e8; }
.avatar.assistant { background: #1a73e8; color: #fff; }

.bubble-wrap { max-width: 78%; min-width: 0; }

.bubble {
  padding: 10px 14px;
  border-radius: 12px;
  line-height: 1.65;
  font-size: 14px;
  word-wrap: break-word;
}
.bubble.user {
  background: #1a73e8; color: #fff;
  border-bottom-right-radius: 4px;
  white-space: pre-wrap;
}
.bubble.bot {
  background: #fff; color: #1f2329;
  border: 1px solid #e5e7eb;
  border-bottom-left-radius: 4px;
}
.bubble.thinking {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 14px 16px;
}
.dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: #c0c4cc;
  animation: blink 1.4s infinite both;
}
.dot:nth-child(2) { animation-delay: .2s; }
.dot:nth-child(3) { animation-delay: .4s; }
@keyframes blink { 0%,80%,100%{opacity:.2} 40%{opacity:1} }

.meta {
  font-size: 11px; color: #9ca3af;
  margin-top: 6px;
  padding: 0 4px;
}

/* Markdown 内部微调 */
.bubble.bot :deep(h1),
.bubble.bot :deep(h2),
.bubble.bot :deep(h3) { font-size: 15px; margin: 10px 0 6px; }
.bubble.bot :deep(p) { margin: 6px 0; }
.bubble.bot :deep(p:first-child) { margin-top: 0; }
.bubble.bot :deep(p:last-child) { margin-bottom: 0; }
.bubble.bot :deep(table) { border-collapse: collapse; margin: 8px 0; font-size: 13px; }
.bubble.bot :deep(th),
.bubble.bot :deep(td) { border: 1px solid #e5e7eb; padding: 4px 8px; }
.bubble.bot :deep(pre) {
  background: #f6f8fa; padding: 10px; border-radius: 8px;
  overflow-x: auto; margin: 8px 0;
}
.bubble.bot :deep(code) {
  background: #f6f8fa; padding: 1px 5px;
  border-radius: 4px; font-size: 0.9em;
}
.bubble.bot :deep(pre code) { background: none; padding: 0; }
.bubble.bot :deep(ul),
.bubble.bot :deep(ol) { padding-left: 20px; margin: 6px 0; }

/* ---------- 底部输入 ---------- */
.chat-footer {
  padding: 16px 24px;
  border-top: 1px solid #e5e7eb;
  background: #fff;
  display: flex;
  gap: 8px;
  align-items: flex-end;
  flex-shrink: 0;
}
</style>