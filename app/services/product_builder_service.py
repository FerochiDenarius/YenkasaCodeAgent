from __future__ import annotations

from typing import Any


class ProductBuilderService:
    def generate(self, *, query: str, context: dict[str, Any]) -> dict[str, Any]:
        generation_type = self._generation_type(query=query, context=context)
        files = self._files_for(generation_type=generation_type, query=query)
        return {
            "generation_type": generation_type,
            "generated_files": files,
            "notes": [
                "Generated output is a proposal only.",
                "No files were modified, committed, deployed, or executed.",
            ],
        }

    def _generation_type(self, *, query: str, context: dict[str, Any]) -> str:
        explicit_type = str(context.get("generation_type") or "").lower()
        if explicit_type in {"flutter", "fastapi", "nodejs", "mongodb", "database", "docs", "documentation"}:
            return "mongodb" if explicit_type == "database" else "docs" if explicit_type == "documentation" else explicit_type

        normalized = query.lower()
        if any(keyword in normalized for keyword in ("flutter", "screen", "widget", "riverpod", "provider")):
            return "flutter"
        if any(keyword in normalized for keyword in ("mongodb", "postgres", "postgresql", "database", "index", "indexes", "create schema")):
            return "mongodb"
        if any(keyword in normalized for keyword in ("fastapi", "router", "repository", "schema", "pydantic")):
            return "fastapi"
        if any(keyword in normalized for keyword in ("node", "node.js", "express", "controller", "middleware")):
            return "nodejs"
        if any(keyword in normalized for keyword in ("readme", "documentation", "docs", "api documentation", "deployment guide")):
            return "docs"
        return "docs"

    def _files_for(self, *, generation_type: str, query: str) -> list[dict[str, str]]:
        builders = {
            "flutter": self._flutter_files,
            "fastapi": self._fastapi_files,
            "nodejs": self._nodejs_files,
            "mongodb": self._mongodb_files,
            "docs": self._docs_files,
        }
        return builders[generation_type](query)

    def _flutter_files(self, query: str) -> list[dict[str, str]]:
        return [
            {
                "path": "lib/features/generated/generated_screen.dart",
                "kind": "screen",
                "content": (
                    "class GeneratedScreen extends ConsumerWidget {\n"
                    "  const GeneratedScreen({super.key});\n\n"
                    "  @override\n"
                    "  Widget build(BuildContext context, WidgetRef ref) {\n"
                    "    return const Scaffold(body: Center(child: Text('Generated screen')));\n"
                    "  }\n"
                    "}\n"
                ),
            },
            {
                "path": "lib/features/generated/generated_provider.dart",
                "kind": "riverpod_provider",
                "content": "final generatedProvider = Provider<String>((ref) => 'generated');\n",
            },
        ]

    def _fastapi_files(self, query: str) -> list[dict[str, str]]:
        return [
            {
                "path": "app/routers/generated.py",
                "kind": "router",
                "content": (
                    "from fastapi import APIRouter\n\n"
                    "router = APIRouter(prefix='/generated', tags=['Generated'])\n\n"
                    "@router.get('')\n"
                    "async def list_generated():\n"
                    "    return {'items': []}\n"
                ),
            },
            {
                "path": "app/schemas/generated.py",
                "kind": "schema",
                "content": "from pydantic import BaseModel\n\nclass GeneratedItem(BaseModel):\n    name: str\n",
            },
        ]

    def _nodejs_files(self, query: str) -> list[dict[str, str]]:
        return [
            {
                "path": "src/routes/generated.routes.js",
                "kind": "route",
                "content": (
                    "const router = require('express').Router();\n"
                    "const controller = require('../controllers/generated.controller');\n\n"
                    "router.get('/', controller.listGenerated);\n\n"
                    "module.exports = router;\n"
                ),
            },
            {
                "path": "src/controllers/generated.controller.js",
                "kind": "controller",
                "content": "exports.listGenerated = async (req, res) => res.json({ items: [] });\n",
            },
        ]

    def _mongodb_files(self, query: str) -> list[dict[str, str]]:
        return [
            {
                "path": "db/generated.schema.json",
                "kind": "mongodb_schema",
                "content": (
                    "{\n"
                    "  \"bsonType\": \"object\",\n"
                    "  \"required\": [\"name\", \"created_at\"],\n"
                    "  \"properties\": {\n"
                    "    \"name\": {\"bsonType\": \"string\"},\n"
                    "    \"created_at\": {\"bsonType\": \"date\"}\n"
                    "  }\n"
                    "}\n"
                ),
            },
            {
                "path": "db/generated.indexes.js",
                "kind": "index",
                "content": "db.generated.createIndex({ name: 1 }, { unique: false });\n",
            },
        ]

    def _docs_files(self, query: str) -> list[dict[str, str]]:
        return [
            {
                "path": "README.generated.md",
                "kind": "readme",
                "content": "# Generated Documentation\n\nThis proposal documents the requested product surface.\n",
            },
            {
                "path": "docs/architecture.generated.md",
                "kind": "architecture_documentation",
                "content": "## Architecture\n\nDescribe components, data flow, and deployment boundaries.\n",
            },
        ]
