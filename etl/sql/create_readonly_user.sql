-- ============================================================
-- Crear usuario de solo lectura para FastAPI
-- Uso: psql -U postgres -d observatorio_ia -f create_readonly_user.sql
-- ============================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'observatorio_readonly') THEN
        CREATE ROLE observatorio_readonly WITH LOGIN PASSWORD 'changeme_readonly' NOBYPASSRLS;
    END IF;
END
$$;

-- Revocar privilegios por defecto (seguridad)
REVOKE ALL ON DATABASE observatorio_ia FROM PUBLIC;

-- Conectar a la base
GRANT CONNECT ON DATABASE observatorio_ia TO observatorio_readonly;

-- Permitir USAGE en esquemas
GRANT USAGE ON SCHEMA gold TO observatorio_readonly;
GRANT USAGE ON SCHEMA audit TO observatorio_readonly;

-- SELECT en tablas y vistas existentes
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO observatorio_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA audit TO observatorio_readonly;

-- Privilegios por defecto para futuros objetos
ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO observatorio_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA audit GRANT SELECT ON TABLES TO observatorio_readonly;

-- Verificar
SELECT grantee, privilege_type, table_schema, table_name
FROM information_schema.role_table_grants
WHERE grantee = 'observatorio_readonly'
ORDER BY table_schema, table_name;
