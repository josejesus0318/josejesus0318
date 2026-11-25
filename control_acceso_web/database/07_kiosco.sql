-- =============================================================================
-- Control de Acceso Campus ITVH  ·  07_kiosco.sql
-- Módulo KIOSCO DE ALUMNOS: una computadora fija con cámara en cada acceso.
--
--   * El alumno teclea su número de control (o muestra a la cámara el código
--     de su credencial). No necesita NIP: la pantalla muestra su FOTO y el
--     guardia la compara con la persona, como se hace hoy en el ITVH.
--   * A diferencia de la computadora actual, la entrada SÍ queda registrada
--     en la bitácora (método 'kiosco').
--   * Solo registra ENTRADAS y solo de alumnos. El personal, los proveedores y
--     las visitas siguen pasando por la caseta de vigilancia.
--
-- Se puede ejecutar sobre una base ya instalada (no borra datos) y se puede
-- volver a ejecutar sin problema. En Neon: SQL Editor → pegar → Run.
-- =============================================================================
SET search_path TO campus, public;

-- -----------------------------------------------------------------------------
-- 1. Nuevo rol de usuario "kiosco" y nuevo método "kiosco" en la bitácora
-- -----------------------------------------------------------------------------
ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS ck_usuario_rol;
ALTER TABLE usuarios ADD CONSTRAINT ck_usuario_rol
    CHECK (rol IN ('admin', 'vigilancia', 'recepcion', 'consulta', 'kiosco'));

ALTER TABLE registro_accesos DROP CONSTRAINT IF EXISTS ck_reg_metodo;
ALTER TABLE registro_accesos ADD CONSTRAINT ck_reg_metodo
    CHECK (metodo IN ('qr', 'nip', 'manual', 'kiosco'));

-- -----------------------------------------------------------------------------
-- 2. Fotografía de las personas (opcional: si no hay, se muestra una imagen
--    de ejemplo generada por la aplicación)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fotos_personas (
    id_persona   INT          PRIMARY KEY REFERENCES personas(id_persona) ON DELETE CASCADE,
    tipo_mime    VARCHAR(20)  NOT NULL,
    datos        BYTEA        NOT NULL,
    actualizada  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ck_foto_tipo   CHECK (tipo_mime IN ('image/jpeg', 'image/png', 'image/webp')),
    CONSTRAINT ck_foto_tamano CHECK (octet_length(datos) <= 900 * 1024)
);

-- -----------------------------------------------------------------------------
-- 3. Configuración del kiosco
-- -----------------------------------------------------------------------------
INSERT INTO configuracion (clave, valor, descripcion) VALUES
('kiosco_segundos_repeticion', '60', 'Kiosco: segundos en los que un mismo alumno no vuelve a registrar entrada'),
('kiosco_segundos_pantalla',   '6',  'Kiosco: segundos que se muestra la foto y el resultado')
ON CONFLICT (clave) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 4. Registrar la entrada de un alumno desde el kiosco
--   p_dato    número de control tecleado, leído del código de barras de la
--             credencial, o el contenido del QR (ITVH-…)
--   p_punto   acceso donde está el kiosco (debe ser una entrada al campus)
--   p_usuario usuario de la aplicación con el que está abierto el kiosco
--
-- Aplica las mismas reglas que la caseta: credencial activa, alumno no dado de
-- baja, vigencia, puertas del perfil y horario programado. Siempre registra
-- ENTRADA (el kiosco no registra salidas).
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_kiosco_registrar(
    p_dato    TEXT,
    p_punto   INT,
    p_usuario INT DEFAULT NULL)
RETURNS TABLE (
    resultado       TEXT,      -- permitido | denegado | repetido
    mensaje         TEXT,
    id_persona      INT,
    persona         TEXT,
    numero_control  TEXT,
    carrera         TEXT,
    semestre        INT,
    hora            TEXT,
    id_registro     BIGINT)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = campus, public AS $$
#variable_conflict use_column
DECLARE
    v_ahora    TIMESTAMPTZ := now();
    v_dato     TEXT := upper(left(trim(coalesce(p_dato, '')), 60));
    v_punto    campus.puntos_acceso;
    v_cred     campus.credenciales;
    v_persona  campus.personas;
    v_alumno   campus.alumnos;
    v_id_pers  INT;
    v_motivo   TEXT;
    v_horario  INT;
    v_carrera  TEXT;
    v_nombre   TEXT;
    v_hora     TEXT;
    v_id_reg   BIGINT;
    v_ultimo   campus.registro_accesos;
