from __future__ import annotations

from teams.planning_team import PlanningTeam
from teams.development_team import DevelopmentTeam
from teams.qa_team import QATeam
from teams.documentation_team import DocumentationTeam
from teams.security_team import SecurityTeam
from teams.automation_team import AutomationTeam


class TeamManager:
    def __init__(self, worker_manager):
        self.teams = {
            "planning_team": PlanningTeam(worker_manager),
            "development_team": DevelopmentTeam(worker_manager),
            "qa_team": QATeam(worker_manager),
            "documentation_team": DocumentationTeam(worker_manager),
            "security_team": SecurityTeam(worker_manager),
            "automation_team": AutomationTeam(worker_manager),
        }

    def execute(self, team_id, worker_id, payload):
        team = self.teams.get(team_id)
        if team is None:
            raise ValueError(f"Unknown team_id: {team_id}")
        return team.execute(worker_id, payload)

    def list_teams(self):
        return [team.profile() for team in self.teams.values()]
