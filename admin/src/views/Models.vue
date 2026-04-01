<template>
  <div class="models-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>模型管理</span>
          <el-button type="primary" @click="showAddDialog">
            <el-icon><Plus /></el-icon>
            添加模型
          </el-button>
        </div>
      </template>

      <el-table :data="models" v-loading="loading">
        <el-table-column prop="name" label="名称" width="150" />
        <el-table-column prop="vendor" label="厂商" width="150" />
        <el-table-column prop="description" label="描述" show-overflow-tooltip />
        <el-table-column prop="sort_order" label="排序" width="80" />
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="editModel(row)">
              编辑
            </el-button>
            <el-button size="small" text type="danger" @click="deleteModel(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 添加/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑模型' : '添加模型'"
      width="500px"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="模型名称" />
        </el-form-item>
        <el-form-item label="厂商">
          <el-input v-model="form.vendor" placeholder="厂商名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" rows="2" placeholder="模型描述" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" />
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
import { Plus } from '@element-plus/icons-vue'
import { modelApi } from '@/api'

const loading = ref(false)
const models = ref<any[]>([])
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref()

const form = reactive({
  name: '',
  vendor: '',
  description: '',
  sort_order: 0,
  is_active: true
})

const rules = {
  name: [{ required: true, message: '请输入模型名称', trigger: 'blur' }]
}

onMounted(() => loadModels())

async function loadModels() {
  loading.value = true
  try {
    const result: any = await modelApi.getAll()
    models.value = result.data || []
  } finally {
    loading.value = false
  }
}

function showAddDialog() {
  editingId.value = null
  Object.assign(form, {
    name: '',
    vendor: '',
    description: '',
    sort_order: 0,
    is_active: true
  })
  dialogVisible.value = true
}

function editModel(row: any) {
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
      await modelApi.update(editingId.value, form)
      ElMessage.success('更新成功')
    } else {
      await modelApi.create(form)
      ElMessage.success('添加成功')
    }
    dialogVisible.value = false
    loadModels()
  } finally {
    submitting.value = false
  }
}

async function deleteModel(row: any) {
  await ElMessageBox.confirm('确定删除该模型吗？', '提示', { type: 'warning' })
  try {
    await modelApi.delete(row.id)
    ElMessage.success('删除成功')
    loadModels()
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
</style>
