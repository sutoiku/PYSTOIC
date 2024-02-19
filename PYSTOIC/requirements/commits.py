import requests


def build_query(repos: list[str], primary_branch: str, fallback_branch: str) -> str:
    """
    GraphQL query so that we can query the latest commit hashes for `n` repos
    in 1 request to GitHub instead of `2*n` requests.
    """
    repo_queries = []
    for i, repo in enumerate(repos, start=1):
        org_name, repo_name = repo.split("/")
        key = repo.replace("/", "___")
        repo_query = f"""
      {key}: repository(owner: "{org_name}", name: "{repo_name}") {{
          primaryBranch: ref(qualifiedName: "{primary_branch}") {{
            target {{
              ... on Commit {{
                history(first: 1) {{
                  edges {{
                    node {{
                      abbreviatedOid
                    }}
                  }}
                }}
              }}
            }}
          }}
          fallbackBranch: ref(qualifiedName: "{fallback_branch}") {{
            target {{
              ... on Commit {{
                history(first: 1) {{
                  edges {{
                    node {{
                      abbreviatedOid
                    }}
                  }}
                }}
              }}
            }}
          }}
      }}
      """
        repo_queries.append(repo_query)
    return "{" + " ".join(repo_queries) + "}"


def latest_commit_hashes(
    repos: list[str], primary_branch: str, fallback_branch: str, gh_token: str
) -> dict:
    URL = "https://api.github.com/graphql"
    HEADERS = {
        "Authorization": f"Bearer {gh_token}",
        "Content-Type": "application/json",
    }
    query = build_query(repos, primary_branch, fallback_branch)
    response = requests.post(URL, json={"query": query}, headers=HEADERS)
    if response.status_code == 200:
        return response.json()["data"]
    else:
        raise Exception(
            f"Query failed with status code {response.status_code}: {response.text}"
        )


def transform_graphql_response(response: dict) -> list[dict]:
    result = []
    for repo, data in response.items():
        primary = (
            data["primaryBranch"]["target"]["history"]["edges"][0]["node"][
                "abbreviatedOid"
            ]
            if data["primaryBranch"]
            else None
        )
        fallback = (
            data["fallbackBranch"]["target"]["history"]["edges"][0]["node"][
                "abbreviatedOid"
            ]
            if data["fallbackBranch"]
            else None
        )
        repo_with_org = repo.replace("___", "/")

        if primary is None and fallback is None:
            raise ValueError(
                f"Neither primary nor fallback branch found for {repo_with_org}"
            )

        result.append(
            {"workbook": repo_with_org, "primary": primary, "fallback": fallback}
        )

    return result
