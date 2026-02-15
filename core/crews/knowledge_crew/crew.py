from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from core.tools import vision_llm
from core.tools.rag_tool import RAGTool

@CrewBase
class KnowledgeCrew:
    """Knowledge Crew"""
    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    @agent
    def knowledge_assistant(self) -> Agent:
        return Agent(
            config=self.agents_config['knowledge_assistant'],
            verbose=True,
            tools=[RAGTool()],
            llm=vision_llm,
            allow_delegation=False
        )

    @task
    def knowledge_retrieval_task(self) -> Task:
        return Task(
            config=self.tasks_config['knowledge_retrieval_task'],
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
