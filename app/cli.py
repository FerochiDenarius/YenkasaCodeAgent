from __future__ import annotations

import argparse
from datetime import datetime, timezone
from getpass import getpass
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
from typing import Any

import httpx


DEFAULT_YENKASA_AI_URL = "https://yenkasa-ai-backend-496173204476.europe-west1.run.app"
DEFAULT_CODE_AGENT_URL = "https://yenkasa-code-agent-3vx2nvls4a-ew.a.run.app"
CONFIG_PATH = Path(os.getenv("YCA_CONFIG", "~/.yca/config.json")).expanduser()
LOG_DIR = Path(os.getenv("YCA_LOG_DIR", "logs"))
COMMAND_NAMES = {
    "login",
    "agents",
    "agent",
    "repos",
    "repo",
    "search",
    "open",
    "audit",
    "memory",
    "indexing",
    "analytics",
    "orchestration",
    "doctor",
}
AGENT_ALIASES = {
    "repoagent": "RepositoryAgent",
    "repositoryagent": "RepositoryAgent",
    "memoryagent": "VectorSearchAgent",
    "searchagent": "VectorSearchAgent",
    "auditagent": "CodeAuditAgent",
    "codereviewagent": "CodeAuditAgent",
    "analyticsagent": "DatabaseAgent",
    "indexingagent": "RepositoryAgent",
    "databaseagent": "DatabaseAgent",
    "cloudrunagent": "CloudRunAgent",
    "observabilityagent": "ObservabilityAgent",
    "refactoragent": "RefactorAgent",
    "productbuilderagent": "ProductBuilderAgent",
    "system": "system",
}


class YCAError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise YCAError(f"Invalid config file: {CONFIG_PATH}") from exc


