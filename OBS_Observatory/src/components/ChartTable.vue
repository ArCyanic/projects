<template>
    <el-table :data="props.data">
        <el-table-column v-for="key in Object.keys(props.data[0])" :key="key" :prop="key" :label="key" />
    </el-table>
</template>

<script setup lang="ts">

const props = defineProps<{
    data: {}[];
}>();

</script>

<style scoped>
</style>