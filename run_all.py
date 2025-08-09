import os
import json
import shutil
import pytest
from datetime import datetime

# === helpers para listas con viñetas ===
def _ul(items):
    if not items:
        return "—"
    return "<ul class='clean'>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>"

def _ul_with_icon(items, icon=""):
    if not items:
        return "—"
    prefix = f"{icon} " if icon else ""
    return "<ul class='clean'>" + "".join(f"<li>{prefix}{x}</li>" for x in items) + "</ul>"

# === INICIO: función para HTML de detalle individual ===
def renderiza_detalle_repo_html(repo_name, branches, commits, tags, workflows=None):
    detalle_html = f"""
    <html>
    <head>
        <title>Detalle de Migración: {repo_name}</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <style>
            /* ---------- Base (detalle) ---------- */
            :root{{
              --ok:#2e7d32; --ok-bg:#e8f5e9;
              --warn:#b26a00; --warn-bg:#fff8e1;
              --fail:#c62828; --fail-bg:#ffebee;
              --ink:#111827; --muted:#6b7280;
              --border:#e5e7eb; --surface:#ffffff; --surface-2:#f9fafb;
              --accent:#2563eb;
            }}
            html,body{{ margin:0; padding:0; }}
            body {{ font-family: Inter, Roboto, Segoe UI, Arial, sans-serif; color:var(--ink); background:#f6f7fb; padding:24px; line-height:1.35; }}

            /* Encabezado del detalle */
            .d-header{{ display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:14px; }}
            .d-left{{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }}
            .d-title{{ margin:0; font-size:26px; font-weight:900; letter-spacing:.2px; }}
            .d-octocat{{ height:66px; width:auto; filter: drop-shadow(0 1px 0 rgba(0,0,0,.05)); }}
            .back-link{{ color:#1d4ed8; text-decoration:none; font-weight:600; }}
            .back-link:hover{{ text-decoration:underline; }}

            table{{ width:100%; border-collapse:separate; border-spacing:0; background:var(--surface); border:1px solid var(--border); border-radius:12px; overflow:hidden; box-shadow:0 1px 2px rgba(0,0,0,.04); margin-bottom:28px; }}
            th, td {{ padding:12px 14px; text-align:left; vertical-align: top; }}
            th {{ background:#eef2ff; color:#111827; font-weight:700; border-bottom:1px solid var(--border); }}
            td {{ border-top:1px solid var(--border); }}
            tr:nth-child(even) td{{ background:var(--surface-2); }}

            .ok{{ color:var(--ok); font-weight:700; background:var(--ok-bg); padding:4px 8px; border-radius:999px; border:1px solid #a5d6a7; display:inline-block; }}
            .fail{{ color:var(--fail); font-weight:700; background:var(--fail-bg); padding:4px 8px; border-radius:999px; border:1px solid #ef9a9a; display:inline-block; }}
            .warn{{ color:var(--warn); font-weight:700; background:var(--warn-bg); padding:4px 8px; border-radius:999px; border:1px solid #ffe082; display:inline-block; }}

            ul.clean {{ margin:0; padding-left:18px; }}
            ul.clean li {{ margin:4px 0; }}

            a{{ color:#1d4ed8; text-decoration:none; font-weight:600; }}
            a:hover{{ text-decoration:underline; }}

            @media (max-width: 840px){{
              th, td{{ padding:10px 12px; font-size:14px; }}
              .d-title{{ font-size:22px; }}
              .d-octocat{{ height:58px; }}
            }}
        </style>
    </head>
    <body>
        <div class="d-header">
          <div class="d-left">
            <a class="back-link" href="../final_report.html">⬅ Volver al reporte principal</a>
            <h1 class="d-title">📄 Detalle de migración: {repo_name}</h1>
          </div>
          <img src="../assets/octocat.png" alt="GitHub Octocat" class="d-octocat">
        </div>
    """
    # -------- Branches --------
    if branches:
        azure_br_ul = _ul(branches["azure_branches"])
        github_br_ul = _ul(branches["github_branches"])
        shared_br_ul = _ul(branches["shared_branches"])
        only_az_ul = _ul(branches["only_in_azure"])
        only_gh_ul = _ul(branches["only_in_github"])
        branches_ok = (not branches["only_in_azure"] and not branches["only_in_github"])
        branches_estado = "<span class='ok'>✔ Completos</span>" if branches_ok else "<span class='fail'>⚠ Incompletos</span>"
        detalle_html += f"""
        <table>
            <tr><th>Branches en Azure</th><th>Branches en GitHub</th><th>Comunes</th><th>Solo Azure</th><th>Solo GitHub</th><th>Estado</th></tr>
            <tr><td>{azure_br_ul}</td><td>{github_br_ul}</td><td>{shared_br_ul}</td><td>{only_az_ul}</td><td>{only_gh_ul}</td><td>{branches_estado}</td></tr>
        </table>
        """

    # -------- Commits --------
    if commits:
        detalle_html += """
        <table>
            <tr><th>Branch</th><th>Commits comunes</th><th>Faltan en GitHub</th><th>Extras en GitHub</th><th>Estado</th></tr>
        """
        for br in commits["branches"]:
            per_branch_ok = (len(br["missing_in_github"]) == 0 and len(br["extra_in_github"]) == 0)
            per_branch_estado = "<span class='ok'>✔ Coinciden</span>" if per_branch_ok else "<span class='fail'>❌ Diferencias</span>"
            detalle_html += (
                f"<tr>"
                f"<td>{br['branch']}</td>"
                f"<td>{len(br['shared_commits'])}</td>"
                f"<td>{len(br['missing_in_github'])}</td>"
                f"<td>{len(br['extra_in_github'])}</td>"
                f"<td>{per_branch_estado}</td>"
                f"</tr>"
            )
        detalle_html += "</table>"

    # -------- Tags --------
    if tags:
        azure_tags_ul = _ul(tags["azure_tags"])
        github_tags_ul = _ul(tags["github_tags"])
        shared_ul = _ul(tags["shared_tags"])
        faltantes_ul = _ul(tags["only_in_azure"] if tags["only_in_azure"] else tags["only_in_github"])
        tags_ok = (not tags["only_in_azure"] and not tags["only_in_github"])
        tags_estado = "<span class='ok'>✔ Tags iguales</span>" if tags_ok else "<span class='fail'>❌ Faltan tags</span>"
        detalle_html += f"""
        <table>
            <tr><th>Tags Azure</th><th>Tags GitHub</th><th>Comunes</th><th>Faltantes</th><th>Estado</th></tr>
            <tr>
                <td>{azure_tags_ul}</td>
                <td>{github_tags_ul}</td>
                <td>{shared_ul}</td>
                <td>{faltantes_ul}</td>
                <td>{tags_estado}</td>
            </tr>
        </table>
        """

    # -------- Workflows --------
    detalle_html += """
    <h2>Workflows</h2>
    <table>
        <tr><th>Directorio existe</th><th>Archivos presentes</th><th>Faltantes</th><th>Estado</th></tr>
    """
    if workflows:
        estado = "<span class='ok'>OK</span>" if workflows.get("ok") else "<span class='fail'>Faltan archivos</span>"
        presentes_list = workflows.get("present_files", [])
        faltantes_list = workflows.get("missing_files", [])
        presentes_html = _ul(presentes_list)
        faltantes_html = _ul_with_icon(faltantes_list, icon="❌")
        dir_existe = "Sí" if workflows.get("workflow_dir_exists") else "No"
        detalle_html += f"<tr><td>{dir_existe}</td><td>{presentes_html}</td><td>{faltantes_html}</td><td>{estado}</td></tr>"
        detalle_html += "</table>"
    else:
        detalle_html += "<tr><td colspan='4'>Sin información</td></tr></table>"

    detalle_html += "</body></html>"
    return detalle_html
