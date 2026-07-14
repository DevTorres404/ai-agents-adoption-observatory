def deduplicate_staging(df):
    """
    Deduplica filas basadas en la clave compuesta:
    fuente + plataforma + id_origen_registro + nombre_agente.

    Devuelve un DataFrame limpio y el conteo de filas descartadas.
    """
    total_inicial = len(df)

    # La fecha describe cuándo ocurrió la observación, pero no identifica a la
    # entidad de origen. Excluirla evita que una nueva instantánea del mismo
    # repositorio, publicación o respuesta sobreviva como un hecho adicional.
    clave_compuesta = ['fuente', 'plataforma', 'id_origen_registro', 'nombre_agente']

    for col in clave_compuesta:
        if col in df.columns:
            # Motivo: reemplazar nulos evita que la deduplicacion deje pasar duplicados por campos vacios.
            df[col] = df[col].fillna('N/A').astype(str)

    # Se conserva la versión más reciente de forma determinista. raw_file_id
    # resuelve empates entre instantáneas cargadas el mismo día.
    orden = [*clave_compuesta, 'fecha_evento']
    if 'raw_file_id' in df.columns:
        orden.append('raw_file_id')
    df_ordenado = df.sort_values(orden, kind='mergesort', na_position='first')
    df_limpio = (
        df_ordenado
        .drop_duplicates(subset=clave_compuesta, keep='last')
        .sort_index(kind='mergesort')
    )
    descartados = total_inicial - len(df_limpio)

    return df_limpio, descartados
