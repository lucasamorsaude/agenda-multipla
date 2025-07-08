from flask import Flask, render_template, request, jsonify
import requests
from datetime import date
import pandas as pd
from login_auth import get_auth_new
import json
import os

app = Flask(__name__)

auth = get_auth_new()

CREDENTIALS_FILE = 'credentials.json'

def load_credentials():
    """Carrega as credenciais do arquivo JSON."""
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"Erro: Arquivo de credenciais '{CREDENTIALS_FILE}' não encontrado.")
        # Em um ambiente de produção, você pode levantar um erro ou ter uma estratégia de fallback.
        return None
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            credentials = json.load(f)
        return credentials
    except json.JSONDecodeError as e:
        print(f"Erro ao decodificar JSON em '{CREDENTIALS_FILE}': {e}")
        return None
    except Exception as e:
        print(f"Erro ao ler arquivo de credenciais: {e}")
        return None


credentials = load_credentials()

cookie = credentials.get("cookie")

HEADERS = {
    'Authorization': f"Bearer {auth}",
    'Cookie': cookie
}

PROFISSIONAIS_URL = 'https://amei.amorsaude.com.br/api/v1/profissionais/by-unidade'
SLOTS_URL = 'https://amei.amorsaude.com.br/api/v1/slots/list-slots-by-professional'
PACIENTE_URL_TEMPLATE = 'https://amei.amorsaude.com.br/api/v1/pacientes/{}' # NOVA URL
APPOINTMENT_URL_TEMPLATE = 'https://amei.amorsaude.com.br/api/v1/appointments/{}' # NOVA URL
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

def get_all_professionals():
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

