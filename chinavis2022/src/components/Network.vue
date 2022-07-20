<template>
  <div class="header" v-if="isDetail">
    <div><el-page-header title="Overview" @click="back" /></div>
    {{ content }}
    <div>
      <el-button
        style="border: 1px solid #dee94e"
        color="transparent"
        round="true"
        @click="switchView"
        >Switch View</el-button
      >
    </div>
  </div>

  <div id="network" style="width: 850px; height: 700px"></div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { fetchData, types } from "../utils";
import { ElPageHeader } from "element-plus";
import { useStore } from "../store";
import * as d3 from "d3";
import * as echarts from "echarts";
import { GroupInformation, Node, Link } from "../interface";

const store = useStore();
const isDetail = ref(false);
const content = ref("Group View");
const nodeCategories = types.node.map((d) => {
  return { name: d };
});

let chart: echarts.ECharts;

onMounted(async () => {
  chart = echarts.init(document.getElementById("network") as HTMLElement);

  let data = await handleOverviewData();
  // Store overview graph data in store
  store.groupsInformation = data;
  store.groupsIndicator = true;

  setOverviewOption(store.groupsInformation);
  chart.on("click", { seriesName: "Overview" }, async function (params: any) {
    store.groupsIndicator = false;
    isDetail.value = true;
    let id: number = params.data.id + 1;
    let data = await handleGroupViewData(id) as any;
    console.log("this is group", id);

    // Attention: change state and invoke scatter drawer
    store.handleDegreeData(
      data.nodes.map((d) => {
        return { category: d.category, degree: d.degree };
      })
    );

    store.handleTableData(data.nodesInfo, data.linksInfo);

    store.groupData = { nodes: data.nodes, links: data.links };
    setGroupViewOption(Object.create({ nodes: data.nodes, links: data.links }));
  } as any);
});

function switchView() {
  if (content.value === "Group View") {
    content.value = "Key&Core View";
    setKeyCoreOption(Object.create(store.groupData));
    console.log;
  } else {
    content.value = "Group View";
    setGroupViewOption(Object.create(store.groupData));
  }
}

function back() {
  isDetail.value = false;
  store.groupsIndicator = true;
  store.degreeIndicator = false;
  store.tableIndicator = false;
  setOverviewOption(store.groupsInformation);
}

async function handleOverviewData(): Promise<GroupInformation[]> {
  // Part I data handling
  let receiver = { data: [] };
  await fetchData(`/api/getgroupsinfo`, receiver);
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
  return data;
}

function setOverviewOption(data: Array<GroupInformation>) {
  // define group types
  const GroupTypes = [
    { name: "小型团伙" },
    { name: "中型团伙" },
    { name: "大型团伙" },
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
        return `Group ID: ${d.id + 1}<br>Nodes Count: ${d.nodesCount}<br>Links Count: ${d.linksCount}<br>Diameter: ${d.diameter}<br>Cluster: ${d.cluster}<br>Core Assets Count: ${d.coreCount}<br>Key Roads Count: ${d.keyCount}`;
      },
    },

    legend: {
      data: GroupTypes.map((d) => d.name),
      icon: "circle",
      textStyle: {
        fontSize: 12,
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
        zoom: 2,
        label: {
          position: "right",
        },
        force: {
          repulsion: 100,
        },
      },
    ],
  };
  chart.setOption(option, true);
}

async function handleGroupViewData(i: number) {
  let nodeReceiver = { info: {}, node: [] };
  let linkReceiver = { info: {}, edge: [] };
  await fetchData(`/api/getnodebyid?id=${i}`, nodeReceiver);
  await fetchData(`/api/getedgebyid?id=${i}`, linkReceiver);
  let nodes = nodeReceiver.node;
  let links = linkReceiver.edge;

  nodes.sort((a, b) => b.degree - a.degree);

  let degrees = nodes.map((d) => d.degree);
  let sizeScale = d3
    .scaleLinear()
    .domain([Math.min(...degrees), Math.max(...degrees)])
    .range([1, 50]);
  nodes.forEach((d) => {
    d.symbolSize = sizeScale(d.degree);
  });
  console.log(nodes);
  console.log(links);

  return {
    nodes: nodes,
    links: links,
    nodesInfo: nodeReceiver.info,
    linksInfo: linkReceiver.info,
  };
}

