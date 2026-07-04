# Entregable 4: Data Warehouse y Analitica

## Proyecto

**Plataforma de Inteligencia de Negocios para el analisis de tendencias, adopcion y evolucion de agentes de Inteligencia Artificial en el dominio del desarrollo de software mediante integracion de datos heterogeneos durante el periodo 2023-2026.**

Este documento explica como auditar el Data Warehouse fisico del Entregable 4. El objetivo es que el docente pueda verificar la existencia del modelo dimensional, la carga desde Staging, la integridad referencial y las vistas KPI implementadas dentro del motor de base de datos.

## Motor Utilizado

- **Motor relacional:** PostgreSQL 16
- **Orquestacion local:** Docker Compose
- **Contenedor de base de datos:** `observatorio_db`
- **Base de datos:** `observatorio_ia`

## Arquitectura Medallion y Esquemas Incluidos

El proyecto mantiene una arquitectura Medallion sobre PostgreSQL:

- `raw`: Capa Bronze, con archivos y registros originales en formato JSONB.
- `staging`: Capa Silver, con la tabla consolidada `staging.stg_actividad_agente_ia`.
- `gold`: Capa Gold, con el Data Warehouse dimensional, sus dimensiones, tabla de hechos y vistas KPI.
- `audit`: bitacoras, errores y metricas de calidad.

La fuente unica permitida para poblar el Data Warehouse Gold es:

```sql
staging.stg_actividad_agente_ia
```

## Orden de Ejecucion de Scripts

Los scripts deben ejecutarse en el siguiente orden:

```text
sql/00_auditoria_staging.sql
sql/01_create_gold_schema.sql
sql/02_load_gold_dimensions.sql
sql/03_load_gold_fact.sql
sql/04_create_kpi_views.sql
sql/05_consultas_analiticas_e4.sql
sql/06_validacion_gold_dw.sql
```

### Proposito de Cada Script

| Script | Proposito |
|---|---|
| `00_auditoria_staging.sql` | Audita la tabla `staging.stg_actividad_agente_ia` antes de poblar Gold. |
| `01_create_gold_schema.sql` | Crea el esquema `gold`, dimensiones, tabla de hechos, llaves foraneas e indices. |
| `02_load_gold_dimensions.sql` | Carga las dimensiones Gold usando exclusivamente datos de Staging. |
| `03_load_gold_fact.sql` | Carga la tabla de hechos conectandola con las dimensiones mediante JOINs explicitos. |
| `04_create_kpi_views.sql` | Crea vistas analiticas KPI dentro del esquema `gold`. |
| `05_consultas_analiticas_e4.sql` | Responde las preguntas de investigacion mediante consultas SQL sobre Gold. |
| `06_validacion_gold_dw.sql` | Genera evidencia auditable: conteos, integridad referencial, merma y validacion de vistas KPI. |

## Ejecucion Sugerida Dentro del Contenedor

Ejemplo de ejecucion desde la raiz del proyecto:

```powershell
docker exec -i observatorio_db psql -U postgres -d observatorio_ia -f /ruta/dentro/del/contenedor/sql/00_auditoria_staging.sql
docker exec -i observatorio_db psql -U postgres -d observatorio_ia -f /ruta/dentro/del/contenedor/sql/01_create_gold_schema.sql
docker exec -i observatorio_db psql -U postgres -d observatorio_ia -f /ruta/dentro/del/contenedor/sql/02_load_gold_dimensions.sql
docker exec -i observatorio_db psql -U postgres -d observatorio_ia -f /ruta/dentro/del/contenedor/sql/03_load_gold_fact.sql
docker exec -i observatorio_db psql -U postgres -d observatorio_ia -f /ruta/dentro/del/contenedor/sql/04_create_kpi_views.sql
docker exec -i observatorio_db psql -U postgres -d observatorio_ia -f /ruta/dentro/del/contenedor/sql/05_consultas_analiticas_e4.sql
docker exec -i observatorio_db psql -U postgres -d observatorio_ia -f /ruta/dentro/del/contenedor/sql/06_validacion_gold_dw.sql
```

Si los scripts se ejecutan desde el host, tambien pueden abrirse en una herramienta como pgAdmin, DBeaver o psql, siempre que la conexion apunte a la base `observatorio_ia`.

## Generacion del Dump Gold

Para entregar o respaldar el esquema Gold del Data Warehouse, ejecutar:

```powershell
docker exec -t observatorio_db pg_dump -U postgres -d observatorio_ia --schema=gold > dump_gold_entregable4.sql
```

Este comando exporta exclusivamente el esquema `gold`, incluyendo estructura, datos cargados y vistas SQL.

## Restauracion del Dump

Para restaurar el dump en una base PostgreSQL disponible:

```powershell
psql -U postgres -d observatorio_ia -f dump_gold_entregable4.sql
```

Antes de restaurar, se recomienda confirmar que la base `observatorio_ia` existe y que el usuario tiene permisos suficientes para crear esquemas, tablas, indices y vistas.

## Notas Academicas de Auditoria

- El Data Warehouse Gold se carga exclusivamente desde `staging.stg_actividad_agente_ia`.
- No se usa la zona Raw para poblar dimensiones, hechos ni KPIs del Entregable 4.
- No se usan datos mock, simulados o manuales dentro de los scripts Gold.
- Las dimensiones y la tabla de hechos se implementan fisicamente en PostgreSQL.
- Las llaves foraneas conectan la tabla `gold.fact_actividad_agente_ia` con las dimensiones del modelo estrella.
- Los KPIs viven dentro del motor de base de datos como vistas SQL en el esquema `gold`.
- El script `06_validacion_gold_dw.sql` debe usarse como evidencia final para comprobar conteos, integridad referencial y disponibilidad de vistas KPI.
