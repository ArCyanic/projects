<template>
    <div style="display: flex; justify-content: center; align-items: center;">
        <el-button @click="store.toggleSidebar" style="border: 0px">
            <el-icon>
                <Menu />
            </el-icon>
        </el-button>
        <el-breadcrumb separator="/">
            <el-breadcrumb-item v-for="item in breadcrumbData" :key="item.name" :to="item.active ? '' : item.path">
                {{ item.name }}
            </el-breadcrumb-item>
        </el-breadcrumb>
    </div>
</template>

<script setup lang="ts">
import { useStore } from '../store'
import router from '../router';
import { onMounted, ref } from 'vue'

interface BreadcrumbData {
    active: boolean,
    name: any, // require type RouteRecordName
    path: string,
}

const store = useStore()
const breadcrumbData = ref<BreadcrumbData[]>()

const getBreadcrumbsData = () => router.currentRoute.value.matched.map((route) => {
    return {
        active: route.path === router.currentRoute.value.path,
        name: route.name,
        path: route.path
    }
})

router.afterEach(() => {
    breadcrumbData.value = getBreadcrumbsData()
})

onMounted(() => {
    breadcrumbData.value = getBreadcrumbsData()
    
})

// onBeforeMount(() => {
//     breadcrumbs.value = getBreadcrumbs()
// })

</script>

<style scoped>
</style>
