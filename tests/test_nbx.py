from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path

import nbformat

from nbx.launcher import (
    build_command,
    build_environment,
    ensure_runtime_directories,
    parse_args,
    project_paths,
)
from nbx.preview import render_notebook_preview, resolve_notebook_path


PACKAGE_DIR = Path(__file__).resolve().parents[1] / "nbx"
PYPROJECT_PATH = Path(__file__).resolve().parents[1] / "pyproject.toml"


def make_notebook(title: str = "Example Notebook") -> nbformat.NotebookNode:
    notebook = nbformat.v4.new_notebook()
    notebook.metadata["title"] = title
    notebook.cells = [
        nbformat.v4.new_markdown_cell("# Example Notebook\n\nA short equation: $x^2$."),
        nbformat.v4.new_code_cell("print('hello')"),
    ]
    return notebook


class LauncherTests(unittest.TestCase):
    def test_parse_args_accepts_project_root_notebook_and_passthrough_jupyter_args(self) -> None:
        parsed = parse_args(
            [
                "--project-root",
                "/tmp/story",
                "drafts/post.ipynb",
                "--no-browser",
                "--ServerApp.port=9999",
            ]
        )

        self.assertEqual(parsed.project_root, Path("/tmp/story"))
        self.assertEqual(parsed.notebook_path, Path("drafts/post.ipynb"))
        self.assertEqual(
            parsed.jupyter_args,
            ["--no-browser", "--ServerApp.port=9999"],
        )

    def test_build_environment_uses_project_local_nbx_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = project_paths(
                project_root=Path(temp_dir),
                package_dir=PACKAGE_DIR,
            )

            env = build_environment({"PATH": "/usr/bin"}, paths)

        self.assertEqual(env["JUPYTER_CONFIG_DIR"], str(paths.config_dir))
        self.assertEqual(env["JUPYTER_DATA_DIR"], str(paths.data_dir))
        self.assertEqual(env["JUPYTERLAB_SETTINGS_DIR"], str(paths.lab_settings_dir))
        self.assertEqual(env["JUPYTERLAB_WORKSPACES_DIR"], str(paths.workspaces_dir))
        self.assertEqual(env["NBX_PROJECT_ROOT"], str(paths.project_root))
        self.assertEqual(env["NBX_PACKAGE_DIR"], str(paths.package_dir))
        self.assertEqual(env["PATH"], "/usr/bin")

    def test_build_command_launches_tree_when_no_notebook_target_is_given(self) -> None:
        command = build_command()

        self.assertEqual(command, ["jupyter", "notebook"])

    def test_build_command_opens_requested_notebook_relative_to_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = project_paths(
                project_root=Path(temp_dir),
                package_dir=PACKAGE_DIR,
            )

            command = build_command(
                notebook_path=Path("drafts/post.ipynb"),
                extra_args=["--no-browser"],
                paths=paths,
            )

        self.assertEqual(
            command,
            ["jupyter", "notebook", "--no-browser", "drafts/post.ipynb"],
        )

    def test_ensure_runtime_directories_materializes_nbx_runtime_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = project_paths(
                project_root=Path(temp_dir),
                package_dir=PACKAGE_DIR,
            )

            ensure_runtime_directories(paths)

            server_config = (paths.config_dir / "jupyter_server_config.py").read_text(
                encoding="utf-8"
            )
            notebook_config = (
                paths.config_dir / "jupyter_notebook_config.py"
            ).read_text(encoding="utf-8")
            css = (paths.config_dir / "custom" / "custom.css").read_text(
                encoding="utf-8"
            )
            theme_settings = (
                paths.lab_settings_dir
                / "@jupyterlab/apputils-extension/themes.jupyterlab-settings"
            ).read_text(encoding="utf-8")
            tracker_settings = (
                paths.lab_settings_dir
                / "@jupyterlab/notebook-extension/tracker.jupyterlab-settings"
            ).read_text(encoding="utf-8")

        self.assertIn('c.ServerApp.jpserver_extensions = {"nbx": True}', server_config)
        self.assertIn(str(paths.project_root), server_config)
        self.assertIn(str(paths.notebook_templates_dir), notebook_config)
        self.assertIn('body[data-jp-theme-name="NBX"]', css)
        self.assertIn(".jp-nbx-toolbar-shell", css)
        self.assertIn('"theme": "NBX"', theme_settings)
        self.assertIn('"windowingMode": "none"', tracker_settings)


