# app/firebase_activity_logger.py
from datetime import datetime
from flask import request, session
from firebase_admin import firestore
import firebase_admin # Importe para usar firestore.SERVER_TIMESTAMP


# A função init_db() não é mais necessária!
# O Firestore cria a coleção automaticamente quando o primeiro log for adicionado.

def log_activity(action: str, details: str = ""):
    """
    Registra uma ação na coleção 'activity_log' do Firestore.
    Ex: log_activity("LOGIN_SUCCESS", "Usuário 'lucas' logou com sucesso.")
    """
    try:
        db = firestore.client()
        # Define a coleção onde os logs serão armazenados
        log_collection_ref = db.collection('activity_log')
        
        # Coleta os dados do contexto da requisição
        username = session.get('username', 'Anônimo')
        ip_address = request.remote_addr if request else 'N/A'
        
        # Monta o dicionário com os dados do log
        log_data = {
            'timestamp': firestore.SERVER_TIMESTAMP, # Melhor prática: usa o timestamp do servidor do Google
            'username': username,
            'ip_address': ip_address,
            'action': action,
            'details': details
        }
        
        # Adiciona um novo documento à coleção. O Firestore gera um ID único.
        log_collection_ref.add(log_data)

    except Exception as e:
        # Se ocorrer um erro, imprime no console para não quebrar a aplicação principal
        print(f"ERRO AO REGISTRAR LOG NO FIRESTORE: {e}")