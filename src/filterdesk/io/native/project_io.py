"""Native `.filterdesk.json` project I/O."""

from __future__ import annotations

import json
from pathlib import Path

from filterdesk.domain.project import Project, project_from_mapping, project_to_mapping


def save_project(project: Project, path: Path | str) -> None:
    out = Path(path)
    payload = project_to_mapping(project)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_project(path: Path | str) -> Project:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("project root must be a JSON object")
    return project_from_mapping(data)
