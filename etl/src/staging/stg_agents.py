import re

# =============================================================
# Diccionario de AGENTES de IA para desarrollo de software.
# Basado estrictamente en la tabla proporcionada por el usuario.
# Orden: los alias MÁS ESPECÍFICOS van primero para evitar falsos positivos.
# =============================================================
AGENTES_ESTANDAR = {
    # 1. Cursor
    'cursor agent': 'Cursor',
    'cursor ai': 'Cursor',
    'cursor': 'Cursor',

    # 2. Claude Code
    'claude code': 'Claude Code',
    'claude cli': 'Claude Code',

    # 3. Codex
    'openai codex': 'Codex',
    'codex': 'Codex',

    # 4. GitHub Copilot
    'copilot coding agent': 'GitHub Copilot',
    'github copilot': 'GitHub Copilot',
    'copilot': 'GitHub Copilot',

    # 5. Cline
    'cline agent': 'Cline',
    'cline': 'Cline',

    # 6. Roo Code
    'roo code': 'Roo Code',
    'roocode': 'Roo Code',
    'roo': 'Roo Code',

    # 7. Windsurf
    'windsurf cascade': 'Windsurf',
    'windsurf': 'Windsurf',
    'cascade': 'Windsurf',

    # 8. Aider
    'aider chat': 'Aider',
    'aider': 'Aider',

    # 9. Augment
    'augment code': 'Augment',
    'augment ai': 'Augment',
    'augment': 'Augment',

    # 10. JetBrains Junie
    'jetbrains junie': 'JetBrains Junie',
    'junie cli': 'JetBrains Junie',
    'junie': 'JetBrains Junie',
    'jetbrains ai': 'JetBrains Junie',

    # 11. Gemini CLI
    'gemini code assist': 'Gemini CLI',
    'gemini cli': 'Gemini CLI',

    # 12. AWS Kiro
    'kiro ide': 'AWS Kiro',
    'kiro cli': 'AWS Kiro',
    'kiro': 'AWS Kiro',

    # 13. Kilo Code
    'kilo code': 'Kilo Code',
    'kilo': 'Kilo Code',

    # 14. Zencoder
    'zencoder': 'Zencoder',
}

# Precompilar patrones para rendimiento masivo
AGENTES_PATTERNS = [
    (re.compile(r'\b' + re.escape(patron) + r'\b'), nombre_oficial)
    for patron, nombre_oficial in AGENTES_ESTANDAR.items()
]

def extract_agent(df):
    """
    Identifica agentes de IA (herramientas de desarrollo) en los
    campos titulo, texto y agente (Google Trends).
    Aplica AGENTES_ESTANDAR con límites de palabra para evitar falsos positivos.
    Si no se detecta ningún agente conocido, asigna 'Otro Agente IA'.
    """
    def find_agent(row):
        agente_directo = str(row.get('agente', '')).strip().replace('_', ' ')
        titulo = str(row.get('titulo', '')).lower()
        texto = str(row.get('texto', '')).lower()
        texto_completo = f"{titulo} {texto}".replace('_', ' ')

        # Primero: campo directo de Google Trends (nombre ya limpio)
        if agente_directo:
            agente_lower = agente_directo.lower()
            for patron_regex, nombre_oficial in AGENTES_PATTERNS:
                if patron_regex.search(agente_lower):
                    return nombre_oficial

        # Segundo: buscar en título + texto
        for patron_regex, nombre_oficial in AGENTES_PATTERNS:
            if patron_regex.search(texto_completo):
                return nombre_oficial

        return "Otro Agente IA"

    df['nombre_agente'] = df.apply(find_agent, axis=1)
    return df
