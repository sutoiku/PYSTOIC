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

        self._setup(
            name=self.package_name,
            version=self.workbook.package_version if self.workbook else "0.0.0",
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
            self.workbook = workbook
            normalize_workbook(workbook)
            normalize_dir_structure(workbook, self.package_name)
            lint_package()
            write_requirements_txt_if_needed(workbook)
        else:
            logging.info(
                f"{target_package_path} already exists, skipping workbook setup"
            )

        _setup(**kwargs)
