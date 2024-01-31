from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from setuptools import setup as _setup, find_packages
from typing import Literal
import ast
import json
import logging
import os
import re
import subprocess

logging.basicConfig(level=logging.DEBUG)

NotebookLanguage = Literal["ai", "html", "javascript", "markdown", "python", "sql"]
BLOCK_SPLIT_PATTERNS: dict[NotebookLanguage, str] = {
    "ai": r"(// @id \w+)",
    "html": r"(<!-- @id \w+ -->)",
    "javascript": r"(// @id \w+)",
    "markdown": r"(<!-- @id \w+ -->)",
    "python": r"(# @id \w+)",
    "sql": r"(-- @id \w+)",
}
NB_FILE_NAMES: dict[NotebookLanguage, str] = {
    "ai": "blocks.ai",
    "html": "blocks.html",
    "javascript": "blocks.js",
    "markdown": "blocks.md",
    "python": "blocks.py",
    "sql": "blocks.sql",
}
PYTHON_EXCLUSION_PATTERNS = [
    re.compile(r"#\s*exclude[:#\s]*"),
    re.compile(r"def\s+test_"),
]


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


def get_package_name(workbook_root: Path) -> str:
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


@dataclass(frozen=True, kw_only=True)
class NotebookBlock:
    id: str
    lang: NotebookLanguage
    pinned: bool = False
    source: str

    @cached_property
    def lines(self):
        return self.source.splitlines()

    @cached_property
    def is_production(self):
        if not self.lines:
            return False

        return not any(
            [pattern.match(self.lines[0]) for pattern in PYTHON_EXCLUSION_PATTERNS]
        )

    @cached_property
    def source_with_id(self):
        return "\n".join([f"# @id {self.id}", self.source])


@dataclass(frozen=True, kw_only=True)
class Notebook:
    id: str
    block_sources: dict[NotebookLanguage, dict[str, str]]
    blocks: list[NotebookBlock]
    description: str | None
    files: dict[NotebookLanguage, Path]
    name: str
    path: Path
    properties: dict[str, str]
    sources: dict[NotebookLanguage, str]
    spec: dict
    tags: list[str]

    @cached_property
    def is_python_excluded(self):
        return "pythonExclude" in self.properties

    @cached_property
    def has_python_source(self):
        return "python" in self.files

    @cached_property
    def production_python_source(self):
        if self.is_python_excluded:
            return ""

        python_blocks = [b for b in self.blocks if b.lang == "python"]
        production_python_blocks = [b for b in python_blocks if b.is_production]
        return "\n\n".join([b.source_with_id for b in production_python_blocks])


@dataclass(frozen=True, kw_only=True)
class Workfolder:
    id: str
    description: str | None
    name: str
    notebooks: list[Notebook]
    path: Path
    properties: dict[str, str]
    spec: dict
    tags: list[str]

    @cached_property
    def python_notebooks(self):
        return [nb for nb in self.notebooks if nb.has_python_source]


@dataclass(frozen=True, kw_only=True)
class FileContext:
    lang: NotebookLanguage
    notebook: Notebook
    path: Path
    source: str
    workfolder: Workfolder


@dataclass(frozen=True, kw_only=True)
class Workbook:
    id: str
    description: str | None
    name: str
    path: Path
    properties: dict[str, str]
    spec: dict
    tags: list[str]
    workfolders: list[Workfolder]

    @cached_property
    def notebooks(self) -> list[Notebook]:
        return [nb for wf in self.workfolders for nb in wf.notebooks]

    @cached_property
    def python_notebooks(self) -> list[Notebook]:
        return [nb for nb in self.notebooks if nb.has_python_source]

    @cached_property
    def python_files(self) -> list[Path]:
        return [nb.files["python"] for nb in self.notebooks if nb.has_python_source]

    def contextualize_file(self, path: Path) -> FileContext:
        if not path.is_file():
            raise ValueError(f"Expected {path} to be a file")

        notebook_name = path.parent.name
        workfolder_name = path.parent.parent.name
        workfolder = next(wf for wf in self.workfolders if wf.name == workfolder_name)
        notebook = next(nb for nb in workfolder.notebooks if nb.name == notebook_name)
        lang = next(
            lang
            for lang, file_path in notebook.files.items()
            if file_path.absolute() == path.absolute()
        )
        source = notebook.sources[lang]
        return FileContext(
            lang=lang,
            notebook=notebook,
            path=path,
            source=source,
            workfolder=workfolder,
        )

    @cached_property
    def python_requirements(self) -> list[str]:
        if "pythonRequirements" in self.properties:
            requirements = self.properties["pythonRequirements"].split(",")
            return [r.strip() for r in requirements]

        return []


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
    workbook_spec = read_workbook_spec()
    return Workbook(
        id=workbook_spec["id"],
        description=workbook_spec.get("description", None),
        name=git_repo_name(),
        path=path,
        properties=read_resource_properties(resource_spec=workbook_spec),
        spec=workbook_spec,
        tags=read_resource_tags(resource_spec=workbook_spec),
        workfolders=read_workfolders(path, workbook_spec["workfolders"]),
    )


