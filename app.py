from flask import Flask, render_template, request, jsonify
from cache_manager import save_agendas_to_cache, load_agendas_from_cache, delete_day_from_cache
from update_cache_script import update_period_cache # Importa a nova função
from datetime import date, timedelta
import pandas as pd
import requests # Manter requests aqui para as funções que fazem chamadas diretas
import json
import os

# Importar as novas funções de cálculo
from metrics import calculate_summary_metrics, calculate_professional_metrics, calculate_conversion_rate_for_date

# Importar get_auth_new do login_auth
from login_auth import get_auth_new

app = Flask(__name__)

auth = get_auth_new()

# BUG FIX: Certifique-se que o cookie_value é obtido de forma robusta
# Adicionei a verificação aqui para garantir que cookie_value sempre tenha um valor,
# seja de local_credentials, ENV, ou vazio.
local_credentials = None
CREDENTIALS_FILE = 'credentials.json' # Define o nome do arquivo aqui, antes de load_credentials

# Tenta carregar credenciais locais. No Render, isso será ignorado.
try:
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, 'r') as f:
            local_credentials = json.load(f)
except Exception as e:
    print(f"Aviso: Não foi possível carregar '{CREDENTIALS_FILE}' localmente: {e}")
    local_credentials = None # Garante que local_credentials seja None em caso de erro

cookie_value = ""
if local_credentials and local_credentials.get("cookie"):
    cookie_value = local_credentials.get("cookie")
else:
    # Fallback para variável de ambiente se o arquivo local não existir ou não tiver 'cookie'
    cookie_value = os.environ.get("COOKIE_VALUE", "")

HEADERS = {
    'Authorization': f"Bearer {auth}",
    'Cookie': cookie_value
}
# Certifique-se de que a variável de ambiente 'COOKIE_VALUE' esteja definida no Render.


PROFISSIONAIS_URL = 'https://amei.amorsaude.com.br/api/v1/profissionais/by-unidade'
SLOTS_URL = 'https://amei.amorsaude.com.br/api/v1/slots/list-slots-by-professional'
PACIENTE_URL_TEMPLATE = 'https://amei.amorsaude.com.br/api/v1/pacientes/{}'
APPOINTMENT_URL_TEMPLATE = 'https://amei.amorsaude.com.br/api/v1/appointments/{}'
AGENDA_URL_TEMPLATE = "https://amei.amorsaude.com.br/schedule/schedule-appointment?profissionalId={}&date={}"

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

