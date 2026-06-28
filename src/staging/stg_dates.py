import pandas as pd


def parse_dates(df):
    """
    Estandariza cualquier formato de fecha a YYYY-MM-DD.
    """
    if 'fecha_evento_raw' not in df.columns:
        # Motivo: si una fuente no trae fecha, se conserva trazabilidad usando la fecha de procesamiento.
        df['fecha_evento'] = pd.Timestamp.today().strftime('%Y-%m-%d')
        return df

    # Motivo: Pandas homologa fechas ISO, timestamps web y fechas de encuesta sin parsers por fuente.
    parsed_dates = pd.to_datetime(df['fecha_evento_raw'], errors='coerce', utc=True)

    # Motivo: los NaT se reemplazan para no romper la clave de deduplicacion ni la carga a Staging.
    parsed_dates = parsed_dates.fillna(pd.Timestamp.today(tz='UTC'))

    # Motivo: el Data Warehouse requiere granularidad diaria, no hora/minuto/segundo.
    df['fecha_evento'] = parsed_dates.dt.strftime('%Y-%m-%d')

    # Motivo: el estudio analiza adopcion reciente de agentes IA en el periodo academico definido.
    df = df[(df['fecha_evento'] >= '2023-01-01') & (df['fecha_evento'] <= '2026-12-31')]
    df = df.reset_index(drop=True)

    # Motivo: se elimina la fecha cruda para mantener el contrato Staging tabular y consistente.
    df = df.drop(columns=['fecha_evento_raw'])

    return df
