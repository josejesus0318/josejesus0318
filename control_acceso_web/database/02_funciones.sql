-- =============================================================================
-- Control de Acceso Campus ITVH  ·  02_funciones.sql
-- Reglas de negocio dentro de PostgreSQL: validación de accesos, horarios,
-- pases de un solo uso, NIP, inicio de sesión, bitácora inmutable y auditoría.
-- =============================================================================
SET search_path TO campus, public;

-- -----------------------------------------------------------------------------
-- Zona horaria del campus (los servidores en la nube trabajan en UTC)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION zona_horaria() RETURNS TEXT
LANGUAGE sql STABLE AS $$
    SELECT coalesce((SELECT valor FROM campus.configuracion WHERE clave = 'zona_horaria'),
                    'America/Mexico_City');
$$;

CREATE OR REPLACE FUNCTION config_int(p_clave TEXT, p_omision INT) RETURNS INT
LANGUAGE sql STABLE AS $$
    SELECT coalesce((SELECT valor::int FROM campus.configuracion WHERE clave = p_clave), p_omision);
$$;

-- Fecha local de un instante (para agrupar por día en el campus)
CREATE OR REPLACE FUNCTION fecha_local(p_ts TIMESTAMPTZ) RETURNS DATE
LANGUAGE sql STABLE AS $$
    SELECT (p_ts AT TIME ZONE campus.zona_horaria())::date;
$$;

-- -----------------------------------------------------------------------------
-- ¿El horario permite el acceso en este instante?  (NULL = sin restricción)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION horario_permite(p_id_horario INT, p_ts TIMESTAMPTZ DEFAULT now())
RETURNS BOOLEAN
LANGUAGE sql STABLE AS $$
    SELECT p_id_horario IS NULL OR EXISTS (
        SELECT 1
          FROM campus.horario_franjas f
         WHERE f.id_horario = p_id_horario
           AND f.dia_semana = extract(isodow FROM p_ts AT TIME ZONE campus.zona_horaria())
           AND (p_ts AT TIME ZONE campus.zona_horaria())::time BETWEEN f.hora_inicio AND f.hora_fin);
$$;

-- -----------------------------------------------------------------------------
-- Estado calculado de una credencial
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION estado_credencial(c campus.credenciales, p_ts TIMESTAMPTZ DEFAULT now())
RETURNS TEXT
LANGUAGE sql STABLE AS $$
    SELECT CASE
        WHEN NOT c.activa                                          THEN 'inactiva'
        WHEN c.vigencia_fin IS NOT NULL AND p_ts > c.vigencia_fin  THEN 'vencida'
        WHEN c.usos_maximos IS NOT NULL
             AND c.usos_realizados >= c.usos_maximos               THEN 'agotada'
        WHEN p_ts < c.vigencia_inicio                              THEN 'pendiente'
        ELSE 'vigente'
    END;
$$;

-- -----------------------------------------------------------------------------
-- Cifrado de contraseñas y NIP (bcrypt)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION cifrar(p_texto TEXT) RETURNS TEXT
LANGUAGE sql VOLATILE AS $$
    SELECT public.crypt(p_texto, public.gen_salt('bf', 8));
$$;

-- -----------------------------------------------------------------------------
-- Inicio de sesión: devuelve el usuario solo si la contraseña coincide
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_login(p_usuario TEXT, p_password TEXT)
RETURNS TABLE (id_usuario INT, usuario TEXT, nombre TEXT, rol TEXT)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = campus, public AS $$
BEGIN
    RETURN QUERY
    UPDATE campus.usuarios u
       SET ultimo_acceso = now()
     WHERE u.usuario = lower(trim(p_usuario))
       AND u.activo
       AND u.password_hash = public.crypt(p_password, u.password_hash)
    RETURNING u.id_usuario, u.usuario::text, u.nombre::text, u.rol::text;
END;
$$;

-- -----------------------------------------------------------------------------
-- La bitácora no se puede modificar ni borrar
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION tg_bitacora_inmutable() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'La bitácora de accesos no se puede modificar ni borrar'
        USING ERRCODE = 'GS001';
END;
$$;

CREATE TRIGGER trg_bitacora_inmutable
    BEFORE UPDATE OR DELETE ON registro_accesos
    FOR EACH ROW EXECUTE FUNCTION tg_bitacora_inmutable();

