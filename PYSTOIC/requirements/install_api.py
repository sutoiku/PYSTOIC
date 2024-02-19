import os
import sh
from loguru import logger
from .utils import (
    Requirement,
    wb_reqs,
    req_to_wheel,
    wheel_file_reqs,
    classify_reqs,
    collect_requirements,
)
from .commits import latest_commit_hashes, transform_graphql_response
from .resolve import resolve_wb_reqs
import time


def install_reqs(reqs: list[Requirement], options: list[str] | None = None):
    if not reqs:
        return
    req_string = " ".join([f'"{str(r)}"' for r in reqs])
    opt = options or []
    opt_string = " ".join(opt)
    return sh.bash(
        "-c", f"{sh.pip} install {req_string} {opt_string}", _out=logger.debug
    )


def install_wb_reqs(reqs: list[Requirement], pypi_local: str):
    return install_reqs(
        reqs=reqs, options=["-v", "--no-deps", f"--find-links={pypi_local}"]
    )


def sync_wheels(pypi_local: str, pypi_remote: str):
    sh.mkdir("-p", pypi_local, _out=logger.debug)
    sh.aws.s3.sync(pypi_remote, pypi_local, "--delete", _out=logger.debug)


def install_requirements(
    workbooks: list[str],
    primary_branch: str,
    fallback_branch: str,
    pypi_remote: str,
    pypi_local: str,
    gh_token: str | None = None,
    wb_prefix: str = "index",
):
    tick = time.time()
    GITHUB_TOKEN = gh_token or os.getenv("GITHUB_TOKEN")
    if not GITHUB_TOKEN:
        raise ValueError(
            "GITHUB_TOKEN is required to access latest commit hashes for dependency resolution"
        )

    logger.info(f'🔁 Syncing wheels from "{pypi_remote}" to "{pypi_local}"...')
    sync_wheels(pypi_local, pypi_remote)

    logger.info("🌳 Analyzing commit trees...")
    hashes_nested = latest_commit_hashes(
        workbooks, primary_branch, fallback_branch, GITHUB_TOKEN
    )
    hashes = transform_graphql_response(hashes_nested)
    logger.debug(f"Transformed GitHub GraphQL API response: {hashes}")

    logger.info("📜 Inspecting wheel file requirements...")
    top_level_reqs = wb_reqs(hashes, primary_branch, fallback_branch)
    all_requirements = collect_requirements(
        set(top_level_reqs), primary_branch, fallback_branch, pypi_local
    )
    logger.debug(f"Wheel file requirements: {sorted(all_requirements)}")

    logger.info("🏷️ Classifying requirements...")
    wb, py = classify_reqs(list(all_requirements), wb_prefix)
    logger.debug(f"📙 Workbook requirements: {wb}")
    logger.debug(f"🐍 Python requirements: {py}")

    logger.info("⚒️ Resolving workbook requirements...")
    wb_resolved = resolve_wb_reqs(wb, primary_branch)

    logger.info("📦 Installing workbook requirements...")
    install_wb_reqs(wb_resolved, pypi_local)

    logger.info("📦 Installing Python requirements...")
    install_reqs(py)

    toc = time.time()

    logger.info(f"🎉 Done in {toc - tick:.2f} seconds.")


PYPI_REMOTE = "s3://stoic-index/pypi/"
PYPI_LOCAL = "/Users/petergy/Downloads/stoic-index/pypi"
WB = [
    "sutoiku/Workers",
]
PRIMARY_BRANCH = "feature/deps-change"
FALLBACK_BRANCH = "feature/deps"


if __name__ == "__main__":
    install_requirements(
        workbooks=WB,
        primary_branch=PRIMARY_BRANCH,
        fallback_branch=FALLBACK_BRANCH,
        pypi_remote=PYPI_REMOTE,
        pypi_local=PYPI_LOCAL,
    )