class PreviewTests(unittest.TestCase):
    def test_render_preview_contains_nbx_shell_and_notebook_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            notebook_path = project_root / "post.ipynb"
            nbformat.write(make_notebook(), notebook_path)
            paths = project_paths(project_root=project_root, package_dir=PACKAGE_DIR)

            html = render_notebook_preview(notebook_path.name, paths=paths)

        self.assertIn("nbx-published-shell", html)
        self.assertIn("nbx-published-canvas", html)
        self.assertIn("Example Notebook", html)
        self.assertIn("jp-MarkdownCell", html)
        self.assertIn("jp-CodeCell", html)
        self.assertIn("MathJax", html)
        self.assertNotIn("editorial-published", html)

    def test_nbx_hide_tag_removes_cell_from_preview(self) -> None:
        notebook = nbformat.v4.new_notebook()
        notebook.metadata["title"] = "Hide Test"
        notebook.cells = [
            nbformat.v4.new_markdown_cell("# Visible heading"),
            nbformat.v4.new_code_cell("secret_setup_code()"),
            nbformat.v4.new_markdown_cell("Visible paragraph"),
        ]
        notebook.cells[1].metadata["tags"] = ["nbx-hide"]

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            notebook_path = project_root / "post.ipynb"
            nbformat.write(notebook, notebook_path)
            paths = project_paths(project_root=project_root, package_dir=PACKAGE_DIR)

            html = render_notebook_preview(notebook_path.name, paths=paths)

        self.assertIn("Visible heading", html)
        self.assertIn("Visible paragraph", html)
        self.assertNotIn("secret_setup_code", html)

    def test_nbx_collapse_tag_wraps_cell_in_details_element(self) -> None:
        notebook = nbformat.v4.new_notebook()
        notebook.metadata["title"] = "Collapse Test"
        notebook.cells = [
            nbformat.v4.new_markdown_cell("# Intro"),
            nbformat.v4.new_code_cell("collapsed_code()"),
        ]
        notebook.cells[1].metadata["tags"] = ["nbx-collapse"]

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            notebook_path = project_root / "post.ipynb"
            nbformat.write(notebook, notebook_path)
            paths = project_paths(project_root=project_root, package_dir=PACKAGE_DIR)

            html = render_notebook_preview(notebook_path.name, paths=paths)

        self.assertIn("<details", html)
        self.assertIn("nbx-collapsed-cell", html)
        self.assertIn("Show code", html)
        self.assertIn("collapsed_code", html)

    def test_figure_mode_tags_add_celltag_classes(self) -> None:
        for tag in ("nbx-fig-hero", "nbx-fig-full", "nbx-fig-inset", "nbx-fig-fullscreen"):
            notebook = nbformat.v4.new_notebook()
            notebook.metadata["title"] = "Fig Test"
            notebook.cells = [nbformat.v4.new_code_cell("plot()")]
            notebook.cells[0].metadata["tags"] = [tag]

            with tempfile.TemporaryDirectory() as temp_dir:
                project_root = Path(temp_dir)
                notebook_path = project_root / "post.ipynb"
                nbformat.write(notebook, notebook_path)
                paths = project_paths(project_root=project_root, package_dir=PACKAGE_DIR)

                html = render_notebook_preview(notebook_path.name, paths=paths)

            self.assertIn(f"celltag_{tag}", html, f"Missing class for {tag}")

    def test_cell_metadata_caption_renders_figcaption(self) -> None:
        notebook = nbformat.v4.new_notebook()
        notebook.metadata["title"] = "Caption Test"
        notebook.cells = [nbformat.v4.new_code_cell("plot()")]
        notebook.cells[0].metadata["caption"] = "Monthly revenue by segment"

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            notebook_path = project_root / "post.ipynb"
            nbformat.write(notebook, notebook_path)
            paths = project_paths(project_root=project_root, package_dir=PACKAGE_DIR)

            html = render_notebook_preview(notebook_path.name, paths=paths)

        self.assertIn("<figure", html)
        self.assertIn("<figcaption", html)
        self.assertIn("Monthly revenue by segment", html)

    def test_nbx_hide_input_tag_adds_celltag_class(self) -> None:
        notebook = nbformat.v4.new_notebook()
        notebook.metadata["title"] = "Hide Input Test"
        notebook.cells = [
            nbformat.v4.new_code_cell("hidden_input_code()"),
        ]
        notebook.cells[0].metadata["tags"] = ["nbx-hide-input"]

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            notebook_path = project_root / "post.ipynb"
            nbformat.write(notebook, notebook_path)
            paths = project_paths(project_root=project_root, package_dir=PACKAGE_DIR)

            html = render_notebook_preview(notebook_path.name, paths=paths)

        self.assertIn("celltag_nbx-hide-input", html)

    def test_resolve_notebook_path_rejects_paths_outside_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir:
            project_root = Path(project_dir)
            outside_path = Path(other_dir) / "outside.ipynb"
            outside_path.write_text("{}", encoding="utf-8")
            paths = project_paths(project_root=project_root, package_dir=PACKAGE_DIR)

            with self.assertRaises(ValueError):
                resolve_notebook_path(str(outside_path), paths=paths)

    def test_resolve_notebook_path_rejects_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = project_paths(project_root=Path(temp_dir), package_dir=PACKAGE_DIR)

            with self.assertRaises(FileNotFoundError):
                resolve_notebook_path("missing.ipynb", paths=paths)


class PackagingTests(unittest.TestCase):
    def test_pyproject_exposes_nbx_as_the_shareable_command(self) -> None:
        with PYPROJECT_PATH.open("rb") as handle:
            config = tomllib.load(handle)

        self.assertEqual(config["project"]["name"], "nbx")
        self.assertEqual(
            config["project"]["scripts"]["nbx"],
            "nbx.launcher:main",
        )
        self.assertNotIn("editorial-notebook", config["project"]["scripts"])
        self.assertIn(
            "runtime_assets/**/*.template",
            config["tool"]["setuptools"]["package-data"]["nbx"],
        )


if __name__ == "__main__":
    unittest.main()
