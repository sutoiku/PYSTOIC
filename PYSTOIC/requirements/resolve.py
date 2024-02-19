from loguru import logger
from .utils import Requirement, wb_req_parts, group_reqs_by_name


def resolve_req_version(
    versions: list[Requirement], primary_branch: str
) -> Requirement:
    logger.debug(f"Resolving version for {versions}...")
    # if there is no conflict, return the only version
    if len(versions) == 1:
        logger.debug(f'No conflict, returning "{versions[0]}"')
        return versions[0]

    # try pick a version homonymous with the primary branch
    primary_branch_normalized = primary_branch.replace("/", ".").replace("-", ".")
    homo_req = [r for r in versions if wb_req_parts(r)[0] == primary_branch_normalized]
    if homo_req:
        logger.debug(f'Homonymous branch found, going to use "{homo_req[0]}"')
        return homo_req[0]

    # Otherwise go with the first one
    logger.warning(f'No homonymous branch found, resorting to "{versions[0]}"')
    return versions[0]


def resolve_wb_reqs(reqs: list[Requirement], primary_branch: str) -> list:
    resolved = set()
    grouped = group_reqs_by_name(reqs)
    for versions in grouped.values():
        resolved_version = resolve_req_version(versions, primary_branch)
        resolved.add(resolved_version)
    return sorted(list(resolved))
