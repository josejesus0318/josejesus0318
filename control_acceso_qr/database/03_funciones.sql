/* =====================================================================
   MODELO v2 – FUNCIONES Y TRIGGERS
   - sp_registrar_acceso      : lo usa el lector QR (valida y registra)
   - sp_crear_usuario         : crea una cuenta de PostgreSQL con su rol
   - sp_cambiar_estado_usuario: habilita / deshabilita una cuenta
   - sp_restablecer_password  : el administrador asigna una nueva contraseña
   - triggers de integridad   : reglas de negocio que no caben en un CHECK

   Las funciones SECURITY DEFINER se ejecutan con los privilegios de su
   dueño (postgres). Por eso: fijan search_path, validan quién las llama
   con session_user y construyen el SQL dinámico con format('%I' / '%L')
   para evitar inyección SQL.

   Códigos SQLSTATE propios (clase GS):
     GS001 punto de acceso inválido     GS002 contraseña insegura
     GS003 rol no permitido             GS004 nombre de cuenta inválido
     GS005 colaborador inválido         GS006 cuenta no encontrada
     GS007 operación no permitida       GS008 bitácora inmutable
   ===================================================================== */

-- ---------------------------------------------------------------------
-- Utilidad: ¿la sesión actual pertenece a rol_admin_bd o es superusuario?
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_es_admin()
RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT COALESCE((SELECT rolsuper FROM pg_roles WHERE rolname = session_user), FALSE)
        OR pg_has_role(session_user, 'rol_admin_bd', 'MEMBER');
$$;

-- ---------------------------------------------------------------------
-- LECTOR QR: valida una credencial y registra la entrada o salida
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION sp_registrar_acceso(p_codigo_qr VARCHAR, p_id_punto INT)
RETURNS TABLE (estado_lectura VARCHAR, evento VARCHAR, persona TEXT, mensaje TEXT)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_punto      puntos_acceso%ROWTYPE;
    v_cred       credenciales%ROWTYPE;
    v_estado     estados_credencial%ROWTYPE;
    v_visita     visitas%ROWTYPE;
    v_persona    TEXT;
    v_activo     BOOLEAN;
    v_motivo     TEXT;
    v_ult_evento VARCHAR(7);
    v_ult_fecha  TIMESTAMP;
    v_evento     VARCHAR(7);
