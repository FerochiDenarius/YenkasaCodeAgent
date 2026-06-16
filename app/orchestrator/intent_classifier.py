from __future__ import annotations


class IntentClassifier:
    yenkasa_context_keywords = (
        "yenkasa",
        "yenkasa app",
        "yenkasa ai",
        "yenkasaai",
        "yenkasa chat",
        "yenkasachat",
        "yenkasa community",
        "yenkasacommunity",
    )
    yenkasa_database_context_keywords = (
        "yenkasa_store",
        "yenkasa store",
        "store database",
    )
    yenkasa_diagnostic_keywords = (
        "bug",
        "bugs",
        "fix",
        "broken",
        "crash",
        "crashes",
        "issue",
        "issues",
        "problem",
        "problems",
        "why",
        "where",
        "find",
        "missing",
        "failing",
        "failure",
        "error",
    )
    keyword_map = {
        "database": (
            "database",
            "mongo",
            "mongodb",
            "embedding",
            "repo_chunks",
            "memory_embeddings",
            "storage",
            "collection",
            "collections",
            "list collections",
            "count documents",
            "document count",
            "show indexes",
            "list indexes",
            "missing indexes",
            "audit schema",
            "database schema",
            "schema inspection",
            "slow query",
            "slow queries",
            "database performance",
            "database health",
            "runtime exception",
            "runtime exceptions",
            "explain plan",
            "sql",
            "mysql",
            "postgres",
            "postgresql",
            "baleshop",
            "bale_shop",
            "yenkasa_store",
            "store database",
        ),
        "repository": (
            "repository",
            "repo",
            "repos",
            "indexed repositories",
            "kotlin files",
            "python files",
            "language breakdown",
            "chunk count",
        ),
        "search": (
            "check",
            "find",
            "search",
            "locate",
            "where is",
            "show code",
            "show implementation",
            "similar code",
            "heroku",
            "procfile",
            "dyno",
            "call server",
            "video call",
            "video server",
            "signaling",
            "signalling",
            "websocket",
            "socket.io",
            "socketio",
            "server",
            "notification",
            "payment",
            "login",
        ),
        "audit": (
            "audit",
            "review code",
            "security audit",
            "architecture audit",
            "analyze repository",
            "find issues",
        ),
        "refactor": (
            "refactor",
            "improve architecture",
            "reduce technical debt",
            "clean up code",
            "extract service",
            "optimize structure",
            "technical debt",
        ),
        "deployment": (
            "deployment",
            "cloud run",
            "revision",
            "service status",
            "traffic",
            "healthy",
            "deployment health",
        ),
        "observability": (
            "logs",
            "log summary",
            "error",
            "errors",
            "failure",
            "failures",
            "failing",
            "performance",
            "incident",
            "monitoring",
            "notification",
            "notification failures",
        ),
        "product_builder": (
            "generate",
            "build",
            "create project",
            "create api",
            "create schema",
            "create screen",
            "generate code",
        ),
    }

    def classify(self, query: str) -> list[str]:
        normalized = query.lower()
        intents = [
            intent
            for intent, keywords in self.keyword_map.items()
            if any(keyword in normalized for keyword in keywords)
        ]
        if self._is_yenkasa_context(normalized):
            self._append_unique(intents, "repository")
            if any(keyword in normalized for keyword in self.yenkasa_diagnostic_keywords):
                self._append_unique(intents, "search")
                self._append_unique(intents, "audit")
        if len(intents) > 1:
            return ["multi-agent", *intents]
        return intents or ["repository"]

    def _is_yenkasa_context(self, normalized_query: str) -> bool:
        if any(keyword in normalized_query for keyword in self.yenkasa_database_context_keywords):
            return False
        return any(keyword in normalized_query for keyword in self.yenkasa_context_keywords)

    @staticmethod
    def _append_unique(intents: list[str], intent: str) -> None:
        if intent not in intents:
            intents.append(intent)
