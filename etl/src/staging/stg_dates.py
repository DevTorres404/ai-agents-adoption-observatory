import pandas as pd


def parse_dates(df):
    """
    Estandariza cualquier formato de fecha a YYYY-MM-DD.
    """
    if 'fecha_evento_raw' not in df.columns:
        # Motivo: si una fuente no trae fecha, se conserva trazabilidad usando la fecha de procesamiento.
        df['fecha_evento'] = pd.Timestamp.today().strftime('%Y-%m-%d')
        return df

    # Motivo: Inicialmente todas las fechas se asumen reales.
    df['is_imputed_date'] = False

    # Motivo: Pandas homologa fechas ISO, timestamps web y fechas de encuesta sin parsers por fuente.
    parsed_dates = pd.to_datetime(df['fecha_evento_raw'], errors='coerce', utc=True)

    # Motivo: El dataset del catalogo (AIDev) agrupa miles de interacciones en la fecha de 'last_activity'.
    # Científicamente no se debe inventar la cronología. Registramos la fecha de extracción actual
    # y marcamos is_imputed_date = True para no falsear datos históricos.
    if 'fuente' in df.columns:
        mask_catalog = df['fuente'] == 'catalogo'
        if mask_catalog.any():
            parsed_dates.loc[mask_catalog] = pd.Timestamp.today(tz='UTC')
            df.loc[mask_catalog, 'is_imputed_date'] = True

    # Motivo: Para fechas nulas en cualquier otra fuente, imputamos a hoy pero 
    # dejamos la huella de auditoría explícita.
    mask_nat = parsed_dates.isna()
    if mask_nat.any():
        parsed_dates.loc[mask_nat] = pd.Timestamp.today(tz='UTC')
        df.loc[mask_nat, 'is_imputed_date'] = True

    # Motivo: el Data Warehouse requiere granularidad diaria, no hora/minuto/segundo.
    df['fecha_evento'] = parsed_dates.dt.strftime('%Y-%m-%d')

    # Motivo: el estudio analiza adopcion reciente de agentes IA en el periodo academico definido.
    # Nota: Filtramos descartando fechas antiguas, pero conservamos las imputadas (que son = hoy) 
    # si 'hoy' <= 2026-12-31.
    df = df[(df['fecha_evento'] >= '2023-01-01') & (df['fecha_evento'] <= '2026-12-31')]
    df = df.reset_index(drop=True)

    # Motivo: se elimina la fecha cruda para mantener el contrato Staging tabular y consistente.
    df = df.drop(columns=['fecha_evento_raw'])

    return df
