-- =============================================================================
-- Control de Acceso Campus ITVH  ·  06_procedimientos.sql
-- Procedimientos almacenados (CREATE PROCEDURE / CALL) que usa la aplicación web.
--
-- Se puede ejecutar solo en una base ya instalada: NO borra datos.
-- (En Neon: SQL Editor → pegar este archivo → Run)
-- =============================================================================
SET search_path TO campus, public;

-- -----------------------------------------------------------------------------
-- sp_crear_pase_visita  (CREATE)
-- En una sola transacción: registra a la persona (si es nueva), su visita y una
-- credencial QR con caducidad, opcionalmente de un solo uso.
--   CALL sp_crear_pase_visita('PRV', NULL, 'Mario', 'López', NULL, NULL, NULL, NULL,
--        NULL, 'Fumigaciones Usumacinta', NULL, 'Fumigación', '2026-11-23 08:00',
--        '2026-11-23 13:00', TRUE, NULL, 1, NULL);
-- -----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_crear_pase_visita(
    p_clase          TEXT,          -- 'VIS' visitante | 'PRV' proveedor
    p_id_persona     INT,           -- NULL = registrar persona nueva
    p_nombre         TEXT,
    p_apellido_pat   TEXT,
    p_apellido_mat   TEXT,
    p_telefono       TEXT,
    p_correo         TEXT,
    p_identificacion TEXT,
    p_id_empresa     INT,           -- proveedor: empresa existente…
    p_empresa_nueva  TEXT,          -- …o empresa nueva
    p_id_anfitrion   INT,
    p_motivo         TEXT,
    p_inicio         TIMESTAMPTZ,
    p_fin            TIMESTAMPTZ,
    p_un_solo_uso    BOOLEAN,
    p_id_horario     INT,
    p_usuario        INT,
    INOUT p_id_credencial INT DEFAULT NULL)
LANGUAGE plpgsql SET search_path = campus, public AS $$
DECLARE
    v_id_persona INT := p_id_persona;
    v_id_empresa INT := p_id_empresa;
    v_id_visita  INT;
BEGIN
    IF p_clase NOT IN ('VIS', 'PRV') THEN
        RAISE EXCEPTION 'Indique si es visitante o proveedor' USING ERRCODE = 'GS010';
    END IF;
    IF p_fin <= p_inicio THEN
        RAISE EXCEPTION 'La caducidad debe ser posterior al inicio del pase' USING ERRCODE = 'GS011';
    END IF;
    PERFORM set_config('app.id_usuario', coalesce(p_usuario::text, ''), true);   -- para la auditoría

    IF v_id_persona IS NULL THEN
        IF coalesce(trim(p_nombre), '') = '' OR coalesce(trim(p_apellido_pat), '') = '' THEN
            RAISE EXCEPTION 'Falta el nombre o el apellido de la persona' USING ERRCODE = 'GS012';
        END IF;
        INSERT INTO personas (id_tipo, nombre, apellido_paterno, apellido_materno, telefono, correo, identificacion)
        VALUES ((SELECT id_tipo FROM tipos_persona WHERE clave = p_clase), trim(p_nombre), trim(p_apellido_pat),
                nullif(trim(p_apellido_mat), ''), p_telefono, p_correo, p_identificacion)
        RETURNING id_persona INTO v_id_persona;

        IF p_clase = 'PRV' THEN
            IF coalesce(trim(p_empresa_nueva), '') <> '' THEN
                INSERT INTO empresas (nombre) VALUES (trim(p_empresa_nueva))
                ON CONFLICT (nombre) DO UPDATE SET nombre = EXCLUDED.nombre
                RETURNING id_empresa INTO v_id_empresa;
            END IF;
            IF v_id_empresa IS NULL THEN
                RAISE EXCEPTION 'Seleccione la empresa del proveedor o escriba una nueva' USING ERRCODE = 'GS013';
            END IF;
            INSERT INTO proveedores (id_persona, id_empresa) VALUES (v_id_persona, v_id_empresa);
        END IF;
    END IF;

    INSERT INTO visitas (id_persona, id_anfitrion, motivo, fecha)
    VALUES (v_id_persona, p_id_anfitrion, p_motivo, fecha_local(p_inicio))
    RETURNING id_visita INTO v_id_visita;

    INSERT INTO credenciales (tipo, id_persona, id_perfil, id_visita, vigencia_inicio, vigencia_fin,
                              usos_maximos, id_horario, creada_por)
    VALUES ('personal', v_id_persona,
            (SELECT id_perfil FROM perfiles_acceso
              WHERE nombre = CASE p_clase WHEN 'PRV' THEN 'Proveedor' ELSE 'Visitante' END),
            v_id_visita, p_inicio, p_fin,
            CASE WHEN p_un_solo_uso THEN 1 END, p_id_horario, p_usuario)
    RETURNING id_credencial INTO p_id_credencial;
END;
$$;

