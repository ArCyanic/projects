<template>
  <div class="tables">
    <el-table
      :data="store.nodeTypesCount"
      height="400"
      border
      style="width: 250px;"
      :header-row-style="{color: 'orange'}"
    >
      <el-table-column prop="type" label="Node Type" width="125" />
      <el-table-column prop="count" label="Count" width="125" />
    </el-table>

    <el-table
      :data="store.linkTypesCount"
      border
      height="520"
      style="width: 250px"
      :header-row-style="{color: 'orange'}"
    >
      <el-table-column prop="type" label="Link Type" width="125" />
      <el-table-column prop="count" label="Count" width="125" />
    </el-table>
  </div>
</template>

<script lang="ts" setup>
import { useStore } from "../store";

const store = useStore();
// const rowStyle = {color: 'white', background-color: 'transparent'}
</script>
<style scoped>
.tables {
  display: flex;
  /* align-items: center; */
  justify-content: space-evenly;
}
/* :deep(tr, thead, tfoot) {
  color: white;
  background-color: #333;
} */
.el-table{
  --el-table-tr-bg-color: #333;
  --el-table-header-bg-color: #333;
  color: white;
}

</style>
