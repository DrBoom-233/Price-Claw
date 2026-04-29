# config.py
import os
from dotenv import load_dotenv


load_dotenv()

API_KEY = os.environ.get("DEEPSEEK_API_KEY")
CHAT_MODEL = os.environ.get("DEEPSEEK_CHAT_MODEL")
REASONING_MODEL = os.environ.get("DEEPSEEK_REASONING_MODEL")
URL   = os.environ.get("DEEPSEEK_URL")


OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL")
OPENAI_REASONING_MODEL = os.environ.get("OPENAI_REASONING_MODEL")
OPENAI_API_KEY_FOR_REASONING = os.environ.get("OPENAI_API_KEY_FOR_REASONING")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

LLM_PROVIDER = os.environ.get("LLM_PROVIDER")
LLM_API_KEY = os.environ.get("LLM_API_KEY")
LLM_MODEL = os.environ.get("LLM_MODEL")
LLM_REASONING_MODEL = os.environ.get("LLM_REASONING_MODEL")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL")
