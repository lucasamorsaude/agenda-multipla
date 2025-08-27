# app/user_manager.py
from firebase_admin import firestore

def get_user(username: str) -> dict | None:
    """Busca um único usuário no Firestore pelo seu username."""
    try:
        db = firestore.client()
        doc_ref = db.collection('users').document(username)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict()
        return None
    except Exception as e:
        print(f"ERRO ao buscar usuário '{username}': {e}")
        return None

def get_all_users() -> dict:
    """Busca todos os usuários do Firestore."""
    try:
        db = firestore.client()
        users_ref = db.collection('users').stream()
        users_dict = {user.id: user.to_dict() for user in users_ref}
        return users_dict
    except Exception as e:
        print(f"ERRO ao buscar todos os usuários: {e}")
        return {}

def save_user(username: str, user_data: dict):
    """Cria ou atualiza um usuário no Firestore."""
    try:
        db = firestore.client()
        db.collection('users').document(username).set(user_data)
    except Exception as e:
        print(f"ERRO ao salvar usuário '{username}': {e}")

def delete_user_from_db(username: str):
    """Deleta um usuário do Firestore."""
    try:
        db = firestore.client()
        db.collection('users').document(username).delete()
    except Exception as e:
        print(f"ERRO ao deletar usuário '{username}': {e}")