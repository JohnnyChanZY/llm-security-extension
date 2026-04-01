<template>
  <div class="event-card" @click="$emit('click')">
    <div class="header">
      <el-tag
        v-if="event.severity"
        :type="severityType(event.severity)"
        size="small"
        effect="dark"
      >
        {{ severityText(event.severity) }}
      </el-tag>
      <span v-if="event.cve_id" class="cve-id">{{ event.cve_id }}</span>
    </div>

    <h3 class="title">{{ event.title }}</h3>

    <p class="description" v-if="event.description">
      {{ truncate(event.description, 100) }}
    </p>

    <div class="footer">
      <span class="source">{{ event.source_name }}</span>
      <span class="time">{{ formatTime(event.published_at) }}</span>
    </div>

    <div class="tags" v-if="event.category || event.affected_models?.length">
      <el-tag v-if="event.category" type="info" size="small">
        {{ event.category.name }}
      </el-tag>
      <el-tag
        v-for="model in event.affected_models?.slice(0, 2)"
        :key="model.id"
        type="warning"
        size="small"
      >
        {{ model.name }}
      </el-tag>
      <span
        v-if="event.affected_models?.length > 2"
        class="more"
      >
        +{{ event.affected_models.length - 2 }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Event } from '../../shared/types'

defineProps<{
  event: Event
}>()

defineEmits<{
  click: []
}>()

function severityType(severity: string | null) {
  const types: Record<string, string> = {
    critical: 'danger',
    high: 'danger',
    medium: 'warning',
    low: 'success'
  }
  return types[severity || ''] || 'info'
}

function severityText(severity: string | null) {
  const texts: Record<string, string> = {
    critical: '严重',
    high: '高危',
    medium: '中危',
    low: '低危'
  }
  return texts[severity || ''] || '未知'
}

function truncate(text: string, length: number) {
  return text.length > length ? text.slice(0, length) + '...' : text
}

function formatTime(dateStr: string | null) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`
  return date.toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.event-card {
  background: white;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.event-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.cve-id {
  font-family: monospace;
  font-size: 12px;
  color: #666;
}

.title {
  font-size: 15px;
  font-weight: 500;
  color: #333;
  line-height: 1.4;
  margin-bottom: 8px;
}

.description {
  font-size: 13px;
  color: #666;
  line-height: 1.5;
  margin-bottom: 8px;
}

.footer {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #999;
  margin-bottom: 8px;
}

.tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}

.more {
  font-size: 12px;
  color: #999;
}
</style>
