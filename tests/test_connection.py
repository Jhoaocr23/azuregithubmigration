import requests
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GITHUB_TOKEN, GITHUB_OWNER, AZURE_TOKEN, AZURE_ORG, AZURE_PROJECT

def test_check_github_connection():
    print("\n🔌 Verificando conexión con GitHub...")
    url = "https://api.github.com/user"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    response = requests.get(url, headers=headers)
    assert response.status_code == 200, f"❌ GitHub: {response.status_code} - {response.text}"
    print(f"✅ GitHub conectado como: {response.json()['login']}")

def test_check_azure_connection():
    print("\n🔌 Verificando conexión con Azure DevOps...")
    url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories?api-version=7.0"
    response = requests.get(url, auth=("", AZURE_TOKEN))
    assert response.status_code == 200, f"❌ Azure DevOps: {response.status_code} - {response.text}"
    print(f"✅ Azure DevOps conectado - Repos encontrados: {len(response.json()['value'])}")
