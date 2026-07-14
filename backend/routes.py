import os
import docker
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from .database import get_db
from fastapi.responses import JSONResponse
from typing import List, Optional

router = APIRouter()
etl_router = APIRouter()

async def fetch_all(db: AsyncSession, query: str, params: dict = None):
    result = await db.execute(text(query), params or {})
    return [dict(row._mapping) for row in result]

async def fetch_one(db: AsyncSession, query: str, params: dict = None):
    result = await db.execute(text(query), params or {})
    row = result.fetchone()
    return dict(row._mapping) if row else {}

def build_filter_clause(
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
    agentes: Optional[List[str]] = None,
    categoria: Optional[str] = None,
    fuente: Optional[str] = None,
    plataforma: Optional[str] = None,
    tecnologia: Optional[str] = None,
    exclude_unidentified: bool = False
):
    joins = """
        FROM gold.fact_actividad_agente_ia f
        JOIN gold.dim_agente a ON f.id_agente = a.id_agente
        JOIN gold.dim_tiempo t ON f.id_tiempo = t.id_tiempo
        JOIN gold.dim_fuente src ON f.id_fuente = src.id_fuente
        JOIN gold.dim_plataforma p ON f.id_plataforma = p.id_plataforma
        JOIN gold.dim_tecnologia tec ON f.id_tecnologia = tec.id_tecnologia
    """
    where_clauses = ["1=1"]
    params = {}

    if exclude_unidentified:
        where_clauses.append("a.nombre_agente NOT IN ('No Identificado', 'Otro Agente IA')")

    if fecha_inicio:
        where_clauses.append("t.fecha >= :fecha_inicio")
        params["fecha_inicio"] = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
    if fecha_fin:
        where_clauses.append("t.fecha <= :fecha_fin")
        params["fecha_fin"] = datetime.strptime(fecha_fin, "%Y-%m-%d").date()
    
    if agentes:
        safe_agentes = [ag.replace("'", "''") for ag in agentes]
        agentes_str = ','.join([f"'{ag}'" for ag in safe_agentes])
        where_clauses.append(f"a.nombre_agente IN ({agentes_str})")
        
    if categoria:
        where_clauses.append("a.categoria_agente = :categoria")
        params["categoria"] = categoria
    if fuente:
        where_clauses.append("LOWER(src.nombre_fuente) = LOWER(:fuente)")
        params["fuente"] = fuente
    if plataforma:
        where_clauses.append("p.nombre_plataforma = :plataforma")
        params["plataforma"] = plataforma
    if tecnologia:
        where_clauses.append("tec.nombre_tecnologia = :tecnologia")
        params["tecnologia"] = tecnologia
        
    where_sql = " AND ".join(where_clauses)
    return joins, where_sql, params

