interface mockDays {
  data: {
    date: string;
    data: {
      category: string;
      succeed: number;
      total: number;
      succeedRate: number;
    }[];
    total: number;
  }[];
}

export { mockDays };
