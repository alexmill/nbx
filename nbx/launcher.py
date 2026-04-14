from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from .paths import ProjectPaths, project_paths


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="nbx",
        add_help=False,
    )
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("notebook_path", nargs="?", type=Path)
    parser.add_argument("-h", "--help", action="store_true")

    parsed, jupyter_args = parser.parse_known_args(argv)
    parsed.jupyter_args = jupyter_args
    return parsed


def _render_runtime_template(template_path: Path, paths: ProjectPaths) -> str:
    content = template_path.read_text(encoding="utf-8")
    replacements = {
        "__PROJECT_ROOT__": repr(str(paths.project_root)),
        "__NOTEBOOK_TEMPLATES_DIR__": repr(str(paths.notebook_templates_dir)),
    }
    for token, value in replacements.items():
        content = content.replace(token, value)
    return content


def _generate_templates(paths: ProjectPaths) -> None:
    """Generate notebook templates from the installed notebook package, injecting nbx.js."""
    import notebook

    source_dir = Path(notebook.__file__).resolve().parent / "templates"
    target_dir = paths.notebook_templates_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    nbx_script = (
        '<script defer="defer" src="{{ base_url | escape }}'
        'nbx-preview/assets/nbx.js"></script>'
    )

    for template_file in source_dir.glob("*.html"):
        content = template_file.read_text(encoding="utf-8")
        content = content.replace("</head>", f"{nbx_script}</head>")
        (target_dir / template_file.name).write_text(content, encoding="utf-8")


def _sync_runtime_assets(paths: ProjectPaths) -> None:
    for source in paths.runtime_assets_dir.rglob("*"):
        if source.is_dir():
            continue

        relative_path = source.relative_to(paths.runtime_assets_dir)
        target = paths.runtime_dir / relative_path

        if target.suffix == ".template":
            target = target.with_suffix("")
            rendered = _render_runtime_template(source, paths)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def ensure_runtime_directories(paths: ProjectPaths | None = None) -> ProjectPaths:
    resolved_paths = paths or project_paths()

    for directory in (
        resolved_paths.config_dir,
        resolved_paths.config_dir / "custom",
        resolved_paths.data_dir,
        resolved_paths.lab_settings_dir,
        resolved_paths.workspaces_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    _sync_runtime_assets(resolved_paths)
    _generate_templates(resolved_paths)
    return resolved_paths


def build_environment(
    base_env: dict[str, str] | None = None,
    paths: ProjectPaths | None = None,
) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    resolved_paths = paths or project_paths()

    env["JUPYTER_CONFIG_DIR"] = str(resolved_paths.config_dir)
    env["JUPYTER_DATA_DIR"] = str(resolved_paths.data_dir)
    env["JUPYTERLAB_SETTINGS_DIR"] = str(resolved_paths.lab_settings_dir)
    env["JUPYTERLAB_WORKSPACES_DIR"] = str(resolved_paths.workspaces_dir)
    env["NBX_PROJECT_ROOT"] = str(resolved_paths.project_root)
    env["NBX_PACKAGE_DIR"] = str(resolved_paths.package_dir)

    return env


def build_command(
    notebook_path: Path | None = None,
    extra_args: list[str] | None = None,
    paths: ProjectPaths | None = None,
) -> list[str]:
    command = ["jupyter", "notebook", *(extra_args or [])]
    if notebook_path is None:
        return command

    resolved_paths = paths or project_paths()
    target_path = notebook_path

    if notebook_path.is_absolute():
        try:
            target_path = notebook_path.resolve().relative_to(resolved_paths.project_root)
        except ValueError:
            target_path = notebook_path.resolve()

    command.append(str(target_path))
    return command


def render_to_html(notebook_path: Path, output_path: Path | None = None) -> Path:
    """Render a notebook to static HTML using the nbx-preview template."""
    from .preview import render_notebook_preview

    resolved = notebook_path.resolve()
    paths = project_paths(project_root=resolved.parent)
    html = render_notebook_preview(resolved.name, paths=paths)

    if output_path is None:
        output_path = resolved.with_suffix(".html")

    output_path.write_text(html, encoding="utf-8")
    return output_path


def tag_all_hidden(notebook_path: Path) -> None:
    """Add 'nbx-hide' tag to every code cell that doesn't already have an nbx-fig-* or nbx-collapse tag."""
    import nbformat

    resolved = notebook_path.resolve()
    notebook = nbformat.read(resolved, as_version=4)

    for cell in notebook.cells:
        if cell.cell_type != "code":
            continue
        tags = list(cell.metadata.get("tags", []))
        if any(t.startswith("nbx-") for t in tags):
            continue
        tags.append("nbx-hide")
        cell.metadata["tags"] = tags

    nbformat.write(notebook, resolved)
    print(f"Tagged {sum(1 for c in notebook.cells if c.cell_type == 'code')} code cells with nbx-hide")


HELP_TEXT = """\
nbx — a shareable notebook shell for Jupyter

Commands:
  nbx [notebook.ipynb]                  Launch the notebook editor
  nbx render <notebook.ipynb>           Render notebook to static HTML
  nbx render <notebook.ipynb> --watch   Render and re-render on every save
  nbx render <notebook.ipynb> -o FILE   Render to a custom output path
  nbx hide-all <notebook.ipynb>         Tag all code cells with nbx-hide
  nbx help                              Show this help message

Configuration:
  Place an nbx.json in the project root to configure fonts, etc.
  See https://github.com/alexmill/nbx for details.
"""


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv

    if not args or (len(args) == 1 and args[0] in ("help", "-h", "--help")):
        if not args:
            pass  # fall through to launch editor
        else:
            print(HELP_TEXT)
            return 0

    if args and args[0] == "render":
        render_args = args[1:]
        if not render_args or render_args[0] in ("-h", "--help"):
            print("Usage: nbx render <notebook.ipynb> [-o output.html] [--watch]")
            return 0

        nb_path = Path(render_args[0])
        out_path = None
        watch = "--watch" in render_args

        remaining = [a for a in render_args[1:] if a != "--watch"]
        if "-o" in remaining:
            idx = remaining.index("-o")
            if idx + 1 < len(remaining):
                out_path = Path(remaining[idx + 1])

        result = render_to_html(nb_path, out_path)
        print(result)

        if watch:
            import time

            resolved = nb_path.resolve()
            last_mtime = resolved.stat().st_mtime
            print(f"Watching {resolved.name} for changes... (Ctrl+C to stop)")
            try:
                while True:
                    time.sleep(1)
                    current_mtime = resolved.stat().st_mtime
                    if current_mtime != last_mtime:
                        last_mtime = current_mtime
                        result = render_to_html(nb_path, out_path)
                        print(f"Re-rendered → {result}")
            except KeyboardInterrupt:
                print("\nStopped watching.")

        return 0

    if args and args[0] == "hide-all":
        hide_args = args[1:]
        if not hide_args or hide_args[0] in ("-h", "--help"):
            print("Usage: nbx hide-all <notebook.ipynb>")
            return 0
        tag_all_hidden(Path(hide_args[0]))
        return 0

    parsed = parse_args(args)
    paths = ensure_runtime_directories(project_paths(project_root=parsed.project_root))

    if parsed.help:
        command = build_command(extra_args=["--help"], paths=paths)
    else:
        command = build_command(
            notebook_path=parsed.notebook_path,
            extra_args=parsed.jupyter_args,
            paths=paths,
        )

    try:
        completed = subprocess.run(
            command,
            cwd=paths.project_root,
            env=build_environment(paths=paths),
            check=False,
        )
    except KeyboardInterrupt:
        return 130

    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
