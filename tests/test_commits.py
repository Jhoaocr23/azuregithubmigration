# tests/test_commits.py

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
from config import GITHUB_TOKEN, AZURE_TOKEN, AZURE_ORG, AZURE_PROJECT

def get_github_commits(owner, repo, branch):
    commits = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/commits?sha={branch}&per_page=100&page={page}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 409:  # empty branch (e.g., no commits)
            return []
        response.raise_for_status()
        data = response.json()
        if not data:
            break
        commits.extend([c["sha"] for c in data])
        page += 1
    return commits

def get_azure_commits(repo_id, branch):
    commits = []
    continuation_token = None
    while True:
        url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/commits"
        params = {
            "searchCriteria.itemVersion.versionType": "branch",
            "searchCriteria.itemVersion.version": branch,
            "$top": 100,
            "api-version": "7.0"
        }
        headers = {"Authorization": f"Basic {AZURE_TOKEN}"}
        if continuation_token:
            headers["x-ms-continuationtoken"] = continuation_token
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        data = response.json()
        commits.extend([c["commitId"] for c in data["value"]])
        continuation_token = response.headers.get("x-ms-continuationtoken")
        if not continuation_token:
            break
    return commits

def get_shared_branches(azure_repo_id, github_owner, github_repo):
    azure_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{azure_repo_id}/refs?filter=heads/&api-version=7.0"
    azure_response = requests.get(azure_url, auth=("", AZURE_TOKEN))
    azure_branches = {b["name"].replace("refs/heads/", "") for b in azure_response.json()["value"]}

    github_url = f"https://api.github.com/repos/{github_owner}/{github_repo}/branches"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    github_response = requests.get(github_url, headers=headers)
    github_branches = {b["name"] for b in github_response.json()}

    return sorted(azure_branches & github_branches)

def test_commit_comparison(matched_repos):
    print("\n🔍 Comparando commits entre Azure y GitHub...")

    report = []

    for pair in matched_repos:
        azure_repo = pair["azure"]
        github_repo = pair["github"]
        azure_id = azure_repo["repo_id"]
        repo_name = azure_repo["repo_name"]

        print(f"\n📦 Repositorio: {repo_name}")
        shared_branches = get_shared_branches(azure_id, github_repo["owner"], github_repo["repo"])
        if not shared_branches:
            print("⚠️  No hay branches comunes, se omite comparación de commits.")
            continue

        repo_result = {
            "repo": repo_name,
            "branches": []
        }

        for branch in shared_branches:
            try:
                azure_commits = set(get_azure_commits(azure_id, branch))
                github_commits = set(get_github_commits(github_repo["owner"], github_repo["repo"], branch))

                missing_in_github = sorted(azure_commits - github_commits)
                extra_in_github = sorted(github_commits - azure_commits)
                shared_commits = sorted(azure_commits & github_commits)

                print(f"🔁 Branch: {branch}")
                print(f"   ✔ Commits comunes: {len(shared_commits)}")
                if missing_in_github:
                    print(f"   ❌ Faltan en GitHub: {len(missing_in_github)}")
                if extra_in_github:
                    print(f"   ⚠️ Extras en GitHub (no en Azure): {len(extra_in_github)}")

                repo_result["branches"].append({
                    "branch": branch,
                    "shared_commits": shared_commits,
                    "missing_in_github": missing_in_github,
                    "extra_in_github": extra_in_github
                })
            except Exception as e:
                print(f"⚠️ Error al comparar branch {branch}: {str(e)}")

        report.append(repo_result)

    # Guardar reporte en JSON
    os.makedirs("data", exist_ok=True)
    output_path = os.path.join("data", "commits_comparison.json")
    with open(output_path, "w") as f:
        json.dump(report, f, indent=4)

    print(f"\n📝 Reporte de comparación de commits guardado en: {output_path}")
