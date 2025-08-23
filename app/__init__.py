# app/__init__.py
from flask import Flask
import os
import json

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

    # --- Registrar Blueprints ---
    from .routes.auth_routes import auth_bp
    from .routes.main_routes import main_bp
    from .routes.api_routes import api_bp
    from .routes.cache_routes import cache_bp
    from app.routes.user_routes import user_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(cache_bp)
    app.register_blueprint(user_bp)

    # Adiciona uma rota raiz para redirecionar para o login
    @app.route('/')
    def root():
        from flask import redirect, url_for
        return redirect(url_for('auth.login'))

    return app