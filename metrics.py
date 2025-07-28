# app/metrics.py

import pandas as pd

def calculate_summary_metrics(resumo_geral, df_resumo):
    """Calcula as métricas de resumo para os cards principais."""
    total_confirmado_geral = df_resumo.get("Marcado - confirmado", pd.Series(0)).sum()
    total_agendado_geral = sum(sum(d.values()) for d in resumo_geral.values())
    percentual_confirmacao = f"{(total_confirmado_geral / total_agendado_geral * 100):.2f}%" if total_agendado_geral > 0 else "0.00%"
    
    total_ocupados = total_agendado_geral - df_resumo.get("Livre", pd.Series(0)).sum() - df_resumo.get("Bloqueado", pd.Series(0)).sum()
    total_slots_disponiveis = total_agendado_geral
    percentual_ocupacao = f"{(total_ocupados / total_slots_disponiveis * 100):.2f}%" if total_slots_disponiveis > 0 else "0.00%"

    total_agendado_geral = total_ocupados
    
    return {
        "total_agendado_geral": int(total_agendado_geral),
        "total_confirmado_geral": int(total_confirmado_geral),
        "percentual_confirmacao": percentual_confirmacao,
        "total_ocupados": int(total_ocupados),
        "total_slots_disponiveis": int(total_slots_disponiveis),
        "percentual_ocupacao": percentual_ocupacao
    }

def calculate_confirmation_ranking(df):
    """Calcula o ranking de taxa de confirmação por profissional."""
    stats = []
    for prof, row in df.iterrows():
        confirmados = row.get('Marcado - confirmado', 0)
        total_agendamentos = row.sum() - row.get('Livre', 0) - row.get('Bloqueado', 0)
        taxa = (confirmados / total_agendamentos * 100) if total_agendamentos > 0 else 0
        stats.append({
            "profissional": prof,
            "taxa_confirmacao": f"{taxa:.2f}%"
        })
    return sorted(stats, key=lambda x: float(x['taxa_confirmacao'][:-1]), reverse=True)

def calculate_occupation_ranking(df):
    """Calcula o ranking de taxa de ocupação por profissional."""
    stats = []
    for prof, row in df.iterrows():
        ocupados = row.sum() - row.get('Livre', 0) - row.get('Bloqueado', 0)
        total_slots = row.sum()
        taxa = (ocupados / total_slots * 100) if total_slots > 0 else 0
        stats.append({
            "profissional": prof,
            "taxa_ocupacao": f"{taxa:.2f}%"
        })
    return sorted(stats, key=lambda x: float(x['taxa_ocupacao'][:-1]), reverse=True)

def calculate_conversion_ranking(df):
    """Calcula o ranking de taxa de conversão (comparecimento) por profissional."""
    stats = []
    # Adiciona colunas que podem não existir para evitar erros
    if 'Atendido' not in df.columns: df['Atendido'] = 0
    if 'Atendido pós-consulta' not in df.columns: df['Atendido pós-consulta'] = 0
    if 'Não compareceu' not in df.columns: df['Não compareceu'] = 0  #Check

    if 'Livre' not in df.columns: df['Livre'] = 0   #Check
    if 'Bloqueado' not in df.columns: df['Bloqueado'] = 0   #Check
    if 'Marcado - confirmado' not in df.columns: df['Marcado - confirmado'] = 0   #Check
    if 'Agendado' not in df.columns: df['Agendado'] = 0   #Check
    if 'Encaixe' not in df.columns: df['Encaixe'] = 0   #Check
    if 'Aguardando atendimento' not in df.columns: df['Aguardando atendimento'] = 0   #Check
    if 'Em atendimento' not in df.columns: df['Em atendimento'] = 0   #Check
    if 'Aguardando pós-consulta' not in df.columns: df['Aguardando pós-consulta'] = 0   #Check
    
    for prof, row in df.iterrows():
        atendidos = row['Atendido'] + row['Atendido pós-consulta'] + row['Aguardando pós-consulta']

        nao_compareceu = row['Não compareceu'] + row['Livre'] + row['Bloqueado'] + row['Marcado - confirmado'] + row['Agendado'] + row['Encaixe'] + row['Aguardando atendimento'] + row['Em atendimento']
        
        total_validos = atendidos + nao_compareceu
        taxa = (atendidos / total_validos * 100) if total_validos > 0 else 0
        stats.append({
            "profissional": prof,
            "taxa_conversao": f"{taxa:.2f}%"
        })
    return sorted(stats, key=lambda x: float(x['taxa_conversao'][:-1]), reverse=True)

def calculate_global_conversion_rate(df):
    """Calcula a taxa de conversão geral para o card de resumo."""
    if df.empty:
        return {"conversion_rate": "0.00%", "total_atendidos": 0}

    if 'Atendido' not in df.columns: df['Atendido'] = 0
    if 'Atendido pós-consulta' not in df.columns: df['Atendido pós-consulta'] = 0
    if 'Não compareceu' not in df.columns: df['Não compareceu'] = 0  #Check

    if 'Livre' not in df.columns: df['Livre'] = 0   #Check
    if 'Bloqueado' not in df.columns: df['Bloqueado'] = 0   #Check
    if 'Marcado - confirmado' not in df.columns: df['Marcado - confirmado'] = 0   #Check
    if 'Agendado' not in df.columns: df['Agendado'] = 0   #Check
    if 'Encaixe' not in df.columns: df['Encaixe'] = 0   #Check
    if 'Aguardando atendimento' not in df.columns: df['Aguardando atendimento'] = 0   #Check
    if 'Em atendimento' not in df.columns: df['Em atendimento'] = 0   #Check
    if 'Aguardando pós-consulta' not in df.columns: df['Aguardando pós-consulta'] = 0   #Check

    total_atendidos = df['Atendido'].sum() + df['Atendido pós-consulta'].sum() + df['Aguardando pós-consulta'].sum()

    total_nao_compareceu = df['Não compareceu'].sum() + df['Livre'].sum() + df['Bloqueado'].sum() + df['Marcado - confirmado'].sum() + df['Agendado'].sum() + df['Encaixe'].sum() + df['Aguardando atendimento'].sum() + df['Em atendimento'].sum()

    total_validos = total_atendidos + total_nao_compareceu
    taxa = (total_atendidos / total_validos * 100) if total_validos > 0 else 0
    
    return {
        "conversion_rate": f"{taxa:.2f}%",
        "total_atendidos": int(total_atendidos)
    }