# firebase_cache_manager.py

from datetime import date
from firebase_admin import credentials, firestore
import firebase_admin

# --- INICIALIZAÇÃO DO FIREBASE ---
# Coloque este bloco de código no seu arquivo principal (app.py) 
# ou garanta que ele rode uma única vez quando sua aplicação iniciar.

try:
    # Carregue suas credenciais (o arquivo .json que você baixou)
    cred = credentials.Certificate("chave_firebase.json")
    firebase_admin.initialize_app(cred)
    print("Conexão com o Firebase estabelecida!")
except ValueError:
    # Evita erro se o app for inicializado mais de uma vez (comum em dev com Flask)
    print("O app do Firebase já foi inicializado.")

# Crie um cliente para interagir com o Firestore
db = firestore.client()
# -----------------------------------


def _get_month_document_ref(target_date: date, unit_id: str):
    """Retorna a referência do documento no Firestore para o mês/unidade alvo."""
    month_year = target_date.strftime('%Y-%m')
    document_id = f"{unit_id}_{month_year}"
    return db.collection('agendas_cache').document(document_id)

def save_agendas_to_cache(day_data: dict, target_date: date, unit_id: str):
    """Salva ou atualiza os dados de um dia específico no Firestore."""
    doc_ref = _get_month_document_ref(target_date, unit_id)
    day_key = target_date.strftime('%Y-%m-%d')
    
    try:
        # Usa .set com merge=True para criar o documento se não existir
        # ou atualizar/adicionar o campo do dia sem apagar os outros dias.
        doc_ref.set({day_key: day_data}, merge=True)
        print(f"Dados para {day_key} (unidade: {unit_id}) salvos/atualizados no Firestore.")
    except Exception as e:
        print(f"Erro CRÍTICO ao salvar agendas no Firestore para o dia {day_key}. Erro: {e}")

def load_agendas_from_cache(target_date: date, unit_id: str) -> dict | None:
    """Carrega os dados de um dia específico do cache no Firestore."""
    doc_ref = _get_month_document_ref(target_date, unit_id)
    day_key = target_date.strftime('%Y-%m-%d')
    
    try:
        doc = doc_ref.get()
        if doc.exists:
            month_cache = doc.to_dict()
            day_data = month_cache.get(day_key)
            if day_data:
                print(f"Dados para {day_key} (unidade: {unit_id}) carregados do Firestore.")
                return day_data
            else:
                print(f"Dados para o dia {day_key} não encontrados no documento do mês.")
                return None
        else:
            print(f"Documento de cache para o mês {target_date.strftime('%Y-%m')} (unidade: {unit_id}) não encontrado.")
            return None
    except Exception as e:
        print(f"Erro ao carregar agendas do Firestore para o dia {day_key}. Erro: {e}")
        return None

def delete_day_from_cache(target_date: date, unit_id: str):
    """Remove os dados de um dia específico do cache no Firestore."""
    doc_ref = _get_month_document_ref(target_date, unit_id)
    day_key = target_date.strftime('%Y-%m-%d')
    
    try:
        # Para remover um campo de um documento, usamos a constante DELETE_FIELD
        doc_ref.update({day_key: firestore.DELETE_FIELD})
        print(f"Dados do dia {day_key} (unidade: {unit_id}) removidos do Firestore.")
    except Exception as e:
        print(f"Erro ao deletar agendas do Firestore para o dia {day_key}. Erro: {e}")