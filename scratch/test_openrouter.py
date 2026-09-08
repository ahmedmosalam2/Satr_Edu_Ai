import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(".env")

api_key = os.getenv("OPENAI_API_KEY")
api_url = os.getenv("OPENAI_API_URL")
model = os.getenv("GENERATION_MODEL_ID")

print(f"API Key: {api_key[:12]}...")
print(f"API URL: {api_url}")
print(f"Model ID: {model}")

client = OpenAI(api_key=api_key, base_url=api_url)
try:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "test"}],
        max_tokens=10
    )
    print("Success response:")
    print(response.choices[0].message.content)
except Exception as e:
    print("Error calling OpenAI/OpenRouter:")
    print(e)
