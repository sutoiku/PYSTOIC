import logging
import re
import shutil
import subprocess


def git_repo_name() -> str | None:
    git = shutil.which("git")
    if git is None:
        return None

    try:
        remote_url = (
            subprocess.check_output(
                [git, "config", "--get", "remote.origin.url"],
                stderr=subprocess.STDOUT,
            )
            .strip()
            .decode("utf-8")
        )
    except Exception as e:
        logging.error(f"Error getting remote origin URL: {e}", exc_info=True)
        return None

    # Extract the repo name from the URL, assumes SSH or HTTPS
    if remote_url.endswith(".git"):
        remote_url = remote_url.replace(".git", "")

    repo_name = remote_url.split("/")[-1]  # Get the last part of the path
    return repo_name


def git_hash_short() -> str | None:
    git = shutil.which("git")
    if git is None:
        return None

    try:
        return (
            subprocess.check_output(
                [git, "rev-parse", "--short", "HEAD"], stderr=subprocess.STDOUT
            )
            .strip()
            .decode("utf-8")
        )
    except Exception as e:
        logging.error(f"Error getting git hash: {e}", exc_info=True)
        return None


def git_branch() -> str | None:
    git = shutil.which("git")
    if git is None:
        return None

    try:
        return (
            subprocess.check_output(
                [git, "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.STDOUT
            )
            .strip()
            .decode("utf-8")
        )
    except Exception as e:
        logging.error(f"Error getting git branch: {e}", exc_info=True)
        return None


def to_snake_case(text: str) -> str:
    text = text.replace("-", "_").replace(" ", "_").replace(".", "_")
    text = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", text)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", text).lower()


def git_package_identifier() -> str | None:
    sha_short = git_hash_short()
    branch = git_branch()
    if sha_short is None:
        return None

    # feat/e2e-command -> feat.e2e-command
    branch_normalized = branch.replace("/", ".") if branch is not None else "detached"

    # feat.e2e-command -> feat.e2e-command.1234567
    return f"{branch_normalized}.{sha_short}"