-- -----------------------------------------------------------------------------
-- Auditoría automática. La aplicación indica quién hace el cambio con
--   SET LOCAL app.id_usuario = '<id>'
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION tg_auditoria() RETURNS TRIGGER
LANGUAGE plpgsql SECURITY DEFINER SET search_path = campus, public AS $$
DECLARE
    v_usuario INT  := nullif(current_setting('app.id_usuario', true), '')::int;
    v_id      INT;
    v_accion  TEXT;
    v_detalle TEXT;
    v_nuevo   JSONB := to_jsonb(NEW);
    v_viejo   JSONB := CASE WHEN TG_OP = 'UPDATE' THEN to_jsonb(OLD) END;
    v_campo   TEXT  := TG_ARGV[0];                  -- 'activa' o 'activo'
BEGIN
    v_id := (v_nuevo ->> TG_ARGV[1])::int;
    IF TG_OP = 'INSERT' THEN
        v_accion := 'alta';
    ELSIF (v_nuevo ->> v_campo) IS DISTINCT FROM (v_viejo ->> v_campo) THEN
        v_accion := CASE WHEN (v_nuevo ->> v_campo)::boolean THEN 'activar' ELSE 'desactivar' END;
    ELSE
        v_accion := 'modificar';
        SELECT string_agg(k, ', ' ORDER BY k) INTO v_detalle
          FROM jsonb_each(v_nuevo) AS n(k, v)
         WHERE v_viejo -> k IS DISTINCT FROM v
           AND k NOT IN ('password_hash', 'nip_hash', 'ultimo_acceso', 'usos_realizados');
        IF v_detalle IS NULL THEN
            RETURN NEW;                               -- solo cambió un dato interno
        END IF;
        v_detalle := 'Campos: ' || v_detalle;
    END IF;
    INSERT INTO campus.auditoria (id_usuario, accion, tabla, id_afectado, detalle)
    VALUES (v_usuario, v_accion, TG_TABLE_NAME, v_id, v_detalle);
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_auditoria_credenciales AFTER INSERT OR UPDATE ON credenciales
    FOR EACH ROW EXECUTE FUNCTION tg_auditoria('activa', 'id_credencial');
CREATE TRIGGER trg_auditoria_personas AFTER INSERT OR UPDATE ON personas
    FOR EACH ROW EXECUTE FUNCTION tg_auditoria('activo', 'id_persona');
CREATE TRIGGER trg_auditoria_usuarios AFTER INSERT OR UPDATE ON usuarios
    FOR EACH ROW EXECUTE FUNCTION tg_auditoria('activo', 'id_usuario');
CREATE TRIGGER trg_auditoria_puntos AFTER INSERT OR UPDATE ON puntos_acceso
    FOR EACH ROW EXECUTE FUNCTION tg_auditoria('activo', 'id_punto');

-- Al dar de baja a una persona se desactivan sus credenciales
CREATE OR REPLACE FUNCTION tg_baja_persona() RETURNS TRIGGER
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.activo AND NOT NEW.activo THEN
        UPDATE campus.credenciales SET activa = FALSE
         WHERE id_persona = NEW.id_persona AND activa;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_baja_persona AFTER UPDATE OF activo ON personas
    FOR EACH ROW EXECUTE FUNCTION tg_baja_persona();

-- -----------------------------------------------------------------------------
-- Datos que identifican a una persona (número de control, empleado o empresa)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION identificador_persona(p_id_persona INT) RETURNS TEXT
LANGUAGE sql STABLE AS $$
    SELECT coalesce(
        (SELECT 'No. control ' || a.numero_control FROM campus.alumnos a WHERE a.id_persona = p_id_persona),
        (SELECT 'No. empleado ' || e.numero_empleado FROM campus.empleados e WHERE e.id_persona = p_id_persona),
        (SELECT em.nombre FROM campus.proveedores pr JOIN campus.empresas em USING (id_empresa)
          WHERE pr.id_persona = p_id_persona),
        (SELECT p.identificacion FROM campus.personas p WHERE p.id_persona = p_id_persona));
$$;

