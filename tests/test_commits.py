import sys
import os
import time  # <--- NUEVO
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
from config import GITHUB_TOKEN, AZURE_TOKEN, AZURE_ORG, AZURE_PROJECT

# ---------------------------
# 👇 NUEVO: imports y config
# ---------------------------
from concurrent.futures import ThreadPoolExecutor, as_completed  # <--- NUEVO
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "12"))  # <--- NUEVO (ajusta 8–24 según tu token)


def get_github_commits(owner, repo, branch, session=None):  # <--- MOD: acepta session opcional
    commits = []
    page = 1
    s = session or requests.Session()  # <--- NUEVO: reusa conexión si te paso una sesión
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/commits?sha={branch}&per_page=100&page={page}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        response = s.get(url, headers=headers)  # <--- MOD: usa la sesión (o requests.Session temporal)
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
        "$top": 5000,                 # pides hasta 5000 por página
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


def load_shared_branches():
    """
    Lee el archivo branches_comparison.json y devuelve un dict:
    { repo_name: [branch1, branch2, ...] }
    """
    with open("data/branches_comparison.json") as f:
        branches_data = json.load(f)
    return {r["repo"]: r["shared_branches"] for r in branches_data}


# ---------------------------------------------------
# 👇 NUEVO: worker para comparar UNA rama en paralelo
# ---------------------------------------------------
def _compare_one_branch(azure_repo_id, gh_owner, gh_repo, branch):
    try:
        # Sesión propia por hilo para GitHub (reusa keep-alive dentro del hilo)
        gh_sess = requests.Session()

        azure_commits = set(get_azure_commits(azure_repo_id, branch))
        github_commits = set(get_github_commits(gh_owner, gh_repo, branch, session=gh_sess))

        missing_in_github = sorted(azure_commits - github_commits)
        extra_in_github = sorted(github_commits - azure_commits)
        shared_commits = sorted(azure_commits & github_commits)

        log_lines = [
            f"🔁 Branch: {branch}",
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
                "branch": branch,
                "shared_commits": shared_commits,
                "missing_in_github": missing_in_github,
                "extra_in_github": extra_in_github
            }
        }
    except Exception as e:
        return {"ok": False, "log": f"⚠️ Error al comparar branch {branch}: {e}"}


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

        # --------------------------------------------------------
        # 👇 NUEVO: paralelismo por rama (reemplaza tu for actual)
        # --------------------------------------------------------
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = [
                ex.submit(
                    _compare_one_branch,
                    azure_id,
                    github_repo["owner"],
                    github_repo["repo"],
                    branch
                )
                for branch in shared_branches
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
