import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('./views/Home.vue'),
    meta: { title: '首页' }
  },
  {
    path: '/search',
    component: () => import('./views/Search.vue'),
    meta: { title: '搜索' }
  },
  {
    path: '/settings',
    component: () => import('./views/Settings.vue'),
    meta: { title: '设置' }
  },
  {
    path: '/event/:id',
    component: () => import('./views/EventDetail.vue'),
    meta: { title: '事件详情' }
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