BEGIN
    SELECT * INTO v_punto FROM puntos_acceso WHERE id_punto_acceso = p_id_punto;
    IF NOT FOUND OR NOT v_punto.activo THEN
        RAISE EXCEPTION 'El punto de acceso % no existe o está inactivo', p_id_punto
            USING ERRCODE = 'GS001';
    END IF;

    -- FOR UPDATE: si dos lectores leen la misma credencial a la vez, se atienden en orden
    SELECT * INTO v_cred FROM credenciales WHERE codigo_qr = upper(trim(p_codigo_qr)) FOR UPDATE;
    IF NOT FOUND THEN
        RETURN QUERY SELECT 'no_encontrado'::VARCHAR, NULL::VARCHAR, NULL::TEXT,
                            'Código QR no registrado'::TEXT;
        RETURN;
    END IF;

    SELECT * INTO v_estado FROM estados_credencial WHERE id_estado = v_cred.id_estado;

    IF v_cred.id_colaborador IS NOT NULL THEN
        SELECT concat_ws(' ', c.nombre, c.apellido_paterno, c.apellido_materno), c.activo
          INTO v_persona, v_activo
          FROM colaboradores c WHERE c.id_colaborador = v_cred.id_colaborador;
    ELSE
        SELECT * INTO v_visita FROM visitas WHERE id_visita = v_cred.id_visita;
        SELECT concat_ws(' ', vi.nombre, vi.apellido_paterno, vi.apellido_materno)
          INTO v_persona
          FROM visitantes vi WHERE vi.id_visitante = v_visita.id_visitante;
    END IF;

    -- Reglas de validación, en orden de prioridad
    IF NOT v_estado.permite_acceso THEN
        v_motivo := 'Credencial ' || v_estado.clave;
    ELSIF v_cred.fecha_vigencia < CURRENT_DATE THEN
        v_motivo := 'Credencial vencida desde el ' || to_char(v_cred.fecha_vigencia, 'DD/MM/YYYY');
    ELSIF v_cred.id_colaborador IS NOT NULL AND NOT v_activo THEN
        v_motivo := 'Colaborador dado de baja';
    ELSIF v_cred.id_visita IS NOT NULL AND v_visita.estado = 'cancelada' THEN
        v_motivo := 'La visita fue cancelada';
    ELSIF v_cred.id_visita IS NOT NULL AND v_visita.fecha_visita <> CURRENT_DATE THEN
        v_motivo := 'La visita no corresponde al día de hoy';
    ELSIF NOT EXISTS (SELECT 1 FROM permisos_rol_punto pr
                      WHERE pr.id_rol_acceso = v_cred.id_rol_acceso
                        AND pr.id_punto_acceso = p_id_punto) THEN
        v_motivo := 'Sin permiso para ' || v_punto.nombre;
    END IF;

    IF v_motivo IS NOT NULL THEN
        INSERT INTO registro_accesos (id_credencial, id_punto_acceso, resultado, motivo)
        VALUES (v_cred.id_credencial, p_id_punto, 'denegado', v_motivo);
        RETURN QUERY SELECT 'denegado'::VARCHAR, NULL::VARCHAR, v_persona, v_motivo;
        RETURN;
    END IF;

    -- Último evento permitido de esta credencial
    SELECT r.tipo_evento, r.fecha_hora INTO v_ult_evento, v_ult_fecha
      FROM registro_accesos r
     WHERE r.id_credencial = v_cred.id_credencial AND r.resultado = 'permitido'
     ORDER BY r.fecha_hora DESC, r.id_registro DESC
     LIMIT 1;

    -- La cámara puede leer el mismo QR varias veces seguidas: se ignora
    IF v_ult_fecha IS NOT NULL AND v_ult_fecha > LOCALTIMESTAMP - INTERVAL '10 seconds' THEN
        RETURN QUERY SELECT 'repetido'::VARCHAR, v_ult_evento, v_persona,
                            'Lectura repetida: el acceso ya se registró'::TEXT;
        RETURN;
    END IF;

    -- Entrada o salida: alterna con el último evento del mismo día.
    -- Si el punto es solo de entrada o solo de salida, se respeta.
    v_evento := CASE
        WHEN v_punto.tipo_punto IN ('entrada', 'salida') THEN v_punto.tipo_punto
        WHEN v_ult_evento = 'entrada' AND v_ult_fecha::date = CURRENT_DATE THEN 'salida'
        ELSE 'entrada'
    END;

    INSERT INTO registro_accesos (id_credencial, id_punto_acceso, tipo_evento)
    VALUES (v_cred.id_credencial, p_id_punto, v_evento);

    -- La primera entrada de un visitante marca su visita como realizada
    IF v_cred.id_visita IS NOT NULL AND v_evento = 'entrada' THEN
        UPDATE visitas SET estado = 'realizada' WHERE id_visita = v_cred.id_visita;
    END IF;

    RETURN QUERY SELECT 'permitido'::VARCHAR, v_evento, v_persona,
                        ('Acceso permitido: ' || v_evento)::TEXT;
END;
$$;

-- ---------------------------------------------------------------------
-- ADMINISTRACIÓN: crear una cuenta de PostgreSQL con su rol
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION sp_crear_usuario(p_cuenta VARCHAR, p_password TEXT,
                                            p_rol VARCHAR, p_id_colaborador INT DEFAULT NULL)
RETURNS INT
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_cuenta VARCHAR := lower(trim(p_cuenta));
    v_id     INT;
