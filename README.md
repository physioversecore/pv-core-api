# pvc-api

## Prerequisites

- Python 3.13 (see `.python-version`)
- [uv](https://docs.astral.sh/uv/) — install via `curl -LsSf https://astral.sh/uv/install.sh | sh` or `brew install uv`

## Setup

```sh
uv python pin 3.13        # ensure the right Python version
uv venv                    # create virtualenv at .venv/
uv sync                    # install all dependencies (currently none)
```

Activate the virtualenv:

```sh
source .venv/bin/activate
```

## Usage

```sh
uv run python main.py
```

## Managing dependencies

```sh
uv add <package>           # add a new dependency
uv remove <package>        # remove a dependency
uv sync                    # sync lockfile after changes
```

All dependencies are tracked in `pyproject.toml` and `uv.lock`.

To install from an existing `requirements.txt` (one-time import into `pyproject.toml`):

```sh
uv add -r requirements.txt   # imports into pyproject.toml and uv.lock
uv sync                       # install everything
```
