import { createRouter, createWebHashHistory } from "vue-router";

import DefaultLayout from "@/layouts/DefaultLayout.vue";

const routes = [
  {
    path: "/",
    name: "Home",
    component: () => DefaultLayout,
    redirect: '/statistic',
    children: [
      {
        path: "/statistic", 
        name: "Statistic",
        component: () => import('@/pages/Statistic.vue')
      },
      {
        path: '/diff',
        name: "Diffs",
        component: () => import('@/pages/Diff.vue')
      }
    ],
  },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }; // always scroll to top
  },
});

export default router;