# === FIN detalle ===

# Paso 0: Copiar assets a reports/assets (para que las imágenes siempre se vean)
src_assets = os.path.join("assets")
dst_assets = os.path.join("reports", "assets")
if os.path.isdir(src_assets):
    os.makedirs("reports", exist_ok=True)
    # reemplazar si ya existe
    if os.path.isdir(dst_assets):
        shutil.rmtree(dst_assets)
    shutil.copytree(src_assets, dst_assets)

# Paso 1: Ejecutar todos los tests
print("🚀 Ejecutando pruebas...")
pytest.main(["tests/test_repository.py", "-s"])
pytest.main(["tests/test_branches.py", "-s"])
pytest.main(["tests/test_commits.py", "-s"])
pytest.main(["tests/test_tags.py", "-s"])
pytest.main(["tests/test_workflows.py", "-s"])

# Paso 2: Cargar JSONs
with open("data/repos_output.json") as f:
    repos_data = json.load(f)
with open("data/branches_comparison.json") as f:
    branches_data = json.load(f)
with open("data/commits_comparison.json") as f:
    commits_data = json.load(f)
with open("data/tags_comparison.json") as f:
    tags_data = json.load(f)
with open("data/workflows_check.json", "r") as f:
    workflows_data = json.load(f)

# Paso 3: Iniciar HTML principal
fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
html = f"""
<html>
<head>
    <title>Reporte de Migración Azure DevOps → GitHub</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  /* ---------- Base (principal) ---------- */
  :root{{
    --ok:#2e7d32; --ok-bg:#e8f5e9;
    --fail:#c62828; --fail-bg:#ffebee;
    --ink:#111827; --muted:#6b7280;
    --border:#e5e7eb; --surface:#ffffff; --surface-2:#f9fafb;
    --accent:#2563eb;
  }}
  html,body{{ margin:0; padding:0; }}
  body {{
    font-family: Inter, Roboto, Segoe UI, Arial, sans-serif;
    color: var(--ink);
    background: #f6f7fb;
    padding: 24px;
    line-height: 1.35;
  }}

  /* ---------- HERO HEADER centrado ---------- */
  .hero{{ display:flex; flex-direction:column; align-items:center; gap:10px; margin: 4px 0 12px; text-align:center; }}
  .hero-title{{ margin:0; font-size:36px; font-weight:900; letter-spacing:.2px; display:flex; align-items:center; gap:12px; }}
  .hero-sub{{ margin:0; font-size:18px; color:#4b5563; }}
  .hero-sub b{{ color:#1f2937; }}
  .octocat-inline{{ height:74px; width:auto; filter: drop-shadow(0 1px 0 rgba(0,0,0,.05)); }}

  /* Header con buscador */
  .header-flex {{
    display:flex; align-items:center; justify-content:space-between;
    gap:16px; margin: 16px 0 14px;
  }}
  .buscador-repo {{
    width: 360px; max-width: 50vw;
    padding: 10px 12px; font-size: 15px;
    border: 1.5px solid var(--accent); border-radius: 10px;
    outline: none; background: #fff; color: var(--ink);
    box-shadow: 0 1px 0 rgba(0,0,0,.02), inset 0 1px 1px rgba(0,0,0,.04);
  }}
  .buscador-repo:focus {{ box-shadow: 0 0 0 4px rgba(37,99,235,.15); }}

  /* Tabla principal */
  table{{
    width:100%;
    border-collapse:separate; border-spacing:0;
    background: var(--surface);
    border:1px solid var(--border);
    border-radius: 12px;
    overflow:hidden;
    box-shadow: 0 1px 2px rgba(0,0,0,.04);
    margin-bottom: 28px;
  }}
  th, td{{ padding: 12px 14px; text-align:left; vertical-align: top; }}
  th{{
    background: #eef2ff;
    color:#111827;
    font-weight:700;
    border-bottom:1px solid var(--border);
    position: sticky; top: 0; z-index: 1;
  }}
  td{{ border-top:1px solid var(--border); }}
  tr:nth-child(even) td{{ background: var(--surface-2); }}
  tr:hover td{{ background:#f1f5f9; }}

  .ok{{
    color: var(--ok); font-weight:700;
    background: var(--ok-bg); padding:4px 8px; border-radius:999px;
    border:1px solid #a5d6a7; display:inline-block;
  }}
  .fail{{
    color: var(--fail); font-weight:700;
    background: var(--fail-bg); padding:4px 8px; border-radius:999px;
    border:1px solid #ef9a9a; display:inline-block;
  }}

  ul.clean{{ margin:0; padding-left: 18px; }}
  ul.clean li{{ margin: 4px 0; }}

  a{{ color: #1d4ed8; text-decoration: none; font-weight:600; }}
  a:hover{{ text-decoration: underline; }}

  /* ===== Repos no emparejados - UI mejorada ===== */
  .section-title{{ display:flex; align-items:center; gap:10px; margin-top: 22px; }}
  .stat-chips{{ display:flex; gap:10px; flex-wrap:wrap; margin: 6px 0 14px; }}
  .chip{{
    display:inline-flex; align-items:center; gap:6px;
    padding:6px 10px; border-radius:999px; background:#eef2ff;
    border:1px solid var(--border); font-weight:600; color:#1f2937;
  }}
  .grid-2{{ display:grid; grid-template-columns: 1fr 1fr; gap:16px; }}
  @media (max-width: 840px){{ .grid-2 {{ grid-template-columns: 1fr; }} }}
  .panel{{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    box-shadow: 0 1px 2px rgba(0,0,0,.04);
    overflow: hidden;
  }}
  .panel-header{{
    background: #eef2ff;
    border-bottom: 1px solid var(--border);
    padding: 10px 14px;
    display:flex; align-items:center; justify-content:space-between; gap:10px;
  }}
  .panel-title{{ display:flex; align-items:center; gap:10px; font-weight:800; color:#111827; }}
  .count-pill{{ background:#f3f4f6; border:1px solid var(--border); padding:4px 10px; border-radius:999px; font-weight:700; color:#374151; }}
  .panel-body {{ padding: 12px 14px; }}
  ul.tidy {{ margin:0; padding-left: 18px; max-height: 320px; overflow:auto; }}
  ul.tidy li {{ margin:6px 0; }}
  .empty {{ color: var(--muted); font-style: italic; padding: 8px 0 2px; }}

  @media (max-width: 840px){{
    .buscador-repo{{ width: 100%; max-width: 100%; }}
    th, td{{ padding: 10px 12px; font-size: 14px; }}
    .hero-title{{ font-size:28px; }}
    .hero-sub{{ font-size:16px; }}
    .octocat-inline{{ height:64px; }}
  }}
</style>

</head>
<body>

    <!-- HERO HEADER centrado -->
    <div class="hero">
      <h1 class="hero-title">
        📦 Reporte de Migración Azure DevOps → GitHub
        <img src="assets/octocat.png" alt="GitHub Octocat" class="octocat-inline">
      </h1>
      <p class="hero-sub"><b>Responsable de la certificación:</b> Jhoao Carranza</p>
      <p class="hero-sub"><b>Fecha de ejecución:</b> {fecha_hora}</p>
    </div>

    <!-- Encabezado de tabla + buscador -->
    <div class="header-flex">
        <h2 style="margin: 0;">🔁 Repositorios Emparejados <span style='font-weight:normal;'>(<b>{len(repos_data['matched'])}</b>)</span></h2>
        <input type="text" id="buscadorRepo" onkeyup="filtrarRepos()" placeholder="🔎 Buscar repositorio..." class="buscador-repo">
    </div>

    <table>
        <tr><th>Repositorio</th><th>Estado Branches</th><th>Estado Commits</th><th>Estado Tags</th><th>Workflows</th></tr>
"""

