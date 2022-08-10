<template>
    <DiffTable :data="receiver.data" v-if="indicator" />
</template>

<script setup lang="ts">
import { onBeforeMount, reactive, ref } from 'vue';
import { fetchData } from '../utils';
import DiffTable from './Diff/DiffTable.vue'

import { diffItem } from '../types';

const receiver = reactive<{data: diffItem[]}>({
    data: [],
})

const data = reactive({

})

const indicator = ref(false) 
onBeforeMount(async () => { 
    await fetchData('/api/getDiffs', receiver) 

    indicator.value = true 
})

</script>

<style scoped>

</style>