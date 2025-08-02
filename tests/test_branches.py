# tests/test_branches.py

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
from config import GITHUB_TOKEN, AZURE_TOKEN, AZURE_ORG, AZURE_PROJECT

def get_github_branches(repo_owner, repo_name):
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/branches"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return [branch["name"] for branch in response.json()]

def get_azure_branches(repo_id):
    url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs?filter=heads/&api-version=7.0"
    response = requests.get(url, auth=("", AZURE_TOKEN))
    response.raise_for_status()
    return [branch["name"].replace("refs/heads/", "") for branch in response.json()["value"]]

def test_branch_comparison(matched_repos):
    print("\n🔍 Comparando branches entre Azure y GitHub...")
    
    report = []

    for pair in matched_repos:
        azure_repo = pair["azure"]
        github_repo = pair["github"]

        azure_name = azure_repo["repo_name"]
        github_name = github_repo["repo"]

        try:
            azure_branches = set(get_azure_branches(azure_repo["repo_id"]))
            github_branches = set(get_github_branches(github_repo["owner"], github_name))

            shared = sorted(azure_branches & github_branches)
            only_in_azure = sorted(azure_branches - github_branches)
            only_in_github = sorted(github_branches - azure_branches)

            print(f"\n📦 Repositorio emparejado: {azure_name} ↔ {github_name}")
            print(f"🔁 Branches en Azure DevOps: {sorted(azure_branches)}")
            print(f"🔁 Branches en GitHub:       {sorted(github_branches)}")
            print(f"✅ Branches comunes:         {shared}")
            if only_in_azure:
                print(f"❌ Branches solo en Azure:   {only_in_azure}")
            if only_in_github:
                print(f"❌ Branches solo en GitHub:  {only_in_github}")

            report.append({
                "repo": azure_name,
                "azure_branches": sorted(list(azure_branches)),
                "github_branches": sorted(list(github_branches)),
                "shared_branches": shared,
                "only_in_azure": only_in_azure,
                "only_in_github": only_in_github
            })

        except Exception as e:
            print(f"⚠️ Error al comparar branches para {azure_name}: {str(e)}")

    # Guardar reporte en JSON
    os.makedirs("data", exist_ok=True)
    output_path = os.path.join("data", "branches_comparison.json")
    with open(output_path, "w") as f:
        json.dump(report, f, indent=4)

    print(f"\n📝 Reporte de comparación guardado en: {output_path}")
