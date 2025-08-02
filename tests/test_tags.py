# tests/test_tags.py

import requests
import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import GITHUB_TOKEN, GITHUB_OWNER, AZURE_TOKEN, AZURE_ORG, AZURE_PROJECT
import pytest


@pytest.fixture
def matched_repos():
    path = os.path.join("data", "repos_output.json")
    with open(path, "r") as f:
        data = json.load(f)
    return data["matched"]

def get_github_tags(repo_name):
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{repo_name}/tags"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return []
    return [t["name"] for t in response.json()]

def get_azure_tags(repo_id):
    url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs?filter=tags/&api-version=7.0"
    response = requests.get(url, auth=("", AZURE_TOKEN))
    if response.status_code != 200:
        return []
    return [ref["name"].split("refs/tags/")[-1] for ref in response.json().get("value", [])]

def test_compare_tags(matched_repos):
    print("🔍 Comparando tags entre Azure y GitHub...\n")

    results = []

    for pair in matched_repos:
        azure_repo = pair["azure"]
        github_repo = pair["github"]
        repo_name = azure_repo["repo_name"]
        print(f"📦 Repositorio: {repo_name}")

        azure_tags = get_azure_tags(azure_repo["repo_id"])
        github_tags = get_github_tags(github_repo["repo"])

        shared_tags = sorted(set(azure_tags) & set(github_tags))
        only_in_azure = sorted(set(azure_tags) - set(github_tags))
        only_in_github = sorted(set(github_tags) - set(azure_tags))

        # 🖨 Mensajes de consola mejorados
        if not azure_tags and not github_tags:
            print("⚠️ No se encontraron tags ni en Azure ni en GitHub para este repositorio.")
        else:
            print(f"🔁 Tags en Azure:  {azure_tags if azure_tags else '⚠️ Ninguno'}")
            print(f"🔁 Tags en GitHub: {github_tags if github_tags else '⚠️ Ninguno'}")
            print(f"✅ Tags comunes:   {shared_tags if shared_tags else '⚠️ Ninguno'}")

            if only_in_azure:
                print(f"⚠️ Solo en Azure:  {only_in_azure}")
            if only_in_github:
                print(f"⚠️ Solo en GitHub: {only_in_github}")

        results.append({
            "repo": repo_name,
            "azure_tags": azure_tags,
            "github_tags": github_tags,
            "shared_tags": shared_tags,
            "only_in_azure": only_in_azure,
            "only_in_github": only_in_github
        })

        print("")  # Línea vacía

    # Guardar el resultado
    os.makedirs("data", exist_ok=True)
    with open("data/tags_comparison.json", "w") as f:
        json.dump(results, f, indent=4)

    print("📝 Reporte de comparación de tags guardado en: data/tags_comparison.json")
