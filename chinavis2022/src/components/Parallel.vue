<template>
  <div id="parallel" style="width: 600px; height: 600px"></div>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { useStore } from "../store";
import * as echarts from "echarts";
import * as d3 from "d3";
console.log('enter parallel');

const store = useStore();
let chart: echarts.ECharts;
// store.$subscribe((mutation, state) => {
//   if (state.groupsIndicator === true) draw();
// });

onMounted(() => {
  chart = echarts.init(document.getElementById("parallel") as HTMLElement);
  draw();
});

function draw() {
  const GroupTypes = ["小型团伙", "中型团伙", "大型团伙"];
  const wholeData = store.groupsInformation;
  let schema: Array<{ index: number; text: string }> = [
    { index: 0, text: "Nodes Count" },
    { index: 1, text: "Core Nodes Count" },
    { index: 2, text: "Links Count" },
    { index: 3, text: "Key Roads Count" },
    { index: 4, text: "Cluster" },
    { index: 5, text: "Category" },
  ];
  const axisData = schema.map((d, i) => {
    return i !== 5
      ? { dim: i, name: d.text }
      : { dim: i, name: d.text, type: "category" };
  });
  const data = wholeData.map((d) => [
    d.nodesCount,
    d.coreCount,
    d.linksCount,
    d.keyCount,
    d.cluster,
    GroupTypes[d.category],
  ]);
  const colorScale = d3.scaleOrdinal().range(d3.schemeAccent);
  const option = {
    tooltip: {
      padding: 10,
      backgroundColor: "#222",
      borderColor: "#777",
      borderWidth: 1,
      formatter: (params: any) => {
        const d = params.data 
        const i = params.dataIndex
        return `Cluster: ${d[4]}<br> GroupID: ${wholeData[i].id}`
      }
    },
    // grid: {
    //   left: '15%'
    // },
    visualMap: {
      show: false,
      min: 0,
      max: 0.3,
      dimension: 4,
      inRange: {
        color: ["#d94e5d", "#eac736", "#50a3ba"].reverse(),
        // colorAlpha: [0, 1]
      },
    },
    parallelAxis: axisData,
    parallel: {
      left: "5%",
      right: "15%",
      bottom: 100,
      parallelAxisDefault: {
        type: "value",
        nameLocation: "end",
        nameGap: 20,
        nameTextStyle: {
          color: "#fff",
          fontSize: 10,
        },
        axisLine: {
          lineStyle: {
            color: "#aaa",
          },
        },
        axisTick: {
          lineStyle: {
            color: "#777",
          },
        },
        splitLine: {
          show: false,
        },
        axisLabel: {
          color: "#fff",
        },
      },
    },
    series: [
      {
        name: "Groups Information",
        type: "parallel",
        lineStyle: {
          width: 1,
          opacity: 0.5,
        },
        data: data,
      },
    ],
  };
  chart.setOption(option);
}
</script>

<style scoped></style>
