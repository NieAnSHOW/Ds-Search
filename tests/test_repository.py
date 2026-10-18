"""Repository checks must reject broken/disconnected skill resources."""

import tempfile
import unittest
from pathlib import Path


class RepositoryValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.skill = Path(self.temp.name) / "ds-search"
        (self.skill / "agents").mkdir(parents=True)
        (self.skill / "scripts").mkdir()
        (self.skill / "scripts/ds_search.py").write_text("print('ok')\n")
        (self.skill / "SKILL.md").write_text(
            '---\nname: ds-search\ndescription: "Search or fetch with DeepSeek."\n---\n'
            '# ds-search\nRun `scripts/ds_search.py`.\n', encoding="utf-8"
        )
        (self.skill / "agents/openai.yaml").write_text(
            'interface:\n  display_name: "DS Search"\n'
            '  short_description: "Search and fetch pages with DeepSeek APIs"\n'
            '  default_prompt: "Use $ds-search to find sources."\n', encoding="utf-8"
        )

    def validate(self):
        try:
            from tools.check_repository import validate_skill
        except ImportError:
            self.fail("Repository structure validator has not been implemented")
        return validate_skill(self.skill)

    def test_complete_skill_validates_from_any_parent_path(self):
        self.assertEqual(self.validate(), [])

    def test_broken_reference_is_rejected(self):
        with (self.skill / "SKILL.md").open("a", encoding="utf-8") as stream:
            stream.write("Read [setup](references/setup.md).\n")
        self.assertTrue(any("references/setup.md" in item for item in self.validate()))

    def test_markdown_links_in_references_resolve_from_document(self):
        references = self.skill / "references"
        references.mkdir()
        (references / "api.md").write_text("Read [setup](setup.md).", encoding="utf-8")
        (references / "setup.md").write_text("Run `scripts/ds_search.py`.", encoding="utf-8")
        self.assertEqual(self.validate(), [])

    def test_reference_cannot_escape_skill(self):
        outside = self.skill.parent / "outside.md"
        outside.write_text("not distributable", encoding="utf-8")
        with (self.skill / "SKILL.md").open("a", encoding="utf-8") as stream:
            stream.write("Read [outside](../outside.md).\n")
        self.assertTrue(any("outside" in item for item in self.validate()))

    def test_invalid_frontmatter_is_reported_without_traceback(self):
        (self.skill / "SKILL.md").write_text("---\nname: [\n---\n", encoding="utf-8")
        self.assertTrue(self.validate())

    def test_metadata_requires_named_skill_in_prompt(self):
        path = self.skill / "agents/openai.yaml"
        path.write_text(path.read_text().replace("$ds-search", "another tool"), encoding="utf-8")
        self.assertTrue(any("default_prompt" in item for item in self.validate()))


if __name__ == "__main__":
    unittest.main()
