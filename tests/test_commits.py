# tests/test_commits.py
import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
from config import GITHUB_TOKEN, AZURE_TOKEN, AZURE_ORG, AZURE_PROJECT

# ---------------------------
# Imports y config
# ---------------------------
from concurrent.futures import ThreadPoolExecutor, as_completed
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "12"))  # <-- Ajusta 8–24 según tu token)

# ---------------------------
# Utilidades para alias master <-> main
# ---------------------------
def _normalize_branch_name_from_azure_to_github(name: str) -> str:
    """Azure puede tener 'master'; en GitHub usamos 'main' como alias directo."""
    return "main" if name == "master" else name

def _pair_branches_for_commits(azure_branches, github_branches):
    """
    Devuelve una lista de tuplas (az_branch, gh_branch, label) emparejando
    ramas para comparación de commits con estas reglas:
      1) Coincidencia exacta (az == gh)
      2) Alias Azure 'master' -> GitHub 'main'
      3) Alias Azure 'main'   -> GitHub 'master'  (NUEVO)
    """
    gh_set = set(github_branches)
    pairs = []
    for az in azure_branches:
        # 1) Coincidencia exacta primero
        if az in gh_set:
            pairs.append((az, az, az))
            continue

        # 2) Azure 'master' -> GitHub 'main' (ya lo cubría la normalización)
        if az == "master" and "main" in gh_set:
            pairs.append((az, "main", "master → main"))
            continue

        # 3) Azure 'main' -> GitHub 'master' (NUEVO)
        if az == "main" and "master" in gh_set:
            pairs.append((az, "master", "main → master"))
            continue

        # 4) Fallback usando normalización (por seguridad)
        gh = _normalize_branch_name_from_azure_to_github(az)
        if gh in gh_set:
            label = f"{az} → {gh}" if az != gh else gh
            pairs.append((az, gh, label))

    return pairs

def load_branch_pairs():
    """
    Lee data/branches_comparison.json y construye, por repo, los pares (az, gh, label)
    considerando alias master<->main.
    Estructura devuelta:
      { repo_name: [(az_branch, gh_branch, label), ...], ... }
    """
    with open("data/branches_comparison.json") as f:
        rows = json.load(f)

    result = {}
    for r in rows:
        repo_name = r["repo"]
        azure_branches = r.get("azure_branches", [])
        github_branches = r.get("github_branches", [])
        result[repo_name] = _pair_branches_for_commits(azure_branches, github_branches)
    return result


def get_github_commits(owner, repo, branch, session=None):  # <--- acepta session opcional
    commits = []
    page = 1
    s = session or requests.Session()  # <--- Reusa conexión si te paso una sesión
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/commits?sha={branch}&per_page=100&page={page}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        response = s.get(url, headers=headers)
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
    """
    Trae TODOS los commits de Azure DevOps para una rama, usando 7.2-preview.2,
    $top=5000 y paginación via continuationToken (query param).
    """
    commits = []
    continuation_token = None
    page = 1

    session = requests.Session()
    base_url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/commits"

    params = {
        "searchCriteria.itemVersion.versionType": "branch",
        "searchCriteria.itemVersion.version": branch,
        "$top": 5000,
        "api-version": "7.2-preview.2"
    }
    headers = {"Accept": "application/json"}

    while True:
        if continuation_token:
            params["continuationToken"] = continuation_token
        else:
            params.pop("continuationToken", None)

        response = session.get(
            base_url,
            auth=("", AZURE_TOKEN),
            params=params,
            headers=headers,
            timeout=60
        )

        if response.status_code == 404:
            return []
        response.raise_for_status()

        try:
            data = response.json()
        except Exception:
            print(f"\n⚠️ Error al parsear JSON de Azure para {base_url}")
            print("Status code:", response.status_code)
            print("Response text:", response.text[:500])
            raise

        batch = [c["commitId"] for c in data.get("value", [])]
        commits.extend(batch)

        print(f"🔎 [AZURE] Página {page}: Traídos {len(batch)} commits (total: {len(commits)})")

        continuation_token = response.headers.get("x-ms-continuationtoken")
        if not continuation_token:
            break

        page += 1
        time.sleep(0.2)  # pequeño respiro por si hay rate limiting

    return commits


# ---------------------------------------------------
# Worker para comparar UNA rama en paralelo (con alias)
# ---------------------------------------------------
def _compare_one_branch(azure_repo_id, gh_owner, gh_repo, az_branch, gh_branch, label):
    try:
        # Sesión propia por hilo para GitHub (reusa keep-alive dentro del hilo)
        gh_sess = requests.Session()

        azure_commits = set(get_azure_commits(azure_repo_id, az_branch))
        github_commits = set(get_github_commits(gh_owner, gh_repo, gh_branch, session=gh_sess))

        missing_in_github = sorted(azure_commits - github_commits)
        extra_in_github = sorted(github_commits - azure_commits)
        shared_commits = sorted(azure_commits & github_commits)

        log_lines = [
            f"🔁 Branch: {label}",
            f"   ✔ Commits comunes: {len(shared_commits)}"
        ]
        if missing_in_github:
            log_lines.append(f"   ❌ Faltan en GitHub: {len(missing_in_github)}")
        if extra_in_github:
            log_lines.append(f"   ⚠️ Extras en GitHub (no en Azure): {len(extra_in_github)}")

        return {
            "ok": True,
            "log": "\n".join(log_lines),
            "result": {
                "branch": label,  # p.ej. "master → main" o "main → master" o "dev"
                "shared_commits": shared_commits,
                "missing_in_github": missing_in_github,
                "extra_in_github": extra_in_github
            }
        }
    except Exception as e:
        return {"ok": False, "log": f"⚠️ Error al comparar branch {label}: {e}"}


def test_commit_comparison(matched_repos):
    print("\n🔍 Comparando commits entre Azure y GitHub...")

    report = []

    # Cargar pares de ramas (con alias master<->main) por repo
    branch_pairs_dict = load_branch_pairs()

    for pair in matched_repos:
        azure_repo = pair["azure"]
        github_repo = pair["github"]
        azure_id = azure_repo["repo_id"]
        repo_name = azure_repo["repo_name"]

        print(f"\n📦 Repositorio: {repo_name}")
        branch_pairs = branch_pairs_dict.get(repo_name, [])

        if not branch_pairs:
            print("⚠️  No hay ramas emparejadas para commits (considerando alias). Se omite.")
            continue

        repo_result = {
            "repo": repo_name,
            "branches": []
        }

        # --------------------------------------------------------
        # Paralelismo por rama (usa pares az/gh)
        # --------------------------------------------------------
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = [
                ex.submit(
                    _compare_one_branch,
                    azure_id,
                    github_repo["owner"],
                    github_repo["repo"],
                    az_branch,
                    gh_branch,
                    label
                )
                for (az_branch, gh_branch, label) in branch_pairs
            ]

            for fut in as_completed(futures):
                res = fut.result()
                print(res["log"])
                if res.get("ok") and res.get("result"):
                    repo_result["branches"].append(res["result"])

        report.append(repo_result)

    # Guardar reporte en JSON
    os.makedirs("data", exist_ok=True)
    output_path = os.path.join("data", "commits_comparison.json")
    with open(output_path, "w") as f:
        json.dump(report, f, indent=4)

    print(f"\n📝 Reporte de comparación de commits guardado en: {output_path}")
