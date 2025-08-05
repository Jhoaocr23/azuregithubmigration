import os
import json
import pytest
from datetime import datetime 


# Paso 1: Ejecutar todos los tests
print("🚀 Ejecutando pruebas...")
pytest.main(["tests/test_repository.py", "-s"])
pytest.main(["tests/test_branches.py", "-s"])
pytest.main(["tests/test_commits.py", "-s"])
pytest.main(["tests/test_tags.py", "-s"])

# Paso 2: Cargar los archivos JSON
with open("data/repos_output.json") as f:
    repos_data = json.load(f)
with open("data/branches_comparison.json") as f:
    branches_data = json.load(f)
with open("data/commits_comparison.json") as f:
    commits_data = json.load(f)
with open("data/tags_comparison.json") as f:
    tags_data = json.load(f)

# Paso 3: Iniciar HTML
fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  
html = f"""
<html>
<head>
    <title>Reporte de Migración Azure DevOps → GitHub</title>
<style>
    body {{ font-family: Arial, sans-serif; padding: 20px; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 40px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background-color: #f2f2f2; }}
    tr:nth-child(even) {{ background-color: #f9f9f9; }}
    h2 {{ color: #333; }}
    .ok {{ color: green; font-weight: bold; }}
    .fail {{ color: red; font-weight: bold; }}
</style>

</head>
<body>
    <h1>📦 Reporte de Migración Azure DevOps → GitHub</h1>
    <p><strong>Responsable de la certificación:</strong> Jhoao Carranza</p>
    <p><strong>Fecha de ejecución:</strong> {fecha_hora}</p>
    <h2>🔁 Repositorios Emparejados <span style='font-weight:normal;'>(<b>{len(repos_data['matched'])}</b>)</span></h2>
    <table>
        <tr><th>Repositorio</th><th>Estado Branches</th><th>Estado Commits</th><th>Estado Tags</th></tr>
"""

# Paso 4: Repos emparejados
for repo in repos_data['matched']:
    repo_name = repo['azure']['repo_name']
    # Obtener detalles de cada test
    branches = next((b for b in branches_data if b['repo'] == repo_name), None)
    commits = next((c for c in commits_data if c['repo'] == repo_name), None)
    tags = next((t for t in tags_data if t['repo'] == repo_name), None)

    branches_status = "❌ Sin info"
    commits_status = "❌ Sin info"
    tags_status = "❌ Sin info"

    if branches:
        branches_status = "<span class='ok'>✔ Completos</span>" if not branches["only_in_azure"] and not branches["only_in_github"] else "<span class='fail'>⚠ Incompletos</span>"
    if commits:
        commits_status = "<span class='ok'>✔ Coinciden</span>" if all(len(b["missing_in_github"]) == 0 and len(b["extra_in_github"]) == 0 for b in commits["branches"]) else "<span class='fail'>❌ Diferencias</span>"
    if tags:
        tags_status = "<span class='ok'>✔ Tags iguales</span>" if not tags["only_in_azure"] and not tags["only_in_github"] else "<span class='fail'>❌ Faltan tags</span>"

    html += f"<tr><td>{repo_name}</td><td>{branches_status}</td><td>{commits_status}</td><td>{tags_status}</td></tr>"

html += "</table>"

# Paso 5: Repos NO emparejados
html += f"<h2>❌ Repos no emparejados</h2>"
html += f"<p><strong>Total en Azure (no emparejados):</strong> {len(repos_data['only_in_azure'])}</p>"
html += f"<p><strong>Total en GitHub (no emparejados):</strong> {len(repos_data['only_in_github'])}</p>"

if repos_data['only_in_azure']:
    html += "<h3>📁 Solo en Azure:</h3><ul>"
    for r in repos_data['only_in_azure']:
        html += f"<li>{r['repo_name']}</li>"
    html += "</ul>"

if repos_data['only_in_github']:
    html += "<h3>🐙 Solo en GitHub:</h3><ul>"
    for r in repos_data['only_in_github']:
        html += f"<li>{r['repo']}</li>"
    html += "</ul>"

# Paso 6: Detalle por repo
html += "<h2>📄 Detalles por Repositorio</h2>"
for repo in repos_data["matched"]:
    name = repo["azure"]["repo_name"]
    html += f"<h3>{name}</h3>"

    # Branches
    b = next((x for x in branches_data if x["repo"] == name), None)
    if b:
        azure_br = ", ".join(b["azure_branches"])
        github_br = ", ".join(b["github_branches"])
        shared_br = ", ".join(b["shared_branches"])
        only_az = ", ".join(b["only_in_azure"]) or "—"
        only_gh = ", ".join(b["only_in_github"]) or "—"
        html += f"""
        <table>
            <tr><th>Branches en Azure</th><th>Branches en GitHub</th><th>Comunes</th><th>Solo Azure</th><th>Solo GitHub</th></tr>
            <tr><td>{azure_br}</td><td>{github_br}</td><td>{shared_br}</td><td>{only_az}</td><td>{only_gh}</td></tr>
        </table>
        """

    # Commits
    c = next((x for x in commits_data if x["repo"] == name), None)
    if c:
        html += """
        <table>
            <tr><th>Branch</th><th>Commits comunes</th><th>Faltan en GitHub</th><th>Extras en GitHub</th></tr>
        """
        for br in c["branches"]:
            html += f"<tr><td>{br['branch']}</td><td>{len(br['shared_commits'])}</td><td>{len(br['missing_in_github'])}</td><td>{len(br['extra_in_github'])}</td></tr>"
        html += "</table>"

    # Tags
    t = next((x for x in tags_data if x["repo"] == name), None)
    if t:
        shared = ", ".join(t["shared_tags"]) or "—"
        azure_only = ", ".join(t["only_in_azure"]) or "—"
        github_only = ", ".join(t["only_in_github"]) or "—"
        html += f"""
        <table>
            <tr><th>Tags Azure</th><th>Tags GitHub</th><th>Comunes</th><th>Faltantes</th></tr>
            <tr>
                <td>{", ".join(t["azure_tags"]) or "—"}</td>
                <td>{", ".join(t["github_tags"]) or "—"}</td>
                <td>{shared}</td>
                <td>{azure_only if azure_only != "—" else github_only}</td>
            </tr>
        </table>
        """

html += "</body></html>"

# Paso 7: Guardar el reporte
os.makedirs("reports", exist_ok=True)
with open("reports/final_report.html", "w") as f:
    f.write(html)

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
