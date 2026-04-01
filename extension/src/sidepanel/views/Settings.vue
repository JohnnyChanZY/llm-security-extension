<template>
  <div class="settings-page">
    <h2>设置</h2>

    <!-- 用户信息 -->
    <el-card class="user-card">
      <template #header>
        <span>账号信息</span>
      </template>
      <div class="user-info">
        <el-avatar :size="48">
          {{ authStore.user?.nickname?.[0] || authStore.user?.email?.[0] }}
        </el-avatar>
        <div class="info">
          <div class="nickname">{{ authStore.user?.nickname || '未设置昵称' }}</div>
          <div class="email">{{ authStore.user?.email }}</div>
        </div>
      </div>
    </el-card>

    <!-- 关注设置 -->
    <el-card class="preference-card">
      <template #header>
        <div class="card-header">
          <span>关注设置</span>
          <el-button type="primary" size="small" @click="showAddDialog = true">
            添加关注
          </el-button>
        </div>
      </template>

      <div v-if="preferenceStore.loading" class="loading">
        <el-skeleton :rows="3" animated />
      </div>
      <div v-else-if="preferenceStore.preferences.length === 0" class="empty">
        <el-empty description="暂无关注设置" />
      </div>
      <div v-else class="preference-list">
        <div
          v-for="pref in preferenceStore.preferences"
          :key="pref.id"
          class="preference-item"
        >
          <div class="pref-info">
            <span v-if="pref.model_name" class="tag">{{ pref.model_name }}</span>
            <span v-if="pref.category_name" class="tag">{{ pref.category_name }}</span>
          </div>
          <div class="actions">
            <el-switch
              v-model="pref.is_enabled"
              @change="handleTogglePreference(pref)"
            />
            <el-button
              type="danger"
              size="small"
              text
              @click="handleDeletePreference(pref.id)"
            >
              删除
            </el-button>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 添加关注对话框 -->
    <el-dialog v-model="showAddDialog" title="添加关注" width="90%">
      <el-form :model="addForm" label-width="80px">
        <el-form-item label="模型">
          <el-select v-model="addForm.model_id" placeholder="选择模型（可选）" clearable>
            <el-option
              v-for="model in modelStore.models"
              :key="model.id"
              :label="model.name"
              :value="model.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="addForm.category_id" placeholder="选择分类（可选）" clearable>
            <el-option
              v-for="cat in categoryStore.categories"
              :key="cat.id"
              :label="cat.name"
              :value="cat.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAddPreference">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore, usePreferenceStore, useCategoryStore, useModelStore } from '../../shared/stores'

const authStore = useAuthStore()
const preferenceStore = usePreferenceStore()
const categoryStore = useCategoryStore()
const modelStore = useModelStore()

const showAddDialog = ref(false)
const addForm = reactive({
  model_id: null as number | null,
  category_id: null as number | null
})

onMounted(async () => {
  await preferenceStore.fetchPreferences()
  await categoryStore.fetchCategories()
  await modelStore.fetchModels()
})

async function handleTogglePreference(pref: any) {
  const result = await preferenceStore.updatePreference(pref.id, pref.is_enabled)
  if (result.code !== 0) {
    ElMessage.error(result.message || '更新失败')
    // 回滚状态
    pref.is_enabled = !pref.is_enabled
  }
}

async function handleDeletePreference(id: number) {
  const result = await preferenceStore.deletePreference(id)
  if (result.code === 0) {
    ElMessage.success('删除成功')
    await preferenceStore.fetchPreferences()
  } else {
    ElMessage.error(result.message || '删除失败')
  }
}

async function handleAddPreference() {
  if (!addForm.model_id && !addForm.category_id) {
    ElMessage.warning('请至少选择一个模型或分类')
    return
  }

  const result = await preferenceStore.addPreference({
    model_id: addForm.model_id || undefined,
    category_id: addForm.category_id || undefined
  })

  if (result.code === 0) {
    ElMessage.success('添加成功')
    showAddDialog.value = false
    addForm.model_id = null
    addForm.category_id = null
    await preferenceStore.fetchPreferences()
  } else {
    ElMessage.error(result.message || '添加失败')
  }
}
</script>

<style scoped>
.settings-page {
  padding: 16px;
}

h2 {
  margin-bottom: 16px;
  color: #333;
}

.user-card {
  margin-bottom: 16px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.info .nickname {
  font-weight: 500;
  color: #333;
}

.info .email {
  font-size: 12px;
  color: #999;
}

.preference-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.preference-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.preference-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
}

.pref-info .tag {
  display: inline-block;
  padding: 4px 8px;
  margin-right: 8px;
  background: #e6f0ff;
  color: #409eff;
  border-radius: 4px;
  font-size: 12px;
}

.actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
