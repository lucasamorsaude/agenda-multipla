# app/routes/api_routes.py
from flask import Blueprint, jsonify, session
from login_auth import get_auth_new
from app.services.amei_api import get_patient_details, get_appointment_details

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/patient_details/<int:patient_id>')
def patient_details_api(patient_id):
    if 'selected_unit_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    id_unidade_selecionada = session['selected_unit_id']
    auth = get_auth_new(id_unidade_selecionada)
    
    from flask import current_app
    HEADERS = {'Authorization': f"Bearer {auth}", 'Cookie': current_app.config['COOKIE_VALUE']}
    
    details = get_patient_details(patient_id, HEADERS)
    
    if details: return jsonify(details)
    else: return jsonify({"error": "Paciente não encontrado"}), 404

@api_bp.route('/api/appointment_details/<int:appointment_id>')
def appointment_details_api(appointment_id):
    if 'selected_unit_id' not in session: return jsonify({"error": "Unauthorized"}), 401
    
    id_unidade_selecionada = session['selected_unit_id']
    auth = get_auth_new(id_unidade_selecionada)

    from flask import current_app
    HEADERS = {'Authorization': f"Bearer {auth}", 'Cookie': current_app.config['COOKIE_VALUE']}
    
    details = get_appointment_details(appointment_id, HEADERS)
    
    if details: return jsonify(details)
    else: return jsonify({"error": "Agendamento não encontrado"}), 404