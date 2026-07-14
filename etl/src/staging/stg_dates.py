import pandas as pd


def parse_dates(df):
    """
    Estandariza cualquier formato de fecha a YYYY-MM-DD de forma reproducible.

    Se preserva la fecha observada por la fuente. Cuando no existe, se usa la
    fecha inmutable de carga del archivo Raw y se registra la imputación. Nunca
    se utiliza el día de ejecución, porque cambiaría el resultado entre corridas
    sobre la misma evidencia Raw.
    """
    if 'fecha_evento_raw' not in df.columns:
        df['fecha_evento_raw'] = pd.NaT

    # Inicialmente todas las fechas se consideran observadas por la fuente.
    df['is_imputed_date'] = False

    # Pandas homologa fechas ISO, timestamps web y fechas de encuesta.
    parsed_dates = pd.to_datetime(df['fecha_evento_raw'], errors='coerce', utc=True)

    # Si la fuente no aporta fecha, la carga del archivo Raw es un sustituto
    # estable y trazable. Si tampoco existe, la fila queda nula y el filtro de
    # ventana la excluye en lugar de inventar una cronología.
    mask_nat = parsed_dates.isna()
    if mask_nat.any():
        raw_load_dates = pd.to_datetime(
            df.get('fecha_carga_raw', pd.Series(pd.NaT, index=df.index)),
            errors='coerce',
            utc=True,
        )
        has_fallback = mask_nat & raw_load_dates.notna()
        parsed_dates.loc[has_fallback] = raw_load_dates.loc[has_fallback]
        df.loc[has_fallback, 'is_imputed_date'] = True

    # Motivo: el Data Warehouse requiere granularidad diaria, no hora/minuto/segundo.
    df['fecha_evento'] = parsed_dates.dt.strftime('%Y-%m-%d')

    # Motivo: el estudio analiza adopcion reciente de agentes IA en el periodo academico definido.
    # Nota: Filtramos descartando fechas antiguas, pero conservamos las imputadas (que son = hoy) 
    # si 'hoy' <= 2026-12-31.
    df = df[(df['fecha_evento'] >= '2023-01-01') & (df['fecha_evento'] <= '2026-12-31')]
    df = df.reset_index(drop=True)

    # Se eliminan los auxiliares para mantener el contrato Staging tabular.
    df = df.drop(columns=['fecha_evento_raw', 'fecha_carga_raw'], errors='ignore')

    return df
