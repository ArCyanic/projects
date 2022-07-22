<template>
    <el-table :data="props.data">
        <el-table-column v-for="key in Object.keys(props.data[0])" :key="key" :prop="key"
            :label="key.charAt(0).toUpperCase() + key.slice(1)">
        </el-table-column>

    </el-table>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';

const props = defineProps<{
    data: { category: string; succeed: number; total: number; succeedRate: number }[];
}>();

onMounted(async () => {
    console.log('table', Object.keys(props.data))
})

</script>

<style scoped>
</style>