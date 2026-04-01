<template>
  <div class="event-detail-page">
    <!-- 返回按钮 -->
    <div class="back-header">
      <el-button text @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
    </div>

    <div v-loading="loading" class="content">
      <div v-if="event">
        <!-- 标题 -->
        <h1 class="title">{{ event.title }}</h1>

        <!-- 元信息 -->
        <div class="meta">
          <el-tag
            v-if="event.severity"
            :type="severityType(event.severity)"
            effect="dark"
          >
            {{ severityText(event.severity) }}
          </el-tag>
          <span v-if="event.cve_id" class="cve-id">{{ event.cve_id }}</span>
          <span class="source">{{ event.source_name }}</span>
          <span class="time">{{ formatDate(event.published_at) }}</span>
        </div>

        <!-- 分类和模型 -->
        <div class="tags" v-if="event.category || event.affected_models?.length">
          <el-tag v-if="event.category" type="info">
            {{ event.category.name }}
          </el-tag>
          <el-tag
            v-for="model in event.affected_models"
            :key="model.id"
            type="warning"
          >
            {{ model.name }}
          </el-tag>
        </div>

        <!-- 描述 -->
        <div class="description">
          <h3>描述</h3>
          <p>{{ event.description || '暂无描述' }}</p>
        </div>

        <!-- 原文链接 -->
        <div class="source-link" v-if="event.original_url">
          <el-button type="primary" @click="openSource">
            <el-icon><Link /></el-icon>
            查看原文
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Link } from '@element-plus/icons-vue'
import { api } from '../../shared/api'
import type { Event } from '../../shared/types'

const route = useRoute()
const router = useRouter()

const event = ref<Event | null>(null)
const loading = ref(false)

onMounted(async () => {
  const id = route.params.id as string
  const type = (route.query.type as string) || 'historical'

  loading.value = true
  try {
    const result = await api.getEventDetail(parseInt(id), type)
    if (result.code === 0 && result.data) {
      event.value = result.data
    }
  } finally {
    loading.value = false
  }
})

function goBack() {
  router.back()
}

function severityType(severity: string) {
  const types: Record<string, string> = {
    critical: 'danger',
    high: 'danger',
    medium: 'warning',
    low: 'success'
  }
  return types[severity] || 'info'
}

function severityText(severity: string) {
  const texts: Record<string, string> = {
    critical: '严重',
    high: '高危',
    medium: '中危',
    low: '低危'
  }
  return texts[severity] || '未知'
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

function openSource() {
  if (event.value?.original_url) {
    window.open(event.value.original_url, '_blank')
  }
}
</script>

<style scoped>
.event-detail-page {
  background: white;
}

.back-header {
  padding: 12px 16px;
  border-bottom: 1px solid #eee;
}

.content {
  padding: 16px;
}

.title {
  font-size: 20px;
  font-weight: 600;
  color: #333;
  line-height: 1.4;
  margin-bottom: 12px;
}

.meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.cve-id {
  font-family: monospace;
  color: #666;
  font-size: 14px;
}

.source {
  color: #999;
  font-size: 14px;
}

.time {
  color: #999;
  font-size: 14px;
}

.tags {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.description {
  margin-bottom: 24px;
}

.description h3 {
  font-size: 16px;
  margin-bottom: 8px;
  color: #333;
}

.description p {
  color: #666;
  line-height: 1.6;
  white-space: pre-wrap;
}

.source-link {
  padding-top: 16px;
  border-top: 1px solid #eee;
}
</style>
