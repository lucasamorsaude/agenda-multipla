# app/routes/user_routes.py
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from functools import wraps
from app.user_manager import get_user, get_all_users, save_user, delete_user_from_db
from werkzeug.security import generate_password_hash, check_password_hash
from app.activity_logger import log_activity

user_bp = Blueprint('user', __name__, template_folder='../templates')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Você precisa estar logado para acessar esta página.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def _user_in_scope(target_user_data, current_user_session):
    """
    Verifica se o usuário alvo está no escopo de gerenciamento do usuário logado.
    """
    current_role = current_user_session.get('role', 'user')
    
    # Superadmin pode gerenciar todos.
    if current_role == 'superadmin':
        return True
    
    # Admin só pode gerenciar usuários que compartilham pelo menos uma unidade.
    if current_role == 'admin':
        # Admin não pode gerenciar superadmins.
        if target_user_data.get('role') == 'superadmin':
            return False
            
        admin_units = set(current_user_session.get('unidades', {}).keys())
        target_units = set(target_user_data.get('unidades', {}).keys())
        
        # Retorna True se houver intersecção de unidades.
        return not admin_units.isdisjoint(target_units)

    # Usuário comum não gerencia ninguém (exceto a si mesmo, tratado fora daqui).
    return False


@user_bp.route('/users')
@login_required
def user_panel():
    all_users = get_all_users()
    current_user_role = session.get('role', 'user')
    current_username = session.get('username')
    
    users_to_display = {}
    
    if current_user_role == 'superadmin':
        users_to_display = all_users
    elif current_user_role == 'admin':
        for username, data in all_users.items():
            # Mostra o próprio admin e outros usuários no seu escopo.
            if username == current_username or _user_in_scope(data, session):
                users_to_display[username] = data
    else: # user
        if current_username in all_users:
            users_to_display[current_username] = all_users[current_username]

            
    available_units = session.get('unidades', {})
    return render_template('users.html', users=users_to_display, available_units=available_units)


@user_bp.route('/users/add', methods=['POST'])
@login_required
def add_user():
    if session.get('role') not in ['admin', 'superadmin']:
        flash('Você não tem permissão para adicionar usuários.', 'danger')
        return redirect(url_for('user.user_panel'))

    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role', 'user')
    unidades_ids = request.form.getlist('unidades')

    if get_user(username):
        flash(f'Usuário "{username}" já existe!', 'danger')
        return redirect(url_for('user.user_panel'))

    

    # A lógica para atribuir unidades já usa as unidades do admin logado, o que está correto.
    user_units = {}
    admin_available_units = session.get('unidades', {})
    for unit_id in unidades_ids:
        if unit_id in admin_available_units:
            user_units[unit_id] = admin_available_units[unit_id]

    if not user_units:
        flash('Você deve selecionar pelo menos uma unidade válida para o novo usuário.', 'danger')
        return redirect(url_for('user.user_panel'))

    hashed_password = generate_password_hash(password)
    new_user_data = {
        "password_hash": hashed_password, 
        "role": role, 
        "unidades": user_units
    }
    save_user(username, new_user_data)

    log_activity("USER_CREATED", f"'{session.get('username')}' criou o usuário '{username}'.")
    flash(f'Usuário "{username}" criado com sucesso!', 'success')
    return redirect(url_for('user.user_panel'))


@user_bp.route('/users/delete/<username>', methods=['POST'])
@login_required
def delete_user(username):
    # ✅ Busque apenas os dados do usuário que será deletado
    user_to_delete = get_user(username)
    if not user_to_delete:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('user.user_panel'))

    if username == session.get('username'):
        flash('Você não pode deletar seu próprio usuário.', 'danger')
        return redirect(url_for('user.user_panel'))

    # A verificação de permissão usa os dados que buscamos
    if _user_in_scope(user_to_delete, session):
        # ✅ Chame a função correta para deletar do Firestore
        delete_user_from_db(username)
        log_activity("USER_DELETED", f"'{session.get('username')}' deletou o usuário '{username}'.")
        flash(f'Usuário "{username}" deletado com sucesso!', 'success')
    else:
        flash('Você não tem permissão para deletar este usuário.', 'danger')
        
    return redirect(url_for('user.user_panel'))


@user_bp.route('/users/change_password/<username>', methods=['POST'])
@login_required
def change_password(username):
    new_password = request.form.get('password')
    if not new_password:
        flash('A nova senha não pode estar em branco.', 'danger')
        return redirect(url_for('user.user_panel'))

    user_data = get_user(username)
    if not user_data:
        flash('Usuário não encontrado.', 'danger')
        return redirect(url_for('user.user_panel'))

    # Permite que o usuário altere a própria senha
    can_change = (username == session.get('username'))
    
    # Se não for o próprio usuário, verifica se ele está no escopo de gerenciamento
    if not can_change:
        can_change = _user_in_scope(user_data, session)
    
    if can_change:
        # ✅ Gere o HASH da nova senha
        hashed_password = generate_password_hash(new_password)
        # ✅ Atualize o campo correto: 'password_hash'
        user_data['password_hash'] = hashed_password
        
        # ✅ Salve os dados atualizados do usuário com a função correta
        save_user(username, user_data)
        
        log_activity("PASSWORD_CHANGED", f"'{session.get('username')}' alterou a senha do usuário '{username}'.")
        flash(f'Senha do usuário "{username}" alterada com sucesso!', 'success')
    else:
        flash('Você não tem permissão para alterar a senha deste usuário.', 'danger')

    return redirect(url_for('user.user_panel'))