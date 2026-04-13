from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

import nbformat
from jupyter_server.base.handlers import JupyterHandler
from jupyter_server.utils import url_path_join
from nbconvert.exporters import HTMLExporter
from tornado.web import HTTPError, StaticFileHandler, authenticated

from .paths import ProjectPaths, project_paths


def _jupyter_server_extension_points() -> list[dict[str, str]]:
    return [{"module": "nbx"}]


def _is_within(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def resolve_notebook_path(
    raw_path: str | Path,
    paths: ProjectPaths | None = None,
) -> Path:
    resolved_paths = paths or project_paths()
    candidate = Path(raw_path)
    notebook_path = (
        candidate if candidate.is_absolute() else resolved_paths.project_root / candidate
    )
    notebook_path = notebook_path.resolve()

    if not _is_within(resolved_paths.project_root, notebook_path):
        raise ValueError("Preview is limited to notebooks inside this project root.")

    if not notebook_path.exists() or not notebook_path.is_file():
        raise FileNotFoundError(notebook_path)

    return notebook_path


def _derive_notebook_title(notebook: nbformat.NotebookNode, notebook_path: Path) -> str:
    metadata_title = str(notebook.metadata.get("title", "")).strip()
    if metadata_title:
        return metadata_title

    for cell in notebook.cells:
        if cell.cell_type != "markdown":
            continue
        for line in "".join(cell.source).splitlines():
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()

    return notebook_path.stem.replace("-", " ").replace("_", " ").title()


def render_notebook_preview(
    raw_path: str | Path,
    paths: ProjectPaths | None = None,
) -> str:
    resolved_paths = paths or project_paths()
    notebook_path = resolve_notebook_path(raw_path, paths=resolved_paths)
    notebook = nbformat.read(notebook_path, as_version=4)
    notebook.metadata["title"] = _derive_notebook_title(notebook, notebook_path)

    exporter = HTMLExporter(
        template_name="nbx-preview",
        extra_template_basedirs=[str(resolved_paths.preview_templates_dir)],
    )
    exporter.exclude_input_prompt = True
    exporter.exclude_output_prompt = True
    exporter.exclude_anchor_links = True

    html, _ = exporter.from_notebook_node(
        notebook,
        resources={
            "metadata": {"name": notebook_path.stem},
            "theme": "light",
        },
    )
    return html


class PreviewHandler(JupyterHandler):
    @authenticated
    def get(self, notebook_path: str) -> None:
        try:
            html = render_notebook_preview(unquote(notebook_path))
        except FileNotFoundError as exc:
            raise HTTPError(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPError(403, str(exc)) from exc

        self.set_header("Content-Type", "text/html; charset=utf-8")
        self.write(html)


def _load_jupyter_server_extension(server_app) -> None:
    paths = project_paths()
    base_url = server_app.web_app.settings["base_url"]
    handlers = [
        (url_path_join(base_url, "nbx-preview", "render", "(.*)"), PreviewHandler),
        (
            url_path_join(base_url, "nbx-preview", "assets", "(.*)"),
            StaticFileHandler,
            {"path": str(paths.static_dir)},
        ),
    ]
    server_app.web_app.add_handlers(".*$", handlers)
