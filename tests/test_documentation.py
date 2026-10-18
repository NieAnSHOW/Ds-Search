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
        self.assertIn("消费者 CLI 生成", readme)

    def test_install_docs_require_source_review_and_optional_codex_metadata(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertRegex(readme, r"(?i)(核对|验证|检查).{0,100}NieAnSHOW/Ds-Search")
        self.assertRegex(readme, r"(?i)(检查|inspect).{0,100}(复制|copied)")
        self.assertIn("agents/openai.yaml", readme)
        self.assertRegex(readme, r"(?i)optional Codex UI metadata|可选.*Codex.*UI")
        self.assertRegex(readme, r"(?i)(other Harness|其他 Harness).{0,100}(ignore|忽略)")

    def test_install_docs_distinguish_project_and_global_lock_records(self):
        docs = "\n".join(path.read_text(encoding="utf-8") for path in DOCS)

        self.assertRegex(docs, r"项目(?:级|安装).{0,100}skills-lock\.json")
        self.assertRegex(docs, r"全局.{0,100}\.skill-lock\.json")
        self.assertNotRegex(
            docs,
            r"(?s)skills-lock\.json.{0,120}(?:全局|global).{0,120}(?:同一|same|唯一|single)",
        )

    def test_discovery_command_is_scoped_to_local_checkout(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("本地 Ds-Search checkout 根目录", readme)
        self.assertIn("npx skills add . --list", readme)

    def test_fenced_commands_never_combine_list_and_json_flags(self):
        fence = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)

        for path in DOCS:
            text = path.read_text(encoding="utf-8")
            for block in fence.findall(text):
                for line in block.splitlines():
                    command = line.strip()
                    if command and not command.startswith("#"):
                        self.assertFalse(
                            "--list" in command and "--json" in command,
                            f"invalid --list/--json combination in {path}: {command}",
                        )

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
