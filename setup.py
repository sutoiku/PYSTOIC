from setuptools import setup, find_packages
from pathlib import Path

setup(
    name="PYSTOIC",
    version="0.1.1",
    packages=find_packages(),
    install_requires=Path("requirements.txt").read_text().splitlines(),
    python_requires=">=3.10",
)
