import json
from datetime import date, timedelta
import os
import tempfile

CACHE_DIR = 'cache'
CACHE_FILE_TEMPLATE = '{}/agendas_cache_{}.json' # cache/agendas_cache_YYYY-MM.json

def _get_cache_file_path(target_date: date):
    """Retorna o caminho completo do arquivo de cache para o mês da data alvo."""
    month_year = target_date.strftime('%Y-%m')
    os.makedirs(CACHE_DIR, exist_ok=True) # Garante que o diretório 'cache' exista
    return CACHE_FILE_TEMPLATE.format(CACHE_DIR, month_year)

def save_agendas_to_cache(day_data: dict, target_date: date):
    """
    Salva ou atualiza os dados de um dia específico no arquivo de cache do mês.
    'day_data' deve conter todas as informações processadas para aquele dia.
    Implementa escrita atômica para evitar arquivos corrompidos.
    """
    file_path = _get_cache_file_path(target_date)
    month_cache = {}

    # Tenta carregar o cache existente para o mês
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                month_cache = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Aviso: Cache de {file_path} corrompido, recriando. Erro: {e}")
            month_cache = {} # Se corrompido, inicia um novo cache vazio
        except IOError as e: # Adicionado para capturar erros de leitura
            print(f"Aviso: Erro ao ler cache {file_path}, recriando. Erro: {e}")
            month_cache = {}

    # Atualiza ou adiciona os dados para o dia específico
    day_key = target_date.strftime('%Y-%m-%d')
    month_cache[day_key] = day_data # Salva os dados do dia sob a chave da data

    # --- Início da escrita atômica ---
    # Cria um arquivo temporário no mesmo diretório para garantir que o rename funcione entre sistemas de arquivos
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', dir=CACHE_DIR) as temp_file:
            json.dump(month_cache, temp_file, ensure_ascii=False, indent=4)
            temp_file_path = temp_file.name # Armazena o nome do arquivo temporário

        # Se a escrita foi bem-sucedida, renomeia o arquivo temporário para o nome final
        os.replace(temp_file_path, file_path) # os.replace é atômico (ou falha)
        print(f"Dados para {day_key} salvos/atualizados no cache: {file_path}")

    except Exception as e: # Captura qualquer erro durante a escrita ou renomeação
        print(f"Erro CRÍTICO ao salvar agendas no cache {file_path}. O arquivo pode estar corrompido. Erro: {e}")
        # Tenta limpar o arquivo temporário se ele foi criado e o erro ocorreu antes do rename
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
    # --- Fim da escrita atômica ---

def load_agendas_from_cache(target_date: date) -> dict | None:
    """
    Carrega os dados de um dia específico do arquivo de cache para o mês.
    Retorna o dicionário de dados para o dia, ou None se o arquivo/dia não existir ou houver erro.
    """
    file_path = _get_cache_file_path(target_date)
    if not os.path.exists(file_path):
        print(f"Arquivo de cache para o mês {target_date.strftime('%Y-%m')} não encontrado: {file_path}")
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            month_cache = json.load(f)
        
        day_key = target_date.strftime('%Y-%m-%d')
        day_data = month_cache.get(day_key)
        
        if day_data:
            print(f"Dados para {day_key} carregados do cache: {file_path}")
            return day_data
        else:
            print(f"Dados para o dia {day_key} não encontrados no cache mensal.")
            return None
            
    except json.JSONDecodeError as e:
        print(f"Erro ao decodificar JSON do cache {file_path}: {e}")
        return None
    except IOError as e:
        print(f"Erro ao ler arquivo de cache {file_path}: {e}")
        return None

def delete_day_from_cache(target_date: date):
    """
    Remove os dados de um dia específico do arquivo de cache do mês.
    """
    file_path = _get_cache_file_path(target_date)
    day_key = target_date.strftime('%Y-%m-%d')
    month_cache = {}

    if not os.path.exists(file_path):
        print(f"Cache do mês {target_date.strftime('%Y-%m')} não encontrado para exclusão do dia {day_key}.")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            month_cache = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Aviso: Cache de {file_path} corrompido ao tentar excluir dia {day_key}. Erro: {e}")
        print("Removendo o arquivo corrompido para evitar futuros problemas.")
        os.remove(file_path) # Remove o arquivo corrompido para começar do zero
        return
    except IOError as e:
        print(f"Erro ao ler arquivo de cache {file_path} para exclusão do dia {day_key}: {e}")
        return

    if day_key in month_cache:
        del month_cache[day_key]
        print(f"Dados do dia {day_key} removidos do cache mensal.")

        # Re-salvar o cache do mês sem os dados do dia removido
        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', dir=CACHE_DIR) as temp_file:
                json.dump(month_cache, temp_file, ensure_ascii=False, indent=4)
                temp_file_path = temp_file.name

            os.replace(temp_file_path, file_path)
            print(f"Cache mensal atualizado após exclusão do dia {day_key}.")
        except Exception as e:
            print(f"Erro CRÍTICO ao re-salsalvar cache do mês após exclusão do dia {day_key}: {e}")
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    else:
        print(f"Dados do dia {day_key} não encontrados no cache mensal para exclusão.")


# Exemplo de uso (apenas para teste, não será chamado pelo Flask diretamente)
if __name__ == '__main__':
    test_date_today = date.today()
    test_date_tomorrow = date.today() + timedelta(days=1) # Importar timedelta

    sample_data_today = {
        "agendas_por_profissional": {
            "Profissional A": {"id": 1, "horarios": [{"horario": "08:00", "paciente": "Teste Hoje"}]},
        },
        "resumo_geral": {"Profissional A": {"Marcado - confirmado": 1}},
        "df_resumo_html": "<table>...</table>",
        "summary_metrics": {"total_agendado_geral": 1},
        "profissionais_stats_confirmacao": [],
        "profissionais_stats_ocupacao": [],
        "conversion_data_for_selected_day": {"total_atendidos": 0}
    }
    
    sample_data_tomorrow = {
        "agendas_por_profissional": {
            "Profissional B": {"id": 2, "horarios": [{"horario": "09:00", "paciente": "Exemplo Amanhã"}]}
        },
        "resumo_geral": {"Profissional B": {"Marcado - confirmado": 1}},
        "df_resumo_html": "<table>...</table>",
        "summary_metrics": {"total_agendado_geral": 1},
        "profissionais_stats_confirmacao": [],
        "profissionais_stats_ocupacao": [],
        "conversion_data_for_selected_day": {"total_atendidos": 0}
    }

    # Simula o salvamento para dois dias diferentes no mesmo mês
    save_agendas_to_cache(sample_data_today, test_date_today)
    save_agendas_to_cache(sample_data_tomorrow, test_date_tomorrow)

    # Teste de carregamento para um dia específico
    loaded_data_today = load_agendas_from_cache(test_date_today)
    if loaded_data_today:
        print("\nDados carregados para hoje:")
        print(json.dumps(loaded_data_today, indent=4, ensure_ascii=False))
    
    loaded_data_tomorrow = load_agendas_from_cache(test_date_tomorrow)
    if loaded_data_tomorrow:
        print("\nDados carregados para amanhã:")
        print(json.dumps(loaded_data_tomorrow, indent=4, ensure_ascii=False))

    # Teste de remoção (descomente para testar)
    # clear_cache_for_month(test_date_today)
    # loaded_data_after_clear = load_agendas_from_cache(test_date_today)
    # if loaded_data_after_clear is None:
    #     print("\nCache do mês removido com sucesso!")