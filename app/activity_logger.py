# app/activity_logger.py
import sqlite3
import os
from datetime import datetime, timedelta
from flask import request, session

DB_FILE = "activity.db"

def init_db():
    """Cria a tabela de log no banco de dados, se ela não existir."""
    if not os.path.exists(DB_FILE):
        print("Criando banco de dados de atividade...")
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                username TEXT,
                ip_address TEXT,
                action TEXT NOT NULL,
                details TEXT
            )
        ''')
        conn.commit()
        conn.close()
        print("Banco de dados de atividade criado com sucesso.")

def log_activity(action, details=""):
    """
    Registra uma ação no banco de dados de log.
    Ex: log_activity("LOGIN_SUCCESS", "Usuário 'lucas' logou com sucesso.")
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        username = session.get('username', 'Anônimo')
        ip_address = request.remote_addr if request else 'N/A'
        agora_gmt3 = datetime.utcnow() - timedelta(hours=3)
        timestamp = agora_gmt3.strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute(
            "INSERT INTO activity_log (timestamp, username, ip_address, action, details) VALUES (?, ?, ?, ?, ?)",
            (timestamp, username, ip_address, action, details)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"ERRO AO REGISTRAR LOG: {e}")