from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class KnowledgeRetrievalState(BaseModel):
    user_query: str = ""
    retrieved_content: List[Dict[str, Any]] = []
    final_answer: str = ""