# NOVO: Função para buscar detalhes do agendamento
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
    selected_date_str = date.today().strftime('%Y-%m-%d')
    
    df_resumo = pd.DataFrame()
    total_agendado_geral = 0
    total_confirmado_geral = 0
    percentual_confirmacao = 0.0
    total_ocupados = 0
    total_slots_disponiveis = 0
    percentual_ocupacao = 0.0

    profissionais_stats_confirmacao = []
    profissionais_stats_ocupacao = []

    if request.method == 'POST':
        selected_date_str = request.form['selected_date']
        selected_date = date.fromisoformat(selected_date_str)

        profissionais = get_all_professionals()
        
        if profissionais:
            for prof in profissionais:
                prof_id = prof.get('id')
                prof_nome = prof.get('nome', f'Profissional ID {prof_id}')
                
                slots = get_slots_for_professional(prof_id, selected_date)
                
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
            
                if horarios_processados:
                    agendas_por_profissional[prof_nome] = {
                        "id": prof_id,
                        "horarios": sorted(horarios_processados, key=lambda x: x['numeric_hour'] if 'numeric_hour' in x else 0.0)
                    }
                    resumo_geral[prof_nome] = contagem_status

            if resumo_geral:
                dados_resumo = []
                for profissional, status_dict in resumo_geral.items():
                    linha = {"Profissional": profissional}
                    for status, valor in status_dict.items():
                        linha[status] = int(valor) if isinstance(valor, (int, float)) else 0
                    dados_resumo.append(linha)

                df_resumo = pd.DataFrame(dados_resumo).fillna(0)
                for col in df_resumo.columns:
                    if col != "Profissional":
                        df_resumo[col] = df_resumo[col].astype(int)

                df_resumo = df_resumo.set_index("Profissional")
                
                status_excluir = ["Bloqueado", "Livre"]
                colunas_para_somar = [col for col in df_resumo.columns if col not in status_excluir]
                
                # Garante que 'Total Agendado' seja 0 se não houver colunas para somar
                if colunas_para_somar:
                    df_resumo["Total Agendado"] = df_resumo[colunas_para_somar].sum(axis=1)
                else:
                    df_resumo["Total Agendado"] = 0 # Inicializa como 0 se não houver colunas relevantes

                # MODIFICAÇÃO AQUI: Use .get() para acessar as colunas, retornando 0 se não existirem
                total_agendado_geral = df_resumo["Total Agendado"].sum() if "Total Agendado" in df_resumo.columns else 0
                total_confirmado_geral = df_resumo.get("Marcado - confirmado", pd.Series([0])).sum() # Usar .get() com pd.Series([0])
                
                if total_agendado_geral > 0:
                    percentual_confirmacao = (total_confirmado_geral / total_agendado_geral) * 100
                else:
                    percentual_confirmacao = 0.0 # Garante que seja 0.0 se não há agendados

                all_status_cols = [col for col in df_resumo.columns if col not in ["Profissional", "Total Agendado"]]
                # Garante que total_ocupados e total_slots_disponiveis sejam 0 se não houver colunas relevantes
                total_ocupados = df_resumo["Total Agendado"].sum() if "Total Agendado" in df_resumo.columns else 0
                total_slots_disponiveis = df_resumo[all_status_cols].sum().sum() if all_status_cols else 0
                
                if total_slots_disponiveis > 0:
                    percentual_ocupacao = (total_ocupados / total_slots_disponiveis) * 100
                else:
                    percentual_ocupacao = 0.0 # Garante que seja 0.0 se não há slots

                # --- LÓGICA PARA CONFIRMAÇÃO E OCUPAÇÃO POR PROFISSIONAL ---
                profissionais_stats_confirmacao = [] # Reinicializa para garantir que sempre seja uma lista
                profissionais_stats_ocupacao = [] # Reinicializa para garantir que sempre seja uma lista

                for profissional, row in df_resumo.iterrows():
                    # Confirmação por profissional
                    agendados_prof = row.get("Total Agendado", 0) # Já usa .get()
                    confirmados_prof = row.get("Marcado - confirmado", 0) # <--- ESSA LINHA PRECISA USAR .get(..., 0)
                    percentual_prof_confirmacao = (confirmados_prof / agendados_prof * 100) if agendados_prof > 0 else 0.0
                    profissionais_stats_confirmacao.append({
                        "nome": profissional,
                        "agendados": agendados_prof,
                        "confirmados": confirmados_prof,
                        "percentual": f"{percentual_prof_confirmacao:.2f}"
                    })

                    # Ocupação por profissional
                    ocupados_prof = row.get("Total Agendado", 0) # Já usa .get()
                    # total_slots_prof deve somar todas as colunas de status exceto "Profissional" e "Total Agendado"
                    # Se 'all_status_cols' está vazio, a soma deve ser 0 para evitar erro.
                    # Aqui é um pouco mais complexo, pois row[all_status_cols].sum() pode dar erro se all_status_cols
                    # contiver uma coluna que não está no row. A melhor forma é garantir que all_status_cols
                    # contenha apenas colunas que realmente estão no df_resumo para aquele dia.
                    # Ou iterar sobre os status que realmente existem em 'row'.
                    
                    # Vamos manter a versão mais robusta:
                    total_slots_prof = 0
                    for status_col in all_status_cols:
                        total_slots_prof += row.get(status_col, 0) # Soma apenas as colunas que existem

                    percentual_prof_ocupacao = (ocupados_prof / total_slots_prof * 100) if total_slots_prof > 0 else 0.0
                    profissionais_stats_ocupacao.append({
                        "nome": profissional,
                        "ocupados": ocupados_prof,
                        "total_slots": total_slots_prof,
                        "percentual": f"{percentual_prof_ocupacao:.2f}"
                    })

    return render_template(
        'index.html',
        selected_date=selected_date_str,
        agendas=agendas_por_profissional,
        status_styles=STATUS_STYLES,
        agenda_url_template=AGENDA_URL_TEMPLATE,
        resumo_geral=resumo_geral,
        df_resumo_html=df_resumo.T.to_html(classes='table table-striped') if not df_resumo.empty else "",
        total_agendado_geral=total_agendado_geral,
        total_confirmado_geral=total_confirmado_geral,
        percentual_confirmacao=f"{percentual_confirmacao:.2f}",
        total_ocupados=total_ocupados,
        total_slots_disponiveis=total_slots_disponiveis,
        percentual_ocupacao=f"{percentual_ocupacao:.2f}",
        profissionais_stats_confirmacao=profissionais_stats_confirmacao,
        profissionais_stats_ocupacao=profissionais_stats_ocupacao
    )

# NOVO ENDPOINT para buscar detalhes do paciente
@app.route('/api/patient_details/<int:patient_id>', methods=['GET'])
def patient_details_api(patient_id):
    details = get_patient_details(patient_id)
    if details:
        return jsonify(details)
    else:
        return jsonify({"error": "Paciente não encontrado ou erro na API"}), 404

# NOVO ENDPOINT para buscar detalhes do agendamento (completo)
@app.route('/api/appointment_details/<int:appointment_id>', methods=['GET'])
def appointment_details_api(appointment_id):
    details = get_appointment_details(appointment_id)
    if details:
        return jsonify(details)
    else:
        return jsonify({"error": "Agendamento não encontrado ou erro na API"}), 404

if __name__ == '__main__':
    app.run(debug=True)