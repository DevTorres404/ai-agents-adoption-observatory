import json
import time
import requests
import pandas as pd
from sqlalchemy import text
from src.utils.db import db_connector
from src.utils.logger import global_logger
from src.utils.paths import ROOT_DIR

def run_pilot():
    global_logger.info(">>> INICIANDO PRUEBA PILOTO LLAMA 3 (ARQUITECTURA MEDALLION) <<<")
    
    if not db_connector.engine:
        global_logger.error("Sin conexión a PostgreSQL.")
        return

    # Extraer muestra estratificada desde Raw (10 de cada fuente conversacional/noticias)
    query = text("""
        WITH ranked_records AS (
            SELECT 
                f.fuente, 
                r.raw_data,
                ROW_NUMBER() OVER(PARTITION BY f.fuente ORDER BY RANDOM()) as rn
            FROM raw.raw_records r
            JOIN raw.raw_files f ON r.file_id = f.id
            WHERE f.fuente IN ('reddit', 'hackernews', 'stackoverflow', 'devto', 'gnews')
        )
        SELECT fuente, raw_data 
        FROM ranked_records 
        WHERE rn <= 10;
    """)
    
    with db_connector.engine.connect() as conn:
        records = conn.execute(query).fetchall()
        
    global_logger.info(f"Extraídos {len(records)} registros para el piloto.")
    
    resultados = []
    tiempo_total = 0
    errores_json = 0
    
    prompt_template = """
Eres un Ingeniero de Datos especializado. Analiza el siguiente texto y devuelve EXCLUSIVAMENTE un JSON válido, sin Markdown ni comentarios extra.
Debes usar estrictamente estos vocabularios:
- "tipo_integracion": ["IDE dedicado", "Extensión de IDE", "CLI", "Integración nativa", "Aplicación web", "Aplicación de escritorio", "Cloud", "API/SDK", "No determinado"]
- "entorno_uso": ["VS Code", "JetBrains IDEs", "Terminal", "GitHub", "Web", "Cloud", "Desktop", "Cursor IDE", "Windsurf IDE", "Kiro IDE", "No determinado"]
- "categoria_tecnologia": ["lenguaje", "framework", "infraestructura", "herramienta", "capacidad", "metodologia"]
- "capacidades": subconjunto de ["Generación de código", "Autocompletado", "Razonamiento sobre codebase", "Edición multiarchivo", "Refactorización", "Testing", "Depuración", "Revisión de código", "Generación de documentación", "Desarrollo basado en especificaciones", "Orquestación multiagente", "Ejecución autónoma", "No determinado"]
- "tipo_comunidad": ["subreddit", "etiqueta técnica", "foro", "organización", "repositorio", "grupo académico", "comunidad general", "no aplica", "no determinado"]

Formato esperado:
{{
  "entorno_uso": "valor",
  "tipo_integracion": "valor",
  "tecnologias": [{{"nombre": "React", "categoria": "framework"}}],
  "capacidades": ["valor1"],
  "comunidad": {{"nombre": "reactjs", "tipo": "subreddit"}},
  "confianza": 0.95,
  "evidencia": ["cita textual exacta"]
}}

Texto a clasificar:
'{texto}'
"""

    url = "http://localhost:11434/api/generate"
    
    for row in records:
        fuente = row.fuente
        raw_data = row.raw_data
        
        # Extraer el texto según la fuente
        texto = ""
        if fuente == 'reddit':
            texto = raw_data.get('title', '') + " " + raw_data.get('selftext', '')
        elif fuente == 'hackernews':
            texto = raw_data.get('title', '') + " " + raw_data.get('text', '')
        elif fuente == 'devto':
            texto = raw_data.get('title', '') + " " + raw_data.get('description', '')
        elif fuente == 'stackoverflow':
            texto = raw_data.get('title', '') + " " + raw_data.get('body', '')
        elif fuente == 'gnews':
            texto = raw_data.get('title', '') + " " + raw_data.get('description', '')
            
        texto = str(texto).strip()[:1000] # Truncate for speed
        if not texto:
            continue
            
        payload = {
            "model": "llama3",
            "prompt": prompt_template.format(texto=texto),
            "format": "json",
            "options": {
                "temperature": 0.0,
                "seed": 42
            },
            "stream": False
        }
        
        t0 = time.time()
        try:
            response = requests.post(url, json=payload, timeout=20)
            response.raise_for_status()
            respuesta_json = response.json().get("response", "{}")
            parsed = json.loads(respuesta_json)
            valido = True
        except Exception as e:
            global_logger.debug(f"Error parseando JSON: {e}")
            parsed = {}
            valido = False
            errores_json += 1
            
        t1 = time.time()
        duracion = t1 - t0
        tiempo_total += duracion
        
        resultados.append({
            "fuente": fuente,
            "texto_truncado": texto[:100] + "...",
            "json_valido": valido,
            "confianza": parsed.get("confianza", 0),
            "entorno_uso": parsed.get("entorno_uso", "error"),
            "tecnologias_detectadas": len(parsed.get("tecnologias", [])),
            "evidencia_presente": len(parsed.get("evidencia", [])) > 0,
            "tiempo_segundos": round(duracion, 2)
        })
        
        global_logger.info(f"[{fuente}] Procesado en {duracion:.2f}s | JSON válido: {valido} | Confianza: {parsed.get('confianza', 0)}")
        
    df_res = pd.DataFrame(resultados)
    
    global_logger.info("=== RESULTADOS DEL PILOTO LLAMA 3 ===")
    global_logger.info(f"Total procesados: {len(df_res)}")
    global_logger.info(f"JSON Válido: {(df_res['json_valido'].sum() / len(df_res))*100:.1f}%")
    global_logger.info(f"Tiempo medio por registro: {(tiempo_total / len(df_res)):.2f}s")
    
    # Evaluar aceptación
    aceptados = df_res[(df_res['confianza'] >= 0.85) & (df_res['evidencia_presente'] == True)]
    global_logger.info(f"Registros Aceptados (Confianza >= 0.85 con evidencia): {(len(aceptados) / len(df_res))*100:.1f}%")
    
    report_path = ROOT_DIR / "docs" / "piloto_llm_reporte.csv"
    df_res.to_csv(report_path, index=False, encoding='utf-8')
    global_logger.info(f"Reporte detallado guardado en {report_path}")

if __name__ == "__main__":
    run_pilot()
