from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    project_root: Path
    package_dir: Path
    runtime_dir: Path
    config_dir: Path
    data_dir: Path
    lab_settings_dir: Path
    workspaces_dir: Path
    notebook_templates_dir: Path
    preview_templates_dir: Path
    runtime_assets_dir: Path
    static_dir: Path


def project_paths(
    project_root: Path | None = None,
    package_dir: Path | None = None,
) -> ProjectPaths:
    resolved_package_dir = (package_dir or Path(__file__).resolve().parent).resolve()
    resolved_project_root = (project_root or Path.cwd()).resolve()
    runtime_dir = resolved_project_root / ".nbx"

    return ProjectPaths(
        project_root=resolved_project_root,
        package_dir=resolved_package_dir,
        runtime_dir=runtime_dir,
        config_dir=runtime_dir / "jupyter-config",
        data_dir=runtime_dir / "jupyter-data",
        lab_settings_dir=runtime_dir / "jupyterlab-settings",
        workspaces_dir=runtime_dir / "jupyterlab-workspaces",
        notebook_templates_dir=runtime_dir / "templates",
        preview_templates_dir=resolved_package_dir / "preview_templates",
        runtime_assets_dir=resolved_package_dir / "runtime_assets",
        static_dir=resolved_package_dir / "static",
    )
