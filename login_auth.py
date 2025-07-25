# Testa o fluxo de autenticação em dois passos: login + refresh.

import requests
import json
import os

# 1. Definições da Requisição
LOGIN_URL = 'https://amei.amorsaude.com.br/api/v1/security/login'

CREDENTIALS_FILE = 'credentials.json'

def load_credentials():
    """Carrega as credenciais do arquivo JSON."""
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"Erro: Arquivo de credenciais '{CREDENTIALS_FILE}' não encontrado.")
        # Em um ambiente de produção, você pode levantar um erro ou ter uma estratégia de fallback.
        return None
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            credentials = json.load(f)
        return credentials
    except json.JSONDecodeError as e:
        print(f"Erro ao decodificar JSON em '{CREDENTIALS_FILE}': {e}")
        return None
    except Exception as e:
        print(f"Erro ao ler arquivo de credenciais: {e}")
        return None


credentials = load_credentials()

login = credentials.get("login")
senha = credentials.get("senha")

LOGIN_PAYLOAD = {
    'email': login,
    'password': senha, 
    'keepConnected': True
}

def get_auth_new(clinic_id):
    # Crie a URL dinamicamente
    refresh_url = f'https://amei.amorsaude.com.br/api/v1/security/refresh-token?clinicId={clinic_id}'

    # 2. Início do Teste
    print("="*60)
    print("INICIANDO AUTENTICAÇÃO EM 2 PASSOS")
    print("="*60)

    # --- PASSO 1: Login Inicial ---
    try:
        login_response = requests.post(LOGIN_URL, json=LOGIN_PAYLOAD)
        login_response.raise_for_status()
        preliminary_token = login_response.json().get('access_token')

        if not preliminary_token:
            print("\n❌ FALHA NO PASSO 1: Token preliminar não foi encontrado.")
            exit()

        print("\n✅ SUCESSO NO PASSO 1!")

    except requests.exceptions.RequestException as e:
        print(f"\n❌ FALHA NO PASSO 1: Erro na requisição de login. Detalhes: {e}")
        exit()

    # --- PASSO 2: Refresh com o método POST ---
    preliminary_headers = {'Authorization': f"Bearer {preliminary_token}"}

    try:
        # --- MUDANÇA PRINCIPAL AQUI: de requests.get para requests.post ---
        refresh_response = requests.post(refresh_url, headers=preliminary_headers)
        refresh_response.raise_for_status()

        refresh_data = refresh_response.json()
        final_token = refresh_data.get('access_token')

        if not final_token:
            print("\n❌ FALHA NO PASSO 2: Token final não encontrado na resposta.")
            exit()

        print("\n✅ SUCESSO NO PASSO 2! Autenticação completa.")
        return final_token
            
        

    except requests.exceptions.RequestException as e:
        print(f"\n❌ FALHA NO PASSO 2: Erro na requisição de refresh.")
        print(f"Detalhes: {e}")
        if 'refresh_response' in locals():
            print(f"Resposta do Servidor: {refresh_response.text}")


