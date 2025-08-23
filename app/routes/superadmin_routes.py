# app/routes/superadmin_routes.py
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from functools import wraps
from datetime import date
import pandas as pd

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