import sys
import os
from datetime import date, timedelta
import json
import requests
import pandas as pd

# Adicione o caminho do diretório atual ao sys.path para que imports funcionem
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cache_manager import save_agendas_to_cache, load_agendas_from_cache
from metrics import calculate_summary_metrics, calculate_professional_metrics, calculate_conversion_rate_for_date
from login_auth import get_auth_new 

# Replicar as configurações de HEADERS e URLs do app.py
# (Idealmente, estas deveriam estar em um arquivo config.py compartilhado)
auth = get_auth_new()
local_credentials = None
CREDENTIALS_FILE = 'credentials.json'

try:
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, 'r') as f:
            local_credentials = json.load(f)
except Exception as e:
    print(f"Aviso [update_script]: Não foi possível carregar '{CREDENTIALS_FILE}' localmente: {e}")
    local_credentials = None

cookie_value = ""
if local_credentials and local_credentials.get("cookie"):
    cookie_value = local_credentials.get("cookie")
else:
    cookie_value = os.environ.get("COOKIE_VALUE", "")

HEADERS = {
    'Authorization': f"Bearer {auth}",
    'Cookie': cookie_value
}

PROFISSIONAIS_URL = 'https://amei.amorsaude.com.br/api/v1/profissionais/by-unidade'
SLOTS_URL = 'https://amei.amorsaude.com.br/api/v1/slots/list-slots-by-professional'

STATUS_STYLES = {
    "Livre": "background-color: #c7e5ff; border: 1px solid #7cb9e8; color: #1565C0;",
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

# Funções de API (copiadas do app.py)
def get_all_professionals_script():
    try:
        response = requests.get(PROFISSIONAIS_URL, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro [update_script]: Erro de conexão ao buscar profissionais: {e}")
        return None

def get_slots_for_professional_script(professional_id, selected_date):
    params = {
        'idClinic': 932,
        'idSpecialty': 'null',
        'idProfessional': professional_id,
        'initialDate': selected_date.strftime('%Y%m%d'),
        'finalDate': selected_date.strftime('%Y%m%d'),
        'initialHour': '00:00',
        'endHour': '23:59'
    }
    try:
        response = requests.get(SLOTS_URL, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()
        if data and isinstance(data, list) and len(data) > 0:
            return data[0].get('hours', [])
        else:
            return []
    except requests.exceptions.RequestException as e:
        print(f"Erro [update_script]: Erro ao buscar slots para profissional {professional_id} na data {selected_date}: {e}")
        return []

def process_and_cache_day(target_date: date):
    """
    Processa os dados de agenda para um dia específico e os salva no cache.
    """
    print(f"Processando e atualizando cache para a data: {target_date.strftime('%Y-%m-%d')}")
    
    agendas_por_profissional = {}
    resumo_geral = {}
    df_resumo_html = ""
    summary_metrics = {}
    profissionais_stats_confirmacao = []
    profissionais_stats_ocupacao = []
    conversion_data_for_selected_day = {}

    all_profissionais = get_all_professionals_script()
    
    if not all_profissionais:
        print("Nenhum profissional encontrado. Pulando atualização para este dia.")
        return # Sai da função se não houver profissionais

    for prof in all_profissionais:
        prof_id = prof.get('id')
        prof_nome = prof.get('nome', f'Profissional ID {prof_id}')
        
        slots = get_slots_for_professional_script(prof_id, target_date)
        
        active_slots_for_prof = [
            slot for slot in slots 
            if slot.get('status', 'Indefinido') not in ["Livre", "Bloqueado"]
        ]

        if active_slots_for_prof:
            horarios_processados = []
            contagem_status = {}

            for slot in slots: 
                status_atual = slot.get('status', 'Indefinido')
                
                processed_slot = slot.copy()
                processed_slot['horario'] = slot.get('formatedHour', 'N/A')
                processed_slot['paciente'] = slot.get('patient')
                processed_slot['status'] = status_atual
                
                horarios_processados.append(processed_slot)
                contagem_status[status_atual] = contagem_status.get(status_atual, 0) + 1
            
            agendas_por_profissional[prof_nome] = {
                "id": prof_id,
                "horarios": sorted(horarios_processados, key=lambda x: x['numeric_hour'] if 'numeric_hour' in x else 0.0)
            }
            resumo_geral[prof_nome] = contagem_status

    if resumo_geral:
        dados_resumo_para_df = []
        for profissional, status_dict in resumo_geral.items():
            linha = {"Profissional": profissional}
            for status, valor in status_dict.items():
                linha[status] = int(valor) 
            dados_resumo_para_df.append(linha)

        df_resumo_full = pd.DataFrame(dados_resumo_para_df).fillna(0)
        for col in df_resumo_full.columns:
            if col != "Profissional":
                df_resumo_full[col] = df_resumo_full[col].astype(int)
        df_resumo_full = df_resumo_full.set_index("Profissional")
        
        df_resumo_html = df_resumo_full.T.to_html(classes='table table-striped')

        summary_metrics = calculate_summary_metrics(resumo_geral, df_resumo_full.copy())
        profissionais_stats_confirmacao, profissionais_stats_ocupacao = calculate_professional_metrics(df_resumo_full)
    
    conversion_data_for_selected_day = calculate_conversion_rate_for_date(
        target_date, get_all_professionals_script, get_slots_for_professional_script
    )

    day_cache_data = {
        "agendas_por_profissional": agendas_por_profissional,
        "resumo_geral": resumo_geral,
        "df_resumo_html": df_resumo_html,
        "summary_metrics": summary_metrics,
        "profissionais_stats_confirmacao": profissionais_stats_confirmacao,
        "profissionais_stats_ocupacao": profissionais_stats_ocupacao,
        "conversion_data_for_selected_day": conversion_data_for_selected_day
    }
    save_agendas_to_cache(day_cache_data, target_date)
    print(f"Cache para {target_date.strftime('%Y-%m-%d')} atualizado com sucesso.")

# --- NOVA FUNÇÃO PARA ATUALIZAR UM PERÍODO COMPLETO ---
def update_period_cache(start_date: date, end_date: date):
    """
    Atualiza o cache para um período de datas especificado, dia por dia.
    """
    print(f"Iniciando atualização de cache para o período de {start_date.strftime('%Y-%m-%d')} a {end_date.strftime('%Y-%m-%d')}")
    
    current_date = start_date
    while current_date <= end_date:
        # A função process_and_cache_day já busca da API e salva.
        process_and_cache_day(current_date)
        current_date += timedelta(days=1)
    
    print(f"Atualização de cache finalizada para o período.")

if __name__ == '__main__':
    # Este bloco será executado quando o script for chamado diretamente (ex: pelo Render Cron Job)
    print(f"Iniciando script de atualização de cache em background - {date.today().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Define o período para atualização: do dia atual até o final do mês atual + 15 dias no futuro
    today = date.today()
    # Define o último dia do mês atual
    last_day_of_month = date(today.year, today.month, 1) + timedelta(days=32)
    last_day_of_month = last_day_of_month.replace(day=1) - timedelta(days=1) # Garante o último dia correto
    
    start_date_update = today
    # Escolha entre atualizar até o fim do mês ou mais dias no futuro:
    # 1. Até o fim do mês:
    # end_date_update = last_day_of_month
    # 2. Dia atual + 15 dias no futuro (como antes, mas agora dentro da função)
    end_date_update = today + timedelta(days=15) 

    update_period_cache(start_date_update, end_date_update)
    
    print("Execução do script de atualização de cache em background finalizada.")