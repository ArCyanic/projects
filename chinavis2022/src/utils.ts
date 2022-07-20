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

// define types of nodes, links and industries; define intensity of relation
const types = {'node': ['Domain', 'IP', 'Cert', 'Whois_Name', 'Whois_Phone', 'Whois_Email', 'IP_C', 'ASN'],
        'industry': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I'],
        'link': ['r_cert', 'r_subdomain', 'r_request_jump', 'r_dns_a', 'r_whois_name', 'r_whois_email', 'r_whois_phone', 'r_cert_chain', 'r_cname', 'r_asn', 'r_cidr']}
const intensity = {'r_cert' : 4, 'r_subdomain' : 4, 'r_request_jump' : 4, 'r_dns_a' : 4, 'r_whois_name' : 3, 'r_whois_email' : 3, 'r_whois_phone' : 3, 'r_cert_chain' : 2, 'r_cname' : 2, 'r_asn' : 1, 'r_cidr' : 1}
const importance = {'Domain' : 3, 'IP' : 3, 'Cert' : 3, 'Whois_Name' : 2, 'Whois_Phone' : 2, 'Whois_Email' : 2, 'IP_C' : 1, 'ASN' : 1}
const model = {'Domain' : {'r_subdomain' : 'Domain', 'r_request_jump' : 'Domain', 'r_cname' : 'Domain', 'r_whois_name' : 'Whois_Name', 'r_whois_phone' : 'Whois_Phone', 'r_whois_email' : 'Whois_Email', 'r_cert' : 'Cert', 'r_dns_a' : 'IP'},
               'Cert' : {'r_cert_chain' : 'Cert'},
               'IP' : {'r_cidr' : 'IP_C', 'r_asn' : 'ASN'}}

export { fetchData, types };