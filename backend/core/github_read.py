"""Bounded, read-only GitHub repository context.

Only fixed GitHub REST GET endpoints are exposed. Tokens never leave the backend.
"""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from backend.core import connectors, security

API_ROOT = "https://api.github.com"


def _get(path, token, params=None):
    url = f"{API_ROOT}{path}"
    if params:
        url = f"{url}?{urlencode(params)}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Rasputin-read-only-integration",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urlopen(Request(url, headers=headers, method="GET"), timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise PermissionError("GitHub rejected the stored token or its repository access.") from exc
        if exc.code == 404:
            raise ValueError("GitHub repository or commit was not found.") from exc
        raise RuntimeError(f"GitHub returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise RuntimeError("GitHub could not be reached.") from exc


def _repo_name(value):
    parts = str(value or "").strip().strip("/").split("/")
    if len(parts) != 2 or not all(part.replace("-", "").replace("_", "").replace(".", "").isalnum() for part in parts):
        raise ValueError("A valid GitHub owner/repository remote is required.")
    return parts[0], parts[1]


def repository_context(owner_id, repository, branch="", head_sha=""):
    security.require("allow_github_read")
    cfg = security.load()
    if cfg.get("offline_lock"):
        raise PermissionError("offline_lock blocks GitHub access")

    owner, repo = _repo_name(repository)
    credentials = connectors.connector_credentials(owner_id, "github")
    token = str(credentials.get("token") or "").strip()
    if not token:
        raise PermissionError("Configure a GitHub token in Connector Center first.")

    repo_path = f"/repos/{quote(owner)}/{quote(repo)}"
    metadata = _get(repo_path, token)
    pulls = _get(
        f"{repo_path}/pulls",
        token,
        {"state": "open", "head": f"{owner}:{branch}", "per_page": 10},
    ) if branch else []
    issues = _get(f"{repo_path}/issues", token, {"state": "open", "per_page": 10})
    checks = _get(
        f"{repo_path}/commits/{quote(head_sha)}/check-runs",
        token,
        {"per_page": 50},
    ).get("check_runs", []) if head_sha else []

    return {
        "repository": {
            "fullName": metadata.get("full_name") or repository,
            "url": metadata.get("html_url"),
            "description": metadata.get("description") or "",
            "visibility": metadata.get("visibility") or ("private" if metadata.get("private") else "public"),
            "defaultBranch": metadata.get("default_branch") or "",
        },
        "pullRequests": [
            {"number": item.get("number"), "title": item.get("title"), "url": item.get("html_url"), "draft": bool(item.get("draft"))}
            for item in pulls
        ],
        "issues": [
            {"number": item.get("number"), "title": item.get("title"), "url": item.get("html_url")}
            for item in issues if "pull_request" not in item
        ],
        "checks": [
            {"name": item.get("name"), "status": item.get("status"), "conclusion": item.get("conclusion"), "url": item.get("html_url")}
            for item in checks
        ],
        "readOnly": True,
        "authenticated": True,
    }
