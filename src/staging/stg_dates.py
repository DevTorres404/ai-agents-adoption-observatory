import pandas as pd

def parse_dates(df):
    """
    Estandariza cualquier formato de fecha a YYYY-MM-DD.
    """
    if 'fecha_evento_raw' not in df.columns:
        df['fecha_evento'] = pd.Timestamp.today().strftime('%Y-%m-%d')
        return df

    # Forzar conversión a datetime usando el motor robusto de Pandas
    parsed_dates = pd.to_datetime(df['fecha_evento_raw'], errors='coerce', utc=True)
    
    # Las fechas que no se pudieron parsear (NaT), poner fecha actual como fallback preventivo
    parsed_dates = parsed_dates.fillna(pd.Timestamp.today(tz='UTC'))
    
    # Formatear a YYYY-MM-DD (Date sin Timezone)
    df['fecha_evento'] = parsed_dates.dt.strftime('%Y-%m-%d')
    
    # Filtro de Calidad Académica: Acotar el universo temporal a 2023-2026
    df = df[(df['fecha_evento'] >= '2023-01-01') & (df['fecha_evento'] <= '2026-12-31')]
    df = df.reset_index(drop=True)
    # Limpiar columna temporal
    df = df.drop(columns=['fecha_evento_raw'])
    
    return df
