<template>
    <el-table :data="data.display">
        <el-table-column prop="Project Name" label="Project Name" />
        <el-table-column prop="Repo Name" label="Repo Name" />

        <el-table-column v-for="key in Object.keys(data.display[0]).slice(2, -1)" :key="key" :label="key">
            <template #default="scope">
                {{ scope.row[scope.column.label] }}
                
                <span v-if="+scope.row.addition === +scope.row.addition">
                    <DiffCellPostfix :n="judge(scope)" />
                </span>
            </template>

        </el-table-column>
    </el-table>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue';
import { diffItem } from '../../types';
import DiffCellPostfix from './DiffCellPostfix.vue'

const props = defineProps<{
    data: diffItem[],
}>();

const data = reactive({
    display: props.data.filter((d) => +d.addition !== +d.addition || +d.addition >= 0),
    // display: props.data.filter((d) => +d.addition != 0),
    former: props.data.filter((d) => +d.addition === -1)
})



const judge = (scope: any) => {
    const latter = +scope.row[scope.column.label]
    type keyType = 'Success Rate' | 'Total' | 'Succeeded' | 'Failed' | 'Unresolvable' // this is really really disgusting...
    const former = data.former[+scope.row.addition][scope.column.label as keyType]
    const res = latter - former
    return Math.abs(res) >= 1 ? res : +res.toFixed(2)
}

</script>

<style scoped>
</style>