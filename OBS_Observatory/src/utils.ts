import axios from "axios";
import qs from "qs";

async function fetchData(url: string, receiver: any, addition: object = {}) {
  const response = await axios({
    method: "get",
    url: url,
    data: qs.stringify(addition),
  });
  
  for (const key in receiver) {
    receiver[key] = response.data[key];
  }
}

export { fetchData }