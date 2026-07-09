from __future__ import annotations


def register_agent_commands(subparsers):
    agent_parser = subparsers.add_parser("agent", help="Agent/Team 구조 확인")
    agent_subparsers = agent_parser.add_subparsers(dest="agent_command")
    agent_subparsers.add_parser("list", help="등록된 Agent 목록")
    agent_subparsers.add_parser("teams", help="등록된 Team 목록")


def handle_agent_command(kernel, args) -> None:
    if args.agent_command == "list":
        print("\n=== Agent 목록 ===")
        for agent in kernel.list_agents():
            print(f"{agent['agent_id']} | {agent['role']} | {agent['status']}")
        return

    if args.agent_command == "teams":
        print("\n=== Team 목록 ===")
        for team in kernel.list_teams():
            print(f"{team['team_id']} | {team['role']} | {team['status']}")
        return

    print("agent 하위 명령어가 필요합니다.")
