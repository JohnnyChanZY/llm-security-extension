<template>
  <div class="data-sync-page">
    <el-row :gutter="24">
      <!-- NVD 同步卡片 -->
      <el-col :span="8">
        <el-card class="sync-card">
          <template #header>
            <div class="card-header">
              <span class="title">NVD 数据源</span>
              <el-tag type="info">National Vulnerability Database</el-tag>
            </div>
          </template>

          <div class="card-content">
            <p class="description">
              从美国国家漏洞数据库获取 CVE 漏洞数据，包含详细的 CVSS 评分和影响范围信息。
            </p>

            <div class="sync-options">
              <span class="label">同步范围：</span>
              <el-select v-model="nvdDays" size="small" style="width: 120px;">
                <el-option label="最近 7 天" :value="7" />
                <el-option label="最近 30 天" :value="30" />
                <el-option label="最近 90 天" :value="90" />
              </el-select>
            </div>

            <el-button
              type="primary"
              :loading="syncing.nvd"
              @click="syncNVD"
              style="width: 100%; margin-top: 16px;"
            >
              <el-icon v-if="!syncing.nvd"><Download /></el-icon>
              {{ syncing.nvd ? '同步中...' : '开始同步' }}
            </el-button>

            <div v-if="results.nvd" class="result-box">
              <el-alert
                :title="results.nvd.message"
                :type="results.nvd.new_count > 0 ? 'success' : 'info'"
                :closable="false"
                show-icon
              />
              <div class="result-stats">
                <span>新增: {{ results.nvd.new_count }} 条</span>
                <span>总计: {{ results.nvd.total_count }} 条</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- AIID 同步卡片 -->
      <el-col :span="8">
        <el-card class="sync-card">
          <template #header>
            <div class="card-header">
              <span class="title">AIID 数据源</span>
              <el-tag type="success">AI Incident Database</el-tag>
            </div>
          </template>

          <div class="card-content">
            <p class="description">
              从 AI 事件数据库获取 AI 相关安全事件报告，涵盖 AI 系统的实际危害事件和近失事件。
            </p>

            <el-button
              type="success"
              :loading="syncing.aiid"
              @click="syncAIID"
              style="width: 100%; margin-top: 50px;"
            >
              <el-icon v-if="!syncing.aiid"><Download /></el-icon>
              {{ syncing.aiid ? '同步中...' : '开始同步' }}
            </el-button>

            <div v-if="results.aiid" class="result-box">
              <el-alert
                :title="results.aiid.message"
                :type="results.aiid.new_count > 0 ? 'success' : 'info'"
                :closable="false"
                show-icon
              />
              <div class="result-stats">
                <span>新增: {{ results.aiid.new_count }} 条</span>
                <span>总计: {{ results.aiid.total_count }} 条</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- AIVD 同步卡片 -->
      <el-col :span="8">
        <el-card class="sync-card">
          <template #header>
            <div class="card-header">
              <span class="title">AIVD 数据源</span>
              <el-tag type="warning">AI Vulnerability Database</el-tag>
            </div>
          </template>

          <div class="card-content">
            <p class="description">
              从 AVID 数据库获取 AI 模型漏洞报告，专注于机器学习模型的特定漏洞和风险评估。
            </p>

            <el-button
              type="warning"
              :loading="syncing.aivd"
              @click="syncAIVD"
              style="width: 100%; margin-top: 50px;"
            >
              <el-icon v-if="!syncing.aivd"><Download /></el-icon>
              {{ syncing.aivd ? '同步中...' : '开始同步' }}
            </el-button>

            <div v-if="results.aivd" class="result-box">
              <el-alert
                :title="results.aivd.message"
                :type="results.aivd.new_count > 0 ? 'success' : 'info'"
                :closable="false"
                show-icon
              />
              <div class="result-stats">
                <span>新增: {{ results.aivd.new_count }} 条</span>
                <span>总计: {{ results.aivd.total_count }} 条</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 使用提示 -->
    <el-card class="tips-card">
      <template #header>
        <span>使用说明</span>
      </template>
      <el-alert type="info" :closable="false">
        <template #title>
          <p>1. NVD 数据同步需要配置 NVD_API_KEY 以获得更快的请求速度（可选）</p>
          <p>2. AIID 数据需要下载较大的压缩包文件，同步时间可能较长</p>
          <p>3. AIVD 数据需要克隆 GitHub 仓库，请确保网络可以访问 GitHub</p>
          <p>4. 数据同步会自动跳过已存在的记录，可多次执行</p>
        </template>
      </el-alert>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import { syncApi } from '@/api'

const nvdDays = ref(30)

const syncing = reactive({
  nvd: false,
  aiid: false,
  aivd: false
})

const results = reactive<{
  nvd: null | { new_count: number; total_count: number; message: string }
  aiid: null | { new_count: number; total_count: number; message: string }
  aivd: null | { new_count: number; total_count: number; message: string }
}>({
  nvd: null,
  aiid: null,
  aivd: null
})

async function syncNVD() {
  syncing.nvd = true
  results.nvd = null
  try {
    const res: any = await syncApi.syncNVD(nvdDays.value)
    if (res.data) {
      results.nvd = res.data
      ElMessage.success('NVD 数据同步完成')
    }
  } catch (e) {
    // error handled in interceptor
  } finally {
    syncing.nvd = false
  }
}

async function syncAIID() {
  syncing.aiid = true
  results.aiid = null
  try {
    const res: any = await syncApi.syncAIID()
    if (res.data) {
      results.aiid = res.data
      ElMessage.success('AIID 数据同步完成')
    }
  } catch (e) {
    // error handled in interceptor
  } finally {
    syncing.aiid = false
  }
}

async function syncAIVD() {
  syncing.aivd = true
  results.aivd = null
  try {
    const res: any = await syncApi.syncAIVD()
    if (res.data) {
      results.aivd = res.data
      ElMessage.success('AIVD 数据同步完成')
    }
  } catch (e) {
    // error handled in interceptor
  } finally {
    syncing.aivd = false
  }
}
</script>

<style scoped>
.data-sync-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.sync-card {
  height: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-header .title {
  font-size: 16px;
  font-weight: 600;
}

.card-content {
  min-height: 200px;
}

.description {
  color: #666;
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
}

.sync-options {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.sync-options .label {
  font-size: 14px;
  color: #333;
}

.result-box {
  margin-top: 16px;
}

.result-stats {
  display: flex;
  justify-content: space-around;
  margin-top: 12px;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 13px;
  color: #606266;
}

.tips-card {
  margin-top: 0;
}

.tips-card :deep(.el-alert__title) p {
  margin: 4px 0;
  line-height: 1.6;
}
</style>
