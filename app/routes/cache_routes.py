# app/routes/cache_routes.py
from flask import Blueprint, request, jsonify, session
from datetime import date, datetime
from update_cache_script import process_and_cache_day
from app.activity_logger import log_activity

cache_bp = Blueprint('cache', __name__)

# ROTA CORRIGIDA: SEM THREAD, EXECUÇÃO SÍNCRONA
@cache_bp.route('/force_update_day_cache', methods=['POST'])
def force_update_day_cache_sync():
    # Pega o ID da unidade do formulário enviado pelo JavaScript
    id_unidade = request.form.get('unit_id')
    if not id_unidade:
        return jsonify({"status": "error", "message": "ID da unidade não fornecido."}), 400

    # Verifica se o usuário tem permissão para esta unidade
    if 'unidades' not in session or id_unidade not in session['unidades']:
        return jsonify({"status": "error", "message": "Acesso não autorizado para esta unidade."}), 403
        
    selected_date_str = request.form.get('selected_date_force_update', date.today().strftime('%Y-%m-%d'))
    selected_date = date.fromisoformat(selected_date_str)
    unit_name = session['unidades'].get(id_unidade, f"ID {id_unidade}")
    user = session.get('username')

    try:
        log_activity("CACHE_FORCED_UPDATE", f"Usuário '{user}' forçou atualização da unidade '{unit_name}' para o dia {selected_date_str}")
        print(f"Iniciando atualização para o dia {selected_date} na unidade {unit_name} (ID: {id_unidade}).")
        
        process_and_cache_day(selected_date, id_unidade)
        
        print(f"Atualização para o dia {selected_date} na unidade {unit_name} finalizada.")
        
        return jsonify({
            "status": "success", 
            "message": f"Cache para a unidade {unit_name} atualizado!"
        })
    except Exception as e:
        print(f"Erro durante a atualização do cache para {unit_name}: {e}")
        return jsonify({
            "status": "error",
            "message": f"Erro ao atualizar o cache da unidade {unit_name}."
        }), 500