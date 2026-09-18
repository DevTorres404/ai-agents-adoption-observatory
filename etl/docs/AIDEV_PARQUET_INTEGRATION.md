# Integración de los Parquet AIDev ampliados

## Ubicación activa

`etl/data/manual/aidedev_ai_coding/` es la única ubicación de entrada del ETL.
Los archivos de la raíz no se vuelven a leer ni se suman otra vez.
El volumen `./etl/data:/app/data` de Compose ya incluye esta carpeta.
Los Parquet y el manifiesto local están excluidos de Git: hay que transferirlos
explícitamente al desplegar, además de reconstruir la imagen ETL.

| Archivo | Filas nuevas | Filas anteriores conservadas | Filas consolidadas |
|---|---:|---:|---:|
| `all_pull_request.parquet` | 7.685.281 | 173.815 | 7.859.096 |
| `all_repository.parquet` | 957.209 | 14.489 | 971.698 |
| `all_user.parquet` | 399.962 | 6.713 | 406.675 |
| `pr_reviews.parquet` | 281.170 | 0 | 281.170 |
| `pr_task_type.parquet` | 32.702 | 0 | 32.702 |

Los nuevos datos **no son un superconjunto** de los anteriores. Se conservan
las filas cuyo ID solo existía antes; para IDs compartidos prevalece la fila
nueva completa, incluidas sus anotaciones. Los tres Parquet activos anteriores
fueron reemplazados; la copia de recuperación `.previous-expanded/` queda
apartada, sin ser leída por el ETL, pendiente de autorización explícita para
su eliminación definitiva.
Se preserva `is_forked` de repositorios; para filas históricas sin esa columna
queda nulo. Los 326 usuarios sin ID se conservan en el archivo, pero no se
consideran personas identificadas: hay 406.349 IDs de usuario distintos.

`dataset_manifest.json` registra filas, IDs únicos/nulos y SHA-256 de cada
entrada nueva, archivo anterior y archivo consolidado. `data_table.md` del
snapshot anterior ya no es una dependencia ni describe el conjunto activo.

## Extracción y uso de los cinco archivos

- DuckDB limita su memoria administrada a 1 GB y usa dos hilos. Sus tablas y
  temporales se escriben bajo una carpeta de trabajo exclusiva que se limpia
  al terminar; esto no equivale a un límite duro de RSS del proceso Python.
- Se leen solo columnas analíticas. No se cargan `body` de PR/revisiones ni
  `reason` de anotaciones, aunque permanecen intactos en los Parquet.
- El ETL productivo deduplica PR por ID y agrupa por agente/repositorio/año.
  Las claves anuales y compatibilidad histórica se describen en [ETL por fuente](SOURCE_ETLS.md). Un ID de
  repositorio faltante puede recuperarse por URL si la relación es única.
  Sin catálogo de repositorio se conserva una identidad por URL o por PR.
- Usuarios aportan contribuidores identificados y el total de IDs únicos.
- Las revisiones se deduplican y agregan **por PR antes del join**: totales,
  humanas/bot, aprobaciones, solicitudes de cambios y PR revisados.
- Las anotaciones aportan distribución por tipo de tarea, PR clasificados y
  confianza media original. En estos archivos la confianza está entre 2 y 10;
  **no** es un porcentaje de adopción ni se normaliza como tal.
- Raw conserva todos estos campos. Staging incorpora revisiones, cobertura de
  contribuidores y tipos de tarea en `texto`, sin alterar las fórmulas existentes
  de menciones/interacciones/adopción ni multiplicar el número de PR.
  No se añaden columnas numéricas específicas a Gold en este cambio.
- Se soportan los diez agentes configurados. El snapshot consolidado aporta seis
  etiquetas (`OpenAI_Codex`, `Copilot`, `Claude_Code`, `Cursor`, `Google_Jules`,
  `Devin`), homologadas a los nombres oficiales (`OpenAI_Codex` → `Codex`,
  `Copilot` → `GitHub Copilot Coding Agent`, `Cursor` → `Cursor Agent`,
  `Google_Jules` → `Google Jules`). No se inventan observaciones para las otras
  cuatro etiquetas ausentes.
- Se incluye todo el último día del rango configurado (2026-12-31), no solo
  su medianoche. Las fechas del dataset son UTC explícito; Staging conserva
  su conversión a la zona canónica del proyecto.
- La salida JSON se escribe por lotes/registros, nunca como una lista gigante
  en producción. Se publica mediante renombrado solo después de completarse;
  un fallo no expone un JSON parcial. El helper `build_aidedev_catalog` conserva
  su retorno de lista para pruebas/consumidores pequeños, no para ejecución masiva.

## Actualización reproducible

Con el ETL detenido y los cinco archivos recibidos en una carpeta separada:

```powershell
$env:PYTHONPATH="$PWD\etl"
.\venv\Scripts\python.exe -m src.scripts.prepare_aidedev_datasets `
  --source-dir . `
  --current-dir etl/data/manual/aidedev_ai_coding `
  --incoming-dir etl/data/manual/aidedev_ai_coding/.incoming-next
```

El preparador **no modifica las entradas ni activa el reemplazo**. Rechaza
IDs primarios duplicados, comprueba conteos/retención de IDs y escribe el
manifiesto. No sobrescribe una preparación previa: usar una carpeta vacía.
Validar el conjunto preparado antes de sustituir los cinco archivos activos;
guardar los anteriores hasta comprobar los hashes y publicar el nuevo
manifiesto al final. No sustituir archivos mientras otro ETL los está leyendo.
La preparación usa compresión Zstandard; cambia los bytes del Parquet, no
el significado de sus columnas.

Extracción local posterior:

```powershell
$env:PYTHONPATH="$PWD\etl"
.\venv\Scripts\python.exe -m src.extractors.aidedev
```

En Docker hay que reconstruir la imagen para incluir DuckDB y el nuevo código.
La nueva `.dockerignore` evita enviar varios GB de datos al contexto de build.
Se separó la instalación obligatoria de dependencias de la instalación
opcional del navegador para que un fallo de `pip` no quede oculto.

## Límites de esta entrega

Validación completa local: **1.026.064 registros agente/repositorio**, suma
de **7.859.096 PR**, **281.170 revisiones** de **83.081 PR**, y **32.702 PR
clasificados por tarea**. Google Jules aporta **296.411 PR**. La extracción
desde la ubicación canónica tardó **52,17 segundos**; la lectura posterior
del JSON completo verificó estas sumas. El JSON Raw pesa aproximadamente
971 MB. Evidencia detallada local:
`etl/docs/evidencias/aidedev-expanded-canonical/validation_result.json`.

La consolidación y extracción completa se verifican localmente. La salida
Raw queda lista para la siguiente carga, pero esta actualización de archivos
**no modifica PostgreSQL ni acredita una recarga Raw → Staging → Gold**.
El loader Raw y las fases siguientes mantienen sus implementaciones actuales;
el consumo de memoria acotado descrito aquí corresponde al extractor AIDev.