BEGIN
    SELECT * INTO v_punto FROM puntos_acceso pa WHERE pa.id_punto = p_punto;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'El punto de acceso % no existe', p_punto USING ERRCODE = 'GS003';
    END IF;
    IF NOT v_punto.perimetral OR v_punto.sentido = 'salida' THEN
        RAISE EXCEPTION 'El kiosco solo se puede usar en un acceso de entrada al campus'
            USING ERRCODE = 'GS030';
    END IF;
    IF v_dato = '' THEN
        RAISE EXCEPTION 'Escriba su número de control' USING ERRCODE = 'GS031';
    END IF;

    -- 1. Identificar al alumno ------------------------------------------------
    IF v_dato LIKE 'ITVH-%' THEN                       -- QR de la credencial
        SELECT * INTO v_cred FROM credenciales c WHERE c.token = v_dato FOR UPDATE;
        IF NOT FOUND THEN
            v_motivo := 'Código no registrado';
        ELSE
            v_id_pers := v_cred.id_persona;            -- NULL si es un pase genérico
        END IF;
    ELSE                                               -- número de control
        SELECT a.id_persona INTO v_id_pers FROM alumnos a WHERE a.numero_control = v_dato;
        IF v_id_pers IS NULL THEN
            v_motivo := CASE
                WHEN EXISTS (SELECT 1 FROM empleados e WHERE e.numero_empleado = v_dato)
                    THEN 'El kiosco es solo para alumnos: el personal registra su acceso en la caseta'
                ELSE 'Número de control no registrado' END;
        END IF;
    END IF;

    IF v_motivo IS NULL THEN
        SELECT * INTO v_alumno FROM alumnos a WHERE a.id_persona = v_id_pers;
        IF NOT FOUND THEN
            v_motivo := 'El kiosco es solo para alumnos: pase con el personal de vigilancia';
        ELSIF v_cred.id_credencial IS NULL THEN
            -- La credencial más adecuada del alumno: primero la vigente, luego la más reciente
            SELECT c.* INTO v_cred FROM credenciales c
             WHERE c.id_persona = v_id_pers
             ORDER BY (estado_credencial(c, v_ahora) = 'vigente') DESC, c.id_credencial DESC
             LIMIT 1 FOR UPDATE;
            IF NOT FOUND THEN
                v_motivo := 'No tiene credencial registrada: acuda a Servicios Escolares';
            END IF;
        END IF;
    END IF;

    -- Datos que se muestran en pantalla
    IF v_alumno.id_persona IS NOT NULL THEN
        SELECT * INTO v_persona FROM personas p WHERE p.id_persona = v_alumno.id_persona;
        v_nombre  := concat_ws(' ', v_persona.nombre, v_persona.apellido_paterno, v_persona.apellido_materno);
        SELECT ca.nombre INTO v_carrera FROM carreras ca WHERE ca.id_carrera = v_alumno.id_carrera;
    END IF;
    v_hora := to_char(v_ahora AT TIME ZONE zona_horaria(), 'HH24:MI');

    -- 2. ¿Ya registró su entrada hace unos segundos? (doble Enter, doble lectura)
    IF v_motivo IS NULL THEN
        SELECT * INTO v_ultimo FROM registro_accesos r
         WHERE r.resultado = 'permitido'
           AND r.id_persona = v_alumno.id_persona
           AND r.id_punto = p_punto
           AND r.fecha_hora > v_ahora - make_interval(secs => config_int('kiosco_segundos_repeticion', 60))
         ORDER BY r.fecha_hora DESC
         LIMIT 1;
        IF FOUND THEN
            RETURN QUERY SELECT 'repetido'::text, 'Tu entrada ya quedó registrada'::text,
                v_alumno.id_persona, v_nombre, v_alumno.numero_control::text, v_carrera,
                v_alumno.semestre::int,
                to_char(v_ultimo.fecha_hora AT TIME ZONE zona_horaria(), 'HH24:MI'), v_ultimo.id_registro;
            RETURN;
        END IF;
    END IF;

    -- 3. Validaciones (las mismas reglas que la caseta) ------------------------
    IF v_motivo IS NULL THEN
        v_horario := coalesce(v_cred.id_horario,
                              (SELECT pa.id_horario FROM perfiles_acceso pa WHERE pa.id_perfil = v_cred.id_perfil));
        v_motivo := CASE
            WHEN NOT v_punto.activo
                THEN 'Punto de acceso desactivado'
            WHEN NOT v_persona.activo
                THEN 'Alumno dado de baja'
            WHEN NOT v_cred.activa
                THEN 'Credencial desactivada: acuda a Servicios Escolares'
            WHEN v_ahora < v_cred.vigencia_inicio
                THEN 'La credencial es válida a partir del '
                     || to_char(v_cred.vigencia_inicio AT TIME ZONE zona_horaria(), 'DD/MM/YYYY')
            WHEN v_cred.vigencia_fin IS NOT NULL AND v_ahora > v_cred.vigencia_fin
                THEN 'Credencial vencida el '
                     || to_char(v_cred.vigencia_fin AT TIME ZONE zona_horaria(), 'DD/MM/YYYY')
            WHEN v_cred.usos_maximos IS NOT NULL AND v_cred.usos_realizados >= v_cred.usos_maximos
                THEN 'La credencial ya no tiene usos disponibles'
            WHEN NOT EXISTS (SELECT 1 FROM perfil_puntos pp
                              WHERE pp.id_perfil = v_cred.id_perfil AND pp.id_punto = p_punto)
                THEN 'Sin permiso en este punto de acceso'
            WHEN NOT horario_permite(v_horario, v_ahora)
                THEN 'Fuera del horario permitido'
        END;
    END IF;

    -- 4. Registrar en la bitácora -------------------------------------------------
    IF v_motivo IS NOT NULL THEN
        INSERT INTO registro_accesos (id_punto, id_credencial, id_persona, metodo, evento,
                                      resultado, motivo, dato_leido, id_usuario)
        VALUES (p_punto, v_cred.id_credencial, coalesce(v_alumno.id_persona, v_id_pers), 'kiosco', NULL,
                'denegado', v_motivo,
                CASE WHEN v_cred.id_credencial IS NULL AND v_id_pers IS NULL THEN v_dato END, p_usuario)
        RETURNING registro_accesos.id_registro INTO v_id_reg;

        RETURN QUERY SELECT 'denegado'::text, v_motivo, v_alumno.id_persona, v_nombre,
            v_alumno.numero_control::text, v_carrera, v_alumno.semestre::int, v_hora, v_id_reg;
        RETURN;
    END IF;

    IF v_cred.usos_maximos IS NOT NULL THEN
        UPDATE credenciales c SET usos_realizados = c.usos_realizados + 1
         WHERE c.id_credencial = v_cred.id_credencial;
    END IF;

    INSERT INTO registro_accesos (id_punto, id_credencial, id_persona, metodo, evento,
                                  resultado, motivo, id_usuario)
    VALUES (p_punto, v_cred.id_credencial, v_alumno.id_persona, 'kiosco', 'entrada', 'permitido', NULL, p_usuario)
    RETURNING registro_accesos.id_registro INTO v_id_reg;

    RETURN QUERY SELECT 'permitido'::text, 'Entrada registrada'::text, v_alumno.id_persona, v_nombre,
        v_alumno.numero_control::text, v_carrera, v_alumno.semestre::int, v_hora, v_id_reg;
