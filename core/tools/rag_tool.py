import os
import threading
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from knowledge_base.services.rag_service import RAGService
from django.contrib.auth.models import User

# Disable unstructured library telemetry which can cause hangs
os.environ["SCARF_NO_ANALYTICS"] = "true"
# Allow Django ORM to run in async contexts
os.environ["DJANGO_ALLOW_ASYNC_QUERY"] = "true"

class KnowledgeRetrievalInput(BaseModel):
    """Input schema for KnowledgeRetrievalTool."""
    query: str = Field(..., description="The user's question to be answered by the knowledge base.")

class RAGTool(BaseTool):
    name: str = "Knowledge Retrieval Tool"
    description: str = (
        "Useful for retrieving relevant information from the company's knowledge base "
        "to answer technical or operational questions. Always use this tool when the user asks "
        "about company procedures, manuals, or safety guidelines."
    )
    args_schema: Type[BaseModel] = KnowledgeRetrievalInput

    def _run(self, query: str) -> str:
        """Execute the RAG query in a dedicated thread to bypass Django's SynchronousOnlyOperation."""
        result_container = {"output": None, "error": None}

        def worker():
            try:
                # Inside this new thread, there is no event loop, so Django shouldn't complain.
                user = User.objects.filter(is_superuser=True).first()
                if not user:
                    result_container["output"] = "Error: No system user found."
                    return

                service = RAGService()
                result = service.query_knowledge(query_text=query, user=user)
                
                answer = result.get('answer', "No answer found.")
                sources = result.get('sources', [])
                formatted_sources = "\n".join([f"- {s['document']} (Page {s['page']})" for s in sources])
                
                result_container["output"] = f"Answer: {answer}\n\nSources:\n{formatted_sources}"
            except Exception as e:
                import traceback
                result_container["error"] = f"{str(e)}\n{traceback.format_exc()}"

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()

        if result_container["error"]:
            return f"Error retrieving knowledge: {result_container['error']}"
        
        return result_container["output"] or "Error: Tool execution failed silently."

    async def _arun(self, query: str) -> str:
        """Async version calls the sync version as it handles threading itself."""
        return self._run(query)
