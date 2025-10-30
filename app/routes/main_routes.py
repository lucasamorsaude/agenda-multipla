# app/routes/main_routes.py

from flask import Blueprint, render_template, request, session, redirect, url_for, flash, current_app
from datetime import date, datetime
import pandas as pd
from login_auth import get_auth_new
from cache_manager import load_agendas_from_cache_v2, save_agendas_to_cache_v2
# Importando as novas funções de forma organizada
from metrics import (
    calculate_summary_metrics, 
    calculate_confirmation_ranking,
    calculate_occupation_ranking,
    calculate_conversion_ranking,
    calculate_global_conversion_rate
)
from app.services.amei_api import get_all_professionals, get_slots_for_professional

main_bp = Blueprint('main', __name__, template_folder='../templates')

AGENDA_URL_TEMPLATE = "https://amei.amorsaude.com.br/schedule/schedule-appointment?profissionalId={}&date={}"
STATUS_STYLES = {
    "Livre": "background-color: #eeeeee; border: 1px solid #7cb9e8; color: #1565C0;",
    "Bloqueado": "background-color: #e0e0e0; color: #757575; border: 1px solid #b0b0b0;",
    "Atendido": "background-color: #8ce196; border: 1px solid #4CAF50; color: #1b8c0a;",
    "Atendido pós-consulta": "background-color: #8ce196; border: 1px solid #4CAF50; color: #1b8c0a;",
    "Marcado - confirmado": "background-color: #aed6f1; border: 1px solid #6cb3e0; color: #1565C0;",
    "Em atendimento": "background-color: #fce47c; border: 1px solid #FBC02D; color: #F57F17;",
    "Não compareceu": "background-color: #ff91a4; border: 1px solid #E57373; color: #C62828;",
    "Agendado": "background-color: #f7d98d; border: 1px solid #e0c25a; color: #C62828;",
    "Encaixe": "background-color: #b7a1fc; border: 1px solid #7649fc; color: #7649fc;",
    "Aguardando atendimento": "background-color: #ffe770; border: 1px solid #a89a1d; color: #a89a1d;",
    "Aguardando pós-consulta": "background-color: #c2ffd4; border: 1px solid #07ab38; color: #07ab38;",
    "Não compareceu pós-consulta": "background-color: #c2ffd4; border: 1px solid #07ab38; color: #07ab38;",
    "default": "background-color: #FAFAFA; border: 1px solid #E0E0E0; color: #757575;"
}

def _get_default_context():
    """Retorna o contexto inicial para evitar erros no template."""
    return {
        "agendas": {}, "resumo_geral": {}, "resumo_html": "", "table_headers": [], "table_index": [], "table_body": [],
        "summary_metrics": {"total_agendado_geral": 0, "percentual_confirmacao": "0%", "total_confirmado_geral": 0, "percentual_ocupacao": "0%", "total_ocupados": 0, "total_slots_disponiveis": 0},
        "profissionais_stats_confirmacao": [], "profissionais_stats_ocupacao": [], "profissionais_stats_conversao": [],
        "conversion_data_for_selected_day": {"conversion_rate": "0.00%", "total_atendidos": 0}
    }

def _prepare_ranking_data(stats_list, key_name):
    """Adiciona o valor numérico da porcentagem para a barra de progresso no HTML."""
    for stat in stats_list:
        try:
            stat['percent_numeric'] = float(stat[key_name].strip('%'))
        except (ValueError, KeyError):
            stat['percent_numeric'] = 0
    return stats_list

