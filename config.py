from dotenv import load_dotenv
import os

# Cargar variables del archivo .env
load_dotenv()

# GitHub
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_OWNER = os.getenv("GITHUB_OWNER")
GITHUB_REPO_NAME = os.getenv("GITHUB_REPO")
GITHUB_REPO = f"{GITHUB_OWNER}/{GITHUB_REPO_NAME}"  # Esto es lo que usará la API

# Azure DevOps
AZURE_TOKEN = os.getenv("AZURE_TOKEN")
AZURE_ORG = os.getenv("AZURE_ORG")
AZURE_PROJECT = os.getenv("AZURE_PROJECT")
AZURE_REPO = os.getenv("AZURE_REPO_ID")
