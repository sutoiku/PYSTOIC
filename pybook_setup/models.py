from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from .config import PYTHON_EXCLUSION_PATTERNS, NotebookLanguage


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

    @property
    def package_version(self) -> str:
        return self.properties.get("pythonPackageVersion", "0.0.0")
