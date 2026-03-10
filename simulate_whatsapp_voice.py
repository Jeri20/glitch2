import requests

url = "http://127.0.0.1:5000/webhook"

voice_message = {
    "from": "919876543210",
    "name": "Ravi",
    "type": "voice",  # indicate this is a (simulated) voice note
    "text": "Hello, this is Ravi. I want to see a cardiologist tomorrow morning for chest pain.",
    "timestamp": "1710001000",
}

response = requests.post(url, json=voice_message)

print("\nServer Response (WhatsApp voice note):")
print(response.json())