async function setGroupViewOption(
  data: {
    nodes: Array<Node>;
    links: Array<Link>;
  },
  type: string = "force"
) {
  const nodeCategories = types.node.map((d) => {
    return { name: d };
  });
  let nodes = data.nodes;
  let links = data.links;
  let option;
  if (type === "force") {
    option = {
      title: {
        show: false,
        text: "Group Network",
        textStyle: {
          color: "white",
        },
      },
      tooltip: {
        formatter: "{b}",
      },
      legend: [
        {
          data: nodeCategories.map((d) => d.name),
          textStyle: {
            color: "white",
            fontSize: 10,
          },
          left: "20%",
          icon: "circle",
        },
      ],
      animationDuration: 1500,
      draggable: true,
      // animationEasingUpdate: 'quinticInOut',
      series: [
        {
          type: "graph",
          layout: "force",
          label: {
            // show: (d) => d.degree > 100,
            formatter: "{b}",
          },
          edgeSymbol: ["circle", "arrow"],
          edgeSymbolSize: [4, 5],
          data: nodes,
          links: links,
          roam: true,
          zoom: 0.3,
          categories: nodeCategories,
          itemStyle: {
            borderWidth: 1,
            borderColor: "#000",
          },
          lineStyle: {
            color: "source",
            curveness: 0.5,
            opacity: 0.2,
          },
          force: {
            repulsion: 200,
          },
          emphasis: {
            focus: "adjacency",
            lineStyle: {
              width: 10,
            },
          },
        },
      ],
    };
  } else {
    option = {
      title: {
        show: false,
        text: "Group Network",
        textStyle: {
          color: "white",
        },
      },
      tooltip: {
        formatter: "{b}",
      },
      legend: [
        {
          data: nodeCategories.map((d) => d.name),
          textStyle: {
            color: "white",
            fontSize: 10,
          },
          left: "20%",
          icon: "circle",
        },
      ],
      animationDuration: 1500,
      draggable: true,
      // animationEasingUpdate: 'quinticInOut',
      series: [
        {
          name: "Group View",
          type: "graph",
          layout: "circle",
          label: {
            // show: (d) => d.degree > 100,
            formatter: "{b}",
          },
          edgeSymbol: ["circle", "arrow"],
          edgeSymbolSize: [4, 5],
          data: nodes,
          links: links,
          roam: true,
          // zoom: 0.3,
          categories: nodeCategories,
          itemStyle: {
            borderWidth: 1,
            borderColor: "#000",
          },
          lineStyle: {
            color: "source",
            curveness: 0.5,
            opacity: 0.2,
          },
          emphasis: {
            focus: "adjacency",
            lineStyle: {
              width: 10,
            },
          },
        },
      ],
    };
  }

  chart.setOption(option, true);
}

function setKeyCoreOption(
  data: { nodes: Array<Node>; links: Array<Link> },
  type: string = "force"
) {
  const icons = [
    "circle",
    "rect",
    "roundRect",
    "triangle",
    "diamond",
    "pin",
    "arrow",
    "none",
  ];
  const nodeCategories = types.node.map((d, i) => {
    return { name: d, icon: icons[i], itemStyle: { color: "#DEE94E" } };
  });
  let nodes = data.nodes;
  let links = data.links;
  links.forEach((d) => {
    d.lineStyle = {
      color: d.isRoad ? "#DEE94E" : "#777",
      curveness: 0.5,
      opacity: d.isRoad ? 0.6 : 0.2,
    };
  });
  let option;
  if (type === "force") {
    option = {
      title: {
        show: false,
        text: "Key&Core Network",
        textStyle: {
          color: "white",
        },
      },
      tooltip: {
        formatter: "{b}",
      },
      legend: [
        {
          data: nodeCategories,
          textStyle: {
            color: "white",
            fontSize: 10,
          },
          left: "20%",
          icon: "circle",
        },
      ],
      animationDuration: 1500,
      draggable: true,
      // animationEasingUpdate: 'quinticInOut',
      series: [
        {
          name: "Key&Core View",
          type: "graph",
          layout: "force",
          label: {
            // show: (d) => d.degree > 100,
            formatter: "{b}",
          },
          edgeSymbol: ["circle", "arrow"],
          edgeSymbolSize: [4, 5],
          data: nodes.map(function (d, i) {
            return {
              id: d.id,
              name: d.name,
              symbol: icons[d.category],
              symbolSize:
                d.isKey && d.symbolSize < 10 ? d.symbolSize + 10 : d.symbolSize,
              itemStyle: {
                borderWidth: 1,
                borderColor: "#000",
                color: d.isKey ? "#DEE94E" : "#ccc",
              },
              category: d.category,
            };
          }),
          links: links,
          roam: true,
          // zoom: 0.3,
          categories: nodeCategories,
          emphasis: {
            focus: "adjacency",
            lineStyle: {
              width: 10,
            },
          },
        },
      ],
    };
  } else {
    option = {
      title: {
        text: "Key&Core Network",
        textStyle: {
          color: "white",
        },
      },
      tooltip: {
        formatter: "{b}",
      },
      legend: [
        {
          data: nodeCategories.map((d) => d.name),
          textStyle: {
            color: "white",
            fontSize: 10,
          },
          left: "20%",
          icon: "circle",
        },
      ],
      animationDuration: 1500,
      draggable: true,
      // animationEasingUpdate: 'quinticInOut',
      series: [
        {
          name: "Key&Core View",
          type: "graph",
          layout: "circle",
          label: {
            // show: (d) => d.degree > 100,
            formatter: "{b}",
          },
          edgeSymbol: ["circle", "arrow"],
          edgeSymbolSize: [4, 5],
          data: nodes,
          links: links,
          roam: true,
          // zoom: 0.3,
          categories: nodeCategories,
          itemStyle: {
            borderWidth: 1,
            borderColor: "#000",
            color: (params: any) => {
              const d = params.data as Node;
              return d.isKey ? "steelblue" : "pink";
            },
          },
          lineStyle: {
            // color: "source",
            color: (params: any) => {
              const d = params.data as Link;
              return d.isRoad ? "white" : "steelblue";
            },
            curveness: 0.5,
            opacity: 0.2,
          },
          emphasis: {
            focus: "adjacency",
            lineStyle: {
              width: 10,
            },
          },
        },
      ],
    };
  }

  chart.setOption(option, true);
}
</script>

<style scoped>
.header {
  color: white;
  display: flex;
  height: 50px;
  justify-content: space-around;
  align-items: center;
}
</style>
