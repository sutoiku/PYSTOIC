from .runner import SetupRunner
from os import PathLike
from pathlib import Path


def setup(workbook_root: str | PathLike[str], **kwargs):
    if kwargs.pop("verbose", True):
        import logging

        logging.basicConfig(level=logging.DEBUG)

    workbook_root_path = Path(workbook_root)
    if workbook_root_path.is_file():
        workbook_root_path = workbook_root_path.parent

    package_name = kwargs.pop("package_name", None)
    runner = SetupRunner(workbook_root=workbook_root_path, package_name=package_name)
    runner.setup(**kwargs)
