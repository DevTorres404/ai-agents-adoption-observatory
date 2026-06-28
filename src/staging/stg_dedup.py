def deduplicate_staging(df):
    """
    Deduplica filas basadas en la clave compuesta:
    fuente + plataforma + id_origen_registro + nombre_agente + fecha_evento

    Devuelve un DataFrame limpio y el conteo de filas descartadas.
    """
    total_inicial = len(df)

    # Motivo: la clave compuesta expresa unicidad analitica por fuente, plataforma, registro, agente y dia.
    clave_compuesta = ['fuente', 'plataforma', 'id_origen_registro', 'nombre_agente', 'fecha_evento']

    for col in clave_compuesta:
        if col in df.columns:
            # Motivo: reemplazar nulos evita que la deduplicacion deje pasar duplicados por campos vacios.
            df[col] = df[col].fillna('N/A').astype(str)

    # Motivo: se conserva el primer registro porque Raw mantiene la evidencia completa y el orden de carga es reproducible.
    df_limpio = df.drop_duplicates(subset=clave_compuesta, keep='first')
    descartados = total_inicial - len(df_limpio)

    return df_limpio, descartados
