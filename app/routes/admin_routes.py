# app/routes/admin_routes.py
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from functools import wraps
from app.user_manager import load_users, save_users

admin_bp = Blueprint('admin', __name__, template_folder='../templates')

# Decorator para garantir que apenas admins acessem a rota
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Você não tem permissão para acessar esta página.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/admin')
@admin_required
def admin_panel():
    users = load_users()
    # Passa a lista de unidades disponíveis para o formulário de adição
    # Pega as unidades do próprio admin logado como fonte
    available_units = session.get('unidades', {})
    return render_template('admin.html', users=users, available_units=available_units)

@admin_bp.route('/admin/add_user', methods=['POST'])
@admin_required
def add_user():
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role', 'user')
    # Pega a lista de IDs de unidades selecionadas no formulário
    unidades_ids = request.form.getlist('unidades')

    users = load_users()
    if username in users:
        flash(f'Usuário "{username}" já existe!', 'danger')
        return redirect(url_for('admin.admin_panel'))

    # Monta o dicionário de unidades para o novo usuário
    user_units = {}
    all_units = session.get('unidades', {})
    for unit_id in unidades_ids:
        if unit_id in all_units:
            user_units[unit_id] = all_units[unit_id]

    # Cria o novo usuário
    users[username] = {
        "senha": password, # Lembre-se: em um app real, a senha deve ser criptografada!
        "role": role,
        "unidades": user_units
    }
    
    save_users(users)
    flash(f'Usuário "{username}" criado com sucesso!', 'success')
    return redirect(url_for('admin.admin_panel'))

@admin_bp.route('/admin/delete_user/<username>', methods=['POST'])
@admin_required
def delete_user(username):
    users = load_users()
    if username in users:
        # Impede que o admin se auto-delete
        if username == session.get('username'):
            flash('Você não pode deletar seu próprio usuário.', 'danger')
        else:
            del users[username]
            save_users(users)
            flash(f'Usuário "{username}" deletado com sucesso!', 'success')
    else:
        flash(f'Usuário "{username}" não encontrado.', 'danger')
        
    return redirect(url_for('admin.admin_panel'))