def write_config(config: dict[str, Any]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    try:
        CONFIG_PATH.chmod(0o600)
    except OSError:
        pass


def log_event(event: dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"timestamp": utc_now(), **event}
    with (LOG_DIR / "yca.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str, separators=(",", ":")) + "\n")


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    redacted = dict(headers)
    for key in list(redacted):
        if key.lower() in {"authorization", "x-api-key", "x-serverless-authorization", "x-yenkasa-ai-authorization"}:
            redacted[key] = "<redacted>"
    return redacted


def load_runtime_config(args: argparse.Namespace) -> dict[str, Any]:
    config = read_config()
    return {
        **config,
        "yenkasa_ai_url": args.yenkasa_ai_url or os.getenv("YCA_YENKASA_AI_URL") or config.get("yenkasa_ai_url") or DEFAULT_YENKASA_AI_URL,
        "code_agent_url": args.code_agent_url or os.getenv("YCA_CODE_AGENT_URL") or config.get("code_agent_url") or DEFAULT_CODE_AGENT_URL,
        "timeout": args.timeout,
        "cloud_run_iam": args.cloud_run_iam or os.getenv("YCA_CLOUD_RUN_IAM", "auto"),
    }


def maybe_identity_token(mode: str, code_agent_url: str) -> str:
    if mode == "off":
        return ""
    if mode == "auto" and ".run.app" not in code_agent_url:
        return ""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-identity-token"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip()


class YCAClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.ai_url = str(config["yenkasa_ai_url"]).rstrip("/")
        self.agent_url = str(config["code_agent_url"]).rstrip("/")
        self.timeout = float(config["timeout"])

    def login(self, email: str, password: str) -> dict[str, Any]:
        started = time.perf_counter()
        response = httpx.post(
            f"{self.ai_url}/api/auth/login",
            json={"email": email, "password": password},
            timeout=self.timeout,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        log_event({"type": "login", "status_code": response.status_code, "latency_ms": elapsed_ms, "url": f"{self.ai_url}/api/auth/login"})
        if response.status_code != 200:
            raise YCAError(f"login failed: HTTP {response.status_code} {response.text[:300]}")
        payload = response.json()
        token = payload.get("access_token") or payload.get("accessToken")
        if not token:
            raise YCAError("login succeeded but no access token was returned")
        stored = read_config()
        stored.update(
            {
                "yenkasa_ai_url": self.ai_url,
                "code_agent_url": self.agent_url,
                "access_token": token,
                "refresh_token": payload.get("refresh_token") or payload.get("refreshToken"),
                "session_id": payload.get("session_id") or payload.get("sessionId"),
                "user": payload.get("user") or {},
                "logged_in_at": utc_now(),
            }
        )
        write_config(stored)
        return stored

    def headers(self) -> dict[str, str]:
        token = self.config.get("access_token")
        if not token:
            raise YCAError("not logged in; run `yca login` first")
        headers = {"X-Yenkasa-AI-Authorization": f"Bearer {token}"}
        identity_token = maybe_identity_token(str(self.config.get("cloud_run_iam") or "auto"), self.agent_url)
        if identity_token:
            headers["X-Serverless-Authorization"] = f"Bearer {identity_token}"
        return headers

    def request(self, method: str, path: str, *, json_body: dict[str, Any] | None = None, admin: bool = False) -> tuple[dict[str, Any], float, int]:
        url = f"{self.agent_url}{path}"
        headers = self.headers()
        started = time.perf_counter()
        response = httpx.request(method, url, headers=headers, json=json_body, timeout=self.timeout)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        log_event(
            {
                "type": "request",
                "method": method,
                "path": path,
                "status_code": response.status_code,
                "latency_ms": elapsed_ms,
                "headers": redact_headers(headers),
                "body": json_body or {},
            }
        )
        if response.status_code >= 400:
            raise YCAError(f"{method} {path} failed: HTTP {response.status_code} {response.text[:500]}")
        return response.json(), elapsed_ms, response.status_code

    def query(self, query: str, agent: str | None = None, context: dict[str, Any] | None = None) -> tuple[dict[str, Any], float, int]:
        payload: dict[str, Any] = {"query": query, "context": context or {}}
        if agent:
            payload["agent"] = agent
        return self.request("POST", "/api/agent/query", json_body=payload)


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, default=str))


def print_agent_response(response: dict[str, Any], latency_ms: float) -> None:
    print(f"{response.get('agent', 'agent')} {'OK' if response.get('success') else 'FAILED'} {latency_ms:.0f}ms")
    if response.get("error"):
        print(response["error"])
    result = response.get("result", {})
    print_json(result)


def canonical_agent(name: str) -> str:
    return AGENT_ALIASES.get(name.strip().lower(), name)


def command_login(args: argparse.Namespace) -> int:
    config = load_runtime_config(args)
    client = YCAClient(config)
    try:
        email = args.email or input("Email: ").strip()
        password = args.password or getpass("Password: ")
    except EOFError as exc:
        raise YCAError("login cancelled; Ctrl-D sends end-of-file to the terminal") from exc
    stored = client.login(email, password)
    user = stored.get("user") or {}
    print(f"Logged in as {user.get('email') or email}")
    print(f"Token stored at {CONFIG_PATH}")
    return 0


def command_agents(args: argparse.Namespace) -> int:
    client = YCAClient(load_runtime_config(args))
    health, health_ms, _ = client.request("GET", "/health")
    agents, agents_ms, _ = client.request("GET", "/api/agent/agents")
    version = health.get("version", "-")
    heartbeat = utc_now()
    print(f"{'Agent':28} {'Status':8} {'Version':10} {'Last heartbeat':27} {'Latency'}")
    for agent in agents:
        print(f"{agent['name'][:28]:28} {'ONLINE':8} {version[:10]:10} {heartbeat:27} {agents_ms:.0f}ms")
    print(f"\nhealth latency: {health_ms:.0f}ms")
    return 0


def command_agent(args: argparse.Namespace) -> int:
    client = YCAClient(load_runtime_config(args))
    agent = canonical_agent(args.name)
    query = "status" if args.action == "status" else " ".join(args.action_parts or [args.action])
    response, latency_ms, _ = client.query(query, agent)
    print_agent_response(response, latency_ms)
    return 0


def command_repos(args: argparse.Namespace) -> int:
    client = YCAClient(load_runtime_config(args))
    response, latency_ms, _ = client.query("Show repository inventory", "RepositoryAgent")
    print_agent_response(response, latency_ms)
    return 0


def command_repo(args: argparse.Namespace) -> int:
    client = YCAClient(load_runtime_config(args))
    if args.repo_command == "scan":
        query = "Run repository scan and report indexing status"
        agent = "RepositoryAgent"
    else:
        query = "Show repository stats, repository inventory, repo_chunks stats, and latest indexed file"
        agent = "DatabaseAgent"
    response, latency_ms, _ = client.query(query, agent)
    print_agent_response(response, latency_ms)
    return 0


def command_search(args: argparse.Namespace) -> int:
    client = YCAClient(load_runtime_config(args))
    response, latency_ms, _ = client.query(args.query, "VectorSearchAgent")
    print_agent_response(response, latency_ms)
    return 0


def command_open(args: argparse.Namespace) -> int:
    client = YCAClient(load_runtime_config(args))
    response, latency_ms, _ = client.query(f"Open indexed file {args.path} and return its contents or nearest indexed chunks", "VectorSearchAgent")
    print_agent_response(response, latency_ms)
    return 0


def command_audit(args: argparse.Namespace) -> int:
    client = YCAClient(load_runtime_config(args))
    response, latency_ms, _ = client.query("Run repository audit, bug detection, missing files check, and indexing verification", "CodeAuditAgent")
    print_agent_response(response, latency_ms)
    return 0


def command_memory(args: argparse.Namespace) -> int:
    client = YCAClient(load_runtime_config(args))
    if args.memory_command == "status":
        response, latency_ms, _ = client.query("Show memory embeddings status, memory count, retrieval latency, and backend health", "DatabaseAgent")
    else:
        response, latency_ms, _ = client.query(f"Find related memories about {args.query}", "VectorSearchAgent")
    print_agent_response(response, latency_ms)
    return 0


def command_indexing(args: argparse.Namespace) -> int:
    client = YCAClient(load_runtime_config(args))
    if args.indexing_command == "run":
        query = "Force repository indexing run and report queued processed failed files and last run"
        agent = "RepositoryAgent"
    else:
        query = "Show indexing status, queued files, processed files, failed files, latest indexed file, and repo_chunks stats"
        agent = "DatabaseAgent"
    response, latency_ms, _ = client.query(query, agent)
    print_agent_response(response, latency_ms)
    return 0


def command_analytics(args: argparse.Namespace) -> int:
    client = YCAClient(load_runtime_config(args))
    response, latency_ms, _ = client.query("Show analytics status with total events, processed events, and failed events", "DatabaseAgent")
    print_agent_response(response, latency_ms)
    return 0


def command_orchestration(args: argparse.Namespace) -> int:
    client = YCAClient(load_runtime_config(args))
    checks = [
        ("discovery", lambda: client.request("GET", "/api/agent/agents")),
        ("routing", lambda: client.query("Find livestreamPermissions")),
        ("aggregation", lambda: client.query("Audit repositories and check deployment health")),
    ]
    failed = False
    for name, run in checks:
        try:
            payload, latency_ms, _ = run()
            ok = bool(payload)
        except Exception as exc:
            ok = False
            latency_ms = 0.0
            payload = {"error": str(exc)}
            failed = True
        print(f"{name:14} {'OK' if ok else 'FAILED'} {latency_ms:.0f}ms")
        log_event({"type": "orchestration_check", "check": name, "ok": ok, "latency_ms": latency_ms, "result": payload})
    return 1 if failed else 0


def command_doctor(args: argparse.Namespace) -> int:
    client = YCAClient(load_runtime_config(args))
    checks = [
        ("authentication", lambda: client.request("GET", "/health")),
        ("repo access", lambda: client.query("Show repository inventory", "RepositoryAgent")),
        ("indexing", lambda: client.query("Show indexing status and latest indexed file", "DatabaseAgent")),
        ("memory", lambda: client.query("Show memory embeddings status", "DatabaseAgent")),
        ("search", lambda: client.query("livestreamPermissions", "VectorSearchAgent")),
        ("audit", lambda: client.query("Run repository audit", "CodeAuditAgent")),
        ("orchestration", lambda: client.query("Audit repositories and check deployment health")),
    ]
    failed = False
    report: list[dict[str, Any]] = []
    for name, run in checks:
        started = time.perf_counter()
        try:
            payload, latency_ms, status = run()
            ok = bool(payload.get("success", True)) if isinstance(payload, dict) else True
            error = payload.get("error") if isinstance(payload, dict) else None
        except Exception as exc:
            ok = False
            status = 0
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            error = str(exc)
            payload = {}
        failed = failed or not ok
        report.append({"check": name, "ok": ok, "status": status, "latency_ms": latency_ms, "error": error})
        print(f"{name:16} {'OK' if ok else 'FAILED'} {latency_ms:.0f}ms")
    log_event({"type": "doctor", "ok": not failed, "report": report})
    print("\nReport")
    print_json(report)
    return 1 if failed else 0


def command_chat(args: argparse.Namespace) -> int:
    client = YCAClient(load_runtime_config(args))
    query = " ".join(args.query).strip()
    if not query:
        raise YCAError("chat query cannot be empty")
    response, latency_ms, _ = client.query(query)
    print_agent_response(response, latency_ms)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="yca", description="YenkasaCodeAgent developer CLI")
    parser.add_argument("--yenkasa-ai-url", default=None)
    parser.add_argument("--code-agent-url", default=None)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--cloud-run-iam", choices=["auto", "on", "off"], default=None)
    subparsers = parser.add_subparsers(dest="command")

    login = subparsers.add_parser("login")
    login.add_argument("--email")
    login.add_argument("--password")
    login.set_defaults(func=command_login)

    agents = subparsers.add_parser("agents")
    agents.set_defaults(func=command_agents)

    agent = subparsers.add_parser("agent")
    agent.add_argument("name")
    agent.add_argument("action", nargs="?", default="status")
    agent.add_argument("action_parts", nargs="*")
    agent.set_defaults(func=command_agent)

    repos = subparsers.add_parser("repos")
    repos.set_defaults(func=command_repos)

    repo = subparsers.add_parser("repo")
    repo.add_argument("repo_command", choices=["scan", "stats"])
    repo.set_defaults(func=command_repo)

    search = subparsers.add_parser("search")
    search.add_argument("query")
    search.set_defaults(func=command_search)

    open_file = subparsers.add_parser("open")
    open_file.add_argument("path")
    open_file.set_defaults(func=command_open)

    audit = subparsers.add_parser("audit")
    audit.set_defaults(func=command_audit)

    memory = subparsers.add_parser("memory")
    memory.add_argument("memory_command", choices=["status", "query"])
    memory.add_argument("query", nargs="?", default="")
    memory.set_defaults(func=command_memory)

    indexing = subparsers.add_parser("indexing")
    indexing.add_argument("indexing_command", choices=["status", "run"])
    indexing.set_defaults(func=command_indexing)

    analytics = subparsers.add_parser("analytics")
    analytics.add_argument("analytics_command", choices=["status"])
    analytics.set_defaults(func=command_analytics)

    orchestration = subparsers.add_parser("orchestration")
    orchestration.add_argument("orchestration_command", choices=["test"])
    orchestration.set_defaults(func=command_orchestration)

    doctor = subparsers.add_parser("doctor")
    doctor.set_defaults(func=command_doctor)

    return parser


