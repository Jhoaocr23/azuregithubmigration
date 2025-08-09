# tests/test_workflows.py
import os
import json
import requests
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import GITHUB_TOKEN  # usa tus credenciales
import pytest

# Archivos requeridos dentro de .github/workflows/
REQUIRED_WORKFLOWS = [
    "workflow-dev.yml",
    "workflow-prod.yml",
    "workflow-qa.yml",
    "workflows-pr.yml",  # <- según tu especificación
]

def list_workflow_files(owner: str, repo: str):
    """
    Lista los archivos dentro de .github/workflows de un repo de GitHub.
    Retorna [] si la carpeta no existe (404) o está vacía.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/.github/workflows"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 404:
        # La carpeta .github o workflows no existe
        return []
    r.raise_for_status()
    data = r.json()
    # Si la API devuelve un dict, puede ser archivo individual (raro aquí), si es lista son los elementos del dir
    if isinstance(data, list):
        return [item.get("name", "") for item in data if item.get("type") == "file"]
    return []

def test_workflows_presence(matched_repos):
    """
    Para cada repo matched, valida existencia de .github/workflows y
    de los archivos requeridos. Genera data/workflows_check.json con el resumen.
    """
    print("\n🔍 Validando .github/workflows en repos de GitHub...")

    results = []
    for pair in matched_repos:
        gh = pair["github"]
        owner = gh["owner"]
        repo = gh["repo"]

        print(f"📦 {owner}/{repo} ...")
        try:
            files = list_workflow_files(owner, repo)
            missing = [f for f in REQUIRED_WORKFLOWS if f not in files]
            exists_all = len(missing) == 0

            if exists_all:
                print("   ✅ Todos los workflows requeridos presentes.")
            else:
                print(f"   ❌ Faltan: {missing}")

            results.append({
                "repo": repo,
                "owner": owner,
                "workflow_dir_exists": len(files) > 0,
                "present_files": sorted(files),
                "required_files": REQUIRED_WORKFLOWS,
                "missing_files": missing,
                "ok": exists_all
            })
        except Exception as e:
            print(f"   ⚠️ Error al validar workflows: {e}")
            results.append({
                "repo": repo,
                "owner": owner,
                "workflow_dir_exists": False,
                "present_files": [],
                "required_files": REQUIRED_WORKFLOWS,
                "missing_files": REQUIRED_WORKFLOWS[:],
                "ok": False,
                "error": str(e)
            })

    os.makedirs("data", exist_ok=True)
    out = os.path.join("data", "workflows_check.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=4)
    print(f"📝 Reporte de workflows guardado en: {out}")
