<template>
  <div id="heat" style="width: 600px; height: 400px"></div>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { useStore } from "../store";
import * as echarts from "echarts";
import * as d3 from "d3";
const store = useStore();
let chart: echarts.ECharts;
// const subscribe = store.$onAction(async ({ name, after }) => {
//   if (name === "formatDegreeData") {
//     after(() => {
//       draw();
//     });
//   }
// });
onMounted(() => {
  chart = echarts.init(document.getElementById("heat") as HTMLElement);
  draw();
});

function draw() {
  let data = store.degreeData;
  let counts = data.data.map((d) => d[2]);
  console.log("Draw Heat Map");
  console.log(data);

  const option = {
    title: {
      text: "Degree distribution",
      subtext: "For different types of nodes",
      textStyle: {
        color: "white",
      },
      subtextStyle: {
        color: "white",
      },
    },
    grid: {
      top: "20%",
    },
    tooltip: {
      position: "top",
      formatter: function (params: any) {
        return `count: ${params.value[2]}`;
      },
    },
    xAxis: {
      type: "category",
      data: data.categories,
      //   boundaryGap: true,
      splitArea: {
        // show: true,
      },
      axisLabel: {
        show: true,
        interval: 0,
        fontSize: 8,
        textStyle: {
          color: "white",
        },
      },
    },
    yAxis: {
      type: "category",
      data: data.sections,
      axisLine: {
        show: false,
      },
      axisLabel: {
        fontSize: 8,
        textStyle: {
          color: "white",
        },
      },
      name: "Degree section",
      nameTextStyle: {
        color: 'white'
      }
    },
    visualMap: {
      min: 0,
      max: 30,
      calculable: true,
      orient: "horizontal",
      left: "60%",
      top: 'top',
      dimension: 2,
      show: true,

      color: ["#DEE94E", "#ccc"],
    },
    series: [
      {
        name: "Degree",
        type: "heatmap",
        data: data.data,
        label: {
          show: false,
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
  chart.setOption(option);
}
</script>

<style scoped></style>
