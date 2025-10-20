from flask import Flask
import os
import json
from dotenv import load_dotenv

def create_app():
    """Cria e configura a instância do aplicativo Flask."""
    
    app = Flask(__name__, instance_relative_config=True)

    # Carrega as variáveis de ambiente do arquivo .env
    # É bom fazer isso no início.
    load_dotenv()

    # --- Configuração ---
    app.config.from_mapping(
        # É crucial trocar esta chave em produção!
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-key-default')
    )
    
    # Carrega o cookie de um arquivo ou variável de ambiente (lógica mantida)
    try:
        with open('credentials.json', 'r') as f:
            local_credentials = json.load(f)
        cookie_value = local_credentials.get("cookie", "")
    except (FileNotFoundError, json.JSONDecodeError):
        cookie_value = ""

    app.config['COOKIE_VALUE'] = os.environ.get("COOKIE_VALUE", cookie_value)
    
    # --- Registrar Blueprints ---
    # (Nenhuma alteração aqui)
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

    # --- Hooks da Aplicação ---
    
    # Adiciona uma rota raiz para redirecionar para o login
    @app.route('/')
    def root():
        from flask import redirect, url_for
        return redirect(url_for('auth.login'))
    
    # O logger de atividades continua funcionando, pois o módulo
    # 'activity_logger' já foi migrado internamente.
    @app.after_request
    def log_request_activity(response):
        from .activity_logger import log_activity
        from flask import request

        # Ignora requisições para arquivos estáticos e APIs
        if '.' in request.path or request.path.startswith('/api/'):
            return response
        
        details = f"Rota: {request.path} | Método: {request.method} | Status: {response.status_code}"
        log_activity("PAGE_VIEW", details)
        
        return response

    return app