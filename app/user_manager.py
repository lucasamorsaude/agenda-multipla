# app/user_manager.py
import json
import os

USERS_FILE = 'users.json' # Garante que o caminho é relativo à raiz do projeto

def load_users():
    """Carrega os usuários do arquivo JSON com codificação UTF-8."""
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Se o arquivo não existe ou está vazio, retorna um dicionário vazio
        return {}

def save_users(users_data):
    """Salva os dados dos usuários no arquivo JSON com codificação UTF-8."""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        # indent=4 para o arquivo ficar legível
        # ensure_ascii=False para salvar acentos corretamente
        json.dump(users_data, f, indent=4, ensure_ascii=False)