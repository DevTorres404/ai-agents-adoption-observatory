# Limpieza de la fuente retirada

Se eliminó el soporte de la encuesta propia: extractor, normalización, categorías,
reglas semánticas, métricas específicas, etiquetas de interfaz y columna exclusiva
en el esquema nuevo. Los filtros de fuentes impiden volver a cargarla por accidente.

## Base local: vaciada y verificada

El usuario autorizó después vaciar toda la base local. Se ejecutó `TRUNCATE` con
reinicio de secuencias sobre las 24 tablas de Raw, Staging, Gold y auditoría en
`observatorio_db` / `observatorio_ia`; una conexión posterior verificó **24 tablas,
0 filas totales**. Se conservaron tablas, vistas, relaciones y respaldos, y se
eliminó la columna obsoleta `gold.dim_fuente.es_fuente_propia`.

No se aplicó la migración selectiva a la base local: se sustituyó por ese vaciado
total autorizado. La migración `sql/12_remove_own_survey.sql` queda disponible para
otras bases existentes, **sin haber sido ejecutada ni validada allí**. Realiza el
borrado autorizado de la fuente y sus dependencias, en una transacción y con el
mismo lock de publicación de los workers. No usa `TRUNCATE` ni `CASCADE`.

Detener cualquier worker antiguo antes de aplicarla. Desde la raíz del proyecto,
con PostgreSQL disponible (PowerShell):

```powershell
Get-Content -Raw etl/sql/12_remove_own_survey.sql |
  docker compose exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose build etl etl-github
```

Para producción usar explícitamente `-f docker-compose.prod.yml` si se desea
aplicar allí la misma limpieza. No se ha cambiado producción.

La migración conserva las observaciones de otras fuentes. Invalida resúmenes de
calidad y totales de corridas afectadas, pues restar respuestas de totales no basta
para recalcular porcentajes y deduplicación. Tras aplicarla, regenerar Calidad
para las cohortes restantes; las corridas mixtas GitHub/otras usan `--pipeline all`.
Las corridas que queden vacías no se pueden reauditar como una carga exitosa.

Los dumps/backups multifuente y los informes académicos históricos no se reescriben:
contienen snapshots de otras fuentes, cifras agregadas y trabajo documental ajeno.
No restaurar un dump antiguo sin aplicar después esta migración. Las evidencias
CSV locales filtradas dejan de representar el snapshot original completo; sus
agregados históricos no son resultados recalculados. Deben regenerarse desde la
base una vez aplicada la limpieza. Los archivos de respuestas y Raw exclusivos de
la encuesta sí se eliminan del árbol local.
