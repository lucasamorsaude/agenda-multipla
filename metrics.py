# metrics.py
import pandas as pd

def calculate_summary_metrics(resumo_geral, df_resumo_full):
    """
    Calcula as métricas gerais de confirmação e ocupação.

    Args:
        resumo_geral (dict): Dicionário com a contagem de status por profissional.
        df_resumo_full (pd.DataFrame): DataFrame completo com resumo de slots por profissional.

    Returns:
        dict: Contendo total_agendado_geral, total_confirmado_geral, percentual_confirmacao,
              total_ocupados, total_slots_disponiveis, percentual_ocupacao.
    """
    total_agendado_geral = 0
    total_confirmado_geral = 0
    percentual_confirmacao = 0.0
    total_ocupados = 0
    total_slots_disponiveis = 0
    percentual_ocupacao = 0.0

    if not df_resumo_full.empty:
        # Colunas a serem consideradas para "Total Agendado"
        # AGORA EXCLUI "Livre", "Bloqueado" E "Encaixe"
        status_para_total_agendado = [col for col in df_resumo_full.columns if col not in ["Profissional", "Livre", "Bloqueado", "Encaixe"]]
        
        # Garante que 'Total Agendado' seja calculado apenas com colunas relevantes
        if status_para_total_agendado:
            df_resumo_full["Total Agendado"] = df_resumo_full[status_para_total_agendado].sum(axis=1)
        else:
            df_resumo_full["Total Agendado"] = 0

        # Converte para int() para garantir compatibilidade com JSON
        total_agendado_geral = int(df_resumo_full["Total Agendado"].sum()) if "Total Agendado" in df_resumo_full.columns else 0
        total_confirmado_geral = int(df_resumo_full.get("Marcado - confirmado", pd.Series([0])).sum())

        if total_agendado_geral > 0:
            percentual_confirmacao = (total_confirmado_geral / total_agendado_geral) * 100

        # Para ocupação, consideramos todos os slots (Livre, Bloqueado, etc.)
        all_status_cols_for_occupancy = [col for col in df_resumo_full.columns if col not in ["Profissional", "Total Agendado"]]
        # Converte para int() para garantir compatibilidade com JSON
        total_ocupados = int(df_resumo_full["Total Agendado"].sum()) if "Total Agendado" in df_resumo_full.columns else 0
        total_slots_disponiveis = int(df_resumo_full[all_status_cols_for_occupancy].sum().sum()) if all_status_cols_for_occupancy else 0
        
        if total_slots_disponiveis > 0:
            percentual_ocupacao = (total_ocupados / total_slots_disponiveis) * 100

    return {
        "total_agendado_geral": total_agendado_geral,
        "total_confirmado_geral": total_confirmado_geral,
        "percentual_confirmacao": f"{percentual_confirmacao:.2f}",
        "total_ocupados": total_ocupados,
        "total_slots_disponiveis": total_slots_disponiveis,
        "percentual_ocupacao": f"{percentual_ocupacao:.2f}"
    }

