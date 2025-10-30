# app/metrics.py

import pandas as pd

def calculate_summary_metrics(resumo_geral, df_resumo):
    """Calcula as métricas de resumo para os cards principais."""
    
    df = df_resumo
    
    # Inicializa contadores
    total_horarios_disponiveis = 0
    total_horarios_ocupados = 0
    total_horarios_confirmados = 0
    
    # Percorre cada profissional (linha do DataFrame)
    for profissional, row in df.iterrows():
        profissional_total = 0
        profissional_ocupados = 0
        profissional_confirmados = 0
        
        # Percorre cada coluna (status) do profissional
        for status, quantidade in row.items():
            # Total de horários disponíveis é a soma de TODOS os status
            profissional_total += quantidade
            
            # Verifica se é um horário ocupado (não é Livre nem Bloqueado)
            if status not in ['Livre', 'Bloqueado']:
                profissional_ocupados += quantidade
                
                # Verifica se é confirmado
                if 'confirmado' in status.lower():
                    profissional_confirmados += quantidade
        
        # Adiciona ao total geral (inclui profissionais com apenas "Livre")
        total_horarios_disponiveis += profissional_total
        total_horarios_ocupados += profissional_ocupados
        total_horarios_confirmados += profissional_confirmados
    
    # Calcula as porcentagens
    taxa_ocupacao = (total_horarios_ocupados / total_horarios_disponiveis * 100) if total_horarios_disponiveis > 0 else 0
    taxa_confirmacao = (total_horarios_confirmados / total_horarios_ocupados * 100) if total_horarios_ocupados > 0 else 0
    
    return {
        "total_agendado_geral": int(total_horarios_ocupados),
        "total_confirmado_geral": int(total_horarios_confirmados),
        "percentual_confirmacao": f"{taxa_confirmacao:.2f}%",
        "total_ocupados": int(total_horarios_ocupados),
        "total_slots_disponiveis": int(total_horarios_disponiveis),
        "percentual_ocupacao": f"{taxa_ocupacao:.2f}%"
    }

def calculate_confirmation_ranking(df):
    """Calcula o ranking de taxa de confirmação por profissional."""
    stats = []
    
    for prof, row in df.iterrows():
        total_ocupados_prof = 0
        total_confirmados_prof = 0
        
        for status, quantidade in row.items():
            # Horários ocupados do profissional
            if status not in ['Livre', 'Bloqueado']:
                total_ocupados_prof += quantidade
                
                # Horários confirmados do profissional
                if 'confirmado' in status.lower():
                    total_confirmados_prof += quantidade
        
        # Inclui TODOS os profissionais, mesmo os que só têm "Livre" (total_ocupados_prof = 0)
        taxa = (total_confirmados_prof / total_ocupados_prof * 100) if total_ocupados_prof > 0 else 0
        stats.append({
            "profissional": prof,
            "taxa_confirmacao": f"{taxa:.2f}%",
            "total_ocupados": int(total_ocupados_prof),
            "total_confirmados": int(total_confirmados_prof)
        })
    
    return sorted(stats, key=lambda x: float(x['taxa_confirmacao'][:-1]), reverse=True)

def calculate_occupation_ranking(df):
    """Calcula o ranking de taxa de ocupação por profissional."""
    stats = []

    for prof, row in df.iterrows():
        total_slots_prof = row.sum()
        total_ocupados_prof = 0
        
        for status, quantidade in row.items():
            if status not in ['Livre', 'Bloqueado']:
                total_ocupados_prof += quantidade
        
        # Inclui TODOS os profissionais, mesmo os que só têm "Livre"
        taxa = (total_ocupados_prof / total_slots_prof * 100) if total_slots_prof > 0 else 0
        stats.append({
            "profissional": prof,
            "taxa_ocupacao": f"{taxa:.2f}%",
            "total_slots": int(total_slots_prof),
            "total_ocupados": int(total_ocupados_prof)
        })
        
    return sorted(stats, key=lambda x: float(x['taxa_ocupacao'][:-1]), reverse=True)

def calculate_conversion_ranking(df):
    """Calcula o ranking de taxa de conversão (comparecimento) por profissional."""
    stats = []
    
    for prof, row in df.iterrows():
        # Atendidos: status que representam pacientes que foram atendidos
        atendidos = 0
        status_atendidos = ['atendido', 'atendimento concluído', 'finalizado', 'aguardando pós-consulta']
        for status, quantidade in row.items():
            if any(s in status.lower() for s in status_atendidos):
                atendidos += quantidade
        
        # Total de agendamentos válidos (ocupados)
        total_agendamentos = 0
        for status, quantidade in row.items():
            if status not in ['Livre', 'Bloqueado']:
                total_agendamentos += quantidade
        
        # Inclui TODOS os profissionais, mesmo os que só têm "Livre"
        taxa = (atendidos / total_agendamentos * 100) if total_agendamentos > 0 else 0
        stats.append({
            "profissional": prof,
            "taxa_conversao": f"{taxa:.2f}%",
            "total_agendamentos": int(total_agendamentos),
            "total_atendidos": int(atendidos)
        })
    
    return sorted(stats, key=lambda x: float(x['taxa_conversao'][:-1]), reverse=True)

def calculate_global_conversion_rate(df):
    """Calcula a taxa de conversão geral para o card de resumo."""
    if df.empty:
        return {"conversion_rate": "0.00%", "total_atendidos": 0}

    total_atendidos = 0
    total_agendamentos = 0
    
    status_atendidos = ['atendido', 'atendimento concluído', 'finalizado', 'aguardando pós-consulta']
    
    for _, row in df.iterrows():
        for status, quantidade in row.items():
            # Total de agendamentos (exclui Livre e Bloqueado)
            if status not in ['Livre', 'Bloqueado']:
                total_agendamentos += quantidade
            
            # Total de atendidos
            if any(s in status.lower() for s in status_atendidos):
                total_atendidos += quantidade
    
    taxa = (total_atendidos / total_agendamentos * 100) if total_agendamentos > 0 else 0
    
    return {
        "conversion_rate": f"{taxa:.2f}%",
        "total_atendidos": int(total_atendidos)
    }