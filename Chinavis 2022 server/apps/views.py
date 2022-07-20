import sys
import os

import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(sys.path[0]))

from django.http import JsonResponse, HttpResponse


def getnodebyid(request):
    if request.method == 'GET':
        group_id = request.GET.get('id')
        count = 0

        domain = 0
        iP = 0
        cert = 0
        whois_Name = 0
        whois_Phone = 0
        whois_Email = 0
        iP_C = 0
        aSN = 0

        data = {
            "info": {
                "value": count,
                "count": {
                    "Domain": domain,
                    "IP": iP,
                    "Cert": cert,
                    "Whois_Name": whois_Name,
                    "Whois_Phone": whois_Phone,
                    "Whois_Email": whois_Email,
                    "IP_C": iP_C,
                    "ASN": aSN
                }
            },
            "node": [

            ]
        }
        # "Domain": [],
        # "IP": [],
        # "Cert": [],
        # "Whois_Name": [],
        # "Whois_Phone": [],
        # "Whois_Email": [],
        # "IP_C": [],
        # "ASN": []
        dict = {'Domain': 3, 'IP': 3, 'Cert': 3, 'Whois_Name': 2, 'Whois_Phone': 2, 'Whois_Email': 2, 'IP_C': 1,
                'ASN': 1}
        type = {'Domain': 0, 'IP': 1, 'Cert': 2, 'Whois_Name': 3, 'Whois_Phone': 4, 'Whois_Email': 5, 'IP_C': 6,
                'ASN': 7}

        import networkx as nx
        import pandas as pd

        link: pd.DataFrame = pd.read_csv('./apps/resource/node/edge_of_' + group_id + '.csv')
        G = nx.from_pandas_edgelist(link)
        degreedict = nx.degree(G)

        core: pd.DataFrame = pd.read_csv('./apps/resource/core/coreAsts_of_' + group_id + '.csv')
        array = np.array(core["id"])



        import csv
        name = "./apps/resource/node/node_of_" + group_id + ".csv"
        with open(name, 'r', encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row[1] != "id":
                    count = count + 1
                    data["info"]["count"][row[3]] += 1
                    dat = {
                        "id": row[1],
                        "name": row[2],
                        "industry": row[4],
                        # "category": row[3],
                        "weight": dict[row[3]],
                        "category": type[row[3]],
                        "degree": degreedict[row[1]],
                        "isKey": row[1] in array
                    }
                    data["node"].append(dat)
        data["info"]["value"] = count

    return JsonResponse(data, charset='utf-8', safe=False, json_dumps_params={'ensure_ascii': False})


def getedgebyid(request):
    if request.method == 'GET':
        group_id = request.GET.get('id')
        count = 0
        r_cert = 0
        r_subdomain = 0
        r_request_jump = 0
        r_dns_a = 0
        r_whois_name = 0
        r_whois_email = 0
        r_whois_phone = 0
        r_cname = 0
        r_asn = 0
        r_cidr = 0
        r_cert_chain = 0
        data = {
            "info": {
                "value": count,
                "count": {
                    "r_cert": r_cert,
                    "r_subdomain": r_subdomain,
                    "r_request_jump": r_request_jump,
                    "r_dns_a": r_dns_a,
                    "r_whois_name": r_whois_name,
                    "r_whois_email": r_whois_email,
                    "r_whois_phone": r_whois_phone,
                    "r_cert_chain": r_cert_chain,
                    "r_cname": r_cname,
                    "r_asn": r_asn,
                    "r_cidr": r_cidr
                }

            },
            "edge": []
        }

        # "r_cert": [],
        # "r_subdomain": [],
        # "r_request_jump": [],
        # "r_dns_a": [],
        # "r_whois_name": [],
        # "r_whois_email": [],
        # "r_whois_phone": [],
        # "r_cert_chain": [],
        # "r_cname": [],
        # "r_asn": [],
        # "r_cidr": []

        core: pd.DataFrame = pd.read_csv('./apps/resource/road/keyRoads_' + group_id + '.csv')
        array = np.array(core)


        type = {'r_cert': 0, 'r_subdomain': 1, 'r_request_jump': 2, 'r_dns_a': 3, 'r_whois_name': 4, 'r_whois_email': 5,
                'r_whois_phone': 6,
                'r_cert_chain': 7, 'r_cname': 8, 'r_asn': 9, 'r_cidr': 10}
        import csv
        name = "./apps/resource/node/edge_of_" + group_id + ".csv"
        with open(name, 'r', encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row[1] != "source":
                    count = count + 1
                    data["info"]["count"][row[3]] += 1
                    dat = {
                        "source": row[1],
                        "target": row[2],
                        "weight": int(row[4]),
                        "category": type[row[3]],
                        "isRoad": (row[1] in array and row[2] in array)
                    }
                    data["edge"].append(dat)
        data["info"]["value"] = count

    return JsonResponse(data, charset='utf-8', safe=False, json_dumps_params={'ensure_ascii': False})


def getnodecountlist(request):
    if request.method == 'GET':
        name = request.GET.get('name')
        data = {
            "data": []
        }
        for i in range(10):
            filename = "./apps/resource/node/node_of_" + str(i + 1) + ".csv"
            total = sum(1 for line in open(filename, encoding="UTF-8"))
            total = total - 1

            filename = "./apps/resource/core/coreAsts_of_" + str(i + 1) + ".csv"
            corecount = sum(1 for line in open(filename, encoding="UTF-8"))
            corecount = corecount - 1

            import networkx as nx
            import pandas as pd

            link: pd.DataFrame = pd.read_csv('./apps/resource/node/edge_of_' + str(i + 1) + '.csv')
            G = nx.from_pandas_edgelist(link)
            cluster = nx.average_clustering(G)
            diameter = nx.diameter(G)

            dat = {
                "id": i,
                "nodesCount": total,
                "coreCount": corecount,
                "cluster": cluster,
                "diameter": diameter
            }
            data["data"].append(dat)
    return JsonResponse(data, charset='utf-8', safe=False, json_dumps_params={'ensure_ascii': False})


def getedgecountlist(request):
    if request.method == 'GET':
        name = request.GET.get('name')
        data = {
            "data": []
        }
        for i in range(10):
            filename = "./apps/resource/node/edge_of_" + str(i + 1) + ".csv"
            total = sum(1 for line in open(filename, encoding="UTF-8"))
            total = total - 1

            filename = "./apps/resource/road/keyRoads_" + str(i + 1) + ".csv"
            keycount = sum(1 for line in open(filename, encoding="UTF-8"))
            keycount = keycount - 1


            dat = {
                "id": i,
                "linksCount": total,
                "keyCount": keycount,
            }
            data["data"].append(dat)
    return JsonResponse(data, charset='utf-8', safe=False, json_dumps_params={'ensure_ascii': False})


def getgroupsinfo(request):
    if request.method == 'GET':
        name = request.GET.get('name')
        data = {
            "data": []
        }
        for i in range(10):
            filename = "./apps/resource/node/node_of_" + str(i + 1) + ".csv"
            total = sum(1 for line in open(filename, encoding="UTF-8"))
            total = total - 1

            filename = "./apps/resource/core/coreAsts_of_" + str(i + 1) + ".csv"
            corecount = sum(1 for line in open(filename, encoding="UTF-8"))
            corecount = corecount - 1

            import networkx as nx
            import pandas as pd


            link: pd.DataFrame = pd.read_csv('./apps/resource/node/edge_of_' + str(i + 1) + '.csv')
            G = nx.from_pandas_edgelist(link)
            cluster = nx.average_clustering(G)
            if(i==8):
                cluster = 	0.05224456432548607
            # diameter = nx.diameter(G)

            filename = "./apps/resource/node/edge_of_" + str(i + 1) + ".csv"
            total1 = sum(1 for line in open(filename, encoding="UTF-8"))
            total1 = total1 - 1

            filename = "./apps/resource/road/keyRoads_" + str(i + 1) + ".csv"
            keycount = sum(1 for line in open(filename, encoding="UTF-8"))
            keycount = keycount - 1

            dat = {
                "id": i,
                "nodesCount": total,
                "coreCount": corecount,
                "cluster": cluster,
                # "diameter": diameter,

                "linksCount": total1,
                "keyCount": keycount
            }
            data["data"].append(dat)


    return JsonResponse(data, charset='utf-8', safe=False, json_dumps_params={'ensure_ascii': False})

def getcorebyid(request):
    if request.method == 'GET':
        group_id = request.GET.get('id')
        count = 0

        domain = 0
        iP = 0
        cert = 0
        whois_Name = 0
        whois_Phone = 0
        whois_Email = 0
        iP_C = 0
        aSN = 0

        data = {
            "info": {
                "value": count,
                "count": {
                    "Domain": domain,
                    "IP": iP,
                    "Cert": cert,
                    "Whois_Name": whois_Name,
                    "Whois_Phone": whois_Phone,
                    "Whois_Email": whois_Email,
                    "IP_C": iP_C,
                    "ASN": aSN
                }
            },
            "node": [

            ]
        }
        # "Domain": [],
        # "IP": [],
        # "Cert": [],
        # "Whois_Name": [],
        # "Whois_Phone": [],
        # "Whois_Email": [],
        # "IP_C": [],
        # "ASN": []
        dict = {'Domain': 3, 'IP': 3, 'Cert': 3, 'Whois_Name': 2, 'Whois_Phone': 2, 'Whois_Email': 2, 'IP_C': 1,
                'ASN': 1}
        type = {'Domain': 0, 'IP': 1, 'Cert': 2, 'Whois_Name': 3, 'Whois_Phone': 4, 'Whois_Email': 5, 'IP_C': 6,
                'ASN': 7}

        import networkx as nx
        import pandas as pd

        link: pd.DataFrame = pd.read_csv('./apps/resource/node/edge_of_' + group_id + '.csv')
        G = nx.from_pandas_edgelist(link)
        degreedict = nx.degree(G)





        import csv
        name = "./apps/resource/core/coreAsts_of_" + group_id + ".csv"
        with open(name, 'r', encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row[1] != "id":
                    count = count + 1
                    data["info"]["count"][row[3]] += 1
                    dat = {
                        "id": row[1],
                        "name": row[2],
                        "industry": row[4],
                        # "category": row[3],
                        "weight": dict[row[3]],
                        "category": type[row[3]],
                        "degree": degreedict[row[1]],
                       # "isCore":
                    }
                    data["node"].append(dat)
        data["info"]["value"] = count

    return JsonResponse(data, charset='utf-8', safe=False, json_dumps_params={'ensure_ascii': False})


def getroadbyid(request):
    if request.method == 'GET':
        group_id = request.GET.get('id')
        count = 0
        # r_cert = 0
        # r_subdomain = 0
        # r_request_jump = 0
        # r_dns_a = 0
        # r_whois_name = 0
        # r_whois_email = 0
        # r_whois_phone = 0
        # r_cname = 0
        # r_asn = 0
        # r_cidr = 0
        # r_cert_chain = 0
        data = {
            "info": {
                "count": count
                #     {
                #     "r_cert": r_cert,
                #     "r_subdomain": r_subdomain,
                #     "r_request_jump": r_request_jump,
                #     "r_dns_a": r_dns_a,
                #     "r_whois_name": r_whois_name,
                #     "r_whois_email": r_whois_email,
                #     "r_whois_phone": r_whois_phone,
                #     "r_cert_chain": r_cert_chain,
                #     "r_cname": r_cname,
                #     "r_asn": r_asn,
                #     "r_cidr": r_cidr
                # }

            },
            "road": []
        }

        # "r_cert": [],
        # "r_subdomain": [],
        # "r_request_jump": [],
        # "r_dns_a": [],
        # "r_whois_name": [],
        # "r_whois_email": [],
        # "r_whois_phone": [],
        # "r_cert_chain": [],
        # "r_cname": [],
        # "r_asn": [],
        # "r_cidr": []

        # type = {'r_cert': 0, 'r_subdomain': 1, 'r_request_jump': 2, 'r_dns_a': 3, 'r_whois_name': 4, 'r_whois_email': 5,
        #         'r_whois_phone': 6,
        #         'r_cert_chain': 7, 'r_cname': 8, 'r_asn': 9, 'r_cidr': 10}
        import csv
        name = "./apps/resource/road/keyRoads_" + group_id + ".csv"
        with open(name, 'r', encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row[1] != "0":
                    count = count + 1
                    # data["info"]["count"][row[3]] += 1
                    dat = {
                        "source": row[1],
                        "target1": row[2],
                        "target2": row[3],
                        "target3": row[4]
                    }
                    data["road"].append(dat)
        data["info"]["count"] = count

    return JsonResponse(data, charset='utf-8', safe=False, json_dumps_params={'ensure_ascii': False})


def getnodebyid1(request):
    if request.method == 'GET':
        group_id = request.GET.get('id')
        count = 0
        data = {
            "info": {
                "count": count
            },
            "node": [

            ]
        }
        # "Domain": [],
        # "IP": [],
        # "Cert": [],
        # "Whois_Name": [],
        # "Whois_Phone": [],
        # "Whois_Email": [],
        # "IP_C": [],
        # "ASN": []
        dict = {'Domain': 3, 'IP': 3, 'Cert': 3, 'Whois_Name': 2, 'Whois_Phone': 2, 'Whois_Email': 2, 'IP_C': 1,
                'ASN': 1}
        type = {'Domain': 0, 'IP': 1, 'Cert': 2, 'Whois_Name': 3, 'Whois_Phone': 4, 'Whois_Email': 5, 'IP_C': 6,
                'ASN': 7}

        import networkx as nx
        import pandas as pd

        link: pd.DataFrame = pd.read_csv('./apps/resource/edge_of_' + group_id + '.csv')
        G = nx.from_pandas_edgelist(link)
        degreedict = nx.degree(G)


        import csv
        name = "./apps/resource/node_of_" + group_id + ".csv"
        with open(name, 'r', encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row[1] != "id":
                    count = count + 1
                    dat = {
                        "id": row[1],
                        "name": row[2],
                        "industry": row[4],
                        # "category": row[3],
                        "weight": dict[row[3]],
                        "category": type[row[3]],
                        "degree": degreedict[row[1]]
                    }
                    data["node"].append(dat)
        data["info"]["count"] = count

    return JsonResponse(data, charset='utf-8', safe=False, json_dumps_params={'ensure_ascii': False})


def getedgebyid1(request):
    if request.method == 'GET':
        group_id = request.GET.get('id')
        count = 0
        data = {
            "info": {
                "count": count
            },
            "edge": []
        }

        # "r_cert": [],
        # "r_subdomain": [],
        # "r_request_jump": [],
        # "r_dns_a": [],
        # "r_whois_name": [],
        # "r_whois_email": [],
        # "r_whois_phone": [],
        # "r_cert_chain": [],
        # "r_cname": [],
        # "r_asn": [],
        # "r_cidr": []

        type = {'r_cert': 0, 'r_subdomain': 1, 'r_request_jump': 2, 'r_dns_a': 3, 'r_whois_name': 4, 'r_whois_email': 5,
                'r_whois_phone': 6,
                'r_cert_chain': 7, 'r_cname': 8, 'r_asn': 9, 'r_cidr': 10}
        import csv
        name = "./apps/resource/edge_of_" + group_id + ".csv"
        with open(name, 'r', encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row[1] != "source":
                    count = count + 1
                    dat = {
                        "source": row[1],
                        "target": row[2],
                        "weight": int(row[4]),
                        "category": type[row[3]]
                    }
                    data["edge"].append(dat)
        data["info"]["count"] = count

    return JsonResponse(data, charset='utf-8', safe=False, json_dumps_params={'ensure_ascii': False})
