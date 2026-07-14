# Enriquecimiento de dimensiones semánticas

## Objetivo

`dim_plataforma`, `dim_tecnologia` y `dim_comunidad` se alimentan desde atributos
explícitos de Staging. Gold ya no usa `categoria`, `tipo_fuente`, `plataforma` o
`llm_capacidades` como sustitutos de entidades dimensionales.

## Jerarquía de evidencia

1. **Metadata estructurada:** lenguaje de GitHub/AIDev, etiquetas de Stack
   Overflow/DEV, entorno o integración declarada, propietario de repositorio,
   fuente editorial, institución o comunidad identificada.
2. **Regla contextual:** vocabulario versionado sobre título, texto y capacidades
   enriquecidas. Cada coincidencia produce nombre, categoría y dominio.
3. **Sin evidencia:** se carga el miembro explícito `No determinada`. No se copia
   otra columna para aparentar completitud.

## Trazabilidad en Staging

Cada registro conserva:

- `dim_plataforma_metodo`
- `dim_tecnologia_metodo`
- `dim_comunidad_metodo`

Los valores posibles distinguen metadata estructurada, regla de fuente, regla
contextual, normalización controlada o ausencia de evidencia.

`fuente` conserva el canal desde el que se capturó la observación. En cambio,
`dim_plataforma` representa el entorno de ejecución o integración del agente
(por ejemplo VS Code, JetBrains IDEs, Terminal/CLI, API/SDK o cloud). Su cálculo
no consulta `fuente` ni la columna heredada `plataforma`; si el registro no
contiene evidencia se carga `No determinada`. Al terminar el enriquecimiento,
la columna histórica `plataforma` se sincroniza con `dim_nombre_plataforma`
para que Staging tampoco conserve un espejo del canal de extracción.

## Ejemplos

| Evidencia | Plataforma | Tecnología | Comunidad |
|---|---|---|---|
| Repositorio capturado desde GitHub con `language=Python`, owner `acme`, sin entorno declarado | No determinada | Python | acme |
| Pregunta Stack Overflow que menciona integración con VS Code y tag `reactjs` | VS Code | React | Stack Overflow |
| Registro AIDev de Claude Code con `language=TypeScript` | Terminal / CLI | TypeScript | owner |
| Noticia sin plataforma ni tecnología verificable, publisher Reuters | No determinada | No determinada | Reuters |

## Extensión futura con LLM

Un LLM puede mejorar la cobertura, pero debe escribir atributos semánticos con
evidencia y confianza. El fallback seguirá siendo `No determinada`; nunca debe
reintroducirse el reciclaje de columnas de captura.
