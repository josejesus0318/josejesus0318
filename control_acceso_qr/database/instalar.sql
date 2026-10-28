/* =====================================================================
   INSTALADOR DEL MODELO v2
   Crea la base grupo_solutions_v2 (si no existe) y ejecuta en orden los
   scripts 01 a 05. Se puede volver a ejecutar: reconstruye las tablas.

   Uso (desde la carpeta control_acceso_qr, como usuario postgres):
       sudo -u postgres psql -f database/instalar.sql
   ===================================================================== */
\set ON_ERROR_STOP on

SELECT 'CREATE DATABASE grupo_solutions_v2'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'grupo_solutions_v2') \gexec

\c grupo_solutions_v2

\echo '>> 01 Esquema'
\ir 01_esquema.sql
\echo '>> 02 Datos'
\ir 02_datos.sql
\echo '>> 03 Funciones y triggers'
\ir 03_funciones.sql
\echo '>> 04 Vistas'
\ir 04_vistas.sql
\echo '>> 05 Seguridad'
\ir 05_seguridad.sql
\echo '>> Instalación terminada'