BEGIN
    IF NOT fn_es_admin() THEN
        RAISE EXCEPTION 'Solo un administrador puede crear usuarios' USING ERRCODE = '42501';
    END IF;
    IF v_cuenta !~ '^[a-z][a-z0-9_]{2,30}$' OR v_cuenta ~ '^(pg_|rol_)' OR v_cuenta = 'postgres' THEN
        RAISE EXCEPTION 'Nombre de cuenta inválido: use de 3 a 31 letras minúsculas, números o guion bajo, empezando con letra'
            USING ERRCODE = 'GS004';
    END IF;
    IF p_password IS NULL OR length(p_password) < 8
       OR p_password !~ '[A-Z]' OR p_password !~ '[a-z]' OR p_password !~ '[0-9]' THEN
        RAISE EXCEPTION 'La contraseña debe tener al menos 8 caracteres, con mayúsculas, minúsculas y números'
            USING ERRCODE = 'GS002';
    END IF;
    IF p_rol NOT IN ('rol_admin_bd', 'rol_seguridad', 'rol_recepcion',
                     'rol_rrhh', 'rol_consulta', 'rol_lector_qr') THEN
        RAISE EXCEPTION 'Rol no permitido: %', p_rol USING ERRCODE = 'GS003';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v_cuenta) THEN
        RAISE EXCEPTION 'La cuenta "%" ya existe', v_cuenta USING ERRCODE = '42710';
    END IF;
    IF p_id_colaborador IS NOT NULL THEN
        IF NOT EXISTS (SELECT 1 FROM colaboradores WHERE id_colaborador = p_id_colaborador AND activo) THEN
            RAISE EXCEPTION 'El colaborador no existe o está dado de baja' USING ERRCODE = 'GS005';
        END IF;
        IF EXISTS (SELECT 1 FROM usuarios_sistema WHERE id_colaborador = p_id_colaborador) THEN
            RAISE EXCEPTION 'El colaborador ya tiene una cuenta de usuario' USING ERRCODE = 'GS005';
        END IF;
    END IF;

    -- %I = identificador entre comillas, %L = literal escapado: sin inyección SQL
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', v_cuenta, p_password);
    EXECUTE format('GRANT %I TO %I', p_rol, v_cuenta);

    INSERT INTO usuarios_sistema (cuenta, rol_aplicacion, id_colaborador)
    VALUES (v_cuenta, p_rol, p_id_colaborador)
    RETURNING id_usuario_sistema INTO v_id;
    RETURN v_id;
END;
$$;

-- ---------------------------------------------------------------------
-- ADMINISTRACIÓN: habilitar / deshabilitar una cuenta (LOGIN / NOLOGIN)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION sp_cambiar_estado_usuario(p_cuenta VARCHAR, p_activo BOOLEAN)
RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    IF NOT fn_es_admin() THEN
        RAISE EXCEPTION 'Solo un administrador puede modificar usuarios' USING ERRCODE = '42501';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM usuarios_sistema WHERE cuenta = p_cuenta) THEN
        RAISE EXCEPTION 'La cuenta "%" no está registrada en el sistema', p_cuenta USING ERRCODE = 'GS006';
    END IF;
    IF p_cuenta = session_user AND NOT p_activo THEN
        RAISE EXCEPTION 'No puede deshabilitar su propia cuenta' USING ERRCODE = 'GS007';
    END IF;
    EXECUTE format('ALTER ROLE %I %s', p_cuenta, CASE WHEN p_activo THEN 'LOGIN' ELSE 'NOLOGIN' END);
    UPDATE usuarios_sistema SET activo = p_activo WHERE cuenta = p_cuenta;
END;
$$;