def calculate_professional_metrics(df_resumo_full):
    """
    Calcula as métricas de confirmação e ocupação por profissional.

    Args:
        df_resumo_full (pd.DataFrame): DataFrame completo com resumo de slots por profissional.

    Returns:
        tuple: Duas listas de dicionários, uma para confirmação e outra para ocupação por profissional.
    """
    profissionais_stats_confirmacao = []
    profissionais_stats_ocupacao = []

    if not df_resumo_full.empty:
        # AGORA EXCLUI "Livre", "Bloqueado" E "Encaixe" para o total agendado
        status_para_total_agendado = [col for col in df_resumo_full.columns if col not in ["Profissional", "Livre", "Bloqueado", "Encaixe"]]
        all_status_cols_for_occupancy = [col for col in df_resumo_full.columns if col not in ["Profissional", "Total Agendado"]]

        for profissional, row in df_resumo_full.iterrows():
            # Converte para int() para garantir compatibilidade com JSON
            agendados_prof = int(row.get("Total Agendado", 0)) 
            confirmados_prof = int(row.get("Marcado - confirmado", 0))
            percentual_prof_confirmacao = (confirmados_prof / agendados_prof * 100) if agendados_prof > 0 else 0.0
            profissionais_stats_confirmacao.append({
                "nome": profissional,
                "agendados": agendados_prof,
                "confirmados": confirmados_prof,
                "percentual": f"{percentual_prof_confirmacao:.2f}"
            })

            # Ocupação por profissional
            # Converte para int() para garantir compatibilidade com JSON
            ocupados_prof = int(row.get("Total Agendado", 0)) 
            total_slots_prof = 0
            for status_col in all_status_cols_for_occupancy:
                total_slots_prof += int(row.get(status_col, 0)) # Converte para int()
            
            percentual_prof_ocupacao = (ocupados_prof / total_slots_prof * 100) if total_slots_prof > 0 else 0.0
            profissionais_stats_ocupacao.append({
                "nome": profissional,
                "ocupados": ocupados_prof,
                "total_slots": total_slots_prof,
                "percentual": f"{percentual_prof_ocupacao:.2f}"
            })
            
    return profissionais_stats_confirmacao, profissionais_stats_ocupacao

def calculate_conversion_rate_for_date(target_date, get_all_professionals_func, get_slots_for_professional_func):
    """
    Calcula a taxa de conversão de atendimentos para uma data específica.

    Args:
        target_date (datetime.date): A data para a qual a conversão deve ser calculada.
        get_all_professionals_func (function): Função para obter todos os profissionais.
        get_slots_for_professional_func (function): Função para obter slots por profissional.

    Returns:
        dict: Dados de conversão geral e por profissional.
    """
    total_atendidos = 0
    total_agendamentos_validos = 0 
    
    profissionais = get_all_professionals_func()
    
    if not profissionais:
        return {
            "date": target_date.strftime('%d/%m/%Y'),
            "total_atendidos": 0,
            "total_agendamentos_validos": 0,
            "conversion_rate": "0.00%",
            "details_by_professional": []
        }

    details_by_professional = []

    for prof in profissionais:
        prof_id = prof.get('id')
        prof_nome = prof.get('nome', f'Profissional ID {prof_id}')
        
        slots = get_slots_for_professional_func(prof_id, target_date)
        
        prof_atendidos = 0
        prof_agendamentos_validos = 0

        for slot in slots:
            final_status = slot.get('appointmentStatus', slot.get('status', 'Indefinido')) 
            
            if final_status in ["Atendido", "Atendido pós-consulta","Não compareceu pós-consulta","Aguardando pós-consulta"]: 
                prof_atendidos += 1
            
            is_encaixe = slot.get('encaixe', False) 
            
            if final_status not in ["Vago"] and not is_encaixe: 
                prof_agendamentos_validos += 1
        
        # Converte para int() para garantir compatibilidade com JSON
        prof_atendidos = int(prof_atendidos)
        prof_agendamentos_validos = int(prof_agendamentos_validos)

        if prof_agendamentos_validos > 0: 
            total_atendidos += prof_atendidos
            total_agendamentos_validos += prof_agendamentos_validos

            prof_conversion_rate = (prof_atendidos / prof_agendamentos_validos * 100) if prof_agendamentos_validos > 0 else 0.0
            details_by_professional.append({
                "nome": prof_nome,
                "atendidos": prof_atendidos,
                "agendamentos_validos": prof_agendamentos_validos,
                "conversion_rate": f"{prof_conversion_rate:.2f}%"
            })

    # Converte para int() para garantir compatibilidade com JSON
    total_atendidos = int(total_atendidos)
    total_agendamentos_validos = int(total_agendamentos_validos)

    overall_conversion_rate = (total_atendidos / total_agendamentos_validos * 100) if total_agendamentos_validos > 0 else 0.0

    return {
        "date": target_date.strftime('%d/%m/%Y'),
        "total_atendidos": total_atendidos,
        "total_agendamentos_validos": total_agendamentos_validos,
        "conversion_rate": f"{overall_conversion_rate:.2f}%",
        "details_by_professional": sorted(details_by_professional, key=lambda x: x['nome'])
    }