# Paso 4: Repos emparejados
for repo in repos_data['matched']:
    repo_name = repo['azure']['repo_name']
    gh_repo_name = repo.get('github', {}).get('repo')  # para cruzar con workflows

    branches = next((b for b in branches_data if b['repo'] == repo_name), None)
    commits = next((c for c in commits_data if c['repo'] == repo_name), None)
    tags = next((t for t in tags_data if t['repo'] == repo_name), None)
    wf = next((w for w in workflows_data if w.get("repo") == gh_repo_name or w.get("repo") == repo_name), None)

    branches_status = "❌ Sin info"
    commits_status = "❌ Sin info"
    tags_status = "❌ Sin info"
    workflows_status = "❌ Sin info"

    if branches:
        branches_status = "<span class='ok'>✔ Completos</span>" if not branches["only_in_azure"] and not branches["only_in_github"] else "<span class='fail'>⚠ Incompletos</span>"
    if commits:
        commits_status = "<span class='ok'>✔ Coinciden</span>" if all(len(b["missing_in_github"]) == 0 and len(b["extra_in_github"]) == 0 for b in commits["branches"]) else "<span class='fail'>❌ Diferencias</span>"
    if tags:
        tags_status = "<span class='ok'>✔ Tags iguales</span>" if not tags["only_in_azure"] and not tags["only_in_github"] else "<span class='fail'>❌ Faltan tags</span>"
    if wf:
        if wf.get("ok"):
            workflows_status = "<span class='ok'>✔ Requeridos OK</span>"
        elif not wf.get("workflow_dir_exists"):
            workflows_status = "<span class='fail'>❌ Falta .github/workflows</span>"
        else:
            workflows_status = "<span class='fail'>❌ Faltan archivos</span>"

    html += f"<tr><td><a href='detalles/{repo_name}.html'>{repo_name}</a></td><td>{branches_status}</td><td>{commits_status}</td><td>{tags_status}</td><td>{workflows_status}</td></tr>"