def get_all_professionals(): # Esta função não usa HEADERS diretamente, mas sim a global.
                            # Para modularidade, talvez passasse HEADERS como argumento no futuro.
    try:
        response = requests.get(PROFISSIONAIS_URL, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão ao buscar profissionais: {e}")
        return None

def get_slots_for_professional(professional_id, selected_date):
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
    except requests.exceptions.RequestException:
        return []

def get_patient_details(patient_id):
    if not patient_id:
        return None
    try:
        url = PACIENTE_URL_TEMPLATE.format(patient_id)
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar detalhes do paciente {patient_id}: {e}")
        return None

def get_appointment_details(appointment_id):
    if not appointment_id:
        return None
    try:
        url = APPOINTMENT_URL_TEMPLATE.format(appointment_id)
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar detalhes do agendamento {appointment_id}: {e}")
        return None


@app.route('/', methods=['GET', 'POST'])
def index():
    agendas_por_profissional = {}
    resumo_geral = {}
    
    selected_date = date.today()
    selected_date_str = selected_date.strftime('%Y-%m-%d')

    df_resumo_html = ""
    summary_metrics = {}
    profissionais_stats_confirmacao = []
    profissionais_stats_ocupacao = []

    # Garante que conversion_data_for_selected_day tenha uma estrutura completa no início
    conversion_data_for_selected_day = {
        "date": selected_date.strftime('%d/%m/%Y'),
        "total_atendidos": 0,
        "total_agendamentos_validos": 0,
        "conversion_rate": "0.00%",
        "details_by_professional": []
    }

    if request.method == 'POST':
        selected_date_str = request.form['selected_date']
        selected_date = date.fromisoformat(selected_date_str)

        # Tentar carregar do cache primeiro
        cached_data = load_agendas_from_cache(selected_date)

        if cached_data: # cached_data agora contém os dados apenas para o dia selecionado
            print(f"Dados carregados do cache para {selected_date_str}")
            agendas_por_profissional = cached_data.get("agendas_por_profissional", {})
            resumo_geral = cached_data.get("resumo_geral", {})
            
            df_resumo_html = cached_data.get("df_resumo_html", "")
            summary_metrics = cached_data.get("summary_metrics", {})
            profissionais_stats_confirmacao = cached_data.get("profissionais_stats_confirmacao", [])
            profissionais_stats_ocupacao = cached_data.get("profissionais_stats_ocupacao", [])
            
            cached_conversion = cached_data.get("conversion_data_for_selected_day", {})
            conversion_data_for_selected_day = {
                "date": cached_conversion.get("date", selected_date.strftime('%d/%m/%Y')),
                "total_atendidos": cached_conversion.get("total_atendidos", 0),
                "total_agendamentos_validos": cached_conversion.get("total_agendamentos_validos", 0),
                "conversion_rate": cached_conversion.get("conversion_rate", "0.00%"),
                "details_by_professional": cached_conversion.get("details_by_professional", [])
            }


        else:
            print(f"Cache não encontrado ou inválido para {selected_date_str}. Buscando da API...")
            all_profissionais = get_all_professionals()
            
            if all_profissionais:
                for prof in all_profissionais:
                    prof_id = prof.get('id')
                    prof_nome = prof.get('nome', f'Profissional ID {prof_id}')
                    
                    slots = get_slots_for_professional(prof_id, selected_date)
                    
                    has_active_appointments = False 
                    horarios_processados = []
                    contagem_status = {}

                    for slot in slots:
                        status_atual = slot.get('status', 'Indefinido')
                        
                        if status_atual not in ["Livre", "Bloqueado"]:
                            has_active_appointments = True 

                        processed_slot = slot.copy() 
                        processed_slot['horario'] = slot.get('formatedHour', 'N/A')
                        processed_slot['paciente'] = slot.get('patient')
                        processed_slot['status'] = status_atual
                        
                        horarios_processados.append(processed_slot)
                        contagem_status[status_atual] = contagem_status.get(status_atual, 0) + 1
                
                    if has_active_appointments:
                        agendas_por_profissional[prof_nome] = {
                            "id": prof_id,
                            "horarios": sorted(horarios_processados, key=lambda x: x['numeric_hour'] if 'numeric_hour' in x else 0.0)
                        }
                        resumo_geral[prof_nome] = contagem_status

                if resumo_geral: # Este if é importante para evitar erros se não houver dados de resumo
                    dados_resumo_para_df = []
                    for profissional, status_dict in resumo_geral.items():
                        linha = {"Profissional": profissional}
                        for status, valor in status_dict.items():
                            linha[status] = int(valor) if isinstance(valor, (int, float)) else 0
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
                    selected_date, get_all_professionals, get_slots_for_professional
                )

                # Salvar no cache após buscar da API.
                # Este 'cache_data_to_save' é o 'day_data' que será inserido no cache mensal.
                cache_data_to_save = {
                    "agendas_por_profissional": agendas_por_profissional,
                    "resumo_geral": resumo_geral,
                    "df_resumo_html": df_resumo_html,
                    "summary_metrics": summary_metrics,
                    "profissionais_stats_confirmacao": profissionais_stats_confirmacao,
                    "profissionais_stats_ocupacao": profissionais_stats_ocupacao,
                    "conversion_data_for_selected_day": conversion_data_for_selected_day
                }
                save_agendas_to_cache(cache_data_to_save, selected_date)

                summary_metrics = calculate_summary_metrics(resumo_geral, df_resumo_full.copy())
                profissionais_stats_confirmacao, profissionais_stats_ocupacao = calculate_professional_metrics(df_resumo_full)
            
            conversion_data_for_selected_day = calculate_conversion_rate_for_date(
                selected_date, get_all_professionals, get_slots_for_professional
            )

    return render_template(
        'index.html',
        selected_date=selected_date_str,
        agendas=agendas_por_profissional,
        status_styles=STATUS_STYLES,
        agenda_url_template=AGENDA_URL_TEMPLATE,
        resumo_geral=resumo_geral,
        df_resumo_html=df_resumo_html, # Usar o HTML gerado diretamente
        total_agendado_geral=summary_metrics.get("total_agendado_geral", 0),
        total_confirmado_geral=summary_metrics.get("total_confirmado_geral", 0),
        percentual_confirmacao=summary_metrics.get("percentual_confirmacao", "0.00%"),
        total_ocupados=summary_metrics.get("total_ocupados", 0),
        total_slots_disponiveis=summary_metrics.get("total_slots_disponiveis", 0),
        percentual_ocupacao=summary_metrics.get("percentual_ocupacao", "0.00%"),
        profissionais_stats_confirmacao=profissionais_stats_confirmacao,
        profissionais_stats_ocupacao=profissionais_stats_ocupacao,
        conversion_data_for_selected_day=conversion_data_for_selected_day
    )

