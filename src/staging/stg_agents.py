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
    'autogpt': 'AutoGPT',
}


def extract_agent(df):
    """
    Usa Regex para identificar agentes mencionados en titulo o texto.
    """
    def find_agent(row):
        # Motivo: titulo y texto concentran menciones en scraping/API; unirlos mejora recall sin consultar Raw completo.
        titulo = str(row.get('titulo', '')).lower()
        texto = str(row.get('texto', '')).lower()
        texto_completo = f"{titulo} {texto}"

        for patron, nombre_oficial in AGENTES_ESTANDAR.items():
            # Motivo: los limites de palabra evitan falsos positivos al homologar alias cortos como "codex".
            if re.search(r'\b' + re.escape(patron) + r'\b', texto_completo):
                return nombre_oficial

        # Motivo: no se descartan registros sin agente explicito; se agrupan para revision o analisis general.
        return "Otro Agente IA"

    df['nombre_agente'] = df.apply(find_agent, axis=1)
    return df
