import sys
import os
from datetime import date, timedelta, datetime
import json
import requests
import pandas as pd

# Adiciona o caminho do diretório atual ao sys.path para que imports funcionem
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cache_manager import save_agendas_to_cache
# Importando as funções de métrica com os nomes corretos
from metrics import (
    calculate_summary_metrics,
    calculate_confirmation_ranking,
    calculate_occupation_ranking,
    calculate_conversion_ranking,
    calculate_global_conversion_rate
)
from login_auth import get_auth_new

# --- Funções de API ---
# Estas funções agora recebem 'headers' e 'clinic_id' para serem mais flexíveis

def get_all_professionals_script(headers):
    """Busca todos os profissionais da API."""
    try:
        url = 'https://amei.amorsaude.com.br/api/v1/profissionais/by-unidade'
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro [update_script]: Erro de conexão ao buscar profissionais: {e}")
        return None

def get_slots_for_professional_script(professional_id, selected_date, clinic_id, headers):
    """Busca os horários de um profissional para uma data e unidade específicas."""
    params = {
        'idClinic': clinic_id,
        'idSpecialty': 'null',
        'idProfessional': professional_id,
        'initialDate': selected_date.strftime('%Y%m%d'),
        'finalDate': selected_date.strftime('%Y%m%d'),
        'initialHour': '00:00',
        'endHour': '23:59'
    }
    try:
        url = 'https://amei.amorsaude.com.br/api/v1/slots/list-slots-by-professional'
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        if data and isinstance(data, list) and len(data) > 0:
            return data[0].get('hours', [])
        return []
    except requests.exceptions.RequestException as e:
        print(f"Erro [update_script]: Erro ao buscar slots para prof {professional_id} na data {selected_date}: {e}")
        return []

def process_and_cache_day(target_date: date, clinic_id: int):
    """
    Processa os dados de agenda para um dia e unidade específicos e os salva no cache.
    Esta função agora é o "motor" que busca e calcula tudo.
    """
    print(f"--- [CACHE SCRIPT] Iniciando para data: {target_date.strftime('%Y-%m-%d')} | Unidade: {clinic_id} ---")

    # --- Configuração de Autenticação ---
    auth = get_auth_new(clinic_id)
    if not auth:
        print(f"ERRO CRÍTICO [CACHE SCRIPT]: Falha ao obter token para unidade {clinic_id}. Abortando.")
        return

    try:
        with open('credentials.json', 'r') as f:
            cookie_value = json.load(f).get("cookie", "")
            print("DEBUG [CACHE SCRIPT]: Cookie carregado de credentials.json")
    except (FileNotFoundError, json.JSONDecodeError):
        cookie_value = os.environ.get("COOKIE_VALUE", "")
        print("DEBUG [CACHE SCRIPT]: Cookie carregado de variável de ambiente")

    HEADERS = {'Authorization': f"Bearer {auth}", 'Cookie': cookie_value}

    # --- Coleta de Dados da API ---
    context = {"agendas": {}, "resumo_geral": {}}
    all_profissionais = get_all_professionals_script(HEADERS)
    
    if not all_profissionais:
        print("AVISO [CACHE SCRIPT]: Nenhum profissional retornado pela API.")
        return
    
    print(f"DEBUG [CACHE SCRIPT]: Encontrados {len(all_profissionais)} profissionais.")

    for prof in all_profissionais:
        prof_id = prof.get('id')
        prof_nome = prof.get('nome', f'Profissional ID {prof_id}')
        
        slots = get_slots_for_professional_script(prof_id, target_date, clinic_id, HEADERS)
        
        if any(slot.get('status') not in ["Livre", "Bloqueado"] for slot in slots):
            context["agendas"][prof_nome] = {
                "id": prof_id,
                "horarios": sorted(slots, key=lambda x: x.get('numeric_hour', 0.0))
            }
            
            # --- LÓGICA DE CONTAGEM CORRIGIDA (IGUAL AO MAIN_ROUTES.PY) ---
            contagem_status = {}
            for slot in slots:
                main_status = slot.get('status')
                app_status = slot.get('appointmentStatus')
                
                final_key = main_status
                if app_status:
                    if main_status == 'Encaixe':
                        final_key = f"Encaixe ({app_status})"
                    else:
                        final_key = app_status

                if final_key:
                    contagem_status[final_key] = contagem_status.get(final_key, 0) + 1
            
            context["resumo_geral"][prof_nome] = contagem_status

    # --- Cálculo de Métricas ---
    if context["resumo_geral"]:
        df_resumo = pd.DataFrame.from_dict(context["resumo_geral"], orient='index').fillna(0).astype(int)
        
        context["summary_metrics"] = calculate_summary_metrics(context["resumo_geral"], df_resumo.copy())
        context["conversion_data_for_selected_day"] = calculate_global_conversion_rate(df_resumo.copy())
        context["profissionais_stats_confirmacao"] = calculate_confirmation_ranking(df_resumo.copy())
        context["profissionais_stats_ocupacao"] = calculate_occupation_ranking(df_resumo.copy())
        context["profissionais_stats_conversao"] = calculate_conversion_ranking(df_resumo.copy())

        # DEBUG: Imprime as métricas calculadas antes de salvar
        total_atendidos_debug = context.get("conversion_data_for_selected_day", {}).get("total_atendidos", "N/A")
        print(f"DEBUG [CACHE SCRIPT]: Métricas calculadas. Total de atendidos: {total_atendidos_debug}")

    now = datetime.now()
    context['last_updated_iso'] = now.isoformat()
    context['last_updated_formatted'] = now.strftime('%H:%M - %d/%m/%Y')

    # Salva o dicionário 'context' completo no cache
    save_agendas_to_cache(context, target_date, clinic_id)
    print(f"--- [CACHE SCRIPT] Cache para {target_date.strftime('%Y-%m-%d')} atualizado com sucesso. ---")

def update_period_cache(start_date: date, end_date: date, clinic_id: int):
    """Atualiza o cache para um período de datas e uma unidade específica."""
    print(f"Iniciando atualização de cache para o período de {start_date.strftime('%Y-%m-%d')} a {end_date.strftime('%Y-%m-%d')} na unidade {clinic_id}")
    
    current_date = start_date
    while current_date <= end_date:
        process_and_cache_day(current_date, clinic_id)
        current_date += timedelta(days=1)
    
    print("Atualização de cache finalizada para o período.")


if __name__ == '__main__':
    # Este bloco será executado quando o script for chamado diretamente
    print(f"Iniciando script de atualização de cache em background - {date.today().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # ** IMPORTANTE: Defina aqui o ID da unidade padrão para execução standalone **
    DEFAULT_CLINIC_ID = 932 # Altere para o ID da sua clínica principal
    
    today = date.today()
    start_date_update = today
    end_date_update = today + timedelta(days=15) 

    update_period_cache(start_date_update, end_date_update, DEFAULT_CLINIC_ID)
    
    print("Execução do script de atualização de cache em background finalizada.")
