# app/activity_logger.py
import os
from datetime import datetime
from flask import request, session
from supabase import create_client, Client
from dotenv import load_dotenv

# --- Inicialização do Cliente Supabase ---
# (Igual ao user_manager.py)
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(url, key)


def log_activity(action: str, details: str = ""):
    """
    Registra uma ação na tabela 'activity_log' do Supabase.
    Ex: log_activity("LOGIN_SUCCESS", "Usuário 'lucas' logou com sucesso.")
    """
    try:
        # Coleta os dados do contexto da requisição
        username = session.get('username', 'Anônimo')
        ip_address = request.remote_addr if request else 'N/A'
        
        # Monta o dicionário com os dados do log
        # NÃO precisamos mais enviar o 'timestamp'. 
        # O banco de dados (DEFAULT now()) cuida disso.
        log_data = {
            'username': username,
            'ip_address': ip_address,
            'action': action,
            'details': details
        }
        
        # Insere um novo registro na tabela 'activity_log'.
        # O Supabase/PostgreSQL gera o 'id' e o 'timestamp' sozinhos.
        supabase.table('activity_log').insert(log_data).execute()

    except Exception as e:
        # Se ocorrer um erro, imprime no console para não quebrar a aplicação principal
        print(f"ERRO AO REGISTRAR LOG NO SUPABASE: {e}")