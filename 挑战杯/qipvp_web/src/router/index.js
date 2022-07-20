import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home/Home.vue'
import About from '../views/About.vue'
import VisualizedPlatform from "@/views/VisualizedPlatform/VisualizedPlatform";
import TrendAnalysis from "@/views/TrendAnalysis/TrendAnalysis";

const routes = [
  {
    path: '/VisualizedPlatform',
    name: 'VisualizedPlatform',
    component: VisualizedPlatform,
    children: [
      {
        path: 'TrendAnalysis',
        component: TrendAnalysis
      },
      {
        path: 'TechnicalAnalysis',
        component: About
      },
      {
        path: 'PatenteeAnalysis',
        component: Home
      },
      {
        path: 'RegionalAnalysis',
        component: Home
      },
      {
        path: 'PartnershipAnalysis',
        component: Home
      }
    ]
  },
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/about',
    name: 'About',
    // route level code-splitting
    // this generates a separate chunk (about.[hash].js) for this route
    // which is lazy-loaded when the route is visited.
    component: () => import(/* webpackChunkName: "about" */ '../views/About.vue')
  }
]

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes
})

export default router
