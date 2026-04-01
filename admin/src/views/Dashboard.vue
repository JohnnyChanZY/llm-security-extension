<template>
  <div class="dashboard-page">
    <el-row :gutter="24">
      <!-- 统计卡片 -->
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: #1890ff;">
            <el-icon size="24"><Document /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.eventCount }}</div>
            <div class="stat-label">安全事件</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: #52c41a;">
            <el-icon size="24"><Link /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.rssCount }}</div>
            <div class="stat-label">RSS数据源</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: #faad14;">
            <el-icon size="24"><User /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.userCount }}</div>
            <div class="stat-label">注册用户</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: #722ed1;">
            <el-icon size="24"><Box /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.modelCount }}</div>
            <div class="stat-label">预设模型</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- LLM配置状态 -->
    <el-card class="config-card">
      <template #header>
        <span>LLM配置状态</span>
      </template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="自动分类">
          <el-tag :type="config.llm_classify_enabled ? 'success' : 'info'">
            {{ config.llm_classify_enabled ? '已开启' : '已关闭' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="自动评级">
          <el-tag :type="config.llm_rating_enabled ? 'success' : 'info'">
            {{ config.llm_rating_enabled ? '已开启' : '已关闭' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="批量大小">
          {{ config.llm_batch_size }} 条/批次
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 快捷操作 -->
    <el-card class="actions-card">
      <template #header>
        <span>快捷操作</span>
      </template>
      <el-space>
        <el-button type="primary" @click="triggerSync">
          <el-icon><Refresh /></el-icon>
          同步历史数据
        </el-button>
        <el-button @click="triggerRating">
          <el-icon><MagicStick /></el-icon>
          触发LLM评级
        </el-button>
        <el-button @click="router.push('/config')">
          <el-icon><Setting /></el-icon>
          系统配置
        </el-button>
      </el-space>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Document, Link, User, Box, Refresh, MagicStick, Setting } from '@element-plus/icons-vue'
import { configApi, ratingApi } from '@/api'

const router = useRouter()

const stats = reactive({
  eventCount: 0,
  rssCount: 0,
  userCount: 0,
  modelCount: 0
})

const config = reactive({
  llm_classify_enabled: false,
  llm_rating_enabled: false,
  llm_batch_size: 30
})

onMounted(async () => {
  await loadConfig()
})

async function loadConfig() {
  try {
    const result: any = await configApi.getLLM()
    if (result.data) {
      Object.assign(config, result.data)
    }
  } catch (e) {
    // ignore
  }
}

async function triggerSync() {
  ElMessage.info('历史数据同步任务已在后台运行')
}

async function triggerRating() {
  try {
    await ratingApi.trigger()
    ElMessage.success('LLM评级任务已触发')
  } catch (e) {
    // error handled in interceptor
  }
}
</script>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 20px;
}

.stat-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 20px;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  margin-right: 16px;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #333;
}

.stat-label {
  font-size: 14px;
  color: #999;
  margin-top: 4px;
}

.config-card, .actions-card {
  margin-top: 0;
}
</style>
