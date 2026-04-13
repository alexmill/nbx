# NBX

`nbx` is a small Jupyter wrapper that gives notebooks a clean writing and preview shell without forcing users into this exact checkout.

It launches the standard Jupyter Notebook server, writes the required config into a project-local `.nbx/` directory, applies the custom notebook template and theme, and adds a Preview action that renders a saved notebook as a clean reading view.

## Install

With UV, the easiest local install is:

```bash
uv tool install .
```

To share it straight from a GitHub repo, publish this repo and then install from Git:

```bash
uv tool install git+https://github.com/alexmill/nbx.git
```

If someone only wants to try it once without installing it permanently:

```bash
uvx --from git+https://github.com/alexmill/nbx.git nbx
```

## Use

Run it in the folder that should act as the notebook project root:

```bash
nbx
```

That opens Jupyter rooted at the current directory with the NBX interface active.

To open a specific notebook immediately:

```bash
nbx draft.ipynb
```

To point the shell at another folder:

```bash
nbx --project-root ~/work/essay-notebooks draft.ipynb
```

Any extra flags are passed through to `jupyter notebook`:

```bash
nbx draft.ipynb --no-browser --ServerApp.port=9999
```

## What Gets Shared

The package shares:

- the notebook page template
- the NBX theme and toolbar shell
- the preview server extension and preview template
- the generated Jupyter config under `.nbx/`

The user keeps:

- their own notebook files
- their own Python environment and kernels
- their own machine and compute
