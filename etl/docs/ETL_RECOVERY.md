# Recuperación y validación del ETL

> Desde la separación del 16 de septiembre, `etl` excluye GitHub y `etl-github`
> lo procesa de forma independiente. Ver `MICRO_ETL_GITHUB.md` antes de recuperar
> una corrida histórica multifuente.

## Cambios de septiembre de 2026

- Raw revierte metadata y registros juntos, propaga errores al orquestador y
  registra `run_id`. Un JSON ilegible ya no se confirma como un archivo vacío.
- La transacción comienza antes del SELECT del hash (evita el conflicto con
  `autobegin` de SQLAlchemy). Los registros se insertan en lotes de 1.000.
- Calidad distingue la ejecución de auditoría (`run_id`) de la corrida de datos
  (`data_run_id`, persistida en `audit.quality_summary`). Auditar de nuevo no
  cambia el estado de la extracción original ni sus etiquetas manuales.
- Sin registros Raw se publica `empty` y completitud 0%, no éxito al 100%.
  Pérdidas detectadas en Staging hacen fallar la ejecución antes de Gold.
- `process` ejecuta Staging, Calidad y Gold sobre Raw existente, sin descargar
  fuentes ni cargar archivos. Staging y Gold tienen alcance incremental por
  perfil; `--data-run-id` selecciona solamente la cohorte auditada por Calidad.
- `--date` controla el límite superior `created:` de GitHub; `--github-since`
  permite un límite inferior explícito. Las demás fuentes conservan sus rangos.
  Esto NO es extracción incremental por cambios: una ventana de creación omite
  actualizaciones de repositorios antiguos. No se reduce automáticamente la cobertura.
- El log incluye `ETL timing run_id=... phase=... duration_seconds=...` incluso
  si falla una fase. Las pruebas no escriben en los registros/evidencias reales.

## Despliegue seguro

La migración está tanto en `sql/10_quality_governance.sql` (incluida en la imagen
ETL) como en `initdb/10_quality_governance.sql`. Una prueba exige igualdad de ambas.
Una base nueva ejecuta initdb; un volumen existente necesita la migración explícita.
No borrar volúmenes. Verificar previamente respaldo y migraciones anteriores
`08_incremental_staging.sql` y `09_incremental_gold.sql` si aún están pendientes.

Desde la raíz del repositorio, con PostgreSQL disponible:

```powershell
docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/10_quality_governance.sql'
docker compose --profile etl build etl
docker compose --profile etl run --rm etl --phase quality
docker compose --profile etl run --rm etl --phase process
```

Para producción, agregar `-f docker-compose.prod.yml` después de `docker compose`.
No se ejecutó esta migración sobre la base existente ni se desplegó la imagen.
Se validó en un PostgreSQL 16 separado, temporal y sin datos de producción.

`quality` y `process` seleccionan por defecto el mayor `run_id` con registros Raw
del mismo perfil. Las corridas históricas mixtas requieren `--pipeline all`.
Se puede especificar `--data-run-id NUMERO` para auditar otra corrida cargada. Una
corrida inexistente o sin Raw se rechaza. Datos legacy sin `run_id` necesitan una
migración de procedencia explícita; no se atribuyen a una corrida inventada.

Para una extracción deliberadamente acotada de GitHub:

```powershell
docker compose run --rm etl-github --phase all --github-since 2026-09-01 --date 2026-09-13
```

No usar `rebuild` para acelerar: reconstruye datos. Las incidencias externas
(429, DNS, Ollama ausente) siguen dependiendo del proveedor/entorno; no se
eliminan desactivando límites de peticiones. El error histórico de
`transformation_version` requiere verificar que se reconstruyó la imagen: el
código actual asigna `staging-v1` antes de insertar.

## Medición y estimación, no garantía de producción

Validación: 69 pruebas unitarias y 11 subpruebas pasaron. Las 5 integraciones
omitidas en la suite offline se ejecutaron aparte y pasaron en PostgreSQL 16:
migraciones repetidas, Staging, Gold, aislamiento de calidad y un recorrido
Raw → Staging → Calidad → Gold con reejecución y claves estables. El recorrido
usó dos registros sintéticos, sin fuentes externas ni Ollama real. No representa
una extracción completa ni una prueba de volumen de producción.

Microbenchmark PostgreSQL 16 en Docker (almacenamiento temporal en memoria),
SQLAlchemy + psycopg3, tabla temporal JSONB con clave primaria, 10.000 registros,
una transacción, preparación inicial y mediana de 5 repeticiones alternadas.
Se comprobó que ambas variantes insertaron todos los registros.

| Variante | Mediana | Llamadas execute para registros |
|---|---:|---:|
| INSERT individual | 12,811179 s | 10.000 |
| Lotes de 1.000 | 0,531503 s | 10 |

**95,85% menos tiempo en ese microbenchmark de INSERT**, no en el pipeline completo.
La reducción de llamadas a SQLAlchemy es 99,9%; no equivale al mismo porcentaje
de peticiones de red. No mide JSON, hashing, lectura, extracción HTTP,
enriquecimiento, Calidad ni Gold. El escenario no replica el disco, las claves
foráneas ni la carga de producción. Una prueba adicional con SQLite en memoria,
20.000 registros y mediana de 7 repeticiones dio 85,0% menos tiempo (0,539720 s
frente a 0,080943 s), ilustrando que el entorno afecta el resultado.

El tramo histórico del 27 de agosto medía aproximadamente 1.153 s de extracción,
165 s de carga Raw y 61 s de Staging hasta fallar (1.379 s, 23 min). Si TODA la
carga Raw mejorara un 95,85% y lo demás permaneciera idéntico, ese tramo bajaría a
1.221 s (20 min 21 s): **11,5% menos**. Es un escenario optimista ilustrativo,
no una medición extremo a extremo: la carga Raw contiene trabajo no optimizado,
y faltan Calidad/Gold en esa corrida fallida. No extrapolar a una extracción
GitHub con distinto volumen o número de particiones.

`process` evita íntegramente extracción+carga Raw: unos 21 min 58 s del tramo
histórico, a cambio de no actualizar fuentes. No se puede dar un porcentaje
total fiable para una ejecución completa hasta medir todas sus fases con el
mismo conjunto de datos, entorno y configuración.
