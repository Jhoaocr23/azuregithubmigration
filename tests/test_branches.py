# tests/test_branches.py

import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json
from urllib.parse import urlparse, parse_qs
from config import GITHUB_TOKEN, AZURE_TOKEN, AZURE_ORG, AZURE_PROJECT

# Imports y control de hilos ======
from concurrent.futures import ThreadPoolExecutor, as_completed  
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "12"))  

def _normalize_branch_name_from_azure_to_github(name: str) -> str:
    # Azure a veces tiene 'master'; en GitHub usamos 'main'
    return "main" if name == "master" else name



def _parse_next_link(link_header: str):
    """
    Devuelve la URL de 'next' desde el header Link de GitHub, o None si no hay más páginas.
    """
    if not link_header:
        return None
    parts = [p.strip() for p in link_header.split(",")]
    for p in parts:
        segs = p.split(";")
        if len(segs) < 2:
            continue
        url = segs[0].strip()
        rel = segs[1].strip()
        if rel == 'rel="next"':
            # <https://api.github.com/...>; rel="next"
            return url.strip("<>")
    return None


def get_github_branches(repo_owner, repo_name):
   
    session = requests.Session()
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    all_refs = set()

   
    page_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/git/refs/heads"
    page = 1
    while page_url:
        resp = session.get(page_url, headers=headers, timeout=60)
        # Si el repo no tiene refs todavía, GitHub puede devolver 404 o 422. Lo toleramos.
        if resp.status_code in (404, 422):
            print(f"⚠️  [GITHUB-refs] {resp.status_code} en {page_url}. Continuando con respaldo /branches…")
            break
        resp.raise_for_status()

        data = resp.json()
        # /git/refs/heads puede devolver un objeto (si hay 1) o una lista (lo normal)
        if isinstance(data, dict):
            data = [data]

        batch = []
        for ref in data:
            # ref['ref'] = 'refs/heads/<branch name>'
            ref_name = ref.get("ref", "")
            if ref_name.startswith("refs/heads/"):
                b = ref_name.replace("refs/heads/", "", 1)
                if b not in all_refs:
                    all_refs.add(b)
                    batch.append(b)

        print(f"🔎 [GITHUB-refs] Página {page}: {len(batch)} branches (total: {len(all_refs)})")

        next_url = _parse_next_link(resp.headers.get("Link"))
        page_url = next_url
        page += 1
        if page_url:
            time.sleep(0.15)

    # --- (B) Respaldo: endpoint de BRANCHES, por si algo quedó fuera
    branches_backup = set()
    page = 1
    while True:
        url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/branches"
        params = {"per_page": 100, "page": page}
        resp = session.get(url, headers=headers, params=params, timeout=60)

        if resp.status_code == 404:
            # repo inexistente o sin permiso
            print(f"⚠️  [GITHUB-branches] 404 para {repo_owner}/{repo_name}.")
            break

        resp.raise_for_status()
        data = resp.json()
        if not data:
            break

        batch = [b.get("name", "") for b in data if b.get("name")]
        branches_backup.update(batch)
        print(f"🔎 [GITHUB-branches] Página {page}: {len(batch)} (respaldo total: {len(branches_backup)})")

        # paginación por longitud
        if len(data) < 100:
            break
        page += 1
        time.sleep(0.15)

    # Unión de ambos métodos
    union = all_refs | branches_backup
    return sorted(union)


