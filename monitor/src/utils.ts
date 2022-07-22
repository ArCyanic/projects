import axios from "axios";
import qs from "qs";

async function fetchData(url: string, receiver: any, info: object = {}) {
  const response = await axios({
    method: "post",
    url: url,
    data: qs.stringify(info),
  });
  
  for (const key in receiver) {
    receiver[key] = response.data[key];
  }
}

export { fetchData };
