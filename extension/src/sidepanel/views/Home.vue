<template>
  <div class="home-page">
    <!-- 分类标签栏 -->
    <div class="category-tabs">
      <el-tabs v-model="activeCategory" @tab-change="handleCategoryChange">
        <el-tab-pane label="全部" name="" />
        <el-tab-pane
          v-for="cat in categoryStore.categories"
          :key="cat.code"
          :label="cat.name"
          :name="cat.code"
        />
      </el-tabs>
    </div>

    <!-- 推荐/订阅 切换 -->
    <div class="view-tabs">
      <el-radio-group v-model="viewMode" @change="handleViewModeChange">
        <el-radio-button value="recommend">推荐</el-radio-button>
        <el-radio-button value="subscribed">订阅</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 事件列表 -->
    <div class="event-list" v-loading="eventStore.loading">
      <div v-if="eventStore.events.length === 0" class="empty">
        <el-empty description="暂无事件" />
      </div>
      <div v-else>
        <EventCard
          v-for="event in eventStore.events"
          :key="event.id"
          :event="event"
          @click="goToDetail(event)"
        />

        <!-- 加载更多 -->
        <div class="load-more" v-if="hasMore">
          <el-button
            :loading="loadingMore"
            @click="loadMore"
          >
            加载更多
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useEventStore, useCategoryStore } from '../../shared/stores'
import EventCard from '../components/EventCard.vue'

const router = useRouter()
const eventStore = useEventStore()
const categoryStore = useCategoryStore()

const activeCategory = ref('')
const viewMode = ref('recommend')
const loadingMore = ref(false)

const hasMore = computed(() => {
  return eventStore.page * 20 < eventStore.total
})

onMounted(async () => {
  await categoryStore.fetchCategories()
  await loadEvents()
})

async function loadEvents() {
  const category = activeCategory.value || undefined
  if (viewMode.value === 'recommend') {
    await eventStore.fetchRecommendEvents(1, category)
  } else {
    await eventStore.fetchSubscribedEvents(1, category)
  }
}

async function handleCategoryChange(category: string) {
  activeCategory.value = category
  await loadEvents()
}

async function handleViewModeChange(mode: string) {
  viewMode.value = mode
  await loadEvents()
}

async function loadMore() {
  loadingMore.value = true
  try {
    const nextPage = eventStore.page + 1
    const category = activeCategory.value || undefined
    if (viewMode.value === 'recommend') {
      await eventStore.fetchRecommendEvents(nextPage, category)
    } else {
      await eventStore.fetchSubscribedEvents(nextPage, category)
    }
  } finally {
    loadingMore.value = false
  }
}

function goToDetail(event: any) {
  router.push({
    path: `/event/${event.id}`,
    query: { type: event.source_type || 'rss' }
  })
}
</script>

<style scoped>
.home-page {
  background: white;
}

.category-tabs {
  padding: 0 16px;
  background: white;
  border-bottom: 1px solid #eee;
}

.view-tabs {
  padding: 12px 16px;
  background: white;
}

.event-list {
  padding: 16px;
}

.empty {
  padding: 40px 0;
}

.load-more {
  text-align: center;
  padding: 16px 0;
}
</style>