def member_is_excluded(name: str) -> bool:
    """
    Check if the given name should be excluded based on predefined patterns.

    Args:
        name: The name to check for exclusion

    Returns: True if the name should be excluded, False otherwise
    """
    return name.startswith("test_") or name.startswith("__")


def discover_to_be_exported_declarations(python_file: Path) -> list[str]:
    """
    Parses the given python file and returns a list of strings
    representing the names of the functions, classes and variables
    that should be exported in the `__init__.py` file.

    Args:
        python_file: Path to a python file

    Returns: list of strings
    """
    python_src = python_file.read_text()
    tree = ast.parse(python_src)
    exportable_declarations = []

    class DeclarationFinder(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            if not member_is_excluded(node.name):
                exportable_declarations.append(node.name)

        def visit_ClassDef(self, node):
            if not member_is_excluded(node.name):
                exportable_declarations.append(node.name)

        def visit_Assign(self, node):
            # Only consider top-level assignments by checking if the parent node is 'Module'
            if isinstance(node.parent, ast.Module):
                for target in node.targets:
                    if isinstance(target, ast.Name) and not member_is_excluded(
                        target.id
                    ):
                        exportable_declarations.append(target.id)

    # Add a parent attribute to each node that points to the parent node
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            child.parent = node

    # Create an instance of the node visitor and visit the AST
    finder = DeclarationFinder()
    finder.visit(tree)

    return sorted(list(set(exportable_declarations)))


AUTO_GENERATED_HEADER = "# THIS FILE WAS AUTOGENERATED BY setup.py"


def create_init_file_body(module_name: str, declarations: list[str]) -> str:
    """
    Creates the body of an `__init__.py` file for the given module name and list of declarations.

    Args:
        module_name: The name of the module, such as `blocks`
        declarations: The list of declarations to export

    Returns: A string representing the body of the `__init__.py` file
    """
    if len(declarations) == 0:
        return AUTO_GENERATED_HEADER

    import_statement = f'from .{module_name} import {", ".join(declarations)}'
    declaration_strings = [f"'{declaration}'" for declaration in declarations]
    all_statement = f'__all__ = [{", ".join(declaration_strings)}]'
    return "\n\n".join([AUTO_GENERATED_HEADER, import_statement, all_statement])


def setup_module_init_file(module_root: Path):
    parent_init_file = Path(module_root).parent / "__init__.py"
    if not parent_init_file.exists():
        parent_init_file.write_text(AUTO_GENERATED_HEADER)

    init_file = Path(module_root) / "__init__.py"
    if init_file.exists() and file_was_already_processed(init_file):
        logging.debug(f"Skipping {init_file} as it was already processed")
        return

    module_name = "blocks"
    python_module_file = Path(module_root) / f"{module_name}.py"

    if not python_module_file.exists():
        logging.error(f"Expected to find {python_module_file} but it does not exist")
        raise Exception(f"Expected to find {python_module_file} but it does not exist")

    exported_declarations = discover_to_be_exported_declarations(python_module_file)
    logging.debug(f"Exporting {exported_declarations} from {python_module_file}")

    init_file_body = create_init_file_body(module_name, exported_declarations)
    init_file.write_text(init_file_body)
    logging.info(f"Wrote {init_file}")


def remove_tests(python_src: str) -> str:
    class RemoveTestsTransformer(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            # Remove functions starting with 'test_' by skipping their visit
            # i.e. not including them in the returned tree
            if node.name.startswith("test_"):
                return None
            return self.generic_visit(node)

    python_src = python_src.replace("import pytest", "")
    tree = ast.parse(python_src)
    cleaned_tree = RemoveTestsTransformer().visit(tree)
    return ast.unparse(cleaned_tree)


def remove_no_effect_nodes(source_code: str) -> str:
    class NoEffectNodeRemover(ast.NodeTransformer):
        def visit_Expr(self, node):
            # Check if the expression has a value that is not a function call
            # or other side-effect operations like yield
            if not isinstance(
                node.value, (ast.Call, ast.Yield, ast.YieldFrom, ast.Await)
            ):
                return None  # Remove the node by returning None
            return self.generic_visit(node)

    tree = ast.parse(source_code)
    cleaned_tree = NoEffectNodeRemover().visit(tree)
    return ast.unparse(cleaned_tree)


def patch_python_file(ctxt: FileContext):
    python_file = ctxt.path
    if AUTO_GENERATED_HEADER in ctxt.source:
        logging.info(f"Skipping {python_file} as it was already processed")
        return

    # This ensures that excluded and test blocks are not included in the production source
    python_src = ctxt.notebook.production_python_source

    # Apply patches
    python_src = remove_tests(python_src)
    python_src = remove_no_effect_nodes(python_src)
    python_src = "\n".join([AUTO_GENERATED_HEADER, python_src])

    python_file.write_text(python_src)


def lint_package():
    subprocess.run(["ruff", "--fix", "."], check=False)
    subprocess.run(["ruff", "format", "."], check=False)


def write_requirements_txt_if_needed(workbook: Workbook):
    requirements_txt = Path("requirements.txt")
    if requirements_txt.exists():
        logging.info(f"{requirements_txt} already exists, skipping")
        return
    else:
        logging.info(f"Writing {workbook.python_requirements} to {requirements_txt}...")
        requirements_txt.write_text("\n".join(workbook.python_requirements))


def file_was_already_processed(python_file: Path) -> bool:
    """
    Checks if the given python file was already processed
    by checking if it contains the auto-generated header.

    Args:
        python_file: Path to a python file

    Returns: True if the file was already processed, False otherwise
    """
    python_src = python_file.read_text()
    return AUTO_GENERATED_HEADER in python_src


def normalize_workbook(workbook: Workbook):
    python_files = workbook.python_files
    logging.info(f"Applying patches to python files: {python_files}")
    for python_file in python_files:
        file_ctxt = workbook.contextualize_file(python_file)
        patch_python_file(file_ctxt)

    module_roots = [nb.path for nb in workbook.python_notebooks]
    logging.info(f"Creating `__init__.py` in module roots: {module_roots}")
    for module_root in module_roots:
        setup_module_init_file(module_root)


def normalize_dir_structure(workbook: Workbook, package_name: str):
    package_root = workbook.path / package_name
    if package_root.exists():
        logging.info(f"Package root {package_root} already exists, skipping")
        return

    package_root.mkdir(exist_ok=False)
    subfolders: list[Path] = [wf.path for wf in workbook.workfolders]

    # Move each subfolder to the package root
    for subfolder in subfolders:
        target = package_root / subfolder.name
        logging.debug(f"Copying {subfolder} to {target}")
        subfolder.rename(target)

    package_root_init_file = package_root / "__init__.py"
    package_root_init_file.touch()


class SetupRunner:
    def __init__(self, workbook_root: Path, package_name: str):
        self.workbook_root = workbook_root
        self.package_name = package_name

    def setup(self, **kwargs):
        install_requires = []
        wb_requirements = self.workbook_root / "requirements.txt"
        if wb_requirements.exists():
            install_requires = wb_requirements.read_text().splitlines()

        self._setup(
            name=self.package_name,
            packages=find_packages(
                where=self.workbook_root.absolute(),
                exclude=[
                    "tests*",
                    "*.tests",
                    "*.tests.*",
                    "tests.*",
                    "__pycache__",
                    "*.pyc",
                ],
            ),
            python_requires=">=3.10",
            install_requires=install_requires,
            **kwargs,
        )

    def _setup(self, **kwargs):
        target_package_path = self.workbook_root / self.package_name
        if not target_package_path.exists():
            logging.info(f"Producing {target_package_path}...")
            workbook = read_workbook(self.workbook_root)
            normalize_workbook(workbook)
            normalize_dir_structure(workbook, self.package_name)
            lint_package()
            write_requirements_txt_if_needed(workbook)
        else:
            logging.info(
                f"{target_package_path} already exists, skipping workbook setup"
            )

        _setup(**kwargs)
