# tests/test_connection.py

import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Configuración
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_OWNER = os.getenv("GITHUB_OWNER")
GITHUB_REPO = os.getenv("GITHUB_REPO")
AZURE_TOKEN = os.getenv("AZURE_TOKEN")
AZURE_ORG = os.getenv("AZURE_ORG")
AZURE_PROJECT = os.getenv("AZURE_PROJECT")
AZURE_REPO_ID = os.getenv("AZURE_REPO_ID")

def get_github_repo():
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    return requests.get(url, headers=headers)

def get_azure_repo():
    url = f"https://dev.azure.com/{AZURE_ORG}/{AZURE_PROJECT}/_apis/git/repositories/{AZURE_REPO_ID}?api-version=7.0"
    return requests.get(url, auth=("", AZURE_TOKEN))

def test_check_github_connection():
    print("\n✅ GitHub:")
    response = get_github_repo()
    assert response.status_code == 200, f"Error GitHub {response.status_code}: {response.text}"
    print(f"  - Repositorio encontrado: {response.json().get('full_name')}")

def test_check_azure_connection():
    print("\n✅ Azure DevOps:")
    response = get_azure_repo()
    assert response.status_code == 200, f"Error Azure DevOps {response.status_code}: {response.text}"
    print(f"  - Repositorio encontrado: {response.json().get('name')}")
