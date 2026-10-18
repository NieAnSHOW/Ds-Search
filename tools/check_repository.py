#!/usr/bin/env python3
"""Validate distributable skill metadata and local resource references."""

import re
import sys
from pathlib import Path

import yaml


def validate_skill(skill: Path) -> list[str]:
    errors = []
    skill = skill.resolve()
    entry = skill / "SKILL.md"
    try:
        text = entry.read_text(encoding="utf-8")
    except OSError:
        return ["Missing SKILL.md"]
    frontmatter = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.S)
    if not frontmatter:
        return ["SKILL.md needs YAML frontmatter"]
    try:
        metadata = yaml.safe_load(frontmatter[1])
    except yaml.YAMLError:
        return ["Invalid SKILL.md YAML frontmatter"]
    if not isinstance(metadata, dict):
        return ["SKILL.md frontmatter must be a mapping"]
    name = metadata.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
        errors.append("Invalid skill name")
    elif name != skill.name:
        errors.append("Skill name must match its directory")
    description = metadata.get("description")
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        errors.append("description must contain 1–1024 characters")
    body = text[frontmatter.end():]
    if len(body.splitlines()) > 500:
        errors.append("Move detailed guidance out of the >500-line SKILL.md body")
    if re.search(r"\b(?:TODO|TBD|PLACEHOLDER)\b", body):
        errors.append("Unfinished scaffold in SKILL.md")
    documents = [entry, *sorted((skill / "references").glob("*.md"))]
    for document in documents:
        content = document.read_text(encoding="utf-8")
        # Markdown links use their document's directory; command resource paths
        # in backticks follow the skill-root convention.
        targets = [(target, document.parent) for target in re.findall(r"\]\(([^\s)]+)(?:\s+[^)]*)?\)", content)]
        targets += [(target, skill) for target in re.findall(r"`((?:scripts|references|assets)/[^`\s]+)`", content)]
        for target, base in set(targets):
            if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                continue
            target = target.split("#", 1)[0]
            resolved = (base / target).resolve()
            if not resolved.is_relative_to(skill) or not resolved.is_file():
                errors.append(f"{document.relative_to(skill)}: unavailable local resource {target}")
    try:
        ui = yaml.safe_load((skill / "agents/openai.yaml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        errors.append("Missing or invalid agents/openai.yaml")
        return errors
    interface = ui.get("interface") if isinstance(ui, dict) else None
    if not isinstance(interface, dict):
        errors.append("openai.yaml needs interface metadata")
        return errors
    for field in ("display_name", "short_description", "default_prompt"):
        if not isinstance(interface.get(field), str) or not interface[field].strip():
            errors.append(f"interface.{field} must be a nonempty string")
    summary = interface.get("short_description")
    if isinstance(summary, str) and not 25 <= len(summary) <= 64:
        errors.append("interface.short_description must have 25–64 characters")
    if not isinstance(name, str) or f"${name}" not in str(interface.get("default_prompt", "")):
        errors.append("interface.default_prompt must explicitly mention the skill")
    for field in ("icon_small", "icon_large"):
        if field in interface:
            target = (skill / str(interface[field])).resolve()
            if not target.is_relative_to(skill) or not target.is_file():
                errors.append(f"interface.{field} must reference a bundled asset")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = validate_skill(root / "skills/ds-search")
    for filename in ("README.md", "SECURITY.md", "LICENSE", "logo.png"):
        if not (root / filename).is_file():
            errors.append(f"Missing {filename}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Skill metadata, local references and repository assets are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
