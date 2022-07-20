<template>
<div>
    this is overview
</div>

  <div
    id="OverviewNetwork"
    :style="{ width: store.networkWidth, height: store.networkHeight }"
  ></div>
</template>

<script setup lang="ts">
import { useStore } from "../store";
import * as echarts from "echarts";
import { onMounted } from "vue";
import { fetchData } from "../utils";
import * as d3 from "d3";

let chart: echarts.ECharts;
const store = useStore();

onMounted(async () => {
  chart = echarts.init(document.getElementById("GroupNetwork") as HTMLElement);

  await draw();
  chart.on("click", { seriesName: 'Overview'},function (params) {
    let data: any = params.data;
    let id: number = data.id;
    drawNetwork(id);
  });
});

interface Group {
  id: number;
  value: number;
  symbolSize: number;
  category: number;
}

async function draw() {
  // Part I data handling
  let receiver = { data: [] };
  await fetchData(`/api/getnodecountlist`, receiver);
  console.log("Overview Graph Data: ");
  console.log(receiver.data);

  let data = receiver.data;
  let counts = data.map((d) => d.nodesCount);
  const sizeScale = d3
    .scaleLinear()
    .domain([d3.min(counts), d3.max(counts)])
    .range([20, 50]);
  data.forEach((d) => {
    // add symbolSize and category
    d.symbolSize = sizeScale(d.nodesCount); // this property is required
    if (d.nodesCount < 400) d.category = 0;
    else if (d.nodesCount < 800) d.category = 1;
    else d.category = 2;
  });
  // Store overview graph data in store
  store.groupsInformation = data;
  store.groupsIndicator = true;

  // Part II: define and set option
  setOverviewOption(data);
}

function setOverviewOption(data) {
  // define group types
  const GroupTypes = [
    { name: "小型团伙(N<400)" },
    { name: "中型团伙(N<800)" },
    { name: "大型团伙(N<3000)" },
  ];
  const option = {
    title: {
      text: "团伙一览图",
      textStyle: {
        color: "white",
      },
    },
    tooltip: {
      formatter: (params: any) => {
        const d = params.data;
        return `Group ID: ${d.id}<br>Nodes Count: ${d.nodesCount}<br>Links Count: ${d.linksCount}<br>Diameter: ${d.diameter}<br>Cluster: ${d.cluster}<br>Core Assets Count: ${d.coreCount}<br>Key Roads Count: ${d.keyCount}`;
      },
    },
    legend: {
      data: GroupTypes.map((d) => d.name),
      icon: "circle",
      textStyle: {
        fontSize: 10,
        color: "white",
      },
      itemStyle: {},
    },
    series: [
      {
        name: "Overview",
        type: "graph",
        layout: "force",
        data: data,
        // links: graph.links,
        categories: GroupTypes,
        roam: true,
        label: {
          position: "right",
        },
        force: {
          repulsion: 100,
        },
      },
    ],
  };
  chart.setOption(option);
}
</script>

<style scoped></style>
