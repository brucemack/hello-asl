import requests

# The AllStarLink registration server
reg_url = "https://www.allstarlink.org/api/simple-node-auth.php"

reg_msg = { "api": "API_PASSWORD", "node": 61057, "passwd": "xxxx", "cookie": "oatmeal" }
print("Registration URL:", reg_url)
print("Registration request:", reg_msg)
reg_response = requests.post(reg_url, json=reg_msg)
print("Registration response:", reg_response.text)
