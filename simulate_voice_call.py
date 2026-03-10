import requests

url = "http://127.0.0.1:5000/voice_call_webhook"

call_payload = {
    "caller_id": "+919876543210",
    "transcript": "Hello, this is Ravi. I want to see a cardiologist tomorrow morning for chest pain.",
}

response = requests.post(url, json=call_payload)

print("\nServer Response (Voice call):")
print(response.json())

