"""Single source of truth for the app version.

Both the FastAPI app metadata and the OTA updater read from here. Keep this
in sync with [pyproject.toml] `[project] version` and the git tag.

Releases follow `vMAJOR.MINOR.PATCH`; the updater compares numerically.
"""

__version__ = "0.3.6"
__github_repo__ = "tubby124/truecolor-press-console"
