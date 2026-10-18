import unittest
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "ds-search" / "SKILL.md"
DOCS = [
    ROOT / "README.md",
    ROOT / "SECURITY.md",
    ROOT / "skills" / "ds-search" / "references" / "setup.md",
    ROOT / "skills" / "ds-search" / "references" / "api.md",
    ROOT / "docs" / "verification.md",
]


class SkillDocumentationTests(unittest.TestCase):
    def test_skill_is_harness_neutral_and_uses_relative_resources(self):
        text = SKILL.read_text(encoding="utf-8")

        self.assertIn("Harness 注入", text)
        self.assertIn("Skill 根目录", text)
        self.assertNotRegex(text, r"(?i)(CODEX_HOME|~/.codex|codex/skills|重启 Codex)")
        self.assertNotIn("在 Codex 中", text)
        self.assertRegex(text, r"\[[^\]]+\]\(references/setup\.md\)")
        self.assertRegex(text, r"\[[^\]]+\]\(references/api\.md\)")
        self.assertTrue((SKILL.parent / "references" / "setup.md").is_file())
        self.assertTrue((SKILL.parent / "references" / "api.md").is_file())
        self.assertIn("scripts/ds_search.py", text)

    def test_docs_use_npx_skills_for_global_and_project_installation(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn(
            "npx skills add NieAnSHOW/Ds-Search --skill ds-search --agent '*' --global --copy --yes",
            readme,
        )
        self.assertIn(
            "npx skills add NieAnSHOW/Ds-Search --skill ds-search --agent '*' --copy --yes",
            readme,
        )
        self.assertIn("npx skills update ds-search --global --yes", readme)
        self.assertIn("npx skills update ds-search --project --yes", readme)
        self.assertIn("npx skills add . --list", readme)
        self.assertIn("`--list` cannot be combined with `--json`", readme)
        self.assertIn("skills-lock.json", readme)
        self.assertRegex(readme, r"(?i)skills-lock\.json.{0,80}(?:consumer|消费者)")

    def test_readme_is_harness_neutral_and_has_only_optional_codex_example(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertNotIn("在 Codex 中明确调用", readme)
        self.assertNotRegex(readme, r"(?i)(CODEX_HOME|~/.codex|codex/skills|重启 Codex)")
        self.assertRegex(readme, r"(?i)Harness|Agent")
        self.assertRegex(readme, r"(?i)Codex.{0,80}(可选|optional|示例|example)")

    def test_docs_do_not_show_literal_secret_assignments(self):
        combined = "\n".join(path.read_text(encoding="utf-8") for path in DOCS)

        self.assertIsNone(
            re.search(r"(?i)\b(?:export\s+)?DEEPSEEK_API_KEY\s*=", combined),
            "documentation must not contain a literal DEEPSEEK_API_KEY assignment",
        )


if __name__ == "__main__":
    unittest.main()
