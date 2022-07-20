<!--<template>-->
<!--  <el-row>-->
<!--    <el-col :span="8"><div class="grid-content bg-purple"></div></el-col>-->
<!--    <el-col :span="8"><div class="grid-content bg-purple-light"></div></el-col>-->
<!--    <el-col :span="8"><div class="grid-content bg-purple"></div></el-col>-->
<!--  </el-row>-->
<!--</template>-->
<template>
  <el-row>
    <el-col :span="12">
      量子行业专利可视化平台
    </el-col>
    <el-col :span="12">
      <el-menu
          :default-active="activeIndex"
          mode="horizontal"
          @select="handleSelect"
      >
        <el-menu-item index="1">Processing Center</el-menu-item>
        <el-sub-menu index="2">
          <template #title>Workspace</template>
          <el-menu-item index="2-1">item one</el-menu-item>
          <el-menu-item index="2-2">item two</el-menu-item>
          <el-menu-item index="2-3">item three</el-menu-item>
          <el-sub-menu index="2-4">
            <template #title>item four</template>
            <el-menu-item index="2-4-1">item one</el-menu-item>
            <el-menu-item index="2-4-2">item two</el-menu-item>
            <el-menu-item index="2-4-3">item three</el-menu-item>
          </el-sub-menu>
        </el-sub-menu>
        <el-menu-item index="3">Info</el-menu-item>
        <el-menu-item index="4">Orders</el-menu-item>
        <el-menu-item index="/VisualizedPlatform/TrendAnalysis">可视化平台</el-menu-item>
      </el-menu>

    </el-col>
  </el-row>
</template>
<script>
import {ref} from 'vue'
import router from "@/router/index.js";

export default {
  name: "HomeHeader",
  setup() {
    const activeIndex = ref('1')
    const activeIndex2 = ref('1')
    const handleSelect = (key, keyPath) => {
      console.log(key, keyPath)
      router.push(key);
    }
    return {
      activeIndex,
      activeIndex2,
      handleSelect,
    }
  },
}
// export default {
//   name: "HomeHeader"
// }
</script>

<style scoped>

</style>
