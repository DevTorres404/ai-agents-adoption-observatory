import re

AGENTES_ESTANDAR = {
    'github copilot': 'GitHub Copilot',
    'copilot': 'GitHub Copilot',
    'openai_codex': 'OpenAI Codex',
    'openai codex': 'OpenAI Codex',
    'codex': 'OpenAI Codex',
    'cursor': 'Cursor',
    'cursor ai': 'Cursor',
    'claude code': 'Claude Code',
    'claude_code': 'Claude Code',
    'claude': 'Claude Code',
    'devin': 'Devin',
    'codeium': 'Codeium',
    'tabnine': 'Tabnine',
    'replit ai': 'Replit AI',
    'replit': 'Replit AI',
    'aider': 'Aider',
    'auto-gpt': 'AutoGPT',
    'autogpt': 'AutoGPT'
}

def extract_agent(df):
    """
    Usa Regex para identificar agentes mencionados en titulo o texto.
    """
    def find_agent(row):
        # Si la fuente es google trends, el nombre del agente suele venir en el título
        titulo = str(row.get('titulo', '')).lower()
        texto = str(row.get('texto', '')).lower()
        
        texto_completo = f"{titulo} {texto}"
        
        for patron, nombre_oficial in AGENTES_ESTANDAR.items():
            if re.search(r'\b' + re.escape(patron) + r'\b', texto_completo):
                return nombre_oficial
                
        # Si no detecta, se clasifica como general
        return "Otro Agente IA"

    df['nombre_agente'] = df.apply(find_agent, axis=1)
    return df
