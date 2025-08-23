# app/routes/auth_routes.py
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
import json
from app.user_manager import load_users

auth_bp = Blueprint('auth', __name__, template_folder='../templates')

def load_users():
    # Assume que users.json está na raiz do projeto
    with open('users.json', 'r', encoding='utf-8') as f:
        return json.load(f)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users() # <-- USA A NOVA FUNÇÃO
        user_data = users.get(username)

        if user_data and user_data['senha'] == password:
            session['username'] = username

            # Pega as unidades e ordena pelo nome (o valor do dicionário)
            unidades = user_data.get('unidades', {})
            sorted_unidades = dict(sorted(unidades.items(), key=lambda item: item[1]))
            session['unidades'] = sorted_unidades

            # --- Adiciona a 'role' na sessão ---
            session['role'] = user_data.get('role', 'user') # 'user' é o padrão

            # Agora o len() deve usar o dicionário já ordenado
            if len(session['unidades']) == 1:
                unidade_id = list(session['unidades'].keys())[0]
                session['selected_unit_id'] = unidade_id
                flash('Login bem-sucedido!', 'success')
                return redirect(url_for('main.index'))
            else:
                return redirect(url_for('auth.select_unit'))
        else:
            flash('Usuário ou senha inválidos.', 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
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
        return redirect(url_for('main.index')) # Note a mudança para 'main.index'
    else:
        flash('Você não tem permissão para acessar esta unidade.', 'danger')
        return redirect(url_for('auth.select_unit'))