@app.route('/api/patient_details/<int:patient_id>', methods=['GET'])
def patient_details_api(patient_id):
    details = get_patient_details(patient_id)
    if details:
        return jsonify(details)
    else:
        return jsonify({"error": "Paciente não encontrado ou erro na API"}), 404

@app.route('/api/appointment_details/<int:appointment_id>', methods=['GET'])
def appointment_details_api(appointment_id):
    details = get_appointment_details(appointment_id)
    if details:
        return jsonify(details)
    else:
        return jsonify({"error": "Agendamento não encontrado ou erro na API"}), 404

@app.route('/force_update_day_cache', methods=['POST']) # Renomeado para clareza
def force_update_day_cache():
    selected_date_str = request.form.get('selected_date_force_update', date.today().strftime('%Y-%m-%d'))
    selected_date = date.fromisoformat(selected_date_str)
    
    delete_day_from_cache(selected_date)
    
    # Redireciona para a página principal para que ela recarregue os dados (agora da API)
    return jsonify({"status": "success", "message": "Cache do dia limpo e atualização forçada iniciada.", "redirect_date": selected_date_str})


@app.route('/force_update_month_cache', methods=['POST'])
def force_update_month_cache():
    # Define o período para atualização: do dia atual até o final do mês.
    today = date.today()
    last_day_of_month = date(today.year, today.month, 1) + timedelta(days=32) # Próximo mês + 2 dias para garantir
    last_day_of_month = last_day_of_month.replace(day=1) - timedelta(days=1) # Volta para o último dia do mês atual
    
    # Limpa o cache do mês inteiro para forçar uma recarga completa
    # Nota: delete_day_from_cache opera por dia. Se quiser apagar o arquivo do mês, você precisaria
    # re-adicionar ou ajustar a clear_cache_for_month original em cache_manager e chamar aqui.
    # Por enquanto, ele vai re-processar e sobrescrever cada dia.
    
    # Chama a função de atualização para o período
    # Você pode passar 'today' e 'last_day_of_month' como start/end_date
    # Ou 'today' e 'today + timedelta(days=X)' se preferir X dias a partir de hoje
    update_period_cache(today, last_day_of_month) 
    
    return jsonify({"status": "success", "message": "Atualização do cache do mês iniciada. Isso pode levar alguns minutos."})



if __name__ == '__main__':
    app.run(debug=True)