# tests/test_repository.py

import requests
import json
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import GITHUB_TOKEN, GITHUB_OWNER, AZURE_TOKEN, AZURE_ORG, AZURE_PROJECT

def get_github_repos():
    url = f"https://api.github.com/users/{GITHUB_OWNER}/repos?per_page=100"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return [{"repo": r["name"], "owner": GITHUB_OWNER} for r in response.json()]

def get_azure_repos():
    url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories?api-version=7.0"
    response = requests.get(url, auth=("", AZURE_TOKEN))
    response.raise_for_status()
    return [{"repo_id": r["id"], "repo_name": r["name"], "org": AZURE_ORG, "project": AZURE_PROJECT} for r in response.json()["value"]]

def test_generate_repo_list_json():
    print("\n📦 Obteniendo repositorios...")

    github_repos = get_github_repos()
    azure_repos = get_azure_repos()

    # Crear diccionarios por nombre (case insensitive)
    azure_names_dict = {r["repo_name"].lower(): r for r in azure_repos}
    github_names_dict = {r["repo"].lower(): r for r in github_repos}

    matched_keys = set(azure_names_dict.keys()) & set(github_names_dict.keys())
    only_in_azure = set(azure_names_dict.keys()) - matched_keys
    only_in_github = set(github_names_dict.keys()) - matched_keys

    # Armar lista combinada de emparejados
    combined = []
    for name in matched_keys:
        combined.append({
            "azure": azure_names_dict[name],
            "github": github_names_dict[name]
        })

    # Armar estructura de reporte
    report = {
        "matched": combined,
        "only_in_azure": [azure_names_dict[name] for name in only_in_azure],
        "only_in_github": [github_names_dict[name] for name in only_in_github]
    }

    # Guardar el archivo JSON
    os.makedirs("data", exist_ok=True)
    output_path = os.path.join("data", "repos_output.json")
    with open(output_path, "w") as f:
        json.dump(report, f, indent=4)

    # Mostrar resumen en consola
    print(f"\n✅ Repositorios emparejados: {len(combined)}")
    print(f"❌ Repositorios solo en Azure DevOps: {len(only_in_azure)}")
    print(f"❌ Repositorios solo en GitHub: {len(only_in_github)}")
    print(f"📝 Archivo generado: {output_path}")

def test_dummy():
    print("✅ test_repository ejecutado.")
