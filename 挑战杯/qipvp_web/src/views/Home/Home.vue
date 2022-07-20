<template>
  <el-container style="height: 100%">
    <el-header style="background: #ffffff;height: 8%">
      <HomeHeader/>
    </el-header>
    <el-main style="background: #2c3e50">Main</el-main>
  </el-container>
</template>

<script>
// @ is an alias to /src
// import HelloWorld from '@/components/HelloWorld.vue'
import HomeHeader from "@/views/Home/components/HomeHeader";

export default {
  name: 'Home',
  components: {
    // HelloWorld,
    HomeHeader
  }
}
</script>
<style>


</style>
