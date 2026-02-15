import logging
from .state import KnowledgeRetrievalState
from crewai.flow import Flow, start, listen
from core.crews.knowledge_crew.crew import KnowledgeCrew
from django.conf import settings

logger = logging.getLogger(__name__)

class KnowledgeRetrievalFlow(Flow[KnowledgeRetrievalState]):
    
    @start()
    def retrieve_knowledge(self):
        """Execute the Knowledge Crew to retrieve and synthesize information."""
        logger.info(f"Knowledge Flow Started: {self.state.user_query}")
        
        try:
            crew = KnowledgeCrew().crew()
            response = crew.kickoff(inputs={'user_query': self.state.user_query})
            
            # The crew result is typically a CrewOutput object, we want the raw string
            self.state.final_answer = response.raw
            logger.info("Knowledge Crew execution completed.")
            
            return self.state.final_answer
            
        except Exception as e:
            logger.exception(f"Knowledge Crew execution failed: {e}")
            self.state.final_answer = "I encountered an error while searching the knowledge base. Please try again later."
            return self.state.final_answer
            
    def kickoff(self, user_query: str):
        """Start the flow with a user query."""
        self.state.user_query = user_query
        super().kickoff()
        return self.state.final_answer
