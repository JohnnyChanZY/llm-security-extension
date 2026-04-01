<template>
  <div class="rss-sources-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>RSS数据源管理</span>
          <div class="header-buttons">
            <el-button type="success" @click="crawlAllSources" :loading="crawlingAll">
              <el-icon><Refresh /></el-icon>
              一键爬取
            </el-button>
            <el-button type="primary" @click="showAddDialog">
              <el-icon><Plus /></el-icon>
              添加数据源
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="sources" v-loading="loading">
        <el-table-column prop="name" label="名称" width="150" />
        <el-table-column prop="rss_url" label="URL" show-overflow-tooltip />
        <el-table-column prop="source_type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ typeText(row.source_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="crawl_interval" label="爬取间隔" width="100">
          <template #default="{ row }">{{ row.crawl_interval }} 分钟</template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_crawled_at" label="最后爬取" width="160">
          <template #default="{ row }">
            {{ row.last_crawled_at ? formatDate(row.last_crawled_at) : '未爬取' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="validateSource(row)">
              验证
            </el-button>
            <el-button size="small" text type="primary" @click="crawlSource(row)">
              爬取
            </el-button>
            <el-button size="small" text type="primary" @click="editSource(row)">
              编辑
            </el-button>
            <el-button size="small" text type="danger" @click="deleteSource(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑数据源' : '添加数据源'"
      width="500px"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="数据源名称" />
        </el-form-item>
        <el-form-item label="URL" prop="rss_url">
          <el-input v-model="form.rss_url" placeholder="RSS链接" />
        </el-form-item>
        <el-form-item label="类型" prop="source_type">
          <el-select v-model="form.source_type" style="width: 100%">
            <el-option label="微信公众号" value="wechat" />
            <el-option label="安全博客" value="blog" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="爬取间隔">
          <el-input-number v-model="form.crawl_interval" :min="5" :max="1440" />
          <span style="margin-left: 8px; color: #999;">分钟</span>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { rssApi } from '@/api'

const loading = ref(false)
const crawlingAll = ref(false)
const sources = ref<any[]>([])
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref()

const form = reactive({
  name: '',
  rss_url: '',
  source_type: 'other',
  crawl_interval: 60,
  is_active: true
})

const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  rss_url: [
    { required: true, message: '请输入RSS链接', trigger: 'blur' },
    { type: 'url', message: '请输入有效的URL', trigger: 'blur' }
  ]
}

onMounted(() => loadSources())

async function loadSources() {
  loading.value = true
  try {
    const result: any = await rssApi.getAll()
    sources.value = result.data || []
  } finally {
    loading.value = false
  }
}

function typeText(type: string) {
  const texts: Record<string, string> = {
    wechat: '微信公众号',
    blog: '安全博客',
    other: '其他'
  }
  return texts[type] || type
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString('zh-CN')
}

function showAddDialog() {
  editingId.value = null
  Object.assign(form, {
    name: '',
    rss_url: '',
    source_type: 'other',
    crawl_interval: 60,
    is_active: true
  })
  dialogVisible.value = true
}

function editSource(row: any) {
  editingId.value = row.id
  Object.assign(form, row)
  dialogVisible.value = true
}

async function submitForm() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (editingId.value) {
      await rssApi.update(editingId.value, form)
      ElMessage.success('更新成功')
    } else {
      await rssApi.create(form)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    loadSources()
  } finally {
    submitting.value = false
  }
}

async function validateSource(row: any) {
  try {
    const result: any = await rssApi.validate(row.id)
    if (result.data?.valid) {
      ElMessage.success(`验证成功: ${result.data.title || '有效RSS源'}`)
    } else {
      ElMessage.error(result.data?.message || '验证失败')
    }
  } catch (e) {
    // error handled
  }
}

async function crawlSource(row: any) {
  try {
    await rssApi.crawl(row.id)
    ElMessage.success('爬取任务已触发')
    loadSources()
  } catch (e) {
    // error handled
  }
}

async function crawlAllSources() {
  crawlingAll.value = true
  try {
    const result: any = await rssApi.crawlAll()
    ElMessage.success(result.message || '爬取完成')
    loadSources()
  } finally {
    crawlingAll.value = false
  }
}

async function deleteSource(row: any) {
  await ElMessageBox.confirm('确定删除该数据源吗？', '提示', { type: 'warning' })
  try {
    await rssApi.delete(row.id)
    ElMessage.success('删除成功')
    loadSources()
  } catch (e) {
    // error handled
  }
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-buttons {
  display: flex;
  gap: 8px;
}
</style>
