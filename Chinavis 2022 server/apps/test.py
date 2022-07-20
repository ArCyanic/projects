import networkx as nx
import numpy as np
import pandas as pd

ID = []
TOTAL = []

TATAL1 = []

DOMAIN = []
IP = []
CERT = []
WHOIS_NAME = []
WHOIS_PHONE = []
WHOIS_EMAIL = []
IP_C = []
ASN = []

R_CERT = []
R_SUBDOMAIN = []
R_REQUEST_JUMP = []
R_DNS_A = []
R_WHOIS_NAME = []
R_WHOIS_EMAIL = []
R_WHOIS_PHONE = []
R_CERT_CHAIN = []
R_CNAME = []
R_ASN = []
R_CIDR = []

for i in range(10):
    ID.append(i + 1)

    filename = "./resource/node/node_of_" + str(i + 1) + ".csv"
    total = sum(1 for line in open(filename, encoding="UTF-8"))
    total = total - 1
    TOTAL.append(total)

    filename = "./resource/node/edge_of_" + str(i + 1) + ".csv"
    total1 = sum(1 for line in open(filename, encoding="UTF-8"))
    total1 = total1 - 1
    TATAL1.append(total1)

    domain = 0
    iP = 0
    cert = 0
    whois_Name = 0
    whois_Phone = 0
    whois_Email = 0
    iP_C = 0
    aSN = 0

    dict = {'Domain': domain, 'IP': iP, 'Cert': cert, 'Whois_Name': whois_Name, 'Whois_Phone': whois_Phone,
            'Whois_Email': whois_Email, 'IP_C': iP_C,
            'ASN': aSN}
    import csv

    name = "./resource/node/node_of_" + str(i + 1) + ".csv"
    with open(name, 'r', encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if row[1] != "id":
                dict[row[3]] += 1
    DOMAIN.append(dict["Domain"])
    IP.append(dict["IP"])
    CERT.append(dict["Cert"])
    WHOIS_NAME.append(dict["Whois_Name"])
    WHOIS_PHONE.append(dict["Whois_Phone"])
    WHOIS_EMAIL.append(dict["Whois_Email"])
    IP_C.append(dict["IP_C"])
    ASN.append(dict["ASN"])

    r_cert = 0
    r_subdomain = 0
    r_request_jump = 0
    r_dns_a = 0
    r_whois_name = 0
    r_whois_email = 0
    r_whois_phone = 0
    r_cert_chain = 0
    r_cname = 0
    r_asn = 0
    r_cidr = 0


    dict = {'r_cert': r_cert, 'r_subdomain': r_subdomain, 'r_request_jump': r_request_jump, 'r_dns_a': r_dns_a, 'r_whois_name': r_whois_name,
            'r_whois_email': r_whois_email,
            'r_whois_phone': r_whois_phone,
            'r_cert_chain': r_cert_chain, 'r_cname': r_cname, 'r_asn': r_asn, 'r_cidr': r_cidr , 'relation':0}
    import csv

    name = "./resource/node/edge_of_" + str(i + 1) + ".csv"
    with open(name, 'r', encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if row[1] != "id":
                dict[row[3]] += 1
    R_CERT.append(dict["r_cert"])
    R_SUBDOMAIN.append(dict["r_subdomain"])
    R_REQUEST_JUMP.append(dict["r_request_jump"])
    R_DNS_A.append(dict["r_dns_a"])
    R_WHOIS_NAME.append(dict["r_whois_name"])
    R_WHOIS_EMAIL.append(dict["r_whois_email"])
    R_WHOIS_PHONE.append(dict["r_whois_phone"])
    R_CERT_CHAIN.append(dict["r_cert_chain"])
    R_CNAME.append(dict["r_cname"])
    R_ASN.append(dict["r_asn"])
    R_CIDR.append(dict["r_cidr"])

print(dict)

dat = {
    "ID": ID,

    "Domain": DOMAIN,
    "IP": IP,
    "Cert": CERT,
    "Whois_Name": WHOIS_NAME,
    "Whois_Phone": WHOIS_PHONE,
    "Whois_Email": WHOIS_EMAIL,
    "IP_C": IP_C,
    "ASN": ASN,
    "nodeCounts": TOTAL,
    "r_cert": R_CERT,
    "r_subdomain": R_SUBDOMAIN,
    "r_request_jump": R_REQUEST_JUMP,
    "r_dns_a": R_DNS_A,
    "r_whois_name": R_WHOIS_NAME,
    "r_whois_email": R_WHOIS_EMAIL,
    "r_whois_phone": R_WHOIS_PHONE,
    "r_cname": R_CNAME,
    "r_asn": R_ASN,
    "r_cidr": R_CIDR,
    "r_cert_chain": R_CERT_CHAIN,
    "linksCount": TATAL1,


}

import csv
print(dat)
df = pd.DataFrame(dat)
# print(df)
df.to_csv('out2.csv')
#
# f = open('xixi.csv', mode='a', encoding='utf-8', newline='')  # xixi为文件名称
# csv_writer = csv.DictWriter(f, fieldnames=['id', 'nodesCount', 'coreCount', 'linksCount', 'keyCount'])  # 列名
# csv_writer.writeheader()  # 列名写入csv
#
# csv_writer.writerow(dat)  # 数据写入csv文件


