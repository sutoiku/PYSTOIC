import argparse
from .install_api import install_requirements


def main():
    parser = argparse.ArgumentParser(
        description="Install requirements for specified workbooks."
    )

    # Define command-line arguments
    parser.add_argument(
        "workbooks", nargs="+", help="List of workbooks in the format 'org/repo'."
    )
    parser.add_argument("--primary-branch", required=True, help="Primary branch name.")
    parser.add_argument(
        "--fallback-branch", required=True, help="Fallback branch name."
    )
    parser.add_argument(
        "--pypi-remote",
        required=True,
        help="S3 path for PyPI remote, e.g., 's3://...'.",
    )
    parser.add_argument("--pypi-local", required=True, help="Local path for PyPI.")
    parser.add_argument(
        "--gh-token",
        help="GitHub token. If not specified, it must be present as 'GITHUB_TOKEN' in the env.",
        default=None,
    )

    # Parse arguments
    args = parser.parse_args()

    # Call the install_requirements function with parsed arguments
    install_requirements(
        workbooks=args.workbooks,
        primary_branch=args.primary_branch,
        fallback_branch=args.fallback_branch,
        pypi_remote=args.pypi_remote,
        pypi_local=args.pypi_local,
        gh_token=args.gh_token,
    )


if __name__ == "__main__":
    main()
