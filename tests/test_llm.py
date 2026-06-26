import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Try to find .env in project root (2 levels up from tests/ folder)
project_root = Path(__file__).resolve().parent.parent
env_path = project_root / ".env"

print(f"Looking for .env at: {env_path}")
print(f".env exists: {env_path.exists()}")

if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(".env loaded successfully")
else:
    print("WARNING: .env not found, trying default load_dotenv()")
    load_dotenv()

# Check what we actually have
api_key = os.getenv("GROQ_API_KEY")
print(f"GROQ_API_KEY found: {'Yes (length: ' + str(len(api_key)) + ')' if api_key else 'No - EMPTY or MISSING'}")

if not api_key:
    print("\n❌ GROQ_API_KEY is empty. Check your .env file contents.")
    sys.exit(1)

print("\nAttempting to connect to Groq...")

try:
    from langchain_groq import ChatGroq
    
    llm = ChatGroq(
        api_key=api_key,
        model="llama-3.3-70b-versatile",
        temperature=0.0,
        max_retries=2,
    )
    
    print("LLM initialized. Sending test message...")
    response = llm.invoke("Say hello and confirm you are online. Reply in one sentence.")
    
    print("\n✅ SUCCESS! Groq LLM is connected and responding.")
    print(f"Response: {response.content}")
    
except ImportError as e:
    print(f"\n❌ Import Error: {e}")
    print("langchain_groq not installed. Run: pip install langchain-groq")
    sys.exit(1)
    
except Exception as e:
    print(f"\n❌ Connection Failed: {type(e).__name__}: {e}")
    sys.exit(1)