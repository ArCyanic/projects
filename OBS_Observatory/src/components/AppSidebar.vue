<template>
    <el-menu default-active="1" :collapse="isCollapsed" :router="true" background-color="#123456" text-color="#cccccc">
        <el-menu-item class="flex-center" style="background-color: #224466">
            <span v-if="!isCollapsed">BRAND</span>
            <el-icon v-if="isCollapsed">
                <Platform />
            </el-icon>
        </el-menu-item>
        <!-- use :router="true" rather than router="true", or compiler will warn you with string "true" -->
        <el-sub-menu index="">
            <template #title>
                <el-icon>
                    <Management />
                </el-icon>
                <span>Projects Observatory</span>
            </template>
            <el-menu-item index="/statistic">Statistic</el-menu-item>
            <el-menu-item index="/diff">Diff</el-menu-item>
        </el-sub-menu>
        <el-menu-item index="">
            <!-- it is necessary to place the <el-icon> tag outside of <template #title> tag 
            if you want to make collapse function working fine -->
            <el-icon>
                <DataBoard />
            </el-icon>
            <template #title>
                Version Observatory
            </template>
        </el-menu-item>
        
    </el-menu>
</template>

<script setup lang="ts">
import { storeToRefs } from "pinia";
import { useStore } from "../store";

const store = useStore();
const { isCollapsed } = storeToRefs(store) // needed to transform into reactive variable
</script>

<style scoped>
.el-menu {
    height: 100%;
}
</style>
