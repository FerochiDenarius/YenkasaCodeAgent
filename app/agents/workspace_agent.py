from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.base import BaseAgent


class WorkspaceAgent(BaseAgent):
    name = "WorkspaceAgent"

    description = (
        "File workspace agent for reading, creating, "
        "updating and deleting files."
    )

    capabilities = [
        "read_file",
        "write_file",
        "create_file",
        "delete_file",
        "list_directory",
    ]

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).resolve()

    def _safe_path(self, path: str) -> Path:
        target = (self.workspace_root / path).resolve()

        if not str(target).startswith(str(self.workspace_root)):
            raise ValueError("Path outside workspace root")

        return target

    async def run(
        self,
        query: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:

        operation = context.get("operation")

        if operation == "read_file":
            return await self.read_file(context)

        if operation == "write_file":
            return await self.write_file(context)

        if operation == "create_file":
            return await self.create_file(context)

        if operation == "delete_file":
            return await self.delete_file(context)

        if operation == "list_directory":
            return await self.list_directory(context)

        return {
            "error": "Unsupported operation"
        }

    async def read_file(self, context):
        path = self._safe_path(context["path"])

        return {
            "path": str(path),
            "content": path.read_text(
                encoding="utf-8"
            ),
        }

    async def write_file(self, context):
        path = self._safe_path(context["path"])

        path.write_text(
            context["content"],
            encoding="utf-8"
        )

        return {
            "success": True,
            "path": str(path),
        }

    async def create_file(self, context):
        path = self._safe_path(context["path"])

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            context.get("content", ""),
            encoding="utf-8"
        )

        return {
            "success": True,
            "path": str(path),
        }

    async def delete_file(self, context):
        path = self._safe_path(context["path"])

        path.unlink(missing_ok=True)

        return {
            "success": True,
            "path": str(path),
        }

    async def list_directory(self, context):
        path = self._safe_path(
            context.get("path", "")
        )

        return {
            "entries": [
                str(p.name)
                for p in path.iterdir()
            ]
        }