import random
import re
import pandas as pd

# fetch data from file
with open('res-backup.txt', 'r') as f:
    data = f.read()
print('Finish reading community data.')

# process string and finally get an array, whose elements are strings
data = data.replace("'", '').replace(' ', '')
pattern = re.compile(r'{(.*?)}', re.S)
data = re.findall(pattern, data)

# randomly select a community and turn the string into an array, whose elements are id of nodes
data = data[random.randint(0, len(data) - 1)]
data = data.split(',')
print('Finish getting a random community.')

# get data from
link: pd.DataFrame = pd.read_csv('./resource/Link.csv')
node: pd.DataFrame = pd.read_csv('./resource/Node.csv')

n: pd.DataFrame = node[node['id'].isin(data)]
l: pd.DataFrame = link[(link['source'].isin(data) & link['target'].isin(data))]
print('Finish filtering data from raw dataset.')

# return result
result = {
    'node': n.to_json(orient='records'),
    'link': l.to_json(orient='records')
}
print('Done generating result.')
