from setuptools import setup, find_packages

setup(
    name="PYSTOIC",
    version="0.2.2",
    packages=find_packages(),
    install_requires=[
        "ruff",
        "setuptools",
    ],
    extras_require={"reqs": ["pkginfo", "loguru", "sh", "requests"]},
    python_requires=">=3.10",
)
