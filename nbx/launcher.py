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


def main(argv: list[str] | None = None) -> int:
    parsed = parse_args(sys.argv[1:] if argv is None else argv)
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
