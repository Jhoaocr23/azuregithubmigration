# tests/conftest.py

import pytest
import json
import os
 
@pytest.fixture(scope="session")
def matched_repos():
    """
    Fixture global que carga los repositorios emparejados
    desde el archivo repos_output.json generado por test_repository.py.
    """
    path = os.path.join("data", "repos_output.json")
    
    if not os.path.exists(path):
        raise FileNotFoundError("⚠️ No se encontró el archivo repos_output.json. Ejecuta primero test_repository.py")
    
    with open(path, "r") as f:
        data = json.load(f)

    matched = data.get("matched", [])

    if not matched:
        raise ValueError("⚠️ No hay repositorios emparejados en el archivo repos_output.json.")

    return matched
