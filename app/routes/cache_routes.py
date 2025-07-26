# app/routes/cache_routes.py
from flask import Blueprint, request, jsonify, session, current_app
from datetime import date
from threading import Thread

# Importe a função que faz o trabalho pesado. Assumindo que está em update_cache_script.py
from update_cache_script import process_and_cache_day 

cache_bp = Blueprint('cache', __name__)

# ROTA CORRIGIDA: SEM THREAD, EXECUÇÃO SÍNCRONA
@cache_bp.route('/force_update_day_cache', methods=['POST'])
def force_update_day_cache_sync():
    if 'selected_unit_id' not in session:
        return jsonify({"status": "error", "message": "Usuário não autenticado"}), 401
        
    id_unidade_selecionada = session['selected_unit_id']
    selected_date_str = request.form.get('selected_date_force_update', date.today().strftime('%Y-%m-%d'))
    selected_date = date.fromisoformat(selected_date_str)

    try:
        print(f"Iniciando atualização SÍNCRONA para o dia {selected_date} na unidade {id_unidade_selecionada}.")
        
        # Chama a função diretamente, sem thread. O código vai esperar aqui.
        process_and_cache_day(selected_date, id_unidade_selecionada)
        
        print(f"Atualização SÍNCRONA para o dia {selected_date} finalizada.")
        
        # Responde SÓ DEPOIS que tudo terminou.
        return jsonify({
            "status": "success", 
            "message": f"Cache para o dia {selected_date.strftime('%d/%m/%Y')} atualizado com sucesso!"
        })
    except Exception as e:
        print(f"Erro durante a atualização síncrona do cache: {e}")
        return jsonify({
            "status": "error",
            "message": "Ocorreu um erro ao atualizar o cache."
        }), 500