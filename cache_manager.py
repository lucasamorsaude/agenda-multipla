# app/cache_manager.py

import os
import json
from datetime import date
from supabase import create_client, Client
from dotenv import load_dotenv

# --- INICIALIZAÇÃO DO CLIENTE SUPABASE ---
load_dotenv()
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(url, key)

# --- FUNÇÕES DO CACHE ---

def save_agendas_to_cache_v2(context: dict, target_date: date, unit_id: str):
    """Salva os dados de agenda e métricas nas tabelas do Supabase."""
    try:
        unit_id_int = int(unit_id)
        date_str = target_date.strftime('%Y-%m-%d')
        
        # 1. Separa os dados das agendas do contexto principal
        agendas_data = context.pop("agendas", {})

        # 2. Salva (ou atualiza) o resumo na tabela 'agendas_cache_summary'
        # O 'context' restante vai para a coluna JSONB 'summary_data'
        summary_payload = {
            "unit_id": unit_id_int,
            "target_date": date_str,
            "summary_data": context
        }
        supabase.table('agendas_cache_summary').upsert(summary_payload).execute()

        # 3. Prepara e salva os detalhes das agendas na tabela 'agendas_cache_details'
        if agendas_data:
            details_payload = []
            for prof_nome, prof_data in agendas_data.items():
                prof_id = prof_data.get("id")
                if prof_id:
                    details_payload.append({
                        "unit_id": unit_id_int,
                        "target_date": date_str,
                        "professional_id": prof_id,
                        "professional_name": prof_nome,
                        "schedule_data": prof_data # O dict inteiro do profissional vai para o JSONB
                    })
            
            if details_payload:
                supabase.table('agendas_cache_details').upsert(details_payload).execute()

        print(f"Cache para {date_str} (unidade: {unit_id}) salvo com sucesso no Supabase.")

    except Exception as e:
        print(f"Erro CRÍTICO ao salvar cache no Supabase. Erro: {e}")
        # Adiciona os dados de volta ao context em caso de falha
        context['agendas'] = agendas_data

def load_agendas_from_cache_v2(target_date: date, unit_id: str) -> dict | None:
    """Carrega os dados de agenda e métricas do cache do Supabase."""
    try:
        unit_id_int = int(unit_id)
        date_str = target_date.strftime('%Y-%m-%d')

        # 1. Carrega o resumo da tabela principal
        summary_response = supabase.table('agendas_cache_summary') \
            .select('summary_data') \
            .eq('unit_id', unit_id_int) \
            .eq('target_date', date_str) \
            .maybe_single() \
            .execute()

        if not summary_response.data:
            print(f"Cache para o dia {date_str} (unidade: {unit_id}) não encontrado.")
            return None
        
        # O contexto principal vem da coluna 'summary_data'
        context = summary_response.data['summary_data']
        context['agendas'] = {}

        # 2. Carrega todas as agendas de profissionais da tabela de detalhes
        details_response = supabase.table('agendas_cache_details') \
            .select('professional_name, schedule_data') \
            .eq('unit_id', unit_id_int) \
            .eq('target_date', date_str) \
            .execute()

        # 3. Remonta o dicionário 'agendas' no formato original
        if details_response.data:
            for item in details_response.data:
                prof_nome = item['professional_name']
                context['agendas'][prof_nome] = item['schedule_data']

        print(f"Cache para {date_str} (unidade: {unit_id}) carregado com sucesso do Supabase.")
        return context

    except Exception as e:
        print(f"Erro CRÍTICO ao carregar cache do Supabase. Erro: {e}")
        return None

def delete_day_from_cache_v2(target_date: date, unit_id: str):
    """
    Deleta o cache de um dia. MUITO MAIS SIMPLES com SQL!
    """
    try:
        unit_id_int = int(unit_id)
        date_str = target_date.strftime('%Y-%m-%d')

        # Graças ao "ON DELETE CASCADE" que definimos no SQL,
        # basta deletar o registro da tabela de resumo.
        # O banco de dados se encarrega de deletar todos os detalhes associados.
        supabase.table('agendas_cache_summary') \
            .delete() \
            .eq('unit_id', unit_id_int) \
            .eq('target_date', date_str) \
            .execute()
        
        print(f"Cache para {date_str} (unidade: {unit_id}) deletado com sucesso do Supabase.")

    except Exception as e:
        print(f"Erro CRÍTICO ao deletar cache do Supabase para o dia {date_str}. Erro: {e}")