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
        try:
            data = response.json()
        except Exception as e:
            print(f"\n⚠️ Error al parsear JSON de GitHub para {url}")
            print("Status code:", response.status_code)
            print("Response text:", response.text[:500])
            raise
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
        # Usa el parámetro 'auth', NO headers, para autenticación básica
        kwargs = {}
        if continuation_token:
            kwargs["headers"] = {"x-ms-continuationtoken": continuation_token}
        response = requests.get(url, auth=("", AZURE_TOKEN), params=params, **kwargs)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        try:
            data = response.json()
        except Exception as e:
            print(f"\n⚠️ Error al parsear JSON de Azure para {url}")
            print("Status code:", response.status_code)
            print("Response text:", response.text[:500])
            raise
        commits.extend([c["commitId"] for c in data["value"]])
        continuation_token = response.headers.get("x-ms-continuationtoken")
        if not continuation_token:
            break
    return commits


def load_shared_branches():
    """
    Lee el archivo branches_comparison.json y devuelve un dict:
    { repo_name: [branch1, branch2, ...] }
    """
    with open("data/branches_comparison.json") as f:
        branches_data = json.load(f)
    return {r["repo"]: r["shared_branches"] for r in branches_data}

def test_commit_comparison(matched_repos):
    print("\n🔍 Comparando commits entre Azure y GitHub...")

    report = []

    # Carga los branches comunes validados previamente
    shared_branches_dict = load_shared_branches()

    for pair in matched_repos:
        azure_repo = pair["azure"]
        github_repo = pair["github"]
        azure_id = azure_repo["repo_id"]
        repo_name = azure_repo["repo_name"]

        print(f"\n📦 Repositorio: {repo_name}")
        shared_branches = shared_branches_dict.get(repo_name, [])

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
