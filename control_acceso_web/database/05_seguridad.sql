-- =============================================================================
-- Control de Acceso Campus ITVH  ·  05_seguridad.sql
-- Rol de mínimo privilegio para la aplicación web (opcional pero recomendado).
--
-- La aplicación puede conectarse con el usuario dueño de la base de datos,
-- pero es más seguro que use "app_campus":
--   * no puede escribir directamente en la bitácora: solo con fn_registrar_acceso
--   * no puede leer las contraseñas cifradas de los usuarios
--   * no puede borrar personas, credenciales ni registros
-- Para activarlo, asígnele una contraseña (ver GUIA_DESPLIEGUE.md):
--   ALTER ROLE app_campus LOGIN PASSWORD 'una-contraseña-larga';
-- =============================================================================
SET search_path TO campus, public;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_campus') THEN
        CREATE ROLE app_campus NOLOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA campus TO app_campus;
GRANT SELECT ON ALL TABLES IN SCHEMA campus TO app_campus;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA campus TO app_campus;

-- Altas y cambios desde la aplicación (nunca DELETE de personas ni credenciales)
GRANT INSERT, UPDATE ON personas, alumnos, empleados, proveedores, empresas,
                        credenciales, visitas, eventos, horarios, puntos_acceso,
                        perfiles_acceso TO app_campus;
GRANT INSERT, DELETE ON horario_franjas, perfil_puntos TO app_campus;
GRANT UPDATE ON configuracion TO app_campus;

-- Bitácora: solo lectura (los accesos se registran con fn_registrar_acceso)
REVOKE INSERT, UPDATE, DELETE ON registro_accesos FROM app_campus;

-- Usuarios: sin acceso a password_hash (el login usa fn_login)
REVOKE SELECT ON usuarios FROM app_campus;
GRANT SELECT (id_usuario, usuario, nombre, rol, activo, ultimo_acceso) ON usuarios TO app_campus;
GRANT INSERT (usuario, password_hash, nombre, rol) ON usuarios TO app_campus;
GRANT UPDATE (password_hash, nombre, rol, activo) ON usuarios TO app_campus;
