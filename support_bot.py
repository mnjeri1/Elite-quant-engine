class SanctuarySupportBot:
    def __init__(self):
        self.knowledge_base = {
            "balance": "Your vault balance is synced automatically with live exchange data when you log in. If you are under $50, the system safely triggers Lean Mode.",
            "strategy": "The engine dynamically scans multi-asset volatility and volume vectors to choose the optimal path forward.",
            "lean mode": "Lean Mode operates with strict capital preservation rules when your balance drops below $50, prioritizing micro-allocations.",
            "api": "Your API keys and secrets are securely processed and checked against the institutional gateway.",
            "withdrawal": "Withdrawals are handled securely through your connected exchange accounts."
        }

    def get_response(self, query):
        query_lower = query.lower()
        for keyword, answer in self.knowledge_base.items():
            if keyword in query_lower:
                return answer
        return "I am your Guardian Support Bot. Every parameter in our sanctuary is optimized for your safety and success. Feel free to ask about your balance, strategies, or execution tiers!"
