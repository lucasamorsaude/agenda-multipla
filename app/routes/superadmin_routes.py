# app/routes/superadmin_routes.py
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from functools import wraps
from datetime import date
import pandas as pd
import sqlite3
import io
from flask import Response

# Importe suas funções de métricas e cache
from cache_manager import load_agendas_from_cache
from metrics import (
    calculate_summary_metrics, 
    calculate_global_conversion_rate
)

superadmin_bp = Blueprint('superadmin', __name__, template_folder='../templates')

# Decorator para garantir que apenas superadmins acessem
def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'superadmin':
            flash('Acesso restrito a Super Admins.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@superadmin_bp.route('/superadmin/dashboard', methods=['GET', 'POST'])
@superadmin_required
def dashboard():
    selected_date = date.fromisoformat(request.form['selected_date']) if request.method == 'POST' else date.today()
    
    all_units = session.get('unidades', {})
    all_units_stats = []
    
    # Dicionários para consolidar os totais globais
    global_summary = {
        'total_agendado_geral': 0, 'total_confirmado_geral': 0, 
        'total_ocupados': 0, 'total_slots_disponiveis': 0, 'total_atendidos': 0,
        'total_nao_compareceu': 0
    }

    # IMPORTANTE: Este painel depende dos caches diários de cada unidade.
    # Ele não busca dados da API em tempo real para não sobrecarregar o sistema.
    for unit_id, unit_name in all_units.items():
        cached_data = load_agendas_from_cache(selected_date, unit_id)
        
        if cached_data and cached_data.get('resumo_geral'):
            resumo_geral_unit = cached_data['resumo_geral']
            df_resumo_unit = pd.DataFrame.from_dict(resumo_geral_unit, orient='index').fillna(0).astype(int)
            
            # Calcula métricas para esta unidade específica
            summary_metrics = calculate_summary_metrics(resumo_geral_unit, df_resumo_unit.copy())
            conversion_metrics = calculate_global_conversion_rate(df_resumo_unit.copy()) 
            nao_compareceu = int(df_resumo_unit['Não compareceu'].sum()) if 'Não compareceu' in df_resumo_unit else 0

            # Adiciona os stats da unidade à lista
            all_units_stats.append({
                'name': unit_name,
                'agendados': summary_metrics['total_agendado_geral'],
                'confirmacao': summary_metrics['percentual_confirmacao'],
                'ocupacao': summary_metrics['percentual_ocupacao'],
                'conversao': conversion_metrics['conversion_rate'],
                'atendidos': conversion_metrics['total_atendidos'],
                'nao_compareceu': nao_compareceu,
                'confirmacao_numeric': float(summary_metrics['percentual_confirmacao'].strip('%')),
                'ocupacao_numeric': float(summary_metrics['percentual_ocupacao'].strip('%')),
                'conversao_numeric': float(conversion_metrics['conversion_rate'].strip('%')),
            })
            
            # Acumula os totais para o resumo global
            global_summary['total_agendado_geral'] += summary_metrics['total_agendado_geral']
            global_summary['total_confirmado_geral'] += summary_metrics['total_confirmado_geral']
            global_summary['total_ocupados'] += summary_metrics['total_ocupados']
            global_summary['total_slots_disponiveis'] += summary_metrics['total_slots_disponiveis']
            global_summary['total_atendidos'] += conversion_metrics['total_atendidos']
            global_summary['total_nao_compareceu'] += nao_compareceu


    # Calcula as taxas globais
    if global_summary['total_agendado_geral'] > 0:
        global_summary['taxa_confirmacao_global'] = f"{(global_summary['total_confirmado_geral'] / global_summary['total_agendado_geral']) * 100:.2f}%"
    else:
        global_summary['taxa_confirmacao_global'] = "0.00%"

    if global_summary['total_slots_disponiveis'] > 0:
        global_summary['taxa_ocupacao_global'] = f"{(global_summary['total_ocupados'] / global_summary['total_slots_disponiveis']) * 100:.2f}%"
    else:
        global_summary['taxa_ocupacao_global'] = "0.00%"
    
    global_summary['total_atendidos_global'] = global_summary['total_atendidos']
    if global_summary['total_agendado_geral'] > 0:
        global_summary['taxa_conversao_global'] = f"{(global_summary['total_atendidos'] / global_summary['total_agendado_geral']) * 100:.2f}%"
    else:
        global_summary['taxa_conversao_global'] = "0.00%"
        
    # Ordena as unidades por nome como padrão
    all_units_stats.sort(key=lambda x: x['name'])
    
    return render_template(
        'superadmin_dashboard.html', 
        selected_date=selected_date.strftime('%Y-%m-%d'),
        global_summary=global_summary,
        units_stats=all_units_stats
    )


@superadmin_bp.route('/superadmin/activity-log')
@superadmin_required
def activity_log():
    # Pega os parâmetros de filtro da URL, incluindo as novas datas
    search_user = request.args.get('username', '')
    search_action = request.args.get('action', '')
    search_details = request.args.get('details', '')
    search_start_date = request.args.get('start_date', '')
    search_end_date = request.args.get('end_date', '')

    logs = []
    all_usernames = []
    all_actions = []

    try:
        conn = sqlite3.connect("activity.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Busca opções para os filtros (sem alteração aqui)
        cursor.execute("SELECT DISTINCT username FROM activity_log ORDER BY username")
        all_usernames = cursor.fetchall()
        cursor.execute("SELECT DISTINCT action FROM activity_log ORDER BY action")
        all_actions = cursor.fetchall()

        # Constrói a busca no banco de dados dinamicamente
        query = "SELECT * FROM activity_log"
        conditions = []
        params = []

        if search_user:
            conditions.append("username = ?")
            params.append(search_user)
        if search_action:
            conditions.append("action = ?")
            params.append(search_action)
        if search_details:
            conditions.append("details LIKE ?")
            params.append(f"%{search_details}%")
        
        # --- LÓGICA NOVA PARA DATAS ---
        if search_start_date:
            conditions.append("timestamp >= ?")
            params.append(f"{search_start_date} 00:00:00") # Começo do dia
        if search_end_date:
            conditions.append("timestamp <= ?")
            params.append(f"{search_end_date} 23:59:59") # Fim do dia
        # --------------------------------

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY id DESC LIMIT 500"
        
        cursor.execute(query, params)
        logs = cursor.fetchall()
        
        conn.close()
    except Exception as e:
        flash(f"Erro ao carregar logs: {e}", "danger")

    # Passa os filtros atuais de volta para o template
    current_filters = {
        'username': search_user,
        'action': search_action,
        'details': search_details,
        'start_date': search_start_date, # <-- NOVO
        'end_date': search_end_date      # <-- NOVO
    }

    return render_template('activity_log.html', 
                           logs=logs, 
                           all_usernames=all_usernames,
                           all_actions=all_actions,
                           current_filters=current_filters)


@superadmin_bp.route('/superadmin/activity-log/export')
@superadmin_required
def export_activity_log():
    # 1. Reutiliza exatamente a mesma lógica de filtros da página de visualização
    search_user = request.args.get('username', '')
    search_action = request.args.get('action', '')
    search_details = request.args.get('details', '')
    search_start_date = request.args.get('start_date', '')
    search_end_date = request.args.get('end_date', '')

    try:
        conn = sqlite3.connect("activity.db")
        # A busca no banco é idêntica à da outra rota
        query = "SELECT id, timestamp, username, ip_address, action, details FROM activity_log"
        conditions = []
        params = []

        if search_user:
            conditions.append("username = ?")
            params.append(search_user)
        if search_action:
            conditions.append("action = ?")
            params.append(search_action)
        if search_details:
            conditions.append("details LIKE ?")
            params.append(f"%{search_details}%")
        if search_start_date:
            conditions.append("timestamp >= ?")
            params.append(f"{search_start_date} 00:00:00")
        if search_end_date:
            conditions.append("timestamp <= ?")
            params.append(f"{search_end_date} 23:59:59")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY id DESC" # Pega todos os resultados, sem limite de 500
        
        # 2. Carrega os dados em um DataFrame do Pandas
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()

        if df.empty:
            flash("Nenhum dado encontrado para exportar com os filtros selecionados.", "warning")
            return redirect(url_for('superadmin.activity_log'))

        # Renomeia as colunas para o arquivo Excel
        df.columns = ['ID', 'Data/Hora', 'Usuário', 'Endereço IP', 'Ação', 'Detalhes']
        
        # 3. Cria o arquivo Excel em memória
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Log_de_Atividades')
        output.seek(0)

        # 4. Retorna o arquivo para download
        filename = f"log_atividades_{date.today().strftime('%Y-%m-%d')}.xlsx"
        return Response(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )

    except Exception as e:
        flash(f"Erro ao exportar dados: {e}", "danger")
        return redirect(url_for('superadmin.activity_log'))