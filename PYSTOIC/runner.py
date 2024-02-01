import logging
from pathlib import Path

from setuptools import setup as _setup, find_packages
from .reader import read_workbook
from .codemod import (
    normalize_workbook,
    normalize_dir_structure,
    lint_package,
    write_requirements_txt_if_needed,
)
from .models import Workbook


class SetupRunner:
    def __init__(self, workbook_root: Path, package_name: str):
        self.workbook_root = workbook_root
        self.package_name = package_name
        self.workbook: Workbook | None = None

    def setup(self, **kwargs):
        install_requires = []
        wb_requirements = self.workbook_root / "requirements.txt"
        if wb_requirements.exists():
            install_requires = wb_requirements.read_text().splitlines()

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
