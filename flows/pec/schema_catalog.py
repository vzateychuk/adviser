from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class SchemaDefinition(BaseModel):
    schema_id: str = Field(min_length=1)
    path: Path
    title: str | None = None
    category: str | None = None
    intended_use: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    raw: dict

    @property
    def prompt_excerpt(self) -> str:
        return yaml.safe_dump(self.raw, allow_unicode=True, sort_keys=False).strip()


class SchemaCatalog:
    """Loads and resolves schema definitions used by the PEC flow.

    The catalog gives the planner and executor a canonical schema source so they
    can stay aligned even when LLM output uses fuzzy or descriptive names.
    """

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self._schemas = self.scan(self.root)

    @classmethod
    def scan(cls, root: Path | str) -> dict[str, SchemaDefinition]:
        root_path = Path(root)
        schemas: dict[str, SchemaDefinition] = {}
        for path in sorted(root_path.glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            meta = data.get("schema_meta", {})
            selection = data.get("selection_hints", {})
            schema_id = meta.get("id")
            if not schema_id:
                raise ValueError(f"Schema {path} is missing schema_meta.id")
            if schema_id in schemas:
                raise ValueError(f"Duplicate schema id detected: {schema_id}")
            schemas[schema_id] = SchemaDefinition(
                schema_id=schema_id,
                path=path,
                title=meta.get("title"),
                category=meta.get("category"),
                intended_use=list(meta.get("intended_use", [])),
                aliases=list(selection.get("aliases", [])),
                raw=data,
            )
        return schemas

    def ids(self) -> list[str]:
        """Return canonical schema ids in sorted order for prompts and validation."""

        return sorted(self._schemas)

    def has(self, schema_id: str | None) -> bool:
        """Check whether a schema id is known to the catalog."""

        return bool(schema_id) and schema_id in self._schemas

    @staticmethod
    def _normalize(text: str) -> str:
        return "_".join(text.strip().lower().replace("-", " ").split())

    def resolve_schema_id(self, candidate: str | None) -> str | None:
        """Resolve a fuzzy schema label to a canonical catalog id when possible.

        This lets the planner recover from near-miss names such as `lab_panel`
        instead of failing a run that is otherwise close to valid.
        """

        if not candidate:
            return None

        normalized = self._normalize(candidate)
        if normalized in self._schemas:
            return normalized

        for schema_id, schema in self._schemas.items():
            if normalized == self._normalize(schema_id):
                return schema_id
            if normalized == self._normalize(schema.title or ""):
                return schema_id
            if normalized == self._normalize(schema.category or ""):
                return schema_id
            if normalized in {self._normalize(alias) for alias in schema.aliases}:
                return schema_id

        return None

    def get(self, schema_id: str) -> SchemaDefinition:
        """Fetch a schema definition for prompt rendering and validation."""

        try:
            return self._schemas[schema_id]
        except KeyError as exc:
            raise KeyError(f"Unknown PEC schema: {schema_id}") from exc

    def prompt_summary(self) -> str:
        """Render a compact schema summary that can be injected into prompts."""

        parts: list[str] = []
        for schema_id in self.ids():
            schema = self._schemas[schema_id]
            aliases = ", ".join(schema.aliases) if schema.aliases else "-"
            intended = ", ".join(schema.intended_use) if schema.intended_use else "-"
            parts.append(
                f"- id: {schema.schema_id}\n"
                f"  title: {schema.title or '-'}\n"
                f"  category: {schema.category or '-'}\n"
                f"  intended_use: {intended}\n"
                f"  aliases: {aliases}\n"
            )
        return "\n".join(parts).strip()


# Module-level lazy singleton — loaded once from the schemas/ directory next to this file.
# Used by MedicalDoc.normalize_schema_id for catalog-based validation without
# requiring callers to pass a catalog instance.
_default_instance: SchemaCatalog | None = None


def default_catalog() -> SchemaCatalog:
    """Return the default SchemaCatalog loaded from the schemas/ directory next to this file."""
    global _default_instance
    if _default_instance is None:
        _default_instance = SchemaCatalog(Path(__file__).parent / "schemas")
    return _default_instance
