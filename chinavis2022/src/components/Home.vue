<template>
  <el-row>
    <el-col :span="14">
      <Network />
    </el-col>
    <el-col :span="10">
      <div v-if="store.groupsIndicator" style="display: fixed; height: 70px;width: 100%"></div>
      <Parallel v-if="store.groupsIndicator" />
      <Heat v-if="store.degreeIndicator" />
      <Table v-if="store.tableIndicator" />
      
    </el-col>
  </el-row>
</template>

<script setup lang="ts">
import { ElTable } from "element-plus";
import Network from "./Network.vue";
import Heat from "./Heat.vue";
import Parallel from "./Parallel.vue";
import Table from "./Table.vue";
import { useStore } from "../store";
const store = useStore();
</script>

<style scoped></style>
