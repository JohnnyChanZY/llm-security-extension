<template>
  <div class="llm-events-page">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-value">{{ stats.by_source?.nvd || 0 }}</div>
            <div class="stat-label">NVD 事件</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-value">{{ stats.by_source?.aiid || 0 }}</div>
            <div class="stat-label">AIID 事件</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-value">{{ stats.by_source?.aivd || 0 }}</div>
            <div class="stat-label">AIVD 事件</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-value">{{ stats.by_source?.rss_passed_filter || stats.by_source?.rss || 0 }}</div>
            <div class="stat-label">RSS 事件（已筛选）</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 筛选区域 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="数据源">
          <el-select v-model="filters.source_type" placeholder="全部" clearable style="width: 120px;">
            <el-option label="NVD" value="nvd" />
            <el-option label="AIID" value="aiid" />
            <el-option label="AIVD" value="aivd" />
            <el-option label="RSS" value="rss" />
          </el-select>
        </el-form-item>
        <el-form-item label="处理状态">
          <el-select v-model="filters.is_processed" placeholder="全部" clearable style="width: 120px;">
            <el-option label="已处理" :value="true" />
            <el-option label="未处理" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="安全事件">
          <el-select v-model="filters.is_security_event" placeholder="全部" clearable style="width: 120px;">
            <el-option label="是" :value="true" />
            <el-option label="否" :value="false" />
            <el-option label="未判断" :value="null" />
          </el-select>
        </el-form-item>
        <el-form-item label="安全等级">
          <el-select v-model="filters.severity" placeholder="全部" clearable style="width: 120px;">
            <el-option label="严重" value="critical" />
            <el-option label="高危" value="high" />
            <el-option label="中危" value="medium" />
            <el-option label="低危" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="搜索标题/描述" clearable style="width: 180px;" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadEvents">搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 批量操作区域 -->
    <el-card class="actions-card">
      <!-- 进度条 -->
      <div v-if="taskStatus.running" class="progress-bar">
        <el-progress
          :percentage="Math.round((taskStatus.processed / taskStatus.total) * 100)"
          :format="() => `${taskStatus.processed}/${taskStatus.total}`"
          :stroke-width="20"
          striped
          striped-flow
        />
        <span class="progress-text">
          处理中... 第 {{ taskStatus.current_batch }}/{{ taskStatus.total_batches }} 批
        </span>
      </div>

      <div class="actions-bar">
        <div class="left">
          <span class="selected-count" v-if="selectedEvents.length > 0">
            已选择 {{ selectedEvents.length }} 条事件
          </span>

          <!-- 操作选项（复选框模式） -->
          <div class="operation-options" v-if="selectedEvents.length > 0">
            <el-checkbox-group v-model="selectedOperations" class="operation-checkboxes">
              <el-checkbox label="judge">判断</el-checkbox>
              <el-checkbox label="rate">评级</el-checkbox>
              <el-checkbox label="classify">分类</el-checkbox>
            </el-checkbox-group>

            <el-button-group class="select-all-group">
              <el-button size="small" @click="selectAllOperations">全选</el-button>
              <el-button size="small" @click="clearAllOperations">清空</el-button>
            </el-button-group>

            <el-button
              type="primary"
              :loading="processing"
              @click="executeSelectedOperations"
              :disabled="selectedOperations.length === 0"
            >
              执行选中操作
            </el-button>

            <el-button type="danger" :loading="processing" @click="confirmBatchDelete">
              删除
            </el-button>
          </div>
        </div>
        <div class="right">
          <el-button @click="loadStats">刷新统计</el-button>
        </div>
      </div>
    </el-card>

    <!-- 事件列表 -->
    <el-card class="table-card">
      <el-table
        :data="events"
        v-loading="loading"
        @selection-change="handleSelectionChange"
        style="width: 100%"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" min-width="250">
          <template #default="{ row }">
            <div class="event-title">
              <span>{{ row.title }}</span>
              <el-link v-if="row.original_url" :href="row.original_url" target="_blank" type="primary">
                <el-icon><Link /></el-icon>
              </el-link>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="source_type" label="来源" width="80">
          <template #default="{ row }">
            <el-tag :type="getSourceTagType(row.source_type)" size="small">
              {{ row.source_type?.toUpperCase() }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_security_event" label="安全事件" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.is_security_event === true" type="success" size="small">是</el-tag>
            <el-tag v-else-if="row.is_security_event === false" type="danger" size="small">否</el-tag>
            <el-tag v-else type="info" size="small">未判断</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="severity" label="等级" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.severity" :type="getSeverityTagType(row.severity)" size="small">
              {{ getSeverityLabel(row.severity) }}
            </el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="category_name" label="分类" width="100">
          <template #default="{ row }">
            <span>{{ row.category_name || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="is_processed" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_processed ? 'success' : 'warning'" size="small">
              {{ row.is_processed ? '已处理' : '未处理' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="入库时间" width="160">
          <template #default="{ row }">
            <span>{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button type="danger" size="small" link @click="confirmDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :total="pagination.total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadEvents"
          @current-change="loadEvents"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Link } from '@element-plus/icons-vue'
import { llmEventsApi, ratingApi } from '@/api'

interface Event {
  id: number
  title: string
  description?: string
  source_type?: string
  source_name?: string
  original_url?: string
  published_at?: string
  category_id?: number
  category_name?: string
  severity?: string
  severity_source?: string
  is_processed: boolean
  is_security_event?: boolean
  is_keyword_filtered?: boolean
  keyword_filter_passed?: boolean
  created_at: string
  event_table: string
}

interface Stats {
  rss?: {
    total: number
    processed: number
    security: number
    non_security: number
    unchecked: number
    filtered: number
    passed_filter: number
  }
  historical?: {
    total: number
    processed: number
    security: number
    non_security: number
    unchecked: number
  }
  by_source?: {
    nvd: number
    aiid: number
    aivd: number
    rss: number
    rss_passed_filter: number
  }
}

interface RatingStatus {
  running: boolean
  total: number
  processed: number
  current_batch: number
  total_batches: number
  error: string | null
  mode: string | null
}

const loading = ref(false)
const processing = ref(false)
const events = ref<Event[]>([])
const selectedEvents = ref<Event[]>([])
const stats = ref<Stats>({})

// 选中的操作类型
const selectedOperations = ref<string[]>([])

// 任务状态
const taskStatus = ref<RatingStatus>({
  running: false,
  total: 0,
  processed: 0,
  current_batch: 0,
  total_batches: 0,
  error: null,
  mode: null
})

// 轮询定时器
let pollTimer: ReturnType<typeof setInterval> | null = null

const filters = reactive({
  source_type: '',
  is_processed: null as boolean | null,
  is_security_event: null as boolean | null,
  severity: '',
  keyword: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

onMounted(() => {
  loadStats()
  loadEvents()
  checkTaskStatus()
})

onUnmounted(() => {
  stopPolling()
})

// 开始轮询
function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    await checkTaskStatus()
  }, 2000)
}

// 停止轮询
function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// 检查任务状态
async function checkTaskStatus() {
  try {
    const res: any = await ratingApi.getStatus()
    if (res.data) {
      const prevRunning = taskStatus.value.running
      const prevProcessed = taskStatus.value.processed
      taskStatus.value = res.data

      // 任务运行中，开始轮询
      if (res.data.running) {
        processing.value = true
        if (!pollTimer) {
          startPolling()
        }

        // 有新处理的数据，局部更新列表状态（不清除选中）
        if (res.data.processed > prevProcessed) {
          await refreshEventStatuses()
        }
      }

      // 任务完成
      if (!res.data.running && prevRunning) {
        processing.value = false
        stopPolling()

        if (res.data.error) {
          ElMessage.error(res.data.error)
        } else {
          ElMessage.success(`处理完成，共处理 ${res.data.processed} 条事件`)
        }

        // 最后刷新一次统计
        loadStats()
      }
    }
  } catch (e) {
    console.error('检查任务状态失败', e)
  }
}

// 局部刷新事件状态（保留选中状态）
async function refreshEventStatuses() {
  try {
    const params: any = {
      page: pagination.page,
      page_size: pagination.page_size
    }
    if (filters.source_type) params.source_type = filters.source_type
    if (filters.is_processed !== null) params.is_processed = filters.is_processed
    if (filters.is_security_event !== null) params.is_security_event = filters.is_security_event
    if (filters.severity) params.severity = filters.severity
    if (filters.keyword) params.keyword = filters.keyword

    const res: any = await llmEventsApi.getEvents(params)
    if (res.data) {
      // 创建 ID 到新数据的映射
      const newEventsMap = new Map(res.data.items.map((e: Event) => [e.id, e]))

      // 更新现有事件的状态，保持顺序
      events.value = events.value.map(event => {
        const updated = newEventsMap.get(event.id)
        if (updated) {
          // 只更新状态相关字段
          return {
            ...event,
            is_processed: updated.is_processed,
            is_security_event: updated.is_security_event,
            severity: updated.severity,
            severity_source: updated.severity_source,
            category_id: updated.category_id,
            category_name: updated.category_name,
            cvss_score: updated.cvss_score
          }
        }
        return event
      })
    }
  } catch (e) {
    console.error('刷新事件状态失败', e)
  }
}

async function loadStats() {
  try {
    const res: any = await llmEventsApi.getStats()
    if (res.data) {
      stats.value = res.data
    }
  } catch (e) {
    // error handled
  }
}

async function loadEvents() {
  loading.value = true
  try {
    const params: any = {
      page: pagination.page,
      page_size: pagination.page_size
    }
    if (filters.source_type) params.source_type = filters.source_type
    if (filters.is_processed !== null) params.is_processed = filters.is_processed
    if (filters.is_security_event !== null) params.is_security_event = filters.is_security_event
    if (filters.severity) params.severity = filters.severity
    if (filters.keyword) params.keyword = filters.keyword

    const res: any = await llmEventsApi.getEvents(params)
    if (res.data) {
      events.value = res.data.items
      pagination.total = res.data.total
    }
  } catch (e) {
    // error handled
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.source_type = ''
  filters.is_processed = null
  filters.is_security_event = null
  filters.severity = ''
  filters.keyword = ''
  pagination.page = 1
  loadEvents()
}

function handleSelectionChange(selection: Event[]) {
  selectedEvents.value = selection
}

// 全选操作
function selectAllOperations() {
  selectedOperations.value = ['judge', 'rate', 'classify']
}

// 清空操作选择
function clearAllOperations() {
  selectedOperations.value = []
}

// 执行选中的操作
async function executeSelectedOperations() {
  if (selectedEvents.value.length === 0) {
    ElMessage.warning('请选择要处理的事件')
    return
  }

  if (selectedOperations.value.length === 0) {
    ElMessage.warning('请至少选择一个操作')
    return
  }

  // 检查是否已有任务在运行
  if (taskStatus.value.running) {
    ElMessage.warning('已有任务在运行中，请等待完成')
    return
  }

  processing.value = true
  try {
    const eventTable = selectedEvents.value[0].event_table
    const eventIds = selectedEvents.value.map(e => e.id)

    const res: any = await ratingApi.batchOperations({
      event_ids: eventIds,
      event_type: eventTable === 'rss' ? 'rss' : 'historical',
      operations: selectedOperations.value
    })

    ElMessage.success(res.message || '任务已启动')

    // 开始轮询状态
    startPolling()
  } catch (e) {
    processing.value = false
    // error handled
  }
}

function getSourceTagType(source: string): string {
  const map: Record<string, string> = {
    nvd: 'info',
    aiid: 'success',
    aivd: 'warning',
    rss: 'primary'
  }
  return map[source] || 'info'
}

function getSeverityTagType(severity: string): string {
  const map: Record<string, string> = {
    critical: 'danger',
    high: 'warning',
    medium: 'info',
    low: 'success'
  }
  return map[severity] || 'info'
}

function getSeverityLabel(severity: string): string {
  const map: Record<string, string> = {
    critical: '严重',
    high: '高危',
    medium: '中危',
    low: '低危'
  }
  return map[severity] || severity
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 单个删除确认
function confirmDelete(event: Event) {
  ElMessageBox.confirm(
    `确定要删除事件 "${event.title}" 吗？`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    deleteEvent(event)
  }).catch(() => {
    // 取消删除
  })
}

// 删除单个事件
async function deleteEvent(event: Event) {
  try {
    await llmEventsApi.deleteEvent(event.id, event.event_table)
    ElMessage.success('删除成功')
    loadEvents()
    loadStats()
  } catch (e) {
    // error handled
  }
}

// 批量删除确认
function confirmBatchDelete() {
  if (selectedEvents.value.length === 0) {
    ElMessage.warning('请选择要删除的事件')
    return
  }

  ElMessageBox.confirm(
    `确定要删除选中的 ${selectedEvents.value.length} 条事件吗？`,
    '批量删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(() => {
    batchDeleteEvents()
  }).catch(() => {
    // 取消删除
  })
}

// 批量删除事件
async function batchDeleteEvents() {
  processing.value = true
  try {
    const eventTable = selectedEvents.value[0].event_table
    const eventIds = selectedEvents.value.map(e => e.id)

    const res: any = await llmEventsApi.batchDelete(eventIds, eventTable)
    ElMessage.success(res.message || '删除成功')
    selectedEvents.value = []
    loadEvents()
    loadStats()
  } catch (e) {
    // error handled
  } finally {
    processing.value = false
  }
}
</script>

<style scoped>
.llm-events-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stats-row {
  margin-bottom: 0;
}

.stat-card {
  text-align: center;
}

.stat-content {
  padding: 8px 0;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #1890ff;
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-top: 4px;
}

.filter-card {
  margin-bottom: 0;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.actions-card {
  margin-bottom: 0;
}

.progress-bar {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.progress-bar .el-progress {
  flex: 1;
}

.progress-text {
  color: #1890ff;
  font-size: 14px;
  white-space: nowrap;
}

.actions-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.selected-count {
  font-size: 14px;
  color: #1890ff;
  margin-right: 16px;
}

.operation-options {
  display: flex;
  align-items: center;
  gap: 16px;
}

.operation-checkboxes {
  display: flex;
  gap: 12px;
}

.select-all-group {
  margin-left: 8px;
}

.table-card {
  margin-bottom: 0;
}

.event-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.event-title span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.text-muted {
  color: #999;
}

.pagination-wrapper {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
