import pandas as pd


def _parse_datetimes_utc(series):
    """Parsea una columna de fechas a ``datetime64[ns, UTC]`` sin perder valores.

    Un ``pd.to_datetime(..., utc=True)`` vectorizado sobre una columna que
    mezcla strings naive y tz-aware (p. ej. ``fecha`` de google_trends
    "2023-01-22T00:00:00" junto a ``created_at`` de arxiv
    "2026-09-15T09:21:45+00:00") vuelve NaT a uno de los dos grupos en
    pandas>=3.0. Como Staging concatena todas las fuentes ANTES de
    parse_dates, el parseo vectorizado imputa por accidente a las fuentes
    del grupo perdedor (google_trends, stackoverflow, gnews, reddit,
    hackernews) usando la fecha de carga del archivo.

    Se parsea cada valor de forma individual para conservar la semántica por
    valor (naive => UTC, aware => UTC) sin la interacción entre convenciones.
    """
    parsed = pd.Series(
        [pd.to_datetime(value, errors="coerce", utc=True) for value in series],
        index=series.index,
        # dtype object: evita que pandas infiera datetime64[s] para una serie
        # toda-NaT (pandas>=3.0) e impida luego la conversion a UTC.
        dtype="object",
    )
    return parsed.astype("datetime64[ns, UTC]")


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

    # Pandas homologa fechas ISO y timestamps web.
    # Force one resolution before fallback assignment. Pandas can infer seconds
    # for an all-NaT source series and microseconds for PostgreSQL timestamps;
    # assigning between those dtypes otherwise raises on recent Pandas versions.
    parsed_dates = _parse_datetimes_utc(df['fecha_evento_raw'])

    # Si la fuente no aporta fecha, la carga del archivo Raw es un sustituto
    # estable y trazable. Si tampoco existe, la fila queda nula y el filtro de
    # ventana la excluye en lugar de inventar una cronología.
    mask_nat = parsed_dates.isna()
    if mask_nat.any():
        raw_load_dates = _parse_datetimes_utc(
            df.get('fecha_carga_raw', pd.Series(pd.NaT, index=df.index))
        )
        has_fallback = mask_nat & raw_load_dates.notna()
        parsed_dates.loc[has_fallback] = raw_load_dates.loc[has_fallback]
        df.loc[has_fallback, 'is_imputed_date'] = True

    # Motivo: el Data Warehouse requiere granularidad diaria, no hora/minuto/segundo.
    df['fecha_evento'] = parsed_dates.dt.strftime('%Y-%m-%d')

    # Extraction defines the requested window. Do not silently discard other years.
    df = df[df['fecha_evento'].notna()]
    df = df.reset_index(drop=True)

    # Se eliminan los auxiliares para mantener el contrato Staging tabular.
    df = df.drop(columns=['fecha_evento_raw', 'fecha_carga_raw'], errors='ignore')

    return df