-- -----------------------------------------------------------------------------
-- sp_generar_pases_evento  (CREATE masivo)
-- Genera N pases genéricos de un solo uso, o un pase grupal con N usos,
-- respetando el cupo del evento. Bloquea el evento (FOR UPDATE) para que dos
-- usuarios no rebasen el cupo al mismo tiempo.
--   CALL sp_generar_pases_evento(1, 10, 'individuales', 'Conferencia', 1, NULL);
-- -----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_generar_pases_evento(
    p_id_evento  INT,
    p_cantidad   INT,
    p_modo       TEXT,              -- 'individuales' | 'grupal'
    p_etiqueta   TEXT,
    p_usuario    INT,
    INOUT p_generados INT DEFAULT NULL)
LANGUAGE plpgsql SET search_path = campus, public AS $$
DECLARE
    v_evento   eventos;
    v_emitidos INT;
    v_previos  INT;
    v_perfil   SMALLINT := (SELECT id_perfil FROM perfiles_acceso WHERE nombre = 'Invitado a evento');
    v_etiqueta TEXT := coalesce(nullif(trim(p_etiqueta), ''), 'Pase de evento');
BEGIN
    IF p_cantidad IS NULL OR p_cantidad NOT BETWEEN 1 AND 500 THEN
        RAISE EXCEPTION 'La cantidad debe estar entre 1 y 500' USING ERRCODE = 'GS020';
    END IF;
    IF p_modo NOT IN ('individuales', 'grupal') THEN
        RAISE EXCEPTION 'Modo de generación no válido' USING ERRCODE = 'GS021';
    END IF;
    PERFORM set_config('app.id_usuario', coalesce(p_usuario::text, ''), true);

    SELECT * INTO v_evento FROM eventos WHERE id_evento = p_id_evento FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'El evento % no existe', p_id_evento USING ERRCODE = 'GS022';
    END IF;

    SELECT coalesce(sum(coalesce(usos_maximos, 1)), 0), count(*) INTO v_emitidos, v_previos
      FROM credenciales WHERE id_evento = p_id_evento;
    IF v_evento.cupo IS NOT NULL AND v_emitidos + p_cantidad > v_evento.cupo THEN
        RAISE EXCEPTION 'Se rebasaría el cupo del evento (%). Ya hay % lugares emitidos.',
            v_evento.cupo, v_emitidos USING ERRCODE = 'GS023';
    END IF;

    IF p_modo = 'grupal' THEN
        INSERT INTO credenciales (tipo, descripcion, id_perfil, id_evento, vigencia_inicio, vigencia_fin,
                                  usos_maximos, creada_por)
        VALUES ('generica', v_etiqueta || ' (' || p_cantidad || ' personas)', v_perfil, p_id_evento,
                v_evento.inicio, v_evento.fin, p_cantidad, p_usuario);
        p_generados := 1;
    ELSE
        INSERT INTO credenciales (tipo, descripcion, id_perfil, id_evento, vigencia_inicio, vigencia_fin,
                                  usos_maximos, creada_por)
        SELECT 'generica', v_etiqueta || ' #' || (v_previos + n), v_perfil, p_id_evento,
               v_evento.inicio, v_evento.fin, 1, p_usuario
          FROM generate_series(1, p_cantidad) n;
        p_generados := p_cantidad;
    END IF;
END;
$$;

-- -----------------------------------------------------------------------------
-- sp_cambiar_estado_credencial  (UPDATE)
-- Activa o desactiva una credencial. El trigger de auditoría guarda quién lo hizo.
--   CALL sp_cambiar_estado_credencial(5, FALSE, 2);
-- -----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_cambiar_estado_credencial(
    p_id_credencial INT,
    p_activa        BOOLEAN,
    p_usuario       INT)
LANGUAGE plpgsql SET search_path = campus, public AS $$
BEGIN
    PERFORM set_config('app.id_usuario', coalesce(p_usuario::text, ''), true);
    UPDATE credenciales SET activa = p_activa WHERE id_credencial = p_id_credencial;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'La credencial % no existe', p_id_credencial USING ERRCODE = 'GS030';
    END IF;
END;
$$;

-- -----------------------------------------------------------------------------
-- sp_baja_persona  (DELETE lógico)
-- Nunca se borra a nadie: se marca como inactivo y el trigger tg_baja_persona
-- desactiva todas sus credenciales.
--   CALL sp_baja_persona(6, 1);
-- -----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_baja_persona(
    p_id_persona INT,
    p_usuario    INT)
LANGUAGE plpgsql SET search_path = campus, public AS $$
BEGIN
    PERFORM set_config('app.id_usuario', coalesce(p_usuario::text, ''), true);
    UPDATE personas SET activo = FALSE WHERE id_persona = p_id_persona;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'La persona % no existe', p_id_persona USING ERRCODE = 'GS031';
    END IF;
END;
$$;

-- El rol de la aplicación puede ejecutarlos (si existe; ver 05_seguridad.sql)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_campus') THEN
        GRANT EXECUTE ON PROCEDURE sp_crear_pase_visita, sp_generar_pases_evento,
                                   sp_cambiar_estado_credencial, sp_baja_persona TO app_campus;
    END IF;
END $$;