@main_bp.route('/', methods=['GET', 'POST'])
def index():
    if 'username' not in session: return redirect(url_for('auth.login'))
    if 'selected_unit_id' not in session: return redirect(url_for('auth.select_unit'))
    
    id_unidade_selecionada = session['selected_unit_id']
    

    selected_date_str = request.values.get('selected_date', date.today().strftime('%Y-%m-%d'))
    selected_date = date.fromisoformat(selected_date_str)    

    
    context = _get_default_context()
    cached_data = load_agendas_from_cache_v2(selected_date, id_unidade_selecionada)

    if cached_data and cached_data.get('agendas'):
        print(f"SUCESSO: Usando dados do cache para {selected_date_str}.")
        context.update(cached_data)

        if context.get('last_updated_iso'):
            try:
                dt_object = datetime.fromisoformat(context['last_updated_iso'])
                context['last_updated_formatted'] = dt_object.strftime('%H:%M - %d/%m/%Y')
            except (ValueError, TypeError):
                context['last_updated_formatted'] = None

    else:
        auth = get_auth_new(id_unidade_selecionada)
        if not auth:
            flash('Falha ao obter token de autenticação.', 'danger')
            return redirect(url_for('auth.logout'))
        
        HEADERS = {'Authorization': f"Bearer {auth}", 'Cookie': current_app.config['COOKIE_VALUE']}

        print(f"AVISO: Cache não encontrado ou inválido para {selected_date_str}. Buscando da API.")
        all_profissionais = get_all_professionals(HEADERS)
        if all_profissionais:
            for prof in all_profissionais:
                prof_id = prof.get('id')
                prof_nome = prof.get('nome', f'ID {prof_id}')
                
                slots = get_slots_for_professional(prof_id, selected_date, id_unidade_selecionada, HEADERS)
                
                # REMOVA ESTA CONDIÇÃO PARA INCLUIR TODOS OS PROFISSIONAIS
                # if any(slot.get('status') not in ["Livre", "Bloqueado"] for slot in slots):
                
                # SEMPRE inclui o profissional, mesmo que tenha apenas horários livres
                context["agendas"][prof_nome] = {
                    "id": prof_id,
                    "nome": prof_nome,
                    "horarios": sorted(slots, key=lambda x: x.get('numeric_hour', 0.0))
                }
                
                # --- LÓGICA DE CONTAGEM ATUALIZADA PARA ENVIAR AMBOS OS STATUS ---
                contagem_status = {}
                for slot in slots:
                    main_status = slot.get('status')
                    app_status = slot.get('appointmentStatus')
                    
                    final_key = main_status # Define o status base
                    
                    # Se 'appointmentStatus' existir, ele representa o resultado final da consulta.
                    # Se o slot for um 'Encaixe', preservamos essa informação.
                    if app_status:
                        if main_status == 'Encaixe':
                            # Cria uma chave combinada, ex: "Encaixe (Atendido)"
                            final_key = f"Encaixe ({app_status})"
                        else:
                            # Para agendamentos normais, o resultado final é o que importa
                            final_key = app_status

                    if final_key:
                        contagem_status[final_key] = contagem_status.get(final_key, 0) + 1

                context["resumo_geral"][prof_nome] = contagem_status
                    
            if context.get("agendas"):

                now = datetime.now()
                context['last_updated_iso'] = now.isoformat() # Formato para o computador
                context['last_updated_formatted'] = now.strftime('%H:%M - %d/%m/%Y') # Formato para exibição
                
                save_agendas_to_cache_v2(context, selected_date, id_unidade_selecionada)
        else:
            print("ERRO: A chamada get_all_professionals não retornou dados.")

    # --- CÁLCULO DAS MÉTRICAS (SEMPRE EXECUTA) ---
    if context["resumo_geral"]:
        df_resumo = pd.DataFrame.from_dict(context["resumo_geral"], orient='index').fillna(0).astype(int)
        
        # Calcula todas as métricas usando as novas funções
        context["summary_metrics"] = calculate_summary_metrics(context["resumo_geral"], df_resumo.copy())
        context["conversion_data_for_selected_day"] = calculate_global_conversion_rate(df_resumo.copy())
        context["profissionais_stats_confirmacao"] = calculate_confirmation_ranking(df_resumo.copy())
        context["profissionais_stats_ocupacao"] = calculate_occupation_ranking(df_resumo.copy())
        context["profissionais_stats_conversao"] = calculate_conversion_ranking(df_resumo.copy())

        if not df_resumo.empty:
            df_pivot = df_resumo.T
            
            total_agendado = {}
            for profissional in df_pivot.columns:
                total_slots = df_pivot[profissional].sum()
                livres = df_pivot.loc['Livre', profissional] if 'Livre' in df_pivot.index else 0
                bloqueados = df_pivot.loc['Bloqueado', profissional] if 'Bloqueado' in df_pivot.index else 0
                total_agendado[profissional] = int(total_slots - livres - bloqueados)
            
            df_pivot.loc['Total Agendado'] = pd.Series(total_agendado)
            
            # --- AQUI ESTÁ A MUDANÇA PRINCIPAL ---
            # Em vez de gerar HTML, preparamos os dados para o Jinja2
            context['table_headers'] = df_pivot.columns.tolist()
            context['table_index'] = df_pivot.index.tolist()
            context['table_body'] = df_pivot.values.tolist()

    # Prepara os dados para as barras de progresso
    context["profissionais_stats_confirmacao"] = _prepare_ranking_data(context.get("profissionais_stats_confirmacao", []), 'taxa_confirmacao')
    context["profissionais_stats_ocupacao"] = _prepare_ranking_data(context.get("profissionais_stats_ocupacao", []), 'taxa_ocupacao')
    context["profissionais_stats_conversao"] = _prepare_ranking_data(context.get("profissionais_stats_conversao", []), 'taxa_conversao')

    return render_template('index.html', selected_date=selected_date_str, status_styles=STATUS_STYLES, agenda_url_template=AGENDA_URL_TEMPLATE, **context)


@main_bp.route('/switch_unit/<direction>')
def switch_unit(direction):
    """
    Muda a unidade selecionada na sessão para a próxima ou anterior
    e redireciona para a página inicial, mantendo a data selecionada.
    """
    if 'username' not in session or not session.get('unidades'):
        return redirect(url_for('auth.login'))

    # Pega a data que foi enviada como parâmetro no link
    selected_date = request.args.get('selected_date', date.today().strftime('%Y-%m-%d'))

    sorted_unidades_items = sorted(session['unidades'].items(), key=lambda item: item[1])
    unidades_ids = [item[0] for item in sorted_unidades_items]

    if len(unidades_ids) <= 1:
        return redirect(url_for('main.index', selected_date=selected_date))

    try:
        current_unit_id = session.get('selected_unit_id')
        current_index = unidades_ids.index(current_unit_id)

        if direction == 'next':
            new_index = (current_index + 1) % len(unidades_ids)
        elif direction == 'prev':
            new_index = (current_index - 1 + len(unidades_ids)) % len(unidades_ids)
        else:
            return redirect(url_for('main.index', selected_date=selected_date))

        session['selected_unit_id'] = unidades_ids[new_index]

    except (ValueError, KeyError):
        session['selected_unit_id'] = unidades_ids[0]

    return redirect(url_for('main.index', selected_date=selected_date))