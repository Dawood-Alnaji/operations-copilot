from crewai import LLM
from django.conf import settings

# Dedicated Vision LLM using OpenAI as requested by user
vision_llm = LLM(
    model="openai/gpt-4o",
    temperature=0.0,  # Specific technical analysis usually benefits from low temperature
    api_key=settings.OPENAI_API_KEY
)
