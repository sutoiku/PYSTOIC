from setuptools import setup, find_packages

install_requires = [
    "ruff",
    "setuptools",
]
extras_reqs = ["pkginfo", "loguru", "sh", "requests", "tabulate"]
extras_all = [*extras_reqs]
extras_require = {
    "reqs": extras_reqs,
    "all": extras_all,
}

setup(
    name="PYSTOIC",
    version="0.2.3",
    packages=find_packages(),
    install_requires=install_requires,
    extras_require=extras_require,
    python_requires=">=3.10",
)
