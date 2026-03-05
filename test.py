import requests
import json

url = "http://127.0.0.1:3001/local/dirs"
headers = {"Content-Type": "application/json"}
data = {"path": "F:/音乐收藏/download", "name": "音乐收藏"}

response = requests.post(url, headers=headers, json=data)
print(response.status_code)
print(response.text)