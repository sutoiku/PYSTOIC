import json
import logging
import os
import re
from pathlib import Path

from .config import NB_FILE_NAMES, BLOCK_SPLIT_PATTERNS
from .models import (
    Notebook,
    NotebookBlock,
    Workbook,
    Workfolder,
    NotebookLanguage,
)
from .utils import to_snake_case, git_repo_name


def read_resource_properties(resource_spec: dict) -> dict:
    custom_props: list[dict] = resource_spec.get("locals", [])
    return {prop["id"]: prop["code"] for prop in custom_props}


def read_resource_tags(resource_spec: dict) -> list[str]:
    return resource_spec.get("tags", [])


def read_workbook_spec(workbook_root: Path) -> dict:
    path = workbook_root.absolute()
    workbook_spec_path = path / "Workbook.json"
    if not workbook_spec_path.exists():
        raise ValueError(f"{workbook_spec_path} must exist")

    return json.loads(workbook_spec_path.read_text())


def read_package_name(workbook_root: Path) -> str:
    if "WB_PYTHON_PACKAGE_NAME" in os.environ:
        package_name = os.environ["WB_PYTHON_PACKAGE_NAME"]
        return to_snake_case(package_name)

    workbook_properties: dict = read_resource_properties(
        read_workbook_spec(workbook_root)
    )
    if "pythonPackageName" in workbook_properties:
        package_name = workbook_properties["pythonPackageName"]
        return to_snake_case(package_name)

    repo_name = git_repo_name()
    if repo_name is not None:
        return f"stoic_{to_snake_case(repo_name)}"

    error_message = """
  No package name was found. Please specify it via one of the following methods:
  1. Set the environment variable `WB_PYTHON_PACKAGE_NAME`
  2. Set a custom Workbook property `pythonPackageName`
  3. Try to install the workbook as a package from a `git` context so that the repo name can be used
  """.strip()
    logging.error(error_message)
    raise Exception(error_message)


def read_block(
    sources: dict[NotebookLanguage, dict[str, str]], block_meta: dict
) -> NotebookBlock:
    id = block_meta["id"]
    lang = block_meta["lang"]
    return NotebookBlock(
        id=id,
        lang=lang,
        pinned=block_meta.get("pinned", False),
        source=sources[lang][id],
    )


def read_blocks(
    sources: dict[NotebookLanguage, dict[str, str]], blocks_meta: list[dict]
) -> list[NotebookBlock]:
    return [read_block(sources, block_meta) for block_meta in blocks_meta]


def extract_id(id_comment: str) -> str:
    return re.match(r".* @id (\w+)", id_comment).group(1)


def split_source_to_blocks(
    source: str, split_pattern: str | re.Pattern[str]
) -> dict[str, str]:
    blocks = re.split(split_pattern, source)
    if blocks and not blocks[0].strip():
        blocks = blocks[1:]

    # Pair up the IDs with their corresponding blocks
    blocks_with_ids = [
        (blocks[i].strip(), blocks[i + 1].strip()) for i in range(0, len(blocks), 2)
    ]
    return {extract_id(block_id): block for block_id, block in blocks_with_ids}


def read_block_sources_per_id(
    sources: dict[NotebookLanguage, str],
) -> dict[NotebookLanguage, dict[str, str]]:
    return {
        lang: split_source_to_blocks(source, BLOCK_SPLIT_PATTERNS[lang])
        for lang, source in sources.items()
    }


def read_notebook_files(nb: Path) -> dict[NotebookLanguage, Path]:
    files: dict[NotebookLanguage, Path] = {}
    for lang, file_name in NB_FILE_NAMES.items():
        path = nb / file_name
        if path.exists():
            files[lang] = path

    return files


def read_notebook_sources(
    files: dict[NotebookLanguage, Path],
) -> dict[NotebookLanguage, str]:
    return {lang: path.read_text() for lang, path in files.items()}


def read_notebook(wf: Path, notebook_meta: dict) -> Notebook:
    path = wf / notebook_meta["name"]
    notebook_spec: dict = json.loads((path / "Notebook.json").read_text())
    files = read_notebook_files(path)
    sources = read_notebook_sources(files)
    block_sources = read_block_sources_per_id(sources)
    return Notebook(
        id=notebook_meta["id"],
        block_sources=block_sources,
        blocks=read_blocks(block_sources, notebook_spec["blocks"]),
        description=notebook_spec.get("description", None),
        files=files,
        name=notebook_meta["name"],
        path=path,
        properties=read_resource_properties(resource_spec=notebook_spec),
        sources=sources,
        spec=notebook_spec,
        tags=read_resource_tags(resource_spec=notebook_spec),
    )


def read_notebooks(wf: Path, notebooks_meta: list[dict]) -> list[Notebook]:
    return [read_notebook(wf, nb_meta) for nb_meta in notebooks_meta]


def read_workfolder(wb: Path, workfolder_meta: dict) -> Workfolder:
    path = wb / workfolder_meta["name"]
    workfolder_spec: dict = json.loads((path / "Workfolder.json").read_text())
    notebooks_meta = [p for p in workfolder_spec["pages"] if p["type"] == "notebook"]
    return Workfolder(
        id=workfolder_meta["id"],
        description=workfolder_spec.get("description", None),
        name=workfolder_meta["name"],
        notebooks=read_notebooks(path, notebooks_meta),
        path=path,
        properties=read_resource_properties(resource_spec=workfolder_spec),
        spec=workfolder_spec,
        tags=read_resource_tags(resource_spec=workfolder_spec),
    )


def read_workfolders(wb: Path, workfolders_meta: list[dict]) -> list[Workfolder]:
    return [read_workfolder(wb, wf_meta) for wf_meta in workfolders_meta]


def read_workbook(workbook_root: Path) -> Workbook:
    path = workbook_root.absolute()
    workbook_spec = read_workbook_spec(workbook_root)
    return Workbook(
        id=workbook_spec["id"],
        description=workbook_spec.get("description", None),
        name=workbook_root.name,
        path=path,
        properties=read_resource_properties(resource_spec=workbook_spec),
        spec=workbook_spec,
        tags=read_resource_tags(resource_spec=workbook_spec),
        workfolders=read_workfolders(path, workbook_spec["workfolders"]),
    )
