import re
import subprocess
import logging


def git_repo_name() -> str | None:
    try:
        remote_url = (
            subprocess.check_output(
                ["git", "config", "--get", "remote.origin.url"],
                stderr=subprocess.STDOUT,
            )
            .strip()
            .decode("utf-8")
        )
    except subprocess.CalledProcessError as e:
        logging.error(f"Error getting remote origin URL: {e}", exc_info=True)
        return None

    # Extract the repo name from the URL, assumes SSH or HTTPS
    if remote_url.endswith(".git"):
        remote_url = remote_url.replace(".git", "")

    repo_name = remote_url.split("/")[-1]  # Get the last part of the path
    return repo_name


def to_snake_case(text: str) -> str:
    text = text.replace("-", "_").replace(" ", "_").replace(".", "_")
    text = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", text)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", text).lower()
