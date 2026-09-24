import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"


class LocalConfigError(ValueError):
    """Configuration error whose message is safe to show in the UI."""

    def __init__(self, public_message):
        super().__init__(public_message)
        self.public_message = public_message


def _load(env_file=ENV_FILE):
    load_dotenv(
        dotenv_path=env_file,
        override=True,
    )


def get_config_status(env_file=ENV_FILE):
    _load(env_file)

    raw_entry_id = os.getenv(
        "FPL_ENTRY_ID",
        "",
    ).strip()

    try:
        entry_id = (
            int(raw_entry_id)
            if raw_entry_id
            else None
        )
    except ValueError:
        entry_id = None

    token_configured = bool(
        os.getenv(
            "FPL_REFRESH_TOKEN",
            "",
        ).strip()
    )

    return {
        "configured":
            (
                entry_id is not None
                and entry_id > 0
                and token_configured
            ),
        "entry_id":
            entry_id,
        "refresh_token_configured":
            token_configured,
        "env_file":
            str(env_file),
    }


def is_configured(env_file=ENV_FILE):
    return get_config_status(
        env_file
    )["configured"]


def get_entry_id(env_file=ENV_FILE):
    status = get_config_status(
        env_file
    )

    entry_id = status["entry_id"]

    if entry_id is None or entry_id <= 0:
        raise RuntimeError(
            "FPL_ENTRY_ID is not configured."
        )

    return entry_id


def get_refresh_token(env_file=ENV_FILE):
    _load(env_file)

    token = os.getenv(
        "FPL_REFRESH_TOKEN",
        "",
    ).strip()

    if not token:
        raise RuntimeError(
            "FPL_REFRESH_TOKEN is not configured."
        )

    return token


def _validate_value(name, value):
    if "\n" in value or "\r" in value:
        raise LocalConfigError(
            f"{name} must be a single-line value."
        )


def _replace_setting(lines, key, value):
    prefix = f"{key}="
    replacement = f"{prefix}{value}\n"

    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = replacement
            return

    lines.append(replacement)


def save_local_config(
    entry_id,
    refresh_token=None,
    env_file=ENV_FILE,
):
    try:
        entry_id = int(
            str(entry_id).strip()
        )
    except (TypeError, ValueError):
        raise LocalConfigError(
            "FPL Entry ID must be a number."
        ) from None

    if entry_id <= 0:
        raise LocalConfigError(
            "FPL Entry ID must be greater than zero."
        )

    token = (
        str(refresh_token).strip()
        if refresh_token is not None
        else None
    )

    if token == "":
        token = None

    if token is not None:
        _validate_value(
            "FPL refresh token",
            token,
        )

    env_file = Path(env_file)

    lines = []

    if env_file.exists():
        lines = env_file.read_text(
            encoding="utf-8"
        ).splitlines(
            keepends=True
        )

    _replace_setting(
        lines,
        "FPL_ENTRY_ID",
        str(entry_id),
    )

    if token is not None:
        _replace_setting(
            lines,
            "FPL_REFRESH_TOKEN",
            token,
        )

    existing_token = next(
        (
            line.split("=", 1)[1].strip()
            for line in lines
            if line.startswith(
                "FPL_REFRESH_TOKEN="
            )
        ),
        "",
    )

    if not existing_token:
        raise LocalConfigError(
            "FPL refresh token is required "
            "for authenticated features."
        )

    env_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_file = env_file.with_name(
        f"{env_file.name}.tmp"
    )

    temp_file.write_text(
        "".join(lines),
        encoding="utf-8",
    )
    os.chmod(
        temp_file,
        0o600,
    )
    temp_file.replace(
        env_file
    )
    os.chmod(
        env_file,
        0o600,
    )

    os.environ["FPL_ENTRY_ID"] = (
        str(entry_id)
    )
    os.environ["FPL_REFRESH_TOKEN"] = (
        existing_token
    )

    return get_config_status(
        env_file
    )


def save_refresh_token(
    refresh_token,
    env_file=ENV_FILE,
):
    entry_id = get_entry_id(
        env_file
    )

    return save_local_config(
        entry_id,
        refresh_token,
        env_file=env_file,
    )
