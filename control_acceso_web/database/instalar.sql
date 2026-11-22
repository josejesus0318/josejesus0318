-- Instalación completa con psql:
--   psql "postgresql://usuario:contraseña@servidor/neondb?sslmode=require" -f instalar.sql
-- (Sin psql: python herramientas/instalar_bd.py, ver GUIA_DESPLIEGUE.md)
\set ON_ERROR_STOP on
\echo '>> 1/5 Esquema'
\i 01_esquema.sql
\echo '>> 2/5 Funciones y triggers'
\i 02_funciones.sql
\echo '>> 3/5 Vistas'
\i 03_vistas.sql
\echo '>> 4/5 Datos de demostración'
\i 04_datos.sql
\echo '>> 5/5 Seguridad'
\i 05_seguridad.sql
\echo '>> Instalación terminada'
SELECT 'personas' AS tabla, count(*) FROM campus.personas
UNION ALL SELECT 'credenciales', count(*) FROM campus.credenciales
UNION ALL SELECT 'registro_accesos', count(*) FROM campus.registro_accesos
UNION ALL SELECT 'usuarios', count(*) FROM campus.usuarios;
