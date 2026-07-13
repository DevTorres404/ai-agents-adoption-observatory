import json
import os
import requests
from pathlib import Path
from src.utils.logger import global_logger
from src.utils.paths import ROOT_DIR

CACHE_FILE = ROOT_DIR / "docs" / "llm_cache.json"

def load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_cache(cache):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def query_llama(text_content):
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
  "tecnologias": [{{"nombre": "React", "categoria_tecnologia": "framework"}}],
  "capacidades": ["valor1"],
  "comunidad": {{"nombre": "reactjs", "tipo_comunidad": "subreddit"}},
  "confianza": 0.95,
  "evidencia": ["cita textual exacta"]
}}

Texto a clasificar:
'{texto}'
"""
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "llama3.2",
        "prompt": prompt_template.format(texto=text_content),
        "format": "json",
        "options": {
            "temperature": 0.0,
            "seed": 42
        },
        "stream": False
    }
    
    try:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
        result = json.loads(data.get("response", "{}"))
        return result
    except Exception as e:
        global_logger.warning(f"Error consultando Ollama: {e}")
        return None

def enrich_with_llm(df):
    global_logger.info("Iniciando enriquecimiento semántico con Llama 3.2 (Ollama)...")
    
    # Inicializar columnas nuevas
    df["llm_entorno_uso"] = "No determinado"
    df["llm_tipo_integracion"] = "No determinado"
    df["llm_categoria_tecnologia"] = "No determinado"
    df["llm_capacidades"] = None
    df["llm_comunidad_tipo"] = "No determinado"
    df["llm_confianza"] = 0.0
    
    if "texto" not in df.columns or "fuente" not in df.columns:
        return df

    # Solo enriquecemos fuentes no estructuradas
    fuentes_objetivo = ["reddit", "hackernews", "stackoverflow", "devto", "gnews"]
    mask = df["fuente"].isin(fuentes_objetivo) & df["texto"].notna() & (df["texto"] != "")
    
    try:
        requests.get("http://localhost:11434/", timeout=2)
    except requests.exceptions.RequestException:
        global_logger.warning("Ollama no está disponible en localhost:11434. Se omitirá el enriquecimiento semántico.")
        return df

    cache = load_cache()
    new_cache_entries = 0
    
    total_to_process = mask.sum()
    global_logger.info(f"Se identificaron {total_to_process} registros aptos para enriquecimiento semántico estricto.")
    
    processed = 0
    
    for idx, row in df[mask].iterrows():
        texto_limpio = str(row["texto"])[:1000]
        import hashlib
        cache_key = hashlib.md5(texto_limpio.encode('utf-8')).hexdigest()
        
        res = cache.get(cache_key)
        if not res:
            res = query_llama(texto_limpio)
            if res:
                cache[cache_key] = res
                new_cache_entries += 1
            else:
                res = {}
                
        # Extraer valores y aplicar umbral de confianza
        confianza = float(res.get("confianza", 0.0))
        if confianza >= 0.85:
            df.at[idx, "llm_entorno_uso"] = res.get("entorno_uso", "No determinado")
            df.at[idx, "llm_tipo_integracion"] = res.get("tipo_integracion", "No determinado")
            
            # Extract first technology category if available
            tecnologias = res.get("tecnologias", [])
            if isinstance(tecnologias, list) and len(tecnologias) > 0:
                cat = tecnologias[0].get("categoria_tecnologia", "No determinado")
                df.at[idx, "llm_categoria_tecnologia"] = cat
            
            # Extract array of capabilities as comma separated string
            capacidades = res.get("capacidades", [])
            if isinstance(capacidades, list):
                df.at[idx, "llm_capacidades"] = ",".join(capacidades)
                
            comunidad = res.get("comunidad", {})
            if isinstance(comunidad, dict):
                df.at[idx, "llm_comunidad_tipo"] = comunidad.get("tipo_comunidad", "No determinado")
                
        df.at[idx, "llm_confianza"] = confianza
        
        processed += 1
        global_logger.info(f"LLM: Procesado {processed}/{total_to_process} (Fuente: {row['fuente']}, Confianza: {confianza})")
    
    if new_cache_entries > 0:
        save_cache(cache)
        global_logger.info(f"Se guardaron {new_cache_entries} nuevas inferencias estandarizadas en caché.")
        
    global_logger.info("Enriquecimiento semántico completado.")
    return df
