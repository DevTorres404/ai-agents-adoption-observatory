import pandas as pd

def deduplicate_staging(df):
    """
    Deduplica filas basadas en la clave compuesta:
    fuente + plataforma + id_origen_registro + nombre_agente + fecha_evento
    
    Devuelve un DataFrame limpio y el conteo de filas descartadas.
    """
    total_inicial = len(df)
    
    # Asegurar que no hay nulos en la clave para evitar fallos de drop_duplicates
    clave_compuesta = ['fuente', 'plataforma', 'id_origen_registro', 'nombre_agente', 'fecha_evento']
    
    for col in clave_compuesta:
        if col in df.columns:
            df[col] = df[col].fillna('N/A').astype(str)
            
    # Eliminar duplicados manteniendo el más reciente o el primero que llegó
    df_limpio = df.drop_duplicates(subset=clave_compuesta, keep='first')
    
    descartados = total_inicial - len(df_limpio)
    
    return df_limpio, descartados
