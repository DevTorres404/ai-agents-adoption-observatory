import pandas as pd
import re

def clean_numeric_string(val):
    """
    Control 3.3 (Formatos y Casting): 
    Limpia strings numéricos sucios y los normaliza.
    Ejemplo: "3k" -> 3000, "1,200" -> 1200
    """
    if pd.isna(val) or val == "" or str(val).lower() == "none":
        return 0
    val_str = str(val).lower().replace(",", "").replace(".", "")
    val_str = val_str.replace("k", "000").replace("m", "000000")
    
    # Remover todo lo que no sea dígito
    cleaned = re.sub(r'[^\d]', '', val_str)
    if not cleaned:
        return 0
    return int(cleaned)

def standardize_agent_name(name):
    """
    Control 3.4 (Estandarización Estricta): 
    Homogeneidad sintáctica en categorías maestras.
    """
    if pd.isna(name):
        return "Desconocido"
    name = str(name).strip()
    
    # Reglas para unificar nombres inter-fuentes
    lower_name = name.lower()
    if "copilot" in lower_name:
        return "GitHub Copilot"
    if "chatgpt" in lower_name or "gpt" in lower_name:
        return "ChatGPT"
    if "claude" in lower_name:
        return "Claude"
    if "cursor" in lower_name:
        return "Cursor"
    if "devin" in lower_name:
        return "Devin"
        
    # Capitalización estándar para el resto
    return name.title()

def impute_missing_values(df, strategy_map):
    """
    Control 3.2 (Control de Nulos):
    Aplica estrategias específicas por columna de forma paramétrica.
    """
    for col, strategy in strategy_map.items():
        if col in df.columns:
            if strategy == "drop":
                df = df.dropna(subset=[col])
            elif strategy == "median":
                median_val = df[col].median()
                df[col] = df[col].fillna(median_val)
            elif strategy == "unknown":
                df[col] = df[col].fillna("Desconocido")
            elif strategy == "zero":
                df[col] = df[col].fillna(0)
    return df
