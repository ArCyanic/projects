<template>

    <el-icon >
        <CaretTop color="green" v-if="props.n > 0" />
        <CaretBottom color="red" v-else-if="props.n < 0" />
    </el-icon>

    <span v-if="props.n != 0" :style="{color: props.n > 0 ? 'green' : 'red'}">{{ props.n > 0 ? props.n : -props.n }}</span>
</template>
<script setup lang="ts">
const props = defineProps<{
    n: number
}>()
</script>