# migrate_users.py
import json
import firebase_admin
from firebase_admin import credentials, firestore
from werkzeug.security import generate_password_hash

# --- Bloco de Inicialização do Firebase ---
# (Garanta que seu app não esteja rodando ao executar este script para evitar conflito)
try:
    cred = credentials.Certificate("chave_firebase.json")
    firebase_admin.initialize_app(cred)
except ValueError:
    print("App do Firebase já inicializado.")
db = firestore.client()
# ----------------------------------------

# Nome do seu arquivo JSON de usuários
USERS_JSON_FILE = 'users.json'

def migrate_users_to_firestore():
    """Lê o users.json, gera hashes para as senhas e salva no Firestore."""
    try:
        with open(USERS_JSON_FILE, 'r', encoding='utf-8') as f:
            users_data = json.load(f)
    except FileNotFoundError:
        print(f"ERRO: Arquivo '{USERS_JSON_FILE}' não encontrado.")
        return

    # A coleção 'users' vai armazenar os documentos de cada usuário
    users_collection_ref = db.collection('users')
    
    print(f"Iniciando migração de {len(users_data)} usuários...")

    for username, data in users_data.items():
        if 'senha' not in data:
            print(f"Aviso: Usuário '{username}' sem senha, pulando.")
            continue
        
        # 1. PEGA A SENHA EM TEXTO PURO
        plain_password = data['senha']
        
        # 2. GERA O HASH SEGURO
        hashed_password = generate_password_hash(plain_password)
        
        # 3. MONTA O NOVO OBJETO DE DADOS (SEM A SENHA EM TEXTO!)
        user_doc_data = {
            'password_hash': hashed_password,
            'role': data.get('role', 'user'),
            'unidades': data.get('unidades', {})
        }
        
        # 4. SALVA NO FIRESTORE USANDO O USERNAME COMO ID DO DOCUMENTO
        users_collection_ref.document(username).set(user_doc_data)
        print(f"  - Usuário '{username}' migrado com sucesso.")

    print("\nMigração de usuários concluída! As senhas foram substituídas por hashes seguros.")

if __name__ == '__main__':
    migrate_users_to_firestore()