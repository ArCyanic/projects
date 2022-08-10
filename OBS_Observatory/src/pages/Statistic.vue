<template>
    <div style="font-size:small">
        <ChartTable :data="receiver.data" />
    </div>
</template>

<script setup lang="ts">
import { onBeforeMount, onMounted, reactive, ref } from 'vue';
import { fetchData } from '../utils';
import ChartTable from '@/components/ChartTable.vue'

const receiver = reactive({data: [{}]})

onBeforeMount(async () => {
    await fetchData('/api/getProjectStatistics', receiver)
    
})

</script>

<style scoped>

</style>