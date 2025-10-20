# firebase_cache_manager.py

from datetime import date
from firebase_admin import credentials, firestore
import firebase_admin
from dotenv import load_dotenv
import os
import json

# --- INICIALIZAÇÃO DO FIREBASE ---
# Coloque este bloco de código no seu arquivo principal (app.py) 
# ou garanta que ele rode uma única vez quando sua aplicação iniciar.

# Carrega as variáveis do arquivo .env para o ambiente
load_dotenv()

cred = None

# 1. Tenta carregar do ambiente (Modo Produção - Railway)
cred_json_string = os.environ.get('FIREBASE_CREDENTIALS_JSON')
if cred_json_string:
    print("Iniciando em modo PRODUÇÃO (Railway)")
    cred_dict = json.loads(cred_json_string)
    cred = credentials.Certificate(cred_dict)
else:
    # 2. Tenta carregar do caminho no .env (Modo Local)
    cred_path = os.environ.get('FIREBASE_CREDENTIALS_PATH')
    if cred_path:
        print("Iniciando em modo LOCAL")
        cred = credentials.Certificate(cred_path)
    else:
        print("Erro: Nenhuma credencial do Firebase encontrada.")

# Inicializa o app se a credencial foi carregada
if cred and not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
else:
    print("Firebase já inicializado ou credenciais ausentes.")

# Crie um cliente para interagir com o Firestore
db = firestore.client()
# -----------------------------------


def _get_day_document_ref(target_date: date, unit_id: str):
    """NOVO: Retorna a referência do documento para o DIA específico."""
    document_id = f"{unit_id}_{target_date.strftime('%Y-%m-%d')}"
    return db.collection('agendas_cache').document(document_id)

def save_agendas_to_cache_v2(context: dict, target_date: date, unit_id: str):
    """
    NOVA VERSÃO OTIMIZADA: Salva métricas no documento principal e agendas em uma subcoleção.
    """
    day_doc_ref = _get_day_document_ref(target_date, unit_id)
    agendas_data = context.pop("agendas", {}) # Remove as agendas do context principal

    try:
        # Usa um batch para garantir que tudo seja salvo de uma vez (operação atômica)
        batch = db.batch()

        # 1. Salva as métricas e o resto do context no documento do dia
        batch.set(day_doc_ref, context)

        # 2. Itera sobre os profissionais e salva cada um em um documento separado na subcoleção
        agendas_subcollection = day_doc_ref.collection('agendas')
        for prof_nome, prof_data in agendas_data.items():
            prof_id = prof_data.get("id")
            if prof_id:
                prof_doc_ref = agendas_subcollection.document(str(prof_id))
                batch.set(prof_doc_ref, prof_data)

        # 3. Commita o batch
        batch.commit()
        print(f"Cache V2 para {target_date.strftime('%Y-%m-%d')} (unidade: {unit_id}) salvo com sucesso.")

    except Exception as e:
        print(f"Erro CRÍTICO ao salvar cache V2 no Firestore. Erro: {e}")
        # Se deu erro, adiciona as agendas de volta ao context para não perder os dados na memória
        context['agendas'] = agendas_data

def load_agendas_from_cache_v2(target_date: date, unit_id: str) -> dict | None:
    """
    NOVA VERSÃO OTIMIZADA: Carrega o documento do dia e a subcoleção de agendas.
    """
    day_doc_ref = _get_day_document_ref(target_date, unit_id)
    
    try:
        # 1. Carrega o documento principal (métricas)
        doc = day_doc_ref.get()
        if not doc.exists:
            print(f"Cache V2 para o dia {target_date.strftime('%Y-%m-%d')} não encontrado.")
            return None
        
        context = doc.to_dict()
        context['agendas'] = {}

        # 2. Carrega todos os documentos da subcoleção de agendas
        agendas_subcollection = day_doc_ref.collection('agendas')
        for prof_doc in agendas_subcollection.stream():
            prof_data = prof_doc.to_dict()
            prof_nome = prof_data.get('nome', prof_doc.id) # Usa o nome do profissional se disponível
            context['agendas'][prof_nome] = prof_data
        
        print(f"Cache V2 para {target_date.strftime('%Y-%m-%d')} carregado com sucesso.")
        return context

    except Exception as e:
        print(f"Erro CRÍTICO ao carregar cache V2 do Firestore. Erro: {e}")
        return None

def delete_day_from_cache_v2(target_date: date, unit_id: str):
    """
    NOVA VERSÃO: Deleta o documento do dia e TODOS os documentos na sua subcoleção de agendas.
    """
    day_doc_ref = _get_day_document_ref(target_date, str(unit_id))
    
    try:
        # PASSO 1: Deletar todos os documentos da subcoleção 'agendas' em lotes.
        # Esta é a maneira recomendada pelo Google para deletar subcoleções inteiras.
        agendas_subcollection = day_doc_ref.collection('agendas')
        
        # O loop continua enquanto houver documentos a serem deletados no lote.
        while True:
            # Pega um lote de até 500 documentos (limite do batch)
            docs_to_delete = agendas_subcollection.limit(500).stream()
            
            batch = db.batch()
            doc_count_in_batch = 0
            
            for doc in docs_to_delete:
                batch.delete(doc.reference)
                doc_count_in_batch += 1
            
            # Se não encontrou nenhum documento no lote, a subcoleção está vazia.
            if doc_count_in_batch == 0:
                break
                
            # Envia o lote de deleções para o Firestore
            batch.commit()
            print(f"Lote de {doc_count_in_batch} documentos de agenda deletado.")

        # PASSO 2: Depois que a subcoleção estiver vazia, deletar o documento principal.
        day_doc_ref.delete()
        
        print(f"Cache V2 para {target_date.strftime('%Y-%m-%d')} (unidade: {unit_id}) deletado com sucesso.")

    except Exception as e:
        print(f"Erro CRÍTICO ao deletar cache V2 do Firestore para o dia {target_date.strftime('%Y-%m-%d')}. Erro: {e}")
