from setuptools import setup, find_packages

setup(
    name="PYSTOIC",
    version="0.2.1",
    packages=find_packages(),
    install_requires=["ruff", "setuptools"],
    python_requires=">=3.10",
)
