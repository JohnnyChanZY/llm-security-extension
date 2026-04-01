<template>
  <div class="search-page">
    <!-- 搜索框 -->
    <div class="search-header">
      <el-input
        v-model="keyword"
        placeholder="搜索事件..."
        prefix-icon="Search"
        clearable
        @keyup.enter="handleSearch"
      >
        <template #append>
          <el-button @click="handleSearch">搜索</el-button>
        </template>
      </el-input>
    </div>

    <!-- 筛选条件 -->
    <div class="filters">
      <el-select
        v-model="filters.severity"
        placeholder="安全等级"
        clearable
        @change="handleSearch"
      >
        <el-option label="严重" value="critical" />
        <el-option label="高危" value="high" />
        <el-option label="中危" value="medium" />
        <el-option label="低危" value="low" />
      </el-select>

      <el-select
        v-model="filters.category"
        placeholder="分类"
        clearable
        @change="handleSearch"
      >
        <el-option
          v-for="cat in categoryStore.categories"
          :key="cat.code"
          :label="cat.name"
          :value="cat.code"
        />
      </el-select>

      <el-select
        v-model="filters.model_id"
        placeholder="模型"
        clearable
        @change="handleSearch"
      >
        <el-option
          v-for="model in modelStore.models"
          :key="model.id"
          :label="model.name"
          :value="model.id"
        />
      </el-select>
    </div>

    <!-- 搜索结果 -->
    <div class="results" v-loading="eventStore.loading">
      <div v-if="!searched" class="placeholder">
        <el-empty description="输入关键词搜索事件" />
      </div>
      <div v-else-if="eventStore.events.length === 0" class="empty">
        <el-empty description="未找到相关事件" />
      </div>
      <div v-else>
        <p class="result-count">找到 {{ eventStore.total }} 条结果</p>

        <EventCard
          v-for="event in eventStore.events"
          :key="event.id"
          :event="event"
          @click="goToDetail(event)"
        />

        <!-- 分页 -->
        <div class="pagination">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="20"
            :total="eventStore.total"
            layout="prev, pager, next"
            @current-change="handlePageChange"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useEventStore, useCategoryStore, useModelStore } from '../../shared/stores'
import EventCard from '../components/EventCard.vue'

const router = useRouter()
const eventStore = useEventStore()
const categoryStore = useCategoryStore()
const modelStore = useModelStore()

const keyword = ref('')
const searched = ref(false)
const currentPage = ref(1)

const filters = reactive({
  severity: '',
  category: '',
  model_id: null as number | null
})

onMounted(async () => {
  await categoryStore.fetchCategories()
  await modelStore.fetchModels()
})

async function handleSearch() {
  searched.value = true
  currentPage.value = 1
  await doSearch()
}

async function doSearch() {
  await eventStore.fetchEvents({
    page: currentPage.value,
    keyword: keyword.value || undefined,
    severity: filters.severity || undefined,
    category: filters.category || undefined,
    model_id: filters.model_id || undefined
  })
}

async function handlePageChange(page: number) {
  currentPage.value = page
  await doSearch()
}

function goToDetail(event: any) {
  router.push({
    path: `/event/${event.id}`,
    query: { type: event.source_type || 'historical' }
  })
}
</script>

<style scoped>
.search-page {
  background: white;
}

.search-header {
  padding: 16px;
  background: white;
}

.filters {
  padding: 0 16px 16px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filters .el-select {
  width: 120px;
}

.results {
  padding: 16px;
}

.placeholder, .empty {
  padding: 40px 0;
}

.result-count {
  color: #999;
  font-size: 14px;
  margin-bottom: 12px;
}

.pagination {
  display: flex;
  justify-content: center;
  padding: 16px 0;
}
</style>
