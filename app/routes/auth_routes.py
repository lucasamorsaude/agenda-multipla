# app/routes/auth_routes.py

from flask import Blueprint, render_template, request, session, redirect, url_for, flash
# 1. IMPORTS CORRIGIDOS: Trocamos 'load_users' por 'get_user' e adicionamos 'check_password_hash'
from app.user_manager import get_user
from werkzeug.security import check_password_hash
from app.activity_logger import log_activity

auth_bp = Blueprint('auth', __name__, template_folder='../templates')

# 2. FUNÇÃO REMOVIDA: A função 'def load_users():' que estava aqui foi DELETADA.

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # 3. LÓGICA ATUALIZADA:
        # Busca o usuário DIRETAMENTE no Firestore
        user_data = get_user(username)

        # A MÁGICA ACONTECE AQUI: Compara o hash salvo com a senha digitada 🔐
        if user_data and 'password_hash' in user_data and check_password_hash(user_data['password_hash'], password):
            # O resto do código continua igual, pois ele só usa os dados carregados
            session['username'] = username
            unidades = user_data.get('unidades', {})
            sorted_unidades = dict(sorted(unidades.items(), key=lambda item: item[1]))
            session['unidades'] = sorted_unidades
            session['role'] = user_data.get('role', 'user') 

            log_activity("LOGIN_SUCCESS", f"Usuário '{username}' logou com sucesso.")

            if len(session['unidades']) == 1:
                unidade_id = list(session['unidades'].keys())[0]
                session['selected_unit_id'] = unidade_id
                flash('Login bem-sucedido!', 'success')
                return redirect(url_for('main.index'))
            else:
                return redirect(url_for('auth.select_unit'))
        else:
            log_activity("LOGIN_FAILED", f"Tentativa de login falhou para o usuário '{username}'.")
            flash('Usuário ou senha inválidos.', 'danger')
            
    return render_template('login.html')

# AS OUTRAS ROTAS (logout, select_unit, set_unit) NÃO PRECISAM DE MUDANÇAS ✅
@auth_bp.route('/logout')
def logout():
    username = session.get('username', 'Desconhecido') 
    session.clear()
    log_activity("LOGOUT", f"Usuário '{username}' saiu do sistema.")
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/select_unit')
def select_unit():
    if 'username' not in session or not session.get('unidades'):
        return redirect(url_for('auth.login'))
    return render_template('select_unit.html')

@auth_bp.route('/set_unit/<unit_id>')
def set_unit(unit_id):
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    if unit_id in session.get('unidades', {}):
        session['selected_unit_id'] = unit_id
        return redirect(url_for('main.index'))
    else:
        flash('Você não tem permissão para acessar esta unidade.', 'danger')
        return redirect(url_for('auth.select_unit'))