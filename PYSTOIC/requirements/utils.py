from typing import NamedTuple
import pkginfo
import re
from loguru import logger


def _wb(workbook: str, branch: str, commit: str) -> str:
    _, repo = workbook.split("/")
    package_name = f"index-{repo}".lower()
    branch_normalized = branch.replace("/", ".").replace("-", ".")
    assert len(commit) == 7, "Expected a short, 7 char long commit hash"
    package_version = f"0.0.0+{branch_normalized}.{commit}"
    return f"{package_name}=={package_version}"


def wb(
    workbook: str,
    primary_branch: str,
    primary_commit: str,
    fallback_branch: str,
    fallback_commit: str,
) -> str:
    branch = primary_branch if primary_commit else fallback_branch
    commit = primary_commit if primary_commit else fallback_commit
    return _wb(workbook, branch, commit)


def wb_reqs(hashes: list[dict], primary_branch: str, fallback_branch: str) -> list[str]:
    return [
        wb(
            workbook=item["workbook"],
            primary_branch=primary_branch,
            primary_commit=item["primary"],
            fallback_branch=fallback_branch,
            fallback_commit=item["fallback"],
        )
        for item in hashes
    ]


def req_to_wheel(req: str) -> str:
    package, version = req.split("==")
    return f'{package.replace("-", "_")}-{version}-py3-none-any.whl'


class Requirement(NamedTuple):
    name: str
    version: str | None

    def __str__(self) -> str:
        return f"{self.name}=={self.version}" if self.version else self.name


def parse_pkginfo_req(req_string: str) -> Requirement:
    # e.g. 'index-commands (==0.0.0+feature.deps.acbdc9f)' or index-commands
    pattern = r"^(.+?)\s*\(==(.+?)\)$"
    match = re.match(pattern, req_string)
    if match:
        package, version = match.groups()
        return Requirement(package, version)
    else:
        return Requirement(req_string, None)


def parse_req(req_string: str) -> Requirement:
    # e.g. 'index-files==0.0.0+feature.deps.34330ff' or index-files
    pattern = r"^(.+?)\s*==(.+?)$"
    match = re.match(pattern, req_string)
    if match:
        package, version = match.groups()
        return Requirement(package, version)
    else:
        return Requirement(req_string, None)


def wheel_file_reqs(wheel_file: str) -> list[Requirement]:
    req_strings = pkginfo.Wheel(wheel_file).requires_dist
    reqs = [parse_pkginfo_req(req_string) for req_string in req_strings]
    logger.debug(f'Requirements extracted from "{wheel_file}": {reqs}')
    return reqs


def is_wb_req(req_str: str, wb_prefix: str) -> bool:
    return req_str.startswith(wb_prefix) and "==" in req_str


def collect_requirements(
    initial_reqs: set[str],
    primary_branch: str,
    fallback_branch: str,
    pypi_local: str,
    wb_prefix: str = "index",
    visited: set[str] = None,
) -> set[str]:
    if visited is None:
        visited = set()

    all_reqs = set()
    for req in initial_reqs:
        if req in visited or not is_wb_req(req, wb_prefix):
            continue

        visited.add(req)
        wheel_path = f"{pypi_local}/{req_to_wheel(req)}"
        direct_reqs = wheel_file_reqs(wheel_path)
        # Collect direct requirements' strings
        direct_reqs_strs = {str(req) for req in direct_reqs}
        all_reqs.update(direct_reqs_strs)
        # Recursively collect for nested requirements starting with 'index_'
        nested_reqs = {req for req in direct_reqs_strs if is_wb_req(req, wb_prefix)}
        if nested_reqs:
            reqs = collect_requirements(
                nested_reqs,
                primary_branch,
                fallback_branch,
                pypi_local,
                wb_prefix,
                visited,
            )
            all_reqs.update(reqs)
    return all_reqs


def classify_reqs(
    reqs: list[str], wb_prefix: str
) -> tuple[list[Requirement], list[Requirement]]:
    return (
        sorted(set([parse_req(req) for req in reqs if is_wb_req(req, wb_prefix)])),
        sorted(set([parse_req(req) for req in reqs if not is_wb_req(req, wb_prefix)])),
    )


def group_reqs_by_name(reqs: list[Requirement]) -> dict[str, list[Requirement]]:
    result = {}
    for req in reqs:
        if req.name in result:
            result[req.name].append(req)
        else:
            result[req.name] = [req]
    return result


def wb_req_parts(req: Requirement) -> tuple[str, str]:
    parts = req.version.split("+")[1].split(".")
    branch = ".".join(parts[:-1])
    commit = parts[-1]
    return branch, commit
