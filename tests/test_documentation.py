import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "ds-search" / "SKILL.md"


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


if __name__ == "__main__":
    unittest.main()