-- -----------------------------------------------------------------------------
-- REGISTRAR UN ACCESO
--   p_metodo  'qr'     → p_dato = contenido del QR (token)
--             'nip'    → p_dato = número de control o de empleado, p_nip = NIP
--             'manual' → p_dato = id_persona (el vigilante identificó a la persona)
--   p_punto   punto de acceso donde ocurre
--   p_usuario usuario de la aplicación que opera la caseta (puede ser NULL)
--
-- Decide si es entrada o salida, valida todas las reglas, consume el uso del
-- pase y deja el registro en la bitácora, todo en la misma transacción.
-- La credencial se bloquea con FOR UPDATE: si dos lectores reciben el mismo
-- pase de un solo uso al mismo tiempo, solo uno lo acepta.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_registrar_acceso(
    p_metodo  TEXT,
    p_dato    TEXT,
    p_punto   INT,
    p_nip     TEXT DEFAULT NULL,
    p_usuario INT  DEFAULT NULL)
RETURNS TABLE (
    resultado       TEXT,      -- permitido | denegado | repetido
    evento          TEXT,      -- entrada | salida | NULL
    mensaje         TEXT,
    persona         TEXT,
    tipo            TEXT,
    detalle         TEXT,
    usos_restantes  INT,
    id_registro     BIGINT)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = campus, public AS $$
DECLARE
    v_ahora    TIMESTAMPTZ := now();
    v_dato     TEXT := left(trim(coalesce(p_dato, '')), 60);
    v_punto    campus.puntos_acceso;
    v_cred     campus.credenciales;
    v_persona  campus.personas;
    v_id_pers  INT;
    v_ultimo   campus.registro_accesos;
    v_evento   TEXT;
    v_motivo   TEXT;
    v_horario  INT;
    v_nombre   TEXT;
    v_tipo     TEXT;
    v_detalle  TEXT;
    v_id_reg   BIGINT;
    v_fallos   INT;
    v_dentro   BOOLEAN := FALSE;
    v_grupal   BOOLEAN := FALSE;
