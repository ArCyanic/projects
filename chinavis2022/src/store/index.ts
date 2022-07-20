import { defineStore } from "pinia";
import { GroupInformation } from "../interface";
import { Node, Link } from "../interface";
import { types } from "../utils";

export const useStore = defineStore({
  id: "network",
  state: () => {
    let degreeData: {
      categories: string[];
      sections: string[];
      data: Array<[number, number, any]>;
    } = {
      categories: [],
      sections: [],
      data: [],
    };

    let groupData: {
      nodes: Array<Node>;
      links: Array<Link>;
    } = {
      nodes: [],
      links: [],
    };

    let groupsInformation: Array<GroupInformation> = [];

    let nodeTypesCount: Array<{ type: string; count: number }> = [];
    let linkTypesCount: Array<{ type: string; count: number }> = [];
    return {
      degreeData,
      groupsInformation,
      groupData,
      nodeTypesCount,
      linkTypesCount,
      degreeIndicator: false,
      tableIndicator: false,
      groupsIndicator: false,
    };
  },

  actions: {
    handleDegreeData(
      data: Array<{ category: number; degree: number }>,
      categories: Array<string> = types.node,
      section_step: number = 18
    ) {
      // set categories
      this.degreeData.categories = categories;
      // construct sections based on section step and the highest degree
      const num_sections = Math.ceil(
        Math.max(...data.map((d) => d.degree)) / section_step
      );

      this.degreeData.sections = Array.from(
        { length: num_sections },
        (_, k) => `${k * section_step + 1}~${(k + 1) * section_step}`
      );
      // construct position and value data
      this.degreeData.data = [];
      for (let i = 0; i < num_sections; i++) {
        for (let j = 0; j < categories.length; j++) {
          this.degreeData.data.push([j, i, 0]);
        }
      }
      data.forEach((d) => {
        let temp = this.degreeData.data;
        const index =
          categories.length * Math.floor(d.degree / section_step) + d.category;
        temp[index][2] += 1;
      });
      this.degreeData.data.forEach((d) => {
        d[2] = d[2] || "-";
      });
      this.degreeIndicator = true;
    },

    handleTableData(
      nodesInfo: {value: number, count: {}},
      linksInfo: {value: number, count: {}}
    ) {
      this.linkTypesCount = Object.entries(linksInfo.count).map(d => { return {type: d[0], count: d[1] as number}})
      this.nodeTypesCount = Object.entries(nodesInfo.count).map(d => { return {type: d[0], count: d[1] as number}})
      this.linkTypesCount.push({type: 'total', count: linksInfo.value})
      this.nodeTypesCount.push({type: 'total', count: nodesInfo.value})

      this.tableIndicator = true 
    },
  },
});
