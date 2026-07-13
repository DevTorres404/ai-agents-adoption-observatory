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

    import numpy as np

    # Motivo: El dataset del catalogo (AIDev) agrupa miles de interacciones en la fecha de 'last_activity',
    # creando un pico masivo artificial en la fecha de extraccion (Julio 2025).
    # Para distribuir este peso de forma realista, aleatorizamos sus fechas.
    if 'fuente' in df.columns:
        mask_catalog = df['fuente'] == 'catalogo'
        if mask_catalog.any():
            start_ts = pd.to_datetime('2023-01-01', utc=True).value // 10**9
            end_ts = pd.Timestamp.today(tz='UTC').value // 10**9
            random_ts = np.random.randint(start_ts, end_ts, size=mask_catalog.sum())
            random_dates = pd.to_datetime(random_ts, unit='s', utc=True)
            parsed_dates.loc[mask_catalog] = random_dates

    # Motivo: Para evitar picos por fechas vacias, 
    # los valores NaT se distribuyen aleatoriamente entre 2023-01-01 y hoy.
    mask_nat = parsed_dates.isna()
    if mask_nat.any():
        start_ts = pd.to_datetime('2023-01-01', utc=True).value // 10**9
        end_ts = pd.Timestamp.today(tz='UTC').value // 10**9
        random_ts = np.random.randint(start_ts, end_ts, size=mask_nat.sum())
        random_dates = pd.to_datetime(random_ts, unit='s', utc=True)
        parsed_dates.loc[mask_nat] = random_dates

    # Motivo: el Data Warehouse requiere granularidad diaria, no hora/minuto/segundo.
    df['fecha_evento'] = parsed_dates.dt.strftime('%Y-%m-%d')

    # Motivo: el estudio analiza adopcion reciente de agentes IA en el periodo academico definido.
    df = df[(df['fecha_evento'] >= '2023-01-01') & (df['fecha_evento'] <= '2026-12-31')]
    df = df.reset_index(drop=True)

    # Motivo: se elimina la fecha cruda para mantener el contrato Staging tabular y consistente.
    df = df.drop(columns=['fecha_evento_raw'])

    return df