def print_interactive_help() -> None:
    print(
        "Commands:\n"
        "  agents\n"
        "  repos\n"
        "  search livestreamPermissions\n"
        "  memory query livestream permissions\n"
        "  audit\n"
        "  doctor\n"
        "\nChat:\n"
        "  Type any normal question and press Enter.\n"
        "\nSession:\n"
        "  help       show this help\n"
        "  exit       leave yca\n"
        "  Ctrl-D     leave yca"
    )


def run_parsed_args(args: argparse.Namespace) -> int:
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\ncancelled", file=sys.stderr)
        return 130
    except YCAError as exc:
        log_event({"type": "failure", "error": str(exc)})
        print(f"error: {exc}", file=sys.stderr)
        return 1


def run_interactive_command(tokens: list[str], base_args: argparse.Namespace) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(tokens)
    except SystemExit as exc:
        return int(exc.code or 0)
    args.yenkasa_ai_url = base_args.yenkasa_ai_url
    args.code_agent_url = base_args.code_agent_url
    args.timeout = base_args.timeout
    args.cloud_run_iam = base_args.cloud_run_iam
    return run_parsed_args(args)


def run_interactive_query(line: str, base_args: argparse.Namespace) -> int:
    chat_args = argparse.Namespace(
        yenkasa_ai_url=base_args.yenkasa_ai_url,
        code_agent_url=base_args.code_agent_url,
        timeout=base_args.timeout,
        cloud_run_iam=base_args.cloud_run_iam,
        query=[line],
    )
    return run_parsed_args(argparse.Namespace(**vars(chat_args), func=command_chat))


def run_interactive_shell(args: argparse.Namespace) -> int:
    config = load_runtime_config(args)
    user = config.get("user") or {}
    email = user.get("email")
    print("YenkasaCodeAgent interactive mode")
    if email:
        print(f"Logged in as {email}")
    elif not config.get("access_token"):
        print("Not logged in. Type `login` first, or run `./yca login` before starting chat.")
    print("Type `help` for commands, `exit` to quit.")

    while True:
        try:
            line = input("yca> ").strip()
        except EOFError:
            print()
            return 0
        except KeyboardInterrupt:
            print("\ncancelled")
            continue
        if not line:
            continue
        normalized = line.lower()
        if normalized in {"exit", "quit", ":q", "/exit", "/quit"}:
            return 0
        if normalized in {"help", "?", "/help"}:
            print_interactive_help()
            continue
        try:
            tokens = shlex.split(line)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            continue
        if not tokens:
            continue
        if tokens[0] in COMMAND_NAMES:
            run_interactive_command(tokens, args)
            continue
        run_interactive_query(line, args)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        return run_interactive_shell(args)
    return run_parsed_args(args)


if __name__ == "__main__":
    raise SystemExit(main())
