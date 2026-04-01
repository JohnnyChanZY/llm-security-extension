<template>
  <div class="config-page">
    <el-card>
      <template #header>
        <span>LLM配置</span>
      </template>

      <el-form :model="form" label-width="140px" v-loading="loading">
        <el-form-item label="自动分类">
          <el-switch
            v-model="form.llm_classify_enabled"
            active-text="开启"
            inactive-text="关闭"
          />
          <div class="form-tip">开启后，新事件将自动通过LLM进行分类</div>
        </el-form-item>

        <el-form-item label="自动评级">
          <el-switch
            v-model="form.llm_rating_enabled"
            active-text="开启"
            inactive-text="关闭"
          />
          <div class="form-tip">开启后，新事件将自动通过LLM进行安全等级评估</div>
        </el-form-item>

        <el-form-item label="批量大小">
          <el-input-number
            v-model="form.llm_batch_size"
            :min="1"
            :max="form.max_batch_size || 100"
          />
          <div class="form-tip">每批次处理的事件数量（手动和自动通用）</div>
        </el-form-item>

        <el-form-item label="最大并发批次">
          <el-input-number
            v-model="form.llm_max_concurrent_batches"
            :min="1"
            :max="form.max_concurrent_batches || 10"
          />
          <div class="form-tip">多批数据并行处理时的最大并发数（判断和评级通用，建议2-5）</div>
        </el-form-item>

        <el-form-item label="请求间隔">
          <el-input-number
            v-model="form.llm_request_interval"
            :min="0"
            :max="form.max_request_interval || 60"
            :step="0.5"
            :precision="1"
          />
          <span class="unit-label">秒</span>
          <div class="form-tip">每批并发请求之间的等待时间，用于控制请求频率，避免触发API速率限制</div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="saveConfig" :loading="saving">
            保存配置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="info-card">
      <template #header>
        <span>并行处理说明</span>
      </template>
      <div class="info-content">
        <p><strong>批量大小</strong>：单次LLM调用处理的事件数量。较大的值可以减少API调用次数，但单次调用时间更长。</p>
        <p><strong>最大并发批次</strong>：每批次同时发送的请求数量。</p>
        <p><strong>请求间隔</strong>：每批并发请求完成后的等待时间。</p>
        <ul>
          <li>例如：100条数据，批量大小30，则分为4批</li>
          <li>若最大并发批次为2，请求间隔为2秒</li>
          <li>则第1批2个请求同时发送 → 等待响应 → 等待2秒 → 第2批2个请求同时发送 → ...</li>
          <li>判断和评级两个阶段都会使用此控制策略</li>
        </ul>
        <p class="warning">注意：并发数过高或间隔过短可能触发LLM API的速率限制，建议根据API配额调整。</p>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { configApi } from '@/api'

const loading = ref(false)
const saving = ref(false)

const form = reactive({
  llm_classify_enabled: false,
  llm_rating_enabled: false,
  llm_batch_size: 30,
  llm_max_concurrent_batches: 3,
  llm_request_interval: 2.0,
  max_batch_size: 100,
  max_concurrent_batches: 10,
  max_request_interval: 60.0
})

onMounted(async () => {
  loading.value = true
  try {
    const result: any = await configApi.getLLM()
    if (result.data) {
      Object.assign(form, result.data)
    }
  } finally {
    loading.value = false
  }
})

async function saveConfig() {
  saving.value = true
  try {
    await configApi.update('llm_classify_enabled', String(form.llm_classify_enabled))
    await configApi.update('llm_rating_enabled', String(form.llm_rating_enabled))
    await configApi.update('llm_batch_size', String(form.llm_batch_size))
    await configApi.update('llm_max_concurrent_batches', String(form.llm_max_concurrent_batches))
    await configApi.update('llm_request_interval', String(form.llm_request_interval))
    ElMessage.success('配置保存成功')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.config-page {
  max-width: 700px;
}

.form-tip {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.unit-label {
  margin-left: 8px;
  color: #666;
}

.info-card {
  margin-top: 20px;
}

.info-content {
  font-size: 14px;
  color: #666;
  line-height: 1.8;
}

.info-content p {
  margin: 8px 0;
}

.info-content ul {
  margin: 8px 0;
  padding-left: 20px;
}

.info-content li {
  margin: 4px 0;
}

.warning {
  color: #e6a23c;
  font-weight: 500;
}
</style>