def get_azure_branches(repo_id):
    """
    Lista TODAS las branches (refs/heads/*) de Azure DevOps usando 7.2-preview.2,
    $top=5000 y paginación via continuationToken (query param).
    """
    branches = []
    seen = set()
    continuation = None
    page = 1

    session = requests.Session()
    base = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{repo_id}/refs"

    params = {
        "filter": "heads/",
        "$top": 5000,
        "api-version": "7.2-preview.2",
    }
    headers = {"Accept": "application/json"}

    while True:
        if continuation:
            params["continuationToken"] = continuation
        else:
            params.pop("continuationToken", None)

        resp = session.get(
            base,
            auth=("", AZURE_TOKEN),
            params=params,
            headers=headers,
            timeout=60
        )
        resp.raise_for_status()

        data = resp.json()
        batch = []
        for ref in data.get("value", []):
            name = ref.get("name", "")
            if name.startswith("refs/heads/"):
                b = name.replace("refs/heads/", "", 1)
                if b not in seen:
                    seen.add(b)
                    branches.append(b)
                    batch.append(b)

        print(f"🔎 [AZURE] Página {page}: {len(batch)} branches (total: {len(branches)})")

        continuation = resp.headers.get("x-ms-continuationtoken")
        if not continuation:
            break

        page += 1
        time.sleep(0.2)

    return sorted(branches)


# ====== Wworker que procesa 1 repo emparejado ======
def _process_pair(pair):
    azure_repo = pair["azure"]
    github_repo = pair["github"]

    azure_name = azure_repo["repo_name"]
    github_name = github_repo["repo"]

    try:
        # 1) Traer ramas
        azure_branches_raw = set(get_azure_branches(azure_repo["repo_id"]))
        github_branches = set(get_github_branches(github_repo["owner"], github_name))

        # === INICIO CAMBIO: alias bidireccional main <-> master ===
        def _aliases(name: str):
            if name == "master":
                return {"master", "main"}
            if name == "main":
                return {"main", "master"}
            return {name}

        # Faltantes en GitHub: ninguna de sus variantes aparece en GitHub
        def _covered_in_github(az_b: str) -> bool:
            return len(_aliases(az_b) & github_branches) > 0

        only_in_azure = sorted([b for b in azure_branches_raw if not _covered_in_github(b)])

        # Extras en GitHub: no están cubiertas por ninguna rama de Azure (considerando alias)
        azure_cover = set()
        for b in azure_branches_raw:
            azure_cover |= _aliases(b)
        only_in_github = sorted([g for g in github_branches if g not in azure_cover])

        # Comunes exactas (idénticas por nombre) — informativo
        shared = sorted(azure_branches_raw & github_branches)
        # === FIN CAMBIO ===

        # 5) Log claro
        log_lines = [
            f"\n📦 Repositorio emparejado: {azure_name} ↔ {github_name}",
            f"🔁 Branches en Azure (alias main/master considerados): {sorted(azure_branches_raw)}",
            f"🔁 Branches en GitHub:                                  {sorted(github_branches)}",
            f"✅ Branches comunes (idénticas):                        {shared}",
        ]
        if only_in_azure:
            log_lines.append(f"❌ Faltan en GitHub (obligatorias): {only_in_azure}")
        if only_in_github:
            log_lines.append(f"ℹ️ Extras en GitHub (permitidas):   {only_in_github}")

        return {
            "log": "\n".join(log_lines),
            "entry": {
                "repo": azure_name,
                "azure_branches": sorted(list(azure_branches_raw)),  # crudas para mostrar
                "github_branches": sorted(list(github_branches)),
                "shared_branches": shared,       # EXACTAS (para commits/visual)
                "only_in_azure": only_in_azure,  # FALTANTES (con alias bidireccional)
                "only_in_github": only_in_github # EXTRAS (permitidas, con alias bidireccional)
            }
        }

    except Exception as e:
        return {
            "log": f"⚠️ Error al comparar branches para {azure_name}: {str(e)}",
            "entry": None
        }



def test_branch_comparison(matched_repos):
    print("\n🔍 Comparando branches entre Azure y GitHub...")
    
    report = []

    # ====== Paralelismo por repo emparejado ======
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = [ex.submit(_process_pair, pair) for pair in matched_repos]
        for fut in as_completed(futures):
            res = fut.result()
            print(res["log"])
            if res["entry"] is not None:
                report.append(res["entry"])

    # Guardar reporte en JSON
    os.makedirs("data", exist_ok=True)
    output_path = os.path.join("data", "branches_comparison.json")
    with open(output_path, "w") as f:
        json.dump(report, f, indent=4, ensure_ascii=False)

    print(f"\n📝 Reporte de comparación guardado en: {output_path}")
