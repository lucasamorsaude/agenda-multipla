# app/__init__.py
from flask import Flask
import os
import json

import firebase_admin
from firebase_admin import credentials
from dotenv import load_dotenv


def create_app():
    # Cria a instância do aplicativo Flask
    # instance_relative_config=True diz ao Flask para procurar arquivos de config relativos à pasta 'instance'
    app = Flask(__name__, instance_relative_config=True)

    # --- Configuração ---
    # Carrega a chave secreta e outros valores de config
    app.config.from_mapping(
        SECRET_KEY='sua-chave-secreta-muito-dificil-de-adivinhar-troque-isso',
    )
    

    # Carrega o cookie de um arquivo ou variável de ambiente
    try:
        with open('credentials.json', 'r') as f:
            local_credentials = json.load(f)
        cookie_value = local_credentials.get("cookie", "")
    except (FileNotFoundError, json.JSONDecodeError):
        cookie_value = ""

    app.config['COOKIE_VALUE'] = os.environ.get("COOKIE_VALUE", cookie_value)
    
    # Carrega as variáveis do arquivo .env para o ambiente
    load_dotenv()

    cred = None

    # 1. Tenta carregar do ambiente (Modo Produção - Railway)
    cred_json_string = os.environ.get('FIREBASE_CREDENTIALS_JSON')
    if cred_json_string:
        print("Iniciando em modo PRODUÇÃO (Railway)")
        cred_dict = json.loads(cred_json_string)
        cred = credentials.Certificate(cred_dict)
    else:
        # 2. Tenta carregar do caminho no .env (Modo Local)
        cred_path = os.environ.get('FIREBASE_CREDENTIALS_PATH')
        if cred_path:
            print("Iniciando em modo LOCAL")
            cred = credentials.Certificate(cred_path)
        else:
            print("Erro: Nenhuma credencial do Firebase encontrada.")

    # Inicializa o app se a credencial foi carregada
    if cred and not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    else:
        print("Firebase já inicializado ou credenciais ausentes.")

    # --- Registrar Blueprints ---
    from .routes.auth_routes import auth_bp
    from .routes.main_routes import main_bp
    from .routes.api_routes import api_bp
    from .routes.cache_routes import cache_bp
    from app.routes.user_routes import user_bp
    from app.routes.superadmin_routes import superadmin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(cache_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(superadmin_bp)


    from .activity_logger import log_activity
    from flask import request

    # Adiciona uma rota raiz para redirecionar para o login
    @app.route('/')
    def root():
        from flask import redirect, url_for
        return redirect(url_for('auth.login'))
    
    @app.after_request
    def log_request_activity(response):
        # Ignora requisições para arquivos (css, js, etc.) para não poluir o log
        if '.' in request.path or request.path.startswith('/api/'):
            return response
        
        details = f"Rota: {request.path} | Método: {request.method} | Status: {response.status_code}"
        log_activity("PAGE_VIEW", details)
        
        return response

    return app

