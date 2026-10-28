/* =====================================================================
   SCRIPT 05 – USUARIOS, ROLES Y PRIVILEGIOS (Actividad 3.1)
   Proyecto : Sistema de Control de Acceso con Códigos QR – Grupo Solutions
   Materia  : Taller de Bases de Datos – ITVH (Equipo 6 Magenta)
   SGBD     : PostgreSQL 18 (compatible con 15 o superior)
   Requiere 01, 02 y 04. Las contraseñas son de ejemplo para el entorno
   escolar: cámbialas antes de usar este script en otro entorno.
   ===================================================================== */

-- Restringir el acceso público a la base
REVOKE ALL ON DATABASE grupo_solutions FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- Usuarios
CREATE ROLE admin_gs       LOGIN PASSWORD 'AdminGS#2026' CREATEROLE;
CREATE ROLE guardia_sergio LOGIN PASSWORD 'Seguridad#2026';
CREATE ROLE recep_paola    LOGIN PASSWORD 'Recepcion#2026' VALID UNTIL '2027-06-30';
CREATE ROLE rrhh_roberto   LOGIN PASSWORD 'Personal#2026';
CREATE USER dir_mariana          PASSWORD 'Direccion#2026';
CREATE ROLE app_lector_qr  LOGIN PASSWORD 'LectorQR#2026' CONNECTION LIMIT 5;
CREATE ROLE cont_karla     LOGIN PASSWORD 'Contrato#2026' VALID UNTIL '2026-12-31';

-- Roles de grupo
CREATE ROLE rol_admin_bd  NOLOGIN;
CREATE ROLE rol_seguridad NOLOGIN;
CREATE ROLE rol_recepcion NOLOGIN;
CREATE ROLE rol_rrhh      NOLOGIN;
CREATE ROLE rol_consulta  NOLOGIN;
CREATE ROLE rol_lector_qr NOLOGIN;

-- Conexión a la base para todos los roles
GRANT CONNECT ON DATABASE grupo_solutions
    TO rol_admin_bd, rol_seguridad, rol_recepcion, rol_rrhh, rol_consulta, rol_lector_qr;

-- rol_admin_bd: administración completa del proyecto
GRANT TEMPORARY ON DATABASE grupo_solutions TO rol_admin_bd;
GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO rol_admin_bd;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO rol_admin_bd;
GRANT pg_monitor TO rol_admin_bd;

-- rol_seguridad: bitácora y estado de credenciales
GRANT SELECT ON registro_accesos, credenciales, puntos_acceso, roles_acceso TO rol_seguridad;
GRANT INSERT ON registro_accesos TO rol_seguridad;
GRANT UPDATE (estado) ON credenciales TO rol_seguridad;
GRANT USAGE ON SEQUENCE registro_accesos_id_registro_seq TO rol_seguridad;
GRANT SELECT ON vw_bitacora_detallada, vw_credenciales_activas, vw_afluencia_diaria TO rol_seguridad;

-- rol_recepcion: visitantes y credenciales temporales
GRANT SELECT, INSERT ON visitantes TO rol_recepcion;
GRANT INSERT ON credenciales TO rol_recepcion;
GRANT USAGE ON SEQUENCE visitantes_id_visitante_seq, credenciales_id_credencial_seq TO rol_recepcion;
GRANT SELECT ON vw_directorio_colaboradores, vw_ficha_visitantes, vw_directorio_unificado TO rol_recepcion;

-- rol_rrhh: administración del personal (sin DELETE: las bajas son lógicas)
GRANT SELECT, INSERT, UPDATE ON colaboradores, puestos, departamentos, horarios_laborales TO rol_rrhh;
GRANT USAGE ON SEQUENCE colaboradores_id_colaborador_seq, puestos_id_puesto_seq TO rol_rrhh;
GRANT SELECT ON vw_expediente_colaborador, vw_antiguedad_colaboradores, vw_colaboradores_sin_acceso TO rol_rrhh;

-- rol_consulta: solo vistas de reportes
GRANT SELECT ON vw_afluencia_diaria, vw_departamentos_concentrados, vw_indicadores_colaborador,
                vw_bitacora_detallada, vw_puntos_compartidos, vw_activos_sin_registro TO rol_consulta;

-- rol_lector_qr: validar credenciales y registrar eventos
GRANT SELECT (id_credencial, codigo_qr, estado, fecha_vigencia) ON credenciales TO rol_lector_qr;
GRANT SELECT ON puntos_acceso TO rol_lector_qr;
GRANT INSERT (id_credencial, id_punto_acceso, tipo_evento) ON registro_accesos TO rol_lector_qr;
GRANT USAGE ON SEQUENCE registro_accesos_id_registro_seq TO rol_lector_qr;

-- Asignación de roles a usuarios
GRANT rol_admin_bd  TO admin_gs WITH ADMIN OPTION;
GRANT rol_seguridad TO guardia_sergio;
GRANT rol_recepcion TO recep_paola;
GRANT rol_rrhh      TO rrhh_roberto;
GRANT rol_consulta  TO dir_mariana;
GRANT rol_lector_qr TO app_lector_qr;

-- Baja de la contratista (cuenta deshabilitada, no eliminada)
ALTER ROLE cont_karla NOLOGIN;

-- =====================================================================
-- Verificación
-- =====================================================================
-- Membresías de los roles de grupo
SELECT r.rolname AS rol, m.rolname AS miembro, am.admin_option
FROM pg_auth_members am
JOIN pg_roles r ON r.oid = am.roleid
JOIN pg_roles m ON m.oid = am.member
WHERE r.rolname LIKE 'rol\_%'
ORDER BY rol, miembro;

-- Matriz de privilegios por usuario
SELECT u.usuario, t.tabla,
       has_table_privilege(u.usuario, t.tabla, 'SELECT') AS sel,
       has_table_privilege(u.usuario, t.tabla, 'INSERT') AS ins,
       has_table_privilege(u.usuario, t.tabla, 'UPDATE') AS upd,
       has_table_privilege(u.usuario, t.tabla, 'DELETE') AS del
FROM (VALUES ('guardia_sergio'), ('recep_paola'), ('rrhh_roberto'), ('dir_mariana')) AS u(usuario)
CROSS JOIN (VALUES ('colaboradores'), ('visitantes'), ('credenciales'), ('registro_accesos')) AS t(tabla)
ORDER BY u.usuario, t.tabla;
