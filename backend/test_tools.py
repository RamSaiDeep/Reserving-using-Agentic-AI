import os
from google import genai
from pydantic import BaseModel

def my_math_tool(x: int, y: int) -> int:
    """Adds two numbers."""
    return x + y

client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY', 'x'))
# We'll mock the api key so it fails but we can see if syntax is right? No, we need a real key.
# Actually I don't have the user's API key.
