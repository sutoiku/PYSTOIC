import logging
from pathlib import Path
import os

from setuptools import setup as _setup, find_packages
from .reader import read_workbook, read_package_name
from .codemod import (
    normalize_workbook,
    normalize_dir_structure,
    lint_package,
    write_requirements_txt_if_needed,
)
from .models import Workbook
from .utils import git_package_identifier


def _parse_requirements(requirements_content: str) -> list[str]:
    return [
        os.path.expandvars(line.strip())
        for line in requirements_content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


class SetupRunner:
    def __init__(self, workbook_root: Path, package_name: str | None = None):
        self.workbook_root = workbook_root
        self.package_name = package_name or read_package_name(workbook_root)
        self.workbook: Workbook | None = None

    def setup(self, **kwargs):
        install_requires = []
        wb_requirements = self.workbook_root / "requirements.txt"
        if wb_requirements.exists():
            requirements_content = wb_requirements.read_text()
            should_expand_vars = kwargs.pop("requirements_expand_vars", True)
            install_requires = (
                _parse_requirements(requirements_content)
                if should_expand_vars
                else requirements_content.splitlines()
            )
        version = self.workbook.package_version if self.workbook else "0.0.0"
        git_identifier = git_package_identifier()
        version_maybe_suffixed = (
            f"{version}+{git_identifier}" if git_identifier else version
        )
        packages = find_packages(self.workbook_root, include=[f"{self.package_name}*"])
        logging.info(f"Found packages: {packages}")
        self._setup(
            name=self.package_name,
            version=version_maybe_suffixed,
            packages=packages,
            python_requires=">=3.10",
            install_requires=install_requires,
            **kwargs,
        )

    def _setup(self, **kwargs):
        target_package_path = self.workbook_root / self.package_name
        if not target_package_path.exists():
            logging.info(f"Producing {target_package_path}...")
            workbook = read_workbook(self.workbook_root)
            self.workbook = workbook
            normalize_workbook(
                workbook,
                kwargs.pop("create_module_roots", workbook.schema_version < 18),
            )
            normalize_dir_structure(workbook, self.package_name)
            lint_package()
            write_requirements_txt_if_needed(workbook)
        else:
            logging.info(
                f"{target_package_path} already exists, skipping workbook setup"
            )

        _setup(**kwargs)
