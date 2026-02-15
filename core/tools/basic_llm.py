from crewai import LLM
from django.conf import settings

# Switched to OpenAI to avoid Groq rate limits (8k TPM is too low for orchestration)
basic_llm = LLM(
    model="openai/gpt-4o-mini",
    temperature=0.3,
    api_key=settings.OPENAI_API_KEY
)