html += "</table>"

# Paso 5: Repos NO emparejados (UI mejorada)
total_az = len(repos_data['only_in_azure'])
total_gh = len(repos_data['only_in_github'])

html += f"""
<h2 class="section-title">❌ Repos no emparejados</h2>
<div class="stat-chips">
  <span class="chip">📁 Total en Azure: <strong>{total_az}</strong></span>
  <span class="chip">🐙 Total en GitHub: <strong>{total_gh}</strong></span>
</div>

<div class="grid-2">
  <!-- Card: Solo en Azure -->
  <div class="panel">
    <div class="panel-header">
      <div class="panel-title">📁 Solo en Azure</div>
      <div class="count-pill">{total_az}</div>
    </div>
    <div class="panel-body">
"""

if total_az:
    html += "<ul class='tidy'>"
    for r in repos_data['only_in_azure']:
        html += f"<li>{r['repo_name']}</li>"
    html += "</ul>"
else:
    html += "<div class='empty'>No hay repositorios únicamente en Azure.</div>"

html += """
    </div>
  </div>

  <!-- Card: Solo en GitHub -->
  <div class="panel">
    <div class="panel-header">
      <div class="panel-title">🐙 Solo en GitHub</div>
      <div class="count-pill">""" + str(total_gh) + """</div>
    </div>
    <div class="panel-body">
"""

if total_gh:
    html += "<ul class='tidy'>"
    for r in repos_data['only_in_github']:
        html += f"<li>{r['repo']}</li>"
    html += "</ul>"
else:
    html += "<div class='empty'>No hay repositorios únicamente en GitHub.</div>"

html += """
    </div>
  </div>
</div>  <!-- .grid-2 -->
"""

# === JS buscador ===
html += """
<script>
function filtrarRepos() {
  const input = document.getElementById("buscadorRepo");
  const filtro = input.value.toLowerCase();
  const tabla = document.querySelector("table");
  const filas = tabla.getElementsByTagName("tr");
  for (let i = 1; i < filas.length; i++) {
    const td = filas[i].getElementsByTagName("td")[0];
    if (td) {
      const txt = td.textContent || td.innerText;
      filas[i].style.display = txt.toLowerCase().indexOf(filtro) > -1 ? "" : "none";
    }
  }
}
</script>
"""

html += "</body></html>"

# Paso 7: Guardar el reporte
os.makedirs("reports", exist_ok=True)
with open("reports/final_report.html", "w") as f:
    f.write(html)

# === Generación de reportes individuales ===
os.makedirs("reports/detalles", exist_ok=True)
for repo in repos_data['matched']:
    repo_name = repo['azure']['repo_name']
    gh_repo_name = repo.get('github', {}).get('repo')

    branches = next((b for b in branches_data if b['repo'] == repo_name), None)
    commits = next((c for c in commits_data if c['repo'] == repo_name), None)
    tags = next((t for t in tags_data if t['repo'] == repo_name), None)
    wf_detalle = next((w for w in workflows_data if w.get("repo") == gh_repo_name or w.get("repo") == repo_name), None)

    detalle_html = renderiza_detalle_repo_html(repo_name, branches, commits, tags, workflows=wf_detalle)
    with open(f"reports/detalles/{repo_name}.html", "w") as f:
        f.write(detalle_html)

print("📄 Reporte HTML generado: reports/final_report.html")
from colorama import init, Fore, Style
init(autoreset=True)

print(Fore.CYAN + Style.BRIGHT + r"""
 ____  ____  ____  ____  ____  ____    ____  _  _      __  _  _   __    __    __  
(_  _)(  __)/ ___)(_  _)(  __)(    \  (  _ \( \/ )   _(  )/ )( \ /  \  / _\  /  \ 
  )(   ) _) \___ \  )(   ) _)  ) D (   ) _ ( )  /   / \) \) __ ((  O )/    \(  O )
 (__) (____)(____/ (__) (____)(____/  (____/(__/    \____/\_)(_/ \__/ \_/\_/ \__/  
""")

print(Fore.MAGENTA + Style.BRIGHT + "                                🚀 Tested by Jhoao\n")
