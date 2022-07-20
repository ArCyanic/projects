<template>
  <el-container style="height: 100%; margin: 0">
    <el-aside width="16%" style="margin-right: 2px; border: 1px solid #cccccc">
      <h3 class="vp-title">
        <el-icon>
          <setting />
        </el-icon>
        <span @click="backHome">可视化平台</span>
      </h3>
      <el-menu :default-openeds="['1', '3']">
        <el-sub-menu index="TrendAnalysis">
          <template #title>
            <el-icon>
              <setting />
            </el-icon>
            趋势分析
          </template>
          <el-menu-item index="0-1">历年专利数动向图</el-menu-item>
          <el-menu-item index="2-2">公开年月分布图</el-menu-item>
          <el-menu-item index="3-2">专利生命周期图</el-menu-item>
          <el-menu-item index="1-2">技术功效趋势图</el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="TechnicalAnalysis">
          <template #title>
            <el-icon>
              <setting />
            </el-icon>
            技术分析
          </template>
          <el-menu-item index="9-1">主IPC分析图</el-menu-item>
          <el-menu-item index="8-2">专利技术构成分析图</el-menu-item>
          <el-menu-item index="7-2">重要专利引用族谱</el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="PatenteeAnalysis">
          <template #title>
            <el-icon>
              <setting />
            </el-icon>
            专利权人分析
          </template>
          <el-menu-item index="6-1">国内机构专利数总览图</el-menu-item>
          <el-menu-item index="5-2">国内机构专利竞争分析</el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="RegionalAnalysis">
          <template #title>
            <el-icon>
              <setting />
            </el-icon>
            地域分析
          </template>
          <el-menu-item index="1-1">历年省市专利动向图</el-menu-item>
          <el-menu-item index="2-1">省市专利占有比例图</el-menu-item>
          <el-menu-item index="3-1">专利数热力图</el-menu-item>
          <el-menu-item index="4-2">专利数年度排行榜</el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="PartnershipAnalysis">
          <template #title>
            <el-icon>
              <setting />
            </el-icon>
            合作关系分析
          </template>
          <el-menu-item index="Partnership">合作关系图</el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>

    <el-container
      style="margin-left: 2px; border: 1px solid #cccccc; padding: 5px"
    >
      <router-view />
    </el-container>
  </el-container>
</template>

<script>
import { Setting } from "@element-plus/icons";
import router from "@/router/index.js";

export default {
  components: {
    // Message,
    Setting,
    // 'icon-menu': Menu,
  },
  methods: {
    backHome() {
      router.push("/");
    },
  },
};
</script>

<style>
.vp-title:hover {
  cursor: pointer;
}
.el-header {
  background-color: #b3c0d1;
  color: var(--el-text-color-primary);
  line-height: 60px;
}

.el-aside {
  color: var(--el-text-color-primary);
}
</style>

<!--<script>-->
<!--export default {-->
<!--  name: "VisualizedPlatform"-->
<!--}-->
<!--</script>-->

<!--<style scoped>-->

<!--</style>-->
