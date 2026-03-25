import requests

OPENROUTER_API_KEY = "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"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "meta-llama/llama-3.3-70b-instruct"

headers = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
}
payload = {
    "model": MODEL,
    "messages": [{"role": "user", "content": "hi"}],
}
response = requests.post(
    f"{OPENROUTER_BASE_URL}/chat/completions",
    headers=headers,
    json=payload,
    timeout=30
)
print("Status:", response.status_code)
print("Body:", response.text)
