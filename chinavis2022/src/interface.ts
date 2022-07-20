interface GroupInformation {
  id: number;
  symbolSize: number;
  category: number;

  diameter: number;
  cluster: number;

  nodesCount: number;
  linksCount: number;
  coreCount: number;
  keyCount: number;
}

interface Group {
  id: number;
  value: number;
  symbolSize: number;
  category: number;
}

interface Node {
  id: string;
  name: string;
  category: number;
  degree: number;
  weight: number;
  isKey: boolean;
  symbolSize?: number;
  industry?: string;
}

interface Link {
  source: string;
  target: string;
  weight: number;
  category: number;
  isRoad: boolean;
  lineStyle?: object;
}

export type { GroupInformation, Node, Link };
