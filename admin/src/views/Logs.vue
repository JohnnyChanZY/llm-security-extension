<template>
  <div class="logs-page">
    <el-card>
      <template #header>
        <span>操作日志</span>
      </template>

      <el-table :data="logs" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="user_id" label="用户ID" width="100" />
        <el-table-column prop="action" label="操作" width="150" />
        <el-table-column prop="target_type" label="目标类型" width="120" />
        <el-table-column prop="target_id" label="目标ID" width="100" />
        <el-table-column prop="details" label="详情" show-overflow-tooltip />
        <el-table-column prop="ip_address" label="IP地址" width="130" />
        <el-table-column prop="created_at" label="时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          :page-size="20"
          :total="total"
          layout="prev, pager, next"
          @current-change="loadLogs"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const loading = ref(false)
const logs = ref<any[]>([])
const page = ref(1)
const total = ref(0)

onMounted(() => loadLogs())

async function loadLogs() {
  loading.value = true
  try {
    // TODO: 调用API获取日志
    // const result = await logsApi.getAll({ page: page.value })
    // logs.value = result.data?.items || []
    // total.value = result.data?.total || 0
    logs.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString('zh-CN')
}
</script>

<style scoped>
.pagination {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
</style>
