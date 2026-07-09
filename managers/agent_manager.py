from __future__ import annotations

from agents.ceo_agent import CEOAgent
from agents.pm_agent import PMAgent
from agents.planning_agent import PlanningAgent
from agents.development_agent import DevelopmentAgent
from agents.test_agent import TestAgent
from agents.security_agent import SecurityAgent
from agents.documentation_agent import DocumentationAgent
from agents.deploy_agent import DeployAgent
from agents.automation_agent import AutomationAgent


class AgentManager:
    def __init__(self):
        self.agents = {
            "ceo_agent": CEOAgent(),
            "pm_agent": PMAgent(),
            "planning_agent": PlanningAgent(),
            "development_agent": DevelopmentAgent(),
            "test_agent": TestAgent(),
            "security_agent": SecurityAgent(),
            "documentation_agent": DocumentationAgent(),
            "deploy_agent": DeployAgent(),
            "automation_agent": AutomationAgent(),
        }

    def get(self, agent_id):
        return self.agents[agent_id]

    def list_agents(self):
        return [agent.profile() for agent in self.agents.values()]
