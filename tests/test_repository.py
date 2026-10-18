"""Repository checks must reject broken/disconnected skill resources."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


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

    def _skills_cli_environment(self, sandbox: Path) -> dict[str, str]:
        """Keep npm/skills state and credentials inside a disposable sandbox."""
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(sandbox / "home"),
                "XDG_CONFIG_HOME": str(sandbox / "config"),
                "XDG_DATA_HOME": str(sandbox / "data"),
                "XDG_CACHE_HOME": str(sandbox / "cache"),
                "npm_config_cache": str(sandbox / "npm-cache"),
                "npm_config_userconfig": str(sandbox / "npmrc"),
                "npm_config_global": "false",
                "npm_config_prefix": str(sandbox / "npm-prefix"),
            }
        )
        for key in ("DEEPSEEK_API_KEY", "DEEPSEEK_API_BASE"):
            env.pop(key, None)
        return env

    def _npx_path_or_skip(self) -> str:
        npx = shutil.which("npx")
        if npx is None:
            self.skipTest("npx is unavailable; skipping skills CLI integration test")
        return npx

    def test_local_skills_cli_discovers_ds_search(self):
        """The CLI discovers the named skill while the source path stays canonical."""
        npx = self._npx_path_or_skip()
        repository = Path(__file__).resolve().parents[1]
        entrypoint = repository / "skills/ds-search/SKILL.md"
        self.assertTrue(entrypoint.is_file(), "canonical Skill entrypoint is missing")

        with tempfile.TemporaryDirectory() as directory:
            sandbox = Path(directory)
            project = sandbox / "project"
            project.mkdir()
            result = subprocess.run(
                [npx, "--yes", "skills", "add", str(repository), "--list"],
                cwd=project,
                env=self._skills_cli_environment(sandbox),
                text=True,
                capture_output=True,
                timeout=120,
                check=False,
            )

        output = f"{result.stdout}\n{result.stderr}"
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("ds-search", output)

    def test_local_skills_cli_installs_into_isolated_project(self):
        """A project-scoped copy contains the complete Skill and owns its lock file."""
        npx = self._npx_path_or_skip()
        repository = Path(__file__).resolve().parents[1]
        repository_lock = repository / "skills-lock.json"
        self.assertFalse(repository_lock.exists(), "consumer lock file already exists in repository")

        with tempfile.TemporaryDirectory() as directory:
            sandbox = Path(directory)
            project = sandbox / "project"
            project.mkdir()
            result = subprocess.run(
                [
                    npx,
                    "--yes",
                    "skills",
                    "add",
                    str(repository),
                    "--skill",
                    "ds-search",
                    "--copy",
                    "--yes",
                ],
                cwd=project,
                env=self._skills_cli_environment(sandbox),
                text=True,
                capture_output=True,
                timeout=120,
                check=False,
            )
            output = f"{result.stdout}\n{result.stderr}"
            self.assertEqual(result.returncode, 0, output)

            installed_entries = list(project.rglob("ds-search/SKILL.md"))
            self.assertTrue(installed_entries, output)
            installed_skill = installed_entries[0].parent
            self.assertFalse(installed_skill.is_symlink())
            self.assertTrue((installed_skill / "scripts").is_dir())
            self.assertTrue(any((installed_skill / "scripts").iterdir()))
            self.assertTrue((installed_skill / "references").is_dir())
            self.assertTrue(any((installed_skill / "references").iterdir()))

            self.assertTrue((project / "skills-lock.json").is_file())

        self.assertFalse(repository_lock.exists(), "skills CLI must not write a lock file to the source repository")


if __name__ == "__main__":
    unittest.main()
