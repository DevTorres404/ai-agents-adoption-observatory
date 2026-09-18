# Ejecutar y auditar un ETL por fuente

Las fuentes activas son **AIDev, GitHub, Google Trends y Hacker News**.
Stack Overflow queda desactivado, no Hacker News. El registro compartido
`etl/config/observatory_scope.json` controla extracción, carga y alcance analítico.
No se eliminan archivos Raw, registros históricos ni auditorías de fuentes retiradas.

## Preparación y primera ejecución

En una base existente, aplicar una vez la migración aditiva de trazabilidad:

```powershell
Get-Content -Raw etl/sql/13_source_run_config.sql | docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose build etl etl-aidedev etl-github etl-google-trends etl-hackernews backend
docker compose up -d --no-deps backend
```

Las bases nuevas incorporan esta columna mediante el script de inicialización.
No ejecutar los scripts de inicialización completos sobre una base existente.
Reconstruir el backend para que sus filtros usen el registro actualizado.

Cada comando siguiente ejecuta extracción → Raw → Staging → calidad → Gold
**solo para su fuente**, con un `run_id` independiente:

```powershell
docker compose run --rm etl-aidedev --from-year 2024 --to-year 2025
docker compose run --rm etl-github --from-year 2024 --to-year 2025
docker compose run --rm etl-google-trends --from-year 2024 --to-year 2025
docker compose run --rm etl-hackernews --from-year 2024 --to-year 2025
```

Estos comandos son ejemplos, no un registro de extracciones ejecutadas.
Los límites son inclusivos. Sin argumentos, se solicita desde 2023-01-01 hasta
el día de ejecución. No hace falta editar constantes del código para cambiar años.
Hacker News y Google Trends también admiten fechas concretas; GitHub las interpreta
como fechas de creación de repositorios:

```powershell
docker compose run --rm etl-hackernews --start-date 2022-03-01 --end-date 2022-11-30
```

No combinar fechas con años ni con los argumentos antiguos `--date`/`--github-since`.
Un rango invertido, incompleto o inválido falla antes de abrir una corrida.

## Independencia sin duplicar lógica

| Servicio | Módulo Python | Fuente interna | Artefactos de la fuente |
|---|---|---|---|
| `etl-aidedev` | `src.scripts.run_catalogo_pipeline` | `catalogo` | `etl/docs/catalogo`, `etl/logs/catalogo` |
| `etl-github` | `src.scripts.run_github_pipeline` | `github` | `etl/docs/github`, `etl/logs/github` |
| `etl-google-trends` | `src.scripts.run_google_trends_pipeline` | `google_trends` | `etl/docs/google_trends`, `etl/logs/google_trends` |
| `etl-hackernews` | `src.scripts.run_hackernews_pipeline` | `hackernews` | `etl/docs/hackernews`, `etl/logs/hackernews` |

Los ejecutables fijan su fuente y rechazan otra mediante `--pipeline`.
Comparten las reglas de transformación y PostgreSQL; cada extracción puede
trabajar independientemente. La publicación se serializa mediante un bloqueo
asesor para proteger las dimensiones y hechos compartidos. No son cuatro bases.

El servicio antiguo `etl` se conserva por compatibilidad: `main` agrupa AIDev,
Trends y Hacker News, sin GitHub. Para trazabilidad por fuente usar los cuatro
servicios anteriores. El botón existente del frontend sigue operando el servicio
agrupado; no se han añadido controles individuales en la interfaz.

## Trazabilidad y recuperación

- `audit.pipeline_runs.run_config`: fuente/perfil, fuentes seleccionadas, versión
  del alcance, fase, período solicitado y referencia de datos cuando se indicó.
- `docs/<fuente>/evidencias/runs/<run_id>/summary.json`: misma configuración,
  estado terminal y cantidades de extracción; `evidence.csv` conserva consultas
  e incidentes, incluso si no se obtuvo ningún archivo.
- `data/raw/<fuente>/`: salida original y metadatos del período; cada carga conserva
  el hash y la asociación a `run_id`. La ejecución completa consume únicamente
  su manifiesto, nunca los archivos recién generados por otro worker.
