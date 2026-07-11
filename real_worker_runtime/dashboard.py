class TerminalDashboard:
    def __init__(self, live=True): self.live=live
    def render(self,session):
        if not self.live: return
        print("\nAI Factory OS - Real Worker Runtime")
        print(f"Session: {session.session_id} | Sprint: {session.sprint_id} | Status: {session.status.upper()}")
        for wid,state in session.workers.items(): print(f"[{wid.replace('_',' ').title():24}] {state.upper()}")
        print(f"Current activity: {session.current_activity}\nProgress: {session.progress}%")
