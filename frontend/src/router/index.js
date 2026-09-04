import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', component: () => import('../views/Login.vue'), meta: { public: true } },
  { path: '/', component: () => import('../views/Home.vue') },
  { path: '/entry/:type(income|expense)', component: () => import('../views/Entry.vue') },
  { path: '/transactions', component: () => import('../views/Transactions.vue') },
  { path: '/reports', component: () => import('../views/Reports.vue') },
  { path: '/settings', component: () => import('../views/Settings.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn) return '/login'
  if (to.path === '/login' && auth.isLoggedIn) return '/'
  return true
})

export default router
