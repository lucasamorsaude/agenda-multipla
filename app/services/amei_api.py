# app/services/amei_api.py
import requests

PROFISSIONAIS_URL = 'https://amei.amorsaude.com.br/api/v1/profissionais/by-unidade'
SLOTS_URL = 'https://amei.amorsaude.com.br/api/v1/slots/list-slots-by-professional'
PACIENTE_URL_TEMPLATE = 'https://amei.amorsaude.com.br/api/v1/pacientes/{}'
APPOINTMENT_URL_TEMPLATE = 'https://amei.amorsaude.com.br/api/v1/appointments/{}'

def get_all_professionals(headers):
    try:
        response = requests.get(PROFISSIONAIS_URL, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão ao buscar profissionais: {e}")
        return None

def get_slots_for_professional(professional_id, selected_date, clinic_id, headers):
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
        response = requests.get(SLOTS_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        if data and isinstance(data, list) and len(data) > 0:
            return data[0].get('hours', [])
        else:
            return []
    except requests.exceptions.RequestException:
        return []

def get_patient_details(patient_id, headers):
    if not patient_id:
        return None
    try:
        url = PACIENTE_URL_TEMPLATE.format(patient_id)
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar detalhes do paciente {patient_id}: {e}")
        return None

def get_appointment_details(appointment_id, headers):
    if not appointment_id:
        return None
    try:
        url = APPOINTMENT_URL_TEMPLATE.format(appointment_id)
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar detalhes do agendamento {appointment_id}: {e}")
        return None