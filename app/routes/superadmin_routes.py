# app/routes/superadmin_routes.py
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from functools import wraps
from datetime import date, datetime, timedelta
import pandas as pd
import sqlite3
import io
from flask import Response
from zoneinfo import ZoneInfo


from firebase_admin import firestore
# Importe suas funções de métricas e cache
from cache_manager import load_agendas_from_cache
from metrics import (
    calculate_summary_metrics, 
    calculate_global_conversion_rate
)

SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo") # <-- MUDANÇA 2: Definir fuso horário


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
    db = firestore.client()
    current_filters = {
        'username': request.args.get('username', ''), 'action': request.args.get('action', ''),
        'start_date': request.args.get('start_date', ''), 'end_date': request.args.get('end_date', ''),
        'details': request.args.get('details', '')
    }

    try:
        query = db.collection('activity_log')
        if current_filters['username']:
            query = query.where('username', '==', current_filters['username'])
        if current_filters['action']:
            query = query.where('action', '==', current_filters['action'])
        if current_filters['start_date']:
            start_dt = datetime.fromisoformat(current_filters['start_date'])
            query = query.where('timestamp', '>=', start_dt)
        if current_filters['end_date']:
            end_dt = datetime.fromisoformat(current_filters['end_date']) + timedelta(days=1)
            query = query.where('timestamp', '<', end_dt)
        
        # Firestore não suporta busca 'LIKE'. Uma busca exata é possível.
        if current_filters['details']:
            query = query.where('details', '==', current_filters['details'])

        query = query.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(500)
        logs_from_db = query.stream()
        
        logs = []
        for log in logs_from_db:
            log_data = log.to_dict()
            if 'timestamp' in log_data and isinstance(log_data['timestamp'], datetime):
                # <-- MUDANÇA 3: Converte para o fuso de SP e formata
                log_data['timestamp'] = log_data['timestamp'].astimezone(SAO_PAULO_TZ).strftime('%d/%m/%Y %H:%M:%S')
            logs.append(log_data)

        # Popula os menus de filtro
        all_logs_docs = db.collection('activity_log').stream()
        all_usernames_set = {doc.to_dict().get('username') for doc in all_logs_docs if doc.to_dict().get('username')}
        
        # Reset stream to re-iterate
        all_logs_docs = db.collection('activity_log').stream()
        all_actions_set = {doc.to_dict().get('action') for doc in all_logs_docs if doc.to_dict().get('action')}

        all_usernames = [{'username': name} for name in sorted(list(all_usernames_set))]
        all_actions = [{'action': act} for act in sorted(list(all_actions_set))]

    except Exception as e:
        flash(f"Erro ao carregar logs do Firestore: {e}", "danger")
        logs, all_usernames, all_actions = [], [], []

    return render_template('activity_log.html', logs=logs, all_usernames=all_usernames,
                           all_actions=all_actions, current_filters=current_filters)


@superadmin_bp.route('/superadmin/activity-log/export')
@superadmin_required
def export_activity_log():
    db = firestore.client()
    try:
        # Reutiliza a mesma lógica de query da rota anterior, mas sem o .limit()
        query = db.collection('activity_log')
        if request.args.get('username'):
            query = query.where('username', '==', request.args.get('username'))
        if request.args.get('action'):
            query = query.where('action', '==', request.args.get('action'))
        if request.args.get('start_date'):
            start_dt = datetime.fromisoformat(request.args.get('start_date'))
            query = query.where('timestamp', '>=', start_dt)
        if request.args.get('end_date'):
            end_dt = datetime.fromisoformat(request.args.get('end_date')) + timedelta(days=1)
            query = query.where('timestamp', '<', end_dt)
        if request.args.get('details'):
            query = query.where('details', '==', request.args.get('details'))
        
        query = query.order_by('timestamp', direction=firestore.Query.DESCENDING)
        docs = query.stream()

        logs_list = []
        for doc in docs:
            log_data = doc.to_dict()
            if 'timestamp' in log_data and isinstance(log_data['timestamp'], datetime):
                # <-- MUDANÇA 4: Converte para o fuso de SP e formata
                log_data['timestamp'] = log_data['timestamp'].astimezone(SAO_PAULO_TZ).strftime('%d/%m/%Y %H:%M:%S')
            logs_list.append(log_data)

        if not logs_list:
            flash("Nenhum dado encontrado para exportar.", "warning")
            return redirect(url_for('superadmin.activity_log'))

        df = pd.DataFrame(logs_list)
        # Reordena e renomeia colunas para o Excel
        df = df[['timestamp', 'username', 'ip_address', 'action', 'details']]
        df.columns = ['Data/Hora', 'Usuário', 'Endereço IP', 'Ação', 'Detalhes']
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Log_de_Atividades')
        output.seek(0)

        filename = f"log_atividades_{date.today().strftime('%Y-%m-%d')}.xlsx"
        return Response(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f"attachment;filename={filename}"})

    except Exception as e:
        flash(f"Erro ao exportar dados: {e}", "danger")
        return redirect(url_for('superadmin.activity_log'))
    