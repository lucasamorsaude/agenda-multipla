import os
from supabase import create_client, Client
from dotenv import load_dotenv

# --- Inicialização do Cliente Supabase ---
# Isso é feito UMA VEZ quando o módulo é importado,
# em vez de em cada função.
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(url, key)

# --- Funções ---

def get_user(username: str) -> dict | None:
    """Busca um único usuário no Supabase, juntando suas unidades."""
    try:
        # 1. Fazemos a consulta "JOIN"
        # CORREÇÃO: .maybe_single() precisa do .execute() no final
        response = supabase.table('users') \
            .select('''
                role, 
                password_hash,
                user_unidades!inner (
                    unidades (id, nome)
                )
            ''') \
            .eq('username', username) \
            .maybe_single() \
            .execute()  # <--- .execute() É NECESSÁRIO

        # 2. CORREÇÃO: O resultado real está dentro de 'response.data'
        user_data = response.data 
        
        if not user_data:
            return None

        # 3. Reformatamos os dados para parecer com o Firestore (isto estava correto)
        unidades_map = {}
        
        # Pega a lista de relações e a remove do dict principal
        relations_list = user_data.pop('user_unidades', []) 
        
        for rel in relations_list:
            unidade = rel.get('unidades')
            if unidade:
                unidades_map[str(unidade['id'])] = unidade['nome']
        
        # Adiciona o mapa 'unidades' reformatado
        user_data['unidades'] = unidades_map
        return user_data

    except Exception as e:
        print(f"ERRO ao buscar usuário '{username}': {e}")
        return None

def get_all_users() -> dict:
    """Busca todos os usuários do Supabase."""
    try:
        # 1. Mesma consulta do get_user(), mas sem o filtro '.eq()'
        response = supabase.table('users') \
            .select('''
                username, 
                role, 
                password_hash,
                user_unidades!inner (
                    unidades (id, nome)
                )
            ''') \
            .execute()

        users_dict = {}
        if not response.data:
            return {}

        # 2. Loop para reformatar CADA usuário
        for user_data in response.data:
            username = user_data.pop('username') # Pega o username para ser a chave
            
            unidades_map = {}
            relations_list = user_data.pop('user_unidades', [])
            
            for rel in relations_list:
                unidade = rel.get('unidades')
                if unidade:
                    unidades_map[str(unidade['id'])] = unidade['nome']
            
            user_data['unidades'] = unidades_map
            users_dict[username] = user_data # Monta o dict final
        
        return users_dict
        
    except Exception as e:
        print(f"ERRO ao buscar todos os usuários: {e}")
        return {}

def save_user(username: str, user_data: dict):
    """Cria ou atualiza um usuário no Supabase (modo "transação")."""
    try:
        # Copiamos para não modificar o dicionário original
        data_copy = user_data.copy()
        
        # 1. Separamos o mapa 'unidades' do resto dos dados
        unidades_map = data_copy.pop('unidades', {})
        
        # 2. Inserimos/Atualizamos os dados simples na tabela 'users'
        data_copy['username'] = username # Adiciona a PK
        supabase.table('users').upsert(data_copy).execute()

        # 3. Garantimos que todas as unidades existem na tabela 'unidades'
        if unidades_map:
            unidades_list = [
                {"id": int(uid), "nome": nome} 
                for uid, nome in unidades_map.items()
            ]
            supabase.table('unidades').upsert(unidades_list).execute()

        # 4. Deletamos TODAS as relações antigas (para simular o .set() do Firestore)
        supabase.table('user_unidades').delete().eq('username', username).execute()

        # 5. Inserimos as novas relações
        if unidades_map:
            relations_list = [
                {"username": username, "unidade_id": int(uid)} 
                for uid in unidades_map.keys()
            ]
            supabase.table('user_unidades').insert(relations_list).execute()

    except Exception as e:
        print(f"ERRO ao salvar usuário '{username}': {e}")

def delete_user_from_db(username: str):
    """Deleta um usuário do Supabase."""
    try:
        # Graças ao "ON DELETE CASCADE" que definimos no SQL,
        # deletar o usuário da tabela 'users' automaticamente
        # deletará suas relações em 'user_unidades'.
        supabase.table('users').delete().eq('username', username).execute()
        
    except Exception as e:
        print(f"ERRO ao deletar usuário '{username}': {e}")