@router.get("/adopcion")
async def get_adopcion(
    fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
    agentes: Optional[List[str]] = Query(None), categoria: Optional[str] = None,
    fuente: Optional[str] = None, plataforma: Optional[str] = None, tecnologia: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    try:
        joins, where_sql, params = build_filter_clause(fecha_inicio, fecha_fin, agentes, categoria, fuente, plataforma, tecnologia, exclude_unidentified=True)
        query = f"""
            SELECT a.nombre_agente, a.categoria_agente,
                COUNT(f.id_fact_actividad) AS total_observaciones,
                SUM(f.cantidad_menciones) AS total_menciones,
                SUM(f.cantidad_interacciones) AS total_interacciones,
                ROUND(AVG(f.score_adopcion), 4) AS promedio_score_adopcion,
                ROUND(SUM(f.score_adopcion), 4) AS score_adopcion_total,
                ROUND(AVG(f.valor_numerico_normalizado), 4) AS promedio_valor_normalizado
            {joins}
            WHERE {where_sql}
            GROUP BY a.nombre_agente, a.categoria_agente
            ORDER BY total_observaciones DESC;
        """
        return await fetch_all(db, query, params)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Error al consultar adopción", "detail": str(e)})

@router.get("/participacion")
async def get_participacion(
    fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
    agentes: Optional[List[str]] = Query(None), categoria: Optional[str] = None,
    fuente: Optional[str] = None, plataforma: Optional[str] = None, tecnologia: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    try:
        joins, where_sql, params = build_filter_clause(fecha_inicio, fecha_fin, agentes, categoria, fuente, plataforma, tecnologia)
        query = f"""
            WITH Totales AS (
                SELECT 
                    src.nombre_fuente, src.tipo_fuente,
                    COUNT(f.id_fact_actividad) AS total_observaciones,
                    SUM(f.cantidad_menciones) AS total_menciones,
                    SUM(f.cantidad_interacciones) AS total_interacciones
                {joins}
                WHERE {where_sql}
                GROUP BY src.nombre_fuente, src.tipo_fuente
            )
            SELECT 
                nombre_fuente, tipo_fuente, total_observaciones, total_menciones, total_interacciones,
                ROUND((total_observaciones::numeric / NULLIF(SUM(total_observaciones) OVER (), 0)) * 100, 2) AS porcentaje_participacion
            FROM Totales
            ORDER BY porcentaje_participacion DESC;
        """
        return await fetch_all(db, query, params)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Error al consultar participación", "detail": str(e)})

@router.get("/tendencia")
async def get_tendencia(
    fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
    agentes: Optional[List[str]] = Query(None), categoria: Optional[str] = None,
    fuente: Optional[str] = None, plataforma: Optional[str] = None, tecnologia: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    try:
        joins, where_sql, params = build_filter_clause(fecha_inicio, fecha_fin, agentes, categoria, fuente, plataforma, tecnologia)
        query = f"""
            SELECT 
                t.anio, t.mes, t.nombre_mes,
                COUNT(f.id_fact_actividad) AS total_observaciones,
                SUM(f.cantidad_menciones) AS total_menciones,
                SUM(f.cantidad_interacciones) AS total_interacciones,
                ROUND(SUM(f.score_actividad), 4) AS score_actividad_total,
                ROUND(AVG(f.score_popularidad), 4) AS promedio_popularidad,
                ROUND(AVG(f.score_adopcion), 4) AS promedio_adopcion,
                ROUND(SUM(f.score_adopcion), 4) AS suma_adopcion,
                ROUND(SUM(f.score_innovacion), 4) AS suma_innovacion,
                ROUND(SUM(f.score_comunidad), 4) AS suma_comunidad
            {joins}
            WHERE {where_sql}
            GROUP BY t.anio, t.mes, t.nombre_mes
            ORDER BY t.anio ASC, t.mes ASC;
        """
        return await fetch_all(db, query, params)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Error al consultar tendencia", "detail": str(e)})

@router.get("/tendencia/agentes")
async def get_tendencia_agentes(
    fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
    agentes: Optional[List[str]] = Query(None), categoria: Optional[str] = None,
    fuente: Optional[str] = None, plataforma: Optional[str] = None, tecnologia: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    try:
        joins, where_sql, params = build_filter_clause(fecha_inicio, fecha_fin, agentes, categoria, fuente, plataforma, tecnologia, exclude_unidentified=True)
        query = f"""
            SELECT 
                t.anio, t.mes, t.nombre_mes, a.nombre_agente,
                COUNT(f.id_fact_actividad) AS total_observaciones,
                SUM(f.cantidad_menciones) AS total_menciones,
                SUM(f.cantidad_interacciones) AS total_interacciones,
                ROUND(SUM(f.score_adopcion), 4) AS adopcion
            {joins}
            WHERE {where_sql}
            GROUP BY t.anio, t.mes, t.nombre_mes, a.nombre_agente
            ORDER BY t.anio ASC, t.mes ASC;
        """
        return await fetch_all(db, query, params)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Error al consultar tendencia de agentes", "detail": str(e)})

@router.get("/ranking")
async def get_ranking(
    fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
    agentes: Optional[List[str]] = Query(None), categoria: Optional[str] = None,
    fuente: Optional[str] = None, plataforma: Optional[str] = None, tecnologia: Optional[str] = None,
    limit: int = 15, offset: int = 0, sort_by: str = 'total_observaciones', order: str = 'desc',
    db: AsyncSession = Depends(get_db)
):
    try:
        joins, where_sql, params = build_filter_clause(fecha_inicio, fecha_fin, agentes, categoria, fuente, plataforma, tecnologia, exclude_unidentified=True)
        allowed_sort = ['total_observaciones', 'total_menciones', 'total_interacciones', 'adopcion', 'popularidad', 'actividad', 'comunidad', 'innovacion', 'crecimiento']
        if sort_by not in allowed_sort:
            sort_by = 'total_observaciones'
        order_sql = "ASC" if order.lower() == 'asc' else "DESC"
        
        query = f"""
            WITH Agrupados AS (
                SELECT 
                    a.nombre_agente, a.categoria_agente,
                    COUNT(f.id_fact_actividad) AS total_observaciones,
                    SUM(f.cantidad_menciones) AS total_menciones,
                    SUM(f.cantidad_interacciones) AS total_interacciones,
                    ROUND(SUM(f.score_adopcion), 4) AS adopcion,
                    ROUND(SUM(f.score_popularidad), 4) AS popularidad,
                    ROUND(SUM(f.score_actividad), 4) AS actividad,
                    ROUND(SUM(f.score_comunidad), 4) AS comunidad,
                    ROUND(SUM(f.score_innovacion), 4) AS innovacion,
                    COUNT(DISTINCT src.nombre_fuente) AS total_fuentes,
                    COUNT(DISTINCT t.mes) AS meses_cobertura
                {joins}
                WHERE {where_sql}
                GROUP BY a.nombre_agente, a.categoria_agente
            )
            SELECT *,
                RANK() OVER(ORDER BY {sort_by} {order_sql}) as ranking_agente
            FROM Agrupados
            ORDER BY ranking_agente ASC
            LIMIT :limit OFFSET :offset;
        """
        params['limit'] = limit
        params['offset'] = offset
        return await fetch_all(db, query, params)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Error al consultar ranking", "detail": str(e)})

@router.get("/matriz_cobertura")
async def get_matriz_cobertura(
    fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
    agentes: Optional[List[str]] = Query(None), categoria: Optional[str] = None,
    fuente: Optional[str] = None, plataforma: Optional[str] = None, tecnologia: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    try:
        joins, where_sql, params = build_filter_clause(fecha_inicio, fecha_fin, agentes, categoria, fuente, plataforma, tecnologia, exclude_unidentified=True)
        query = f"""
            SELECT 
                a.nombre_agente, src.nombre_fuente,
                COUNT(f.id_fact_actividad) AS total_observaciones
            {joins}
            WHERE {where_sql}
            GROUP BY a.nombre_agente, src.nombre_fuente
            ORDER BY a.nombre_agente ASC, total_observaciones DESC;
        """
        return await fetch_all(db, query, params)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Error al consultar matriz", "detail": str(e)})

@router.get("/popularidad")
async def get_popularidad(db: AsyncSession = Depends(get_db)):
    try:
        return await fetch_all(db, "SELECT * FROM gold.vw_kpi_popularidad_open_source ORDER BY total_stars DESC LIMIT 20;")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Error al consultar popularidad", "detail": str(e)})

@router.get("/crecimiento")
async def get_crecimiento(db: AsyncSession = Depends(get_db)):
    try:
        return await fetch_all(db, "SELECT * FROM gold.vw_kpi_crecimiento_mensual ORDER BY anio ASC, mes ASC;")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Error al consultar crecimiento", "detail": str(e)})

@router.get("/distribucion")
async def get_distribucion(
    fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
    agentes: Optional[List[str]] = Query(None), categoria: Optional[str] = None,
    fuente: Optional[str] = None, plataforma: Optional[str] = None, tecnologia: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    try:
        joins, where_sql, params = build_filter_clause(fecha_inicio, fecha_fin, agentes, categoria, fuente, plataforma, tecnologia)
        query = f"""
            WITH Totales AS (
                SELECT 
                    p.nombre_plataforma,
                    COUNT(f.id_fact_actividad) AS total_observaciones
                {joins}
                WHERE {where_sql}
                GROUP BY p.nombre_plataforma
            )
            SELECT 
                nombre_plataforma, total_observaciones,
                ROUND((total_observaciones::numeric / NULLIF(SUM(total_observaciones) OVER (), 0)) * 100, 2) AS porcentaje_distribucion
            FROM Totales
            ORDER BY porcentaje_distribucion DESC;
        """
        return await fetch_all(db, query, params)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Error al consultar distribución", "detail": str(e)})

@router.get("/calidad/resumen")
async def get_calidad_resumen(db: AsyncSession = Depends(get_db)):
    try:
        return await fetch_one(db, "SELECT * FROM audit.quality_summary ORDER BY id DESC LIMIT 1;")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Error", "detail": str(e)})

@router.get("/calidad/dedup")
async def get_calidad_dedup(db: AsyncSession = Depends(get_db)):
    try:
        return await fetch_all(db, "SELECT * FROM audit.dedup_report ORDER BY id DESC LIMIT 10;")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Error", "detail": str(e)})

@router.get("/calidad/nulls")
async def get_calidad_nulls(db: AsyncSession = Depends(get_db)):
    try:
        return await fetch_all(db, "SELECT * FROM audit.nulls_matrix ORDER BY id DESC LIMIT 10;")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Error", "detail": str(e)})

@router.get("/categorias")
async def get_categorias(
    fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
    agentes: Optional[List[str]] = Query(None), categoria: Optional[str] = None,
    fuente: Optional[str] = None, plataforma: Optional[str] = None, tecnologia: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    try:
        joins, where_sql, params = build_filter_clause(fecha_inicio, fecha_fin, agentes, categoria, fuente, plataforma, tecnologia, exclude_unidentified=True)
        query = f"""
            SELECT 
                a.categoria_agente,
                COUNT(f.id_fact_actividad) AS total_observaciones,
                SUM(f.cantidad_menciones) AS total_menciones,
                ROUND(SUM(f.score_adopcion), 4) AS adopcion
            {joins}
            WHERE {where_sql}
            GROUP BY a.categoria_agente
            ORDER BY adopcion DESC;
        """
        return await fetch_all(db, query, params)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Error al consultar categorías", "detail": str(e)})

@router.get("/tecnologias")
async def get_tecnologias(
    fecha_inicio: Optional[str] = None, fecha_fin: Optional[str] = None,
    agentes: Optional[List[str]] = Query(None), categoria: Optional[str] = None,
    fuente: Optional[str] = None, plataforma: Optional[str] = None, tecnologia: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    try:
        joins, where_sql, params = build_filter_clause(fecha_inicio, fecha_fin, agentes, categoria, fuente, plataforma, tecnologia)
        query = f"""
            SELECT 
                tec.dominio_tecnologico,
                COUNT(f.id_fact_actividad) AS total_observaciones,
                SUM(f.cantidad_menciones) AS total_menciones,
                ROUND(SUM(f.score_adopcion), 4) AS adopcion
            {joins}
            WHERE {where_sql}
            GROUP BY tec.dominio_tecnologico
            ORDER BY adopcion DESC;
        """
        return await fetch_all(db, query, params)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Error al consultar tecnologías", "detail": str(e)})

@router.get("/filtros_opciones")
async def get_filtros_opciones(db: AsyncSession = Depends(get_db)):
    try:
        categorias = await fetch_all(db, "SELECT DISTINCT categoria_agente FROM gold.dim_agente WHERE categoria_agente IS NOT NULL ORDER BY categoria_agente ASC;")
        fuentes = await fetch_all(db, "SELECT DISTINCT nombre_fuente FROM gold.dim_fuente WHERE nombre_fuente IS NOT NULL ORDER BY nombre_fuente ASC;")
        plataformas = await fetch_all(db, "SELECT DISTINCT nombre_plataforma FROM gold.dim_plataforma WHERE nombre_plataforma IS NOT NULL ORDER BY nombre_plataforma ASC;")
        tecnologias = await fetch_all(db, "SELECT DISTINCT nombre_tecnologia FROM gold.dim_tecnologia WHERE nombre_tecnologia IS NOT NULL ORDER BY nombre_tecnologia ASC;")
        agentes_list = await fetch_all(db, "SELECT DISTINCT nombre_agente FROM gold.dim_agente WHERE nombre_agente NOT IN ('No Identificado', 'Otro Agente IA') ORDER BY nombre_agente ASC;")
        
        return {
            "categorias": [c["categoria_agente"] for c in categorias],
            "fuentes": [f["nombre_fuente"] for f in fuentes],
            "plataformas": [p["nombre_plataforma"] for p in plataformas],
            "tecnologias": [t["nombre_tecnologia"] for t in tecnologias],
            "agentes": [a["nombre_agente"] for a in agentes_list]
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Error al consultar opciones de filtros", "detail": str(e)})

# --- ETL Endpoints ---

@etl_router.post("/etl/run")
async def run_etl():
    try:
        client = docker.from_env()
        container = client.containers.get("observatorio_etl")
        container.start()
        return {"status": "started", "message": "Pipeline ETL iniciado."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Error al iniciar el ETL", "detail": str(e)})

@etl_router.get("/etl/status")
async def get_etl_status():
    try:
        client = docker.from_env()
        container = client.containers.get("observatorio_etl")
        container.reload()
        return {"status": container.status}
    except Exception as e:
        return {"status": "unknown", "detail": str(e)}

@etl_router.get("/etl/logs")
async def get_etl_logs():
    try:
        log_path = "/app/etl_logs/pipeline_run.log"
        if not os.path.exists(log_path):
            return {"logs": "No hay logs disponibles o el archivo no se ha creado."}
        
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            last_lines = lines[-500:] if len(lines) > 500 else lines
            return {"logs": "".join(last_lines)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Error al leer logs", "detail": str(e)})
