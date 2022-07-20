<template>
  <div>
    saas
    <el-container>
      <el-main>
        <el-card class="Card">
          <div ref="container" style="width: 1000px; height: 600px"></div>
        </el-card>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import axios from "axios";
import qs from "qs";
import { ElMessage } from "element-plus";
import { ref, onMounted } from "vue";
import * as echarts from "echarts";

const container = ref(null);
const chart = ref(null);
// const options = ref(null);
let options = {}

onMounted(async () => {
  //load data
  const receiver = { years: [], effects: [], records: [] };
  await fetchData(receiver);

  //init echarts
  chart.value = echarts.init(container.value);

  //create options
  createOptions(receiver);

  //draw graph
  chart.value.setOption(options);
});

async function fetchData(receiver) {
  try {
    console.log("before axios");
    const response = await axios({
      method: "post",
      url: "/api/TrendAnalysis/getTechnicalEfficacyTrends/",
      data: qs.stringify({
        firstName: "Fred",
        lastName: "Flintstone",
      }),
    });

    if (response.status !== 200) {
      ElMessage({
        showClose: true,
        message: "请求失败.",
        type: "error",
      });
    } else {
      if (response && response.data.status && response.data.status === 1) {
        for (const key in receiver) {
          receiver[key] = response.data[key];
        }
      } else {
        ElMessage({
          showClose: true,
          message: response.data.msg,
          type: "error",
        });
      }
    }
  } catch (e) {
    ElMessage({
      showClose: true,
      message: "请求出错！",
      type: "error",
    });
  }
}

function createOptions(data) {
  options = {
    tooltip: {
      position: "top",
    },
    grid: {
      height: "80%",
      top: "5%",
    },
    xAxis: {
      type: "category",
      data: data.years,
      splitArea: {
        show: true,
      },
    },
    yAxis: {
      type: "category",
      data: data.effects,
      splitArea: {
        show: true,
      },
    },
    visualMap: {
      min: 0,
      max: 3000,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: "0%",
    },
    series: [
      {
        type: "heatmap",
        data: data.records,
        label: {
          show: true,
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: "rgba(0, 0, 0, 0.5)",
          },
        },
      },
    ],
  };
}

// export default {
//   name: "TechnicalEfficacyTrends",
// };
</script>

<style scoped>
.container {
  width: 100%;
  height: 100%;
}

/* .Card {
  width: 800vh;
  height: 500vh;
} */
</style>
