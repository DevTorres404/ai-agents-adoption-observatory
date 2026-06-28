def assign_categories(df):
    """
    Categoriza el registro segun la plataforma y la naturaleza de las metricas.
    """
    def categorize(row):
        fuente = row.get('fuente', '')
        stars = row.get('stars_github', 0)

        if fuente == 'github':
            # Motivo: alta atencion publica se analiza como popularidad; el resto como produccion tecnica.
            if stars > 1000:
                return 'popularidad'
            return 'produccion_tecnica'

        if fuente == 'hackernews':
            # Motivo: HN aporta conversacion y validacion comunitaria, no metricas directas de uso.
            return 'comunidad'

        if fuente == 'google_trends':
            # Motivo: Google Trends representa demanda/interes de busqueda agregado.
            return 'popularidad'

        if fuente in ['encuesta', 'fuente_propia']:
            # Motivo: la fuente propia queda separada hasta completar tabulacion y validacion metodologica.
            return 'pendiente_tabulacion'

        # Motivo: fuentes tecnicas estructuradas o articulos quedan como actividad tecnica por defecto.
        return 'actividad_tecnica'

    df['categoria'] = df.apply(categorize, axis=1)
    return df
