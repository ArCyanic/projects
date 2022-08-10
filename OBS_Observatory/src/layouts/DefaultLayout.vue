<template>
    <el-container style="height: 100%" >
        <!-- <el-aside> -->
        <el-aside :width="isCollapsed ? '5%' : '14%'">
            <AppSidebar />
        </el-aside>
        <el-container>
            <el-header>
                <AppHeader />
            </el-header>
            <el-main>
                <router-view />
            </el-main>
            <el-footer height="30px" style="">
                <AppFooter   />
            </el-footer>
        </el-container>
    </el-container>
</template>

<script setup lang="ts">
import AppFooter from '../components/AppFooter.vue';
import AppHeader from '../components/AppHeader.vue';
import AppSidebar from '../components/AppSidebar.vue';

import { storeToRefs } from "pinia";
import { useStore } from "../store";

const store = useStore();
const { isCollapsed } = storeToRefs(store)

</script>

<style scoped>
.el-aside {
    /* display:contents; */
    float: left;
    position:relative;
    height: 100%;
}

.el-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}
</style>