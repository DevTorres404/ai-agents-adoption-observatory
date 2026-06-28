def assign_categories(df):
    """
    Categoriza el registro según la plataforma y la naturaleza de las métricas.
    """
    def categorize(row):
        fuente = row.get('fuente', '')
        stars = row.get('stars_github', 0)
        
        if fuente == 'github':
            if stars > 1000:
                return 'popularidad'
            return 'produccion_tecnica'
            
        elif fuente == 'hackernews':
            return 'comunidad'
            
        elif fuente == 'google_trends':
            return 'popularidad'
            
        elif fuente in ['encuesta', 'fuente_propia']:
            return 'pendiente_tabulacion'
            
        return 'actividad_tecnica'

    df['categoria'] = df.apply(categorize, axis=1)
    return df
