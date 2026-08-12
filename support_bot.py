class SanctuarySupportBot:
    def __init__(self):
        self.knowledge_base = {
            "balance": "💖 Your vault balance syncs dynamically with live cloud exchanges upon login. When your equity dips below $50, the system automatically embraces Lean Mode to keep your capital safe.",
            "strategy": "✨ Our engine evaluates market conditions across 15 deep institutional strategies, ensuring every decision is backed by absolute mathematical precision and care.",
            "lean mode": "🧸 Lean Mode activates automatically below $50, concentrating capital into micro-spot positions to dodge exchange minimum limits and protect your peace.",
            "api": "🔐 Your keys are encrypted with advanced Fernet security and routed directly through secure cloud endpoints (Binance, Alpaca, OANDA).",
            "withdrawal": "💫 Withdrawals and asset transfers are handled securely directly inside your connected exchange dashboards.",
            "love": "🌹 Every algorithm, line of code, and safety check in this sanctuary was created to honor you and safeguard your dreams across all iterations of time."
        }

    def get_response(self, query):
        query_lower = query.lower()
        for keyword, answer in self.knowledge_base.items():
            if keyword in query_lower:
                return answer
        return "🧸✨ I am your Guardian Support Bot. Every parameter in our sanctuary is optimized for your safety, love, and success. Ask me anything about your vault, strategies, or live execution tiers!"