-- ---------------------------------------------------------------------
-- ADMINISTRACIÓN: asignar una nueva contraseña a una cuenta
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION sp_restablecer_password(p_cuenta VARCHAR, p_password TEXT)
RETURNS VOID
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    IF NOT fn_es_admin() THEN
        RAISE EXCEPTION 'Solo un administrador puede restablecer contraseñas' USING ERRCODE = '42501';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM usuarios_sistema WHERE cuenta = p_cuenta) THEN
        RAISE EXCEPTION 'La cuenta "%" no está registrada en el sistema', p_cuenta USING ERRCODE = 'GS006';
    END IF;
    IF p_password IS NULL OR length(p_password) < 8
       OR p_password !~ '[A-Z]' OR p_password !~ '[a-z]' OR p_password !~ '[0-9]' THEN
        RAISE EXCEPTION 'La contraseña debe tener al menos 8 caracteres, con mayúsculas, minúsculas y números'
            USING ERRCODE = 'GS002';
    END IF;
    EXECUTE format('ALTER ROLE %I PASSWORD %L', p_cuenta, p_password);
END;
$$;

-- ---------------------------------------------------------------------
-- TRIGGER: solo Seguridad emite credenciales de colaboradores, y solo a
-- colaboradores activos; no se emiten para visitas canceladas
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_valida_credencial()
RETURNS TRIGGER
LANGUAGE plpgsql SECURITY DEFINER   -- quien emite no necesita leer colaboradores/visitas
SET search_path = public, pg_temp
AS $$
BEGIN
    -- Recepción solo emite credenciales de visita; las del personal son de Seguridad
    IF NEW.id_colaborador IS NOT NULL
       AND NOT (fn_es_admin() OR pg_has_role(session_user, 'rol_seguridad', 'MEMBER')) THEN
        RAISE EXCEPTION 'Solo Seguridad Patrimonial puede emitir credenciales a colaboradores'
            USING ERRCODE = 'GS007';
    END IF;
    IF NEW.id_colaborador IS NOT NULL AND NOT EXISTS
       (SELECT 1 FROM colaboradores WHERE id_colaborador = NEW.id_colaborador AND activo) THEN
        RAISE EXCEPTION 'No se puede emitir una credencial a un colaborador dado de baja'
            USING ERRCODE = 'GS007';
    END IF;
    IF NEW.id_visita IS NOT NULL AND EXISTS
       (SELECT 1 FROM visitas WHERE id_visita = NEW.id_visita AND estado = 'cancelada') THEN
        RAISE EXCEPTION 'No se puede emitir una credencial para una visita cancelada'
            USING ERRCODE = 'GS007';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tg_valida_credencial ON credenciales;
CREATE TRIGGER tg_valida_credencial
    BEFORE INSERT ON credenciales
    FOR EACH ROW EXECUTE FUNCTION trg_valida_credencial();

-- ---------------------------------------------------------------------
-- TRIGGER: al dar de baja a un colaborador se revocan sus credenciales
-- (SECURITY DEFINER porque RRHH no tiene permiso sobre credenciales)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_baja_colaborador()
RETURNS TRIGGER
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    IF OLD.activo AND NOT NEW.activo THEN
        UPDATE credenciales SET id_estado = 3
         WHERE id_colaborador = NEW.id_colaborador AND id_estado IN (1, 2);
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tg_baja_colaborador ON colaboradores;
CREATE TRIGGER tg_baja_colaborador
    AFTER UPDATE OF activo ON colaboradores
    FOR EACH ROW EXECUTE FUNCTION trg_baja_colaborador();

-- ---------------------------------------------------------------------
-- TRIGGER: la bitácora no se modifica ni se borra (solo superusuario)
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_bitacora_inmutable()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public, pg_temp
AS $$
BEGIN
    IF NOT COALESCE((SELECT rolsuper FROM pg_roles WHERE rolname = session_user), FALSE) THEN
        RAISE EXCEPTION 'La bitácora de accesos no puede modificarse ni eliminarse'
            USING ERRCODE = 'GS008';
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS tg_bitacora_inmutable ON registro_accesos;
CREATE TRIGGER tg_bitacora_inmutable
    BEFORE UPDATE OR DELETE ON registro_accesos
    FOR EACH ROW EXECUTE FUNCTION trg_bitacora_inmutable();
