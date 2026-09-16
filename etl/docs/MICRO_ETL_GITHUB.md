# ETL principal y micro ETL de GitHub

El ETL queda dividido en dos procesos batch independientes:

| Servicio Compose | Ejecutable Python | Alcance |
| --- | --- | --- |
| `etl` | `src.scripts.run_pipeline` | Todas las fuentes **excepto GitHub** |
| `etl-github` | `src.scripts.run_github_pipeline` | **Solo GitHub** |

Los perfiles solo procesan fuentes activas. Las fuentes retiradas quedan excluidas
también de `load`, Staging y Gold, incluso en mantenimiento global.

Ambos reutilizan la imagen y las reglas de transformación existentes. Comparten
PostgreSQL y el Data Warehouse: no se duplican bases, tablas ni lógica de negocio.
Cada ejecución tiene su propio `audit.pipeline_runs.run_id`. Los resúmenes de
extracción `runs/<run_id>/summary.json` incluyen el campo `pipeline`.

## Ejecutar desde la raíz del repositorio

```powershell
docker compose build etl etl-github

# Principal: ya no consulta la API de GitHub.
docker compose run --rm etl

# GitHub: ejecutar en otra terminal o con otra programación.
docker compose run --rm etl-github
```

Los comandos `run` habilitan automáticamente el servicio solicitado aunque esté
en un profile. También pueden iniciarse ambos jobs en segundo plano:

```powershell
docker compose --profile etl --profile etl-github up -d etl etl-github
docker compose logs -f etl
docker compose logs -f etl-github
```

Son jobs de una ejecución, no demonios ni tareas periódicas. Para una nueva
ejecución usar `run --rm`. En producción añadir `-f docker-compose.prod.yml`
inmediatamente después de `docker compose`; ambos archivos incluyen la división.
El backend conserva su control anterior del contenedor `observatorio_etl`;
el micro ETL de GitHub se opera mediante estos comandos, no mediante un botón nuevo.

Configurar `GITHUB_TOKEN` en `.env` (sin subirlo a Git). Solo el servicio
`etl-github` recibe ese token. El rate limiting y los reintentos se mantienen:
separar el job evita esperar por GitHub, **no acelera su API ni elimina sus cuotas**.

Para acotar deliberadamente la búsqueda:

```powershell
docker compose run --rm etl-github --github-since 2026-09-01 --date 2026-09-16
```

La ventana es por fecha de **creación** de repositorios, no por actualización.
Sin `--github-since` se conserva el rango histórico del extractor.

## Aislamiento y concurrencia

- **Extracción:** el principal no llama al extractor GitHub; el micro ETL no
  llama a los demás extractores. Las dos extracciones pueden avanzar a la vez.
- **Raw:** en `--phase all` solo se cargan los archivos publicados por esa
  extracción. Un manifiesto vacío no provoca la carga del histórico. La fase
  explícita `load` busca pendientes únicamente de las fuentes del worker.
- **Staging:** selecciona archivos pendientes y versiones solo de sus fuentes.
- **Gold:** los SQL compartidos leen únicamente el Staging de su perfil mediante
  una configuración local a la transacción. Se conservan hechos de otras fuentes
  y claves existentes; las dimensiones siguen siendo compartidas.
- **Publicación:** un advisory lock de PostgreSQL coordina Raw → Staging →
  Calidad → Gold entre los runners. No se toma durante la extracción. Si los dos
  jobs terminan de extraer a la vez, uno espera el procesamiento del otro. No son
  dos escritores concurrentes sobre las mismas dimensiones.
- **Errores:** un fallo total de extracción impide ejecutar las fases siguientes
  y termina con error. Los resultados parciales mantienen `partial_success`.
  Las comprobaciones de integridad Gold siguen validando el almacén compartido.

El servicio GitHub escribe logs en `etl/logs/github/` y documentos/evidencias
en `etl/docs/github/`; el principal conserva `etl/logs/` y `etl/docs/`. Los Raw
permanecen en `etl/data/raw/<fuente>/`, protegidos por los filtros del loader.
Los CSV "latest" representan la última corrida del worker, no la unión de ambos.
Para comparar ejecuciones consultar las evidencias por `run_id` y las tablas audit.

## Recuperación sin repetir extracción

```powershell
docker compose run --rm etl-github --phase extract
docker compose run --rm etl-github --phase load
docker compose run --rm etl-github --phase process
docker compose run --rm etl-github --phase quality --data-run-id 42
```

`process` transforma los pendientes del perfil, audita una cohorte Raw y publica
el Staging de ese perfil en Gold. `quality/process` eligen por defecto el último
`run_id` cargado del **mismo perfil**, no la corrida más reciente del otro ETL.
`--data-run-id` selecciona la cohorte de calidad, no limita todo el procesamiento
a esa corrida. Un ID de otra fuente, vacío o inexistente se rechaza.

Corridas históricas que mezclan GitHub y otras fuentes requieren mantenimiento
global explícito para conservar su reconciliación original:

```powershell
docker compose run --rm etl --pipeline all --phase process --data-run-id 42
```

`--pipeline all` mantiene el modo global. `rebuild` solo se permite en ese modo;
no usarlo para acelerar ni para reintentar. Los scripts de bajo nivel ejecutados
directamente conservan alcance global por compatibilidad: usar los runners para
beneficiarse del aislamiento y del lock. Antes de actualizar, comprobar que no
queda activo un contenedor con la imagen antigua (no conoce el lock). No borrar
volúmenes ni dumps. No se requiere una migración nueva para esta separación;
siguen siendo necesarias las migraciones previas descritas en `ETL_RECOVERY.md`.

## Python local y pruebas

Desde `etl`, con dependencias y conexión PostgreSQL configuradas:

```powershell
python -m src.scripts.run_pipeline
python -m src.scripts.run_github_pipeline
```

Sin los montajes Docker ambos ejecutables locales comparten el directorio de
logs/documentos; las evidencias por `run_id` siguen separadas. Para aislamiento
operativo de archivos usar los servicios Compose.

Desde la raíz, instalar `etl/requirements-dev.txt` en un entorno virtual y ejecutar:

```powershell
$env:PYTHONPATH="$PWD\etl"
python -m pytest etl/tests -q -p no:cacheprovider
```

Las pruebas offline verifican selección de extractores, manifiestos, aislamiento
Raw con SQLAlchemy/SQLite, selección de cohortes, propagación de errores, bloqueo,
protección de rebuild y configuración local/producción. Las integraciones
PostgreSQL requieren una base desechable y activación explícita; no usar producción.