- `audit.quality_summary.data_run_id` y los identificadores Raw en Staging/Gold:
  relación entre el conjunto auditado, las transformaciones y los resultados.

```sql
SELECT run_id, status, execution_start, execution_end, run_config
FROM audit.pipeline_runs ORDER BY run_id DESC;
```

Para repetir procesamiento sin consultar la fuente:

```powershell
docker compose run --rm etl-hackernews --phase process --data-run-id 123
```

`123` debe ser un identificador real de Raw perteneciente exclusivamente a esa
fuente. La auditoría se refiere a esa corrida; Staging procesa los archivos
pendientes de la fuente y Gold publica sus filas normalizadas. No significa
reconstruir únicamente las fechas de esa corrida. Los rangos de extracción se
rechazan en `process`, `load`, `staging`, `quality` y `gold` para no fingir un filtro.
Los conjuntos históricos mixtos o con fuentes retiradas no se reasignan a un
worker: se conservan y se obtiene una corrida nueva de la fuente necesaria.

`--phase extract` no carga la BD. `--phase load` recupera archivos pendientes
de la fuente. `rebuild` es mantenimiento global explícito: no está permitido
en los workers individuales porque podría borrar datos de otras fuentes.

## Qué significa solicitar años

- **AIDev:** filtra por creación de PR en UTC dentro de los Parquet disponibles.
  El ETL publica agregados por agente/repositorio/año, con clave terminada en
  `:year:AAAA`; cargar otro año no sobrescribe el anterior. Se requieren años
  completos o el año actual hasta hoy. Las revisiones, merges y atributos de
  repositorio proceden del snapshot: no representan necesariamente su estado
  al cierre del año. El punto temporal del agregado es su última actividad,
  no una serie mensual de cada PR. El helper local conserva un modo agregado
  antiguo para consumidores pequeños; el ETL productivo usa el grano anual.
- **GitHub:** busca repositorios por `created:`. Estrellas, forks y otros
  atributos se observan al consultar; no reconstruye sus valores históricos.
- **Google Trends:** solicita el período a la fuente. Los valores son relativos
  a cada consulta y grupo de términos; cambiar el período puede cambiar la
  escala. No se deben sumar ni comparar como conteos absolutos de usuarios.
- **Hacker News:** consulta publicaciones por fecha de creación, divide ventanas
  anuales y subdivide intervalos saturados. Las cuotas, presupuestos o ventanas
  que no puedan completarse se registran como fallos o resultados parciales.

Solicitar un año no garantiza cobertura de ese año. Un conjunto vacío no se
rellena con datos de otra fecha, otra fuente o un catálogo manual alternativo.
Staging ya no descarta silenciosamente fechas fuera de 2023–2026.

### Compatibilidad con los agregados antiguos de AIDev

Raw, Staging y Gold históricos se preservan. Cuando se publique el primer
conjunto anual en Gold, la API dará preferencia al grano anual para todo AIDev
y excluirá de las consultas activas los agregados antiguos sin año, evitando
sumar ambos. La cobertura visible será la de los años efectivamente publicados;
conviene comenzar con todo el período que se quiera mantener visible.
Las vistas SQL históricas y los informes de auditoría no se reescriben.

## Comprobación y límites operativos

Las pruebas incluyen contratos sin red para selección de fuente/rango, metadatos,
límites de calendario y claves anuales. La prueba optativa
`etl/tests/test_postgres_recovery.py` ejecuta los cuatro workers contra PostgreSQL
aislado con extractores simulados: comprueba publicación real, claves y auditoría,
pero no acredita cobertura de las APIs externas. Requiere una base desechable
vacía, nunca la base operativa.

La reversión de esta unidad debe limitarse a los cambios de workers, ventanas,
registro de alcance, consultas activas y sus pruebas/documentación. No restaurar
archivos completos que ya contenían cambios ajenos. La columna de auditoría
añadida puede permanecer; no borrar corridas ni archivos como parte de una reversión.