BEGIN
    IF p_metodo NOT IN ('qr', 'nip', 'manual') THEN
        RAISE EXCEPTION 'Método de acceso no válido: %', p_metodo USING ERRCODE = 'GS002';
    END IF;

    SELECT * INTO v_punto FROM puntos_acceso WHERE id_punto = p_punto;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'El punto de acceso % no existe', p_punto USING ERRCODE = 'GS003';
    END IF;

    -- 1. Identificar la credencial según el método ---------------------------
    IF p_metodo = 'qr' THEN
        SELECT * INTO v_cred FROM credenciales WHERE token = upper(v_dato) FOR UPDATE;
        IF NOT FOUND THEN
            v_motivo := 'Código QR no registrado';
        END IF;

    ELSIF p_metodo = 'nip' THEN
        SELECT id_persona INTO v_id_pers FROM (
            SELECT id_persona FROM alumnos   WHERE numero_control  = upper(v_dato)
            UNION ALL
            SELECT id_persona FROM empleados WHERE numero_empleado = upper(v_dato)) x
        LIMIT 1;
        IF v_id_pers IS NULL THEN
            v_motivo := 'Número de control o de empleado no registrado';
        ELSE
            SELECT * INTO v_cred FROM credenciales c
             WHERE c.id_persona = v_id_pers AND c.nip_hash IS NOT NULL
             ORDER BY c.activa DESC, c.id_credencial DESC
             LIMIT 1 FOR UPDATE;
            IF NOT FOUND THEN
                v_motivo := 'La persona no tiene NIP asignado';
            ELSE
                SELECT count(*) INTO v_fallos FROM registro_accesos r
                 WHERE r.id_credencial = v_cred.id_credencial
                   AND r.motivo = 'NIP incorrecto'
                   AND r.fecha_hora > v_ahora - interval '15 minutes';
                IF v_fallos >= config_int('intentos_nip', 5) THEN
                    v_motivo := 'NIP bloqueado por intentos fallidos (espere 15 minutos)';
                ELSIF p_nip IS NULL OR public.crypt(p_nip, v_cred.nip_hash) <> v_cred.nip_hash THEN
                    v_motivo := 'NIP incorrecto';
                END IF;
            END IF;
        END IF;

    ELSE  -- manual
        IF v_dato !~ '^\d+$' THEN
            RAISE EXCEPTION 'Para el registro manual indique el id de la persona' USING ERRCODE = 'GS004';
        END IF;
        v_id_pers := v_dato::int;
        PERFORM 1 FROM personas WHERE id_persona = v_id_pers;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'La persona % no existe', v_id_pers USING ERRCODE = 'GS004';
        END IF;
        -- La credencial más adecuada: primero la vigente, luego la más reciente
        SELECT c.* INTO v_cred FROM credenciales c
         WHERE c.id_persona = v_id_pers
         ORDER BY (estado_credencial(c, v_ahora) = 'vigente') DESC, c.id_credencial DESC
         LIMIT 1 FOR UPDATE;
        IF NOT FOUND THEN
            v_motivo := 'La persona no tiene credencial; registre una visita o pase';
        END IF;
    END IF;

    -- Datos de la persona o del pase genérico
    v_id_pers := coalesce(v_cred.id_persona, v_id_pers);
    IF v_id_pers IS NOT NULL THEN
        SELECT * INTO v_persona FROM personas WHERE id_persona = v_id_pers;
        v_nombre  := concat_ws(' ', v_persona.nombre, v_persona.apellido_paterno, v_persona.apellido_materno);
        SELECT t.nombre INTO v_tipo FROM tipos_persona t WHERE t.id_tipo = v_persona.id_tipo;
        v_detalle := identificador_persona(v_id_pers);
    ELSIF v_cred.id_credencial IS NOT NULL THEN
        v_nombre  := v_cred.descripcion;
        v_tipo    := 'Pase genérico';
        v_detalle := (SELECT e.nombre FROM eventos e WHERE e.id_evento = v_cred.id_evento);
    END IF;

    -- 2. ¿Entrada o salida? ----------------------------------------------------
    -- Un pase genérico con varios usos (grupal o de cuadrilla) lo comparten varias
    -- personas: cada lectura en un acceso de doble sentido cuenta como una entrada.
    v_grupal := v_cred.tipo = 'generica' AND coalesce(v_cred.usos_maximos, 2) > 1;

    IF v_motivo IS NULL THEN
        -- Lectura repetida del mismo pase en el mismo punto (por omisión, menos de 10 s)
        SELECT * INTO v_ultimo FROM registro_accesos r
         WHERE r.resultado = 'permitido'
           AND r.id_credencial = v_cred.id_credencial
           AND r.id_punto = p_punto
           AND r.fecha_hora > v_ahora - make_interval(secs => config_int('segundos_repeticion', 10))
         ORDER BY r.fecha_hora DESC
         LIMIT 1;
        IF FOUND AND NOT v_grupal THEN
            RETURN QUERY SELECT 'repetido'::text, v_ultimo.evento::text,
                'Lectura repetida: ya se registró hace unos segundos'::text,
                v_nombre, v_tipo, v_detalle,
                (v_cred.usos_maximos - v_cred.usos_realizados)::int, v_ultimo.id_registro;
            RETURN;
        END IF;

        -- Último movimiento de hoy por un acceso perimetral (entrada o salida del campus)
        SELECT r.* INTO v_ultimo FROM registro_accesos r
          JOIN puntos_acceso pt ON pt.id_punto = r.id_punto AND pt.perimetral
         WHERE r.resultado = 'permitido'
           AND CASE WHEN v_cred.tipo = 'personal' THEN r.id_persona = v_cred.id_persona
                    ELSE r.id_credencial = v_cred.id_credencial END
           AND fecha_local(r.fecha_hora) = fecha_local(v_ahora)
         ORDER BY r.fecha_hora DESC
         LIMIT 1;
        v_dentro := FOUND AND v_ultimo.evento = 'entrada';

        v_evento := CASE
                        WHEN NOT v_punto.perimetral    THEN 'entrada'   -- acceso a un área interna
                        WHEN v_punto.sentido = 'entrada' THEN 'entrada'
                        WHEN v_punto.sentido = 'salida'  THEN 'salida'
                        WHEN v_grupal                    THEN 'entrada'
                        WHEN v_dentro                    THEN 'salida'
                        ELSE 'entrada'
                    END;
    END IF;

    -- 3. Validaciones (la salida siempre se permite para no retener a nadie) --
    IF v_motivo IS NULL AND NOT v_punto.activo THEN
        v_motivo := 'Punto de acceso desactivado';
    END IF;

    IF v_motivo IS NULL AND v_evento = 'entrada' THEN
        v_horario := coalesce(v_cred.id_horario,
                              (SELECT pa.id_horario FROM perfiles_acceso pa WHERE pa.id_perfil = v_cred.id_perfil));
        v_motivo := CASE
            WHEN NOT v_cred.activa
                THEN 'Credencial desactivada'
            WHEN v_cred.tipo = 'personal' AND NOT v_persona.activo
                THEN 'Persona dada de baja'
            WHEN v_ahora < v_cred.vigencia_inicio
                THEN 'El pase es válido a partir del '
                     || to_char(v_cred.vigencia_inicio AT TIME ZONE zona_horaria(), 'DD/MM/YYYY HH24:MI')
            WHEN v_cred.vigencia_fin IS NOT NULL AND v_ahora > v_cred.vigencia_fin
                THEN 'Pase vencido el '
                     || to_char(v_cred.vigencia_fin AT TIME ZONE zona_horaria(), 'DD/MM/YYYY HH24:MI')
            -- Los usos se consumen al cruzar un acceso perimetral. En un área interna,
            -- un pase con usos limitados solo sirve si su portador ya está dentro.
            WHEN v_punto.perimetral AND v_cred.usos_maximos IS NOT NULL
                 AND v_cred.usos_realizados >= v_cred.usos_maximos
                THEN CASE WHEN v_cred.usos_maximos = 1 THEN 'Pase de un solo uso ya utilizado'
                          ELSE 'El pase ya no tiene usos disponibles' END
            WHEN NOT v_punto.perimetral AND v_cred.usos_maximos IS NOT NULL
                 AND NOT v_dentro AND NOT v_grupal
                THEN 'Registre primero su entrada al campus'
            WHEN v_cred.id_visita IS NOT NULL AND EXISTS (
                     SELECT 1 FROM visitas vi WHERE vi.id_visita = v_cred.id_visita AND vi.estado = 'cancelada')
                THEN 'La visita fue cancelada'
            WHEN NOT EXISTS (SELECT 1 FROM perfil_puntos pp
                              WHERE pp.id_perfil = v_cred.id_perfil AND pp.id_punto = p_punto)
                THEN 'Sin permiso en este punto de acceso'
            WHEN NOT horario_permite(v_horario, v_ahora)
                THEN 'Fuera del horario permitido'
        END;
    END IF;

    -- 4. Registrar ---------------------------------------------------------------
    IF v_motivo IS NOT NULL THEN
        INSERT INTO registro_accesos (id_punto, id_credencial, id_persona, metodo, evento,
                                      resultado, motivo, dato_leido, id_usuario)
        VALUES (p_punto, v_cred.id_credencial, v_id_pers, p_metodo, NULL, 'denegado', v_motivo,
                CASE WHEN v_cred.id_credencial IS NULL AND p_metodo <> 'manual' THEN v_dato END,
                p_usuario)
        RETURNING registro_accesos.id_registro INTO v_id_reg;

        RETURN QUERY SELECT 'denegado'::text, NULL::text, v_motivo, v_nombre, v_tipo, v_detalle,
            (v_cred.usos_maximos - v_cred.usos_realizados)::int, v_id_reg;
        RETURN;
    END IF;

    IF v_evento = 'entrada' AND v_punto.perimetral THEN
        UPDATE credenciales SET usos_realizados = usos_realizados + 1
         WHERE id_credencial = v_cred.id_credencial
        RETURNING * INTO v_cred;
        IF v_cred.id_visita IS NOT NULL THEN
            UPDATE visitas SET estado = 'realizada'
             WHERE id_visita = v_cred.id_visita AND estado = 'programada';
        END IF;
    END IF;

    INSERT INTO registro_accesos (id_punto, id_credencial, id_persona, metodo, evento,
                                  resultado, motivo, id_usuario)
    VALUES (p_punto, v_cred.id_credencial, v_id_pers, p_metodo, v_evento, 'permitido', NULL, p_usuario)
    RETURNING registro_accesos.id_registro INTO v_id_reg;

    RETURN QUERY SELECT 'permitido'::text, v_evento,
        CASE WHEN NOT v_punto.perimetral THEN 'Acceso permitido a ' || v_punto.nombre
             WHEN v_evento = 'entrada'    THEN 'Acceso permitido: entrada registrada'
             ELSE 'Salida registrada' END,
        v_nombre, v_tipo, v_detalle,
        (v_cred.usos_maximos - v_cred.usos_realizados)::int, v_id_reg;
END;
$$;