END;
$$;

-- -----------------------------------------------------------------------------
-- 5. Resumen del panel: se agrega el conteo de entradas por kiosco
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_resumen_hoy AS
SELECT
    (SELECT count(*) FROM vw_presentes)                                           AS dentro_ahora,
    count(*) FILTER (WHERE resultado = 'permitido' AND evento = 'entrada')        AS entradas,
    count(*) FILTER (WHERE resultado = 'permitido' AND evento = 'salida')         AS salidas,
    count(*) FILTER (WHERE resultado = 'denegado')                                AS denegados,
    count(*) FILTER (WHERE resultado = 'permitido' AND metodo = 'qr')             AS por_qr,
    count(*) FILTER (WHERE resultado = 'permitido' AND metodo = 'nip')            AS por_nip,
    count(*) FILTER (WHERE resultado = 'permitido' AND metodo = 'manual')         AS manuales,
    count(*) FILTER (WHERE resultado = 'permitido' AND metodo = 'kiosco')         AS por_kiosco
  FROM registro_accesos
 WHERE fecha_local(fecha_hora) = fecha_local(now());

-- -----------------------------------------------------------------------------
-- 6. Usuario de demostración para el kiosco (contraseña: Campus#2026)
-- -----------------------------------------------------------------------------
INSERT INTO usuarios (usuario, password_hash, nombre, rol)
VALUES ('kiosco', cifrar('Campus#2026'), 'Kiosco de alumnos – Acceso principal', 'kiosco')
ON CONFLICT (usuario) DO NOTHING;
-- La instalación no cuenta como un cambio hecho por un usuario
DELETE FROM auditoria
 WHERE tabla = 'usuarios' AND accion = 'alta' AND id_usuario IS NULL
   AND id_afectado = (SELECT u.id_usuario FROM usuarios u WHERE u.usuario = 'kiosco');

-- -----------------------------------------------------------------------------
-- 7. Permisos del rol de mínimo privilegio (si existe)
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_campus') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON campus.fotos_personas TO app_campus;
        GRANT SELECT ON campus.vw_resumen_hoy TO app_campus;
        GRANT EXECUTE ON FUNCTION campus.fn_kiosco_registrar(TEXT, INT, INT) TO app_campus;
    END IF;
END $$;
