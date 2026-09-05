import os
from google import genai
from google.genai import types

api_key = os.environ.get("GEMINI_API_KEY")
model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

if not api_key:
    raise SystemExit("GEMINI_API_KEY is not set in your environment.")

client = genai.Client(api_key=api_key)
response = client.models.generate_content(
    model=model,
    contents="You are a friendly nutrition coach. Write ONE short, warm, actionable nutrition tip. Maximum 25 words. No medical claims. Return only the tip.",
    config=types.GenerateContentConfig(max_output_tokens=60, temperature=0.7),
)

print(f"Model used: {model}")
print(f"Response text: {response.text!r}")
