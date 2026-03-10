import requests

url = "http://127.0.0.1:5000/webhook"

message = {
    "from": "919876543210",
    "name": "Rahul1",
    "text": "Hi I am in Velachery. I have fever and cough. I need consultation tomorrow morning",
    "timestamp": "1710000000"
}

response = requests.post(url, json=message)

print("\nServer Response:")
print(response.json())