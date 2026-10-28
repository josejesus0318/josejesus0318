/* =====================================================================
   MODELO v2 – SEGURIDAD: ROLES, PRIVILEGIOS Y CUENTAS DE DEMOSTRACIÓN
   Principio de mínimo privilegio. La aplicación no guarda contraseñas:
   cada persona inicia sesión con su propia cuenta de PostgreSQL y la
   base de datos aplica los permisos de su rol.

   Los roles rol_* son de todo el servidor; si ya existen (por ejemplo,
   de la Actividad 3.1) se reutilizan.
   ===================================================================== */

-- ---------------------------------------------------------------------
-- 1. Cerrar el acceso público
-- ---------------------------------------------------------------------
DO $$ BEGIN
    EXECUTE format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database());
END $$;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
-- Por omisión PostgreSQL da EXECUTE a PUBLIC sobre toda función nueva
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;

-- ---------------------------------------------------------------------
-- 2. Roles de grupo (se crean solo si no existen)
-- ---------------------------------------------------------------------
DO $$
DECLARE r TEXT;
BEGIN
    FOREACH r IN ARRAY ARRAY['rol_admin_bd', 'rol_seguridad', 'rol_recepcion',
                             'rol_rrhh', 'rol_consulta', 'rol_lector_qr'] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN', r);
        END IF;
        EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), r);
        EXECUTE format('GRANT USAGE ON SCHEMA public TO %I', r);
    END LOOP;
END $$;

-- ---------------------------------------------------------------------
-- 3. Privilegios comunes
-- ---------------------------------------------------------------------
-- Todos ven sus propios datos y los indicadores del día
GRANT SELECT ON vw_mi_usuario, vw_resumen_hoy
    TO rol_admin_bd, rol_seguridad, rol_recepcion, rol_rrhh, rol_consulta, rol_lector_qr;

-- Catálogos de consulta para las listas desplegables de las pantallas
GRANT SELECT ON ubicaciones, departamentos, puestos, dias_semana, horarios_laborales, horario_dias,
                tipos_identificacion, empresas, roles_acceso, puntos_acceso, permisos_rol_punto,
                estados_credencial
    TO rol_seguridad, rol_recepcion, rol_rrhh;

-- ---------------------------------------------------------------------
-- 4. rol_admin_bd: administración completa del proyecto
-- ---------------------------------------------------------------------
GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO rol_admin_bd;   -- incluye vistas
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO rol_admin_bd;
GRANT EXECUTE ON FUNCTION sp_registrar_acceso(VARCHAR, INT),
                          sp_crear_usuario(VARCHAR, TEXT, VARCHAR, INT),
                          sp_cambiar_estado_usuario(VARCHAR, BOOLEAN),
                          sp_restablecer_password(VARCHAR, TEXT),
                          fn_es_admin()
    TO rol_admin_bd;

-- ---------------------------------------------------------------------
-- 5. rol_rrhh: estructura organizacional, horarios y personal
--    Sin DELETE en colaboradores: las bajas son lógicas
-- ---------------------------------------------------------------------
GRANT INSERT, UPDATE, DELETE ON ubicaciones, departamentos, puestos,
                                horarios_laborales, horario_dias TO rol_rrhh;
GRANT SELECT, INSERT, UPDATE ON colaboradores TO rol_rrhh;
GRANT USAGE ON SEQUENCE ubicaciones_id_ubicacion_seq, departamentos_id_departamento_seq,
                        puestos_id_puesto_seq, horarios_laborales_id_horario_seq,
                        colaboradores_id_colaborador_seq TO rol_rrhh;
GRANT SELECT ON vw_colaboradores_detalle, vw_directorio TO rol_rrhh;

-- ---------------------------------------------------------------------
-- 6. rol_recepcion: visitantes, visitas y credenciales de visita
-- ---------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE ON visitantes, visitas, empresas TO rol_recepcion;
GRANT SELECT, INSERT ON credenciales TO rol_recepcion;
GRANT UPDATE (id_estado) ON credenciales TO rol_recepcion;
GRANT USAGE ON SEQUENCE visitantes_id_visitante_seq, visitas_id_visita_seq,
                        empresas_id_empresa_seq, credenciales_id_credencial_seq TO rol_recepcion;
GRANT SELECT ON vw_directorio, vw_visitantes_detalle, vw_visitas_detalle,
                vw_credenciales_detalle, vw_personas_dentro TO rol_recepcion;

-- ---------------------------------------------------------------------
-- 7. rol_seguridad: credenciales, puntos de acceso y bitácora
-- ---------------------------------------------------------------------
GRANT SELECT, INSERT ON credenciales TO rol_seguridad;
GRANT UPDATE (id_estado, fecha_vigencia) ON credenciales TO rol_seguridad;
GRANT INSERT, UPDATE, DELETE ON puntos_acceso, permisos_rol_punto, roles_acceso TO rol_seguridad;
GRANT SELECT ON registro_accesos, visitas TO rol_seguridad;   -- visitas: para emitir credenciales de visita
GRANT USAGE ON SEQUENCE credenciales_id_credencial_seq, puntos_acceso_id_punto_acceso_seq,
                        roles_acceso_id_rol_acceso_seq TO rol_seguridad;
GRANT SELECT ON vw_directorio, vw_visitas_detalle, vw_credenciales_detalle,
                vw_bitacora, vw_personas_dentro TO rol_seguridad;
GRANT EXECUTE ON FUNCTION sp_registrar_acceso(VARCHAR, INT) TO rol_seguridad;

-- ---------------------------------------------------------------------
-- 8. rol_consulta: solo lectura de vistas (Dirección)
-- ---------------------------------------------------------------------
GRANT SELECT ON vw_bitacora, vw_personas_dentro, vw_credenciales_detalle,
                vw_colaboradores_detalle, vw_visitas_detalle TO rol_consulta;

-- ---------------------------------------------------------------------
-- 9. rol_lector_qr: solo validar y registrar accesos
--    No puede leer ni escribir la bitácora directamente: todo pasa por
--    sp_registrar_acceso
-- ---------------------------------------------------------------------
GRANT SELECT (id_punto_acceso, nombre, tipo_punto, activo) ON puntos_acceso TO rol_lector_qr;
GRANT EXECUTE ON FUNCTION sp_registrar_acceso(VARCHAR, INT) TO rol_lector_qr;

-- ---------------------------------------------------------------------
-- 10. Cuentas de demostración (contraseña: GrupoSol#2026)
--     Se crean con sp_crear_usuario. Si la cuenta ya existe en el
--     servidor (reinstalación), solo se vuelve a ligar con esta base.
--     ¡Cambien las contraseñas fuera del entorno escolar!
-- ---------------------------------------------------------------------
DO $$
DECLARE
    c RECORD;
    v_id_col INT;
BEGIN
    FOR c IN SELECT * FROM (VALUES
            ('gs_admin',     'rol_admin_bd',  'EMP-0004'),   -- Fernando Castillo (TI)
            ('gs_seguridad', 'rol_seguridad', 'EMP-0007'),   -- Sergio Domínguez
            ('gs_recepcion', 'rol_recepcion', 'EMP-0010'),   -- Paola Sánchez
            ('gs_rrhh',      'rol_rrhh',      'EMP-0002'),   -- Roberto Jiménez
            ('gs_direccion', 'rol_consulta',  'EMP-0001'),   -- Mariana Torres
            ('gs_lector',    'rol_lector_qr', NULL)          -- cuenta de servicio del lector
        ) AS t(cuenta, rol, num_empleado)
    LOOP
        SELECT id_colaborador INTO v_id_col FROM colaboradores WHERE numero_empleado = c.num_empleado;
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = c.cuenta) THEN
            PERFORM sp_crear_usuario(c.cuenta, 'GrupoSol#2026', c.rol, v_id_col);
        ELSE
            EXECUTE format('ALTER ROLE %I LOGIN', c.cuenta);
            EXECUTE format('GRANT %I TO %I', c.rol, c.cuenta);
            INSERT INTO usuarios_sistema (cuenta, rol_aplicacion, id_colaborador)
            VALUES (c.cuenta, c.rol, v_id_col)
            ON CONFLICT (cuenta) DO NOTHING;
        END IF;
    END LOOP;
END $$;

-- Verificación: cuentas de la aplicación y su rol
SELECT cuenta, rol_aplicacion, colaborador, puede_conectarse
FROM vw_usuarios_sistema
ORDER BY cuenta;
