-- =============================================================================
-- Control de Acceso Campus ITVH  ·  04_datos.sql
-- Datos de demostración. Todas las personas son ficticias.
-- Las fechas se calculan a partir del día de la instalación, así los pases de
-- prueba (proveedor, visita y evento) siempre están vigentes al instalar.
-- =============================================================================
SET search_path TO campus, public;

INSERT INTO configuracion (clave, valor, descripcion) VALUES
('zona_horaria',  'America/Mexico_City', 'Zona horaria del campus (los servidores en la nube usan UTC)'),
('intentos_nip',  '5',                   'NIP incorrectos permitidos en 15 minutos antes de bloquear'),
('segundos_repeticion', '10',            'Segundos en los que una segunda lectura del mismo pase se ignora'),
('institucion',   'Instituto Tecnológico de Villahermosa', 'Nombre que aparece en la aplicación');

INSERT INTO tipos_persona (clave, nombre) VALUES
('ALU', 'Alumno'), ('DOC', 'Docente'), ('ADM', 'Personal administrativo'),
('PRV', 'Proveedor'), ('VIS', 'Visitante');

INSERT INTO carreras (clave, nombre) VALUES
('ISC',  'Ingeniería en Sistemas Computacionales'),
('IINF', 'Ingeniería Informática'),
('IGE',  'Ingeniería en Gestión Empresarial'),
('IIND', 'Ingeniería Industrial'),
('IBQ',  'Ingeniería Bioquímica'),
('IQ',   'Ingeniería Química'),
('IC',   'Ingeniería Civil'),
('LA',   'Licenciatura en Administración');

INSERT INTO departamentos (nombre) VALUES
('Sistemas y Computación'),                 -- 1
('Ciencias Básicas'),                       -- 2
('Ingeniería Química y Bioquímica'),        -- 3
('Recursos Materiales y Servicios'),        -- 4
('Servicios Escolares'),                    -- 5
('Centro de Información');                  -- 6

INSERT INTO empresas (nombre, rfc, telefono, giro) VALUES
('Agua Purificada del Sureste S.A. de C.V.', 'APS150310AB1', '9933120000', 'Garrafones de agua'),
('Papelería y Suministros del Golfo',         'PSG180722CD2', '9933451200', 'Papelería y consumibles'),
('Instalaciones Eléctricas Grijalva',         'IEG200115EF3', '9931807700', 'Mantenimiento eléctrico');

-- Horarios (nivel de acceso programado) --------------------------------------------
INSERT INTO horarios (nombre, descripcion) VALUES
('Alumnos',          'Lunes a viernes de 06:30 a 21:30 y sábados de 07:00 a 15:00'),   -- 1
('Docentes',         'Lunes a sábado de 06:00 a 22:00'),                               -- 2
('Administrativo',   'Lunes a viernes de 07:00 a 16:00'),                              -- 3
('Proveedores',      'Lunes a viernes de 08:00 a 13:00'),                              -- 4
('Visitas',          'Lunes a viernes de 08:00 a 18:00');                              -- 5

INSERT INTO horario_franjas (id_horario, dia_semana, hora_inicio, hora_fin)
SELECT 1, d, time '06:30', time '21:30' FROM generate_series(1, 5) d UNION ALL
SELECT 1, 6, time '07:00', time '15:00'                             UNION ALL
SELECT 2, d, '06:00', '22:00' FROM generate_series(1, 6) d UNION ALL
SELECT 3, d, '07:00', '16:00' FROM generate_series(1, 5) d UNION ALL
SELECT 4, d, '08:00', '13:00' FROM generate_series(1, 5) d UNION ALL
SELECT 5, d, '08:00', '18:00' FROM generate_series(1, 5) d;

-- Puntos de acceso -------------------------------------------------------------------
INSERT INTO puntos_acceso (nombre, ubicacion, sentido, perimetral) VALUES
('Acceso principal (peatonal)', 'Carretera Villahermosa–Frontera, caseta principal', 'ambos',   TRUE),  -- 1
('Acceso vehicular',            'Estacionamiento norte',                             'ambos',   TRUE),  -- 2
('Centro de Información',       'Biblioteca, planta baja',                           'entrada', FALSE), -- 3
('Centro de Cómputo',           'Edificio de Sistemas y Computación',                'entrada', FALSE), -- 4
('Auditorio',                   'Auditorio principal del campus',                    'entrada', FALSE); -- 5

-- Perfiles de acceso y sus puntos ---------------------------------------------------------
INSERT INTO perfiles_acceso (nombre, descripcion, id_horario) VALUES
('Alumno',             'Alumnos inscritos',                                  1),   -- 1
('Docente',            'Personal docente',                                   2),   -- 2
('Administrativo',     'Personal de apoyo y administración',                 3),   -- 3
('Vigilancia',         'Personal de seguridad: acceso total, sin horario',   NULL),-- 4
('Proveedor',          'Proveedores y contratistas',                         4),   -- 5
('Visitante',          'Visitas programadas',                                5),   -- 6
('Invitado a evento',  'Pases de eventos: la vigencia la marca el evento',   NULL);-- 7

INSERT INTO perfil_puntos (id_perfil, id_punto) VALUES
(1,1),(1,3),(1,4),(1,5),
(2,1),(2,2),(2,3),(2,4),(2,5),
(3,1),(3,2),(3,3),(3,4),(3,5),
(4,1),(4,2),(4,3),(4,4),(4,5),
(5,1),(5,2),
(6,1),(6,3),(6,5),
(7,1),(7,5);

-- Usuarios de la aplicación (contraseña de demostración: Campus#2026) --------------------
INSERT INTO usuarios (usuario, password_hash, nombre, rol) VALUES
('admin',      cifrar('Campus#2026'), 'Administrador del sistema',  'admin'),
('vigilancia', cifrar('Campus#2026'), 'Caseta de vigilancia',       'vigilancia'),
('recepcion',  cifrar('Campus#2026'), 'Recepción y control escolar','recepcion'),
('consulta',   cifrar('Campus#2026'), 'Dirección (solo consulta)',  'consulta');

-- Personas -------------------------------------------------------------------------------
INSERT INTO personas (id_tipo, nombre, apellido_paterno, apellido_materno, correo, telefono, identificacion, activo) VALUES
(1, 'Andrea Guadalupe', 'Hernández', 'Cruz',     'l22301001@villahermosa.tecnm.mx', '9931000001', NULL, TRUE),  -- 1
(1, 'Luis Fernando',    'Pérez',     'Ramos',    'l22301002@villahermosa.tecnm.mx', '9931000002', NULL, TRUE),  -- 2
(1, 'Valeria Montserrat','López',    'Díaz',     'l23301015@villahermosa.tecnm.mx', '9931000003', NULL, TRUE),  -- 3
(1, 'Carlos Eduardo',   'Jiménez',   'Torres',   'l21301120@villahermosa.tecnm.mx', '9931000004', NULL, TRUE),  -- 4
(1, 'Fernanda Isabel',  'Ramírez',   'Ortiz',    'l24301033@villahermosa.tecnm.mx', '9931000005', NULL, TRUE),  -- 5
(1, 'Diego Alejandro',  'Castillo',  'Méndez',   'l20301077@villahermosa.tecnm.mx', '9931000006', NULL, FALSE), -- 6 baja
(2, 'Patricia Elena',   'Morales',   'Vázquez',  'pmorales@villahermosa.tecnm.mx',  '9932000001', NULL, TRUE),  -- 7
(2, 'Ricardo Javier',   'Sánchez',   'Ruiz',     'rsanchez@villahermosa.tecnm.mx',  '9932000002', NULL, TRUE),  -- 8
(2, 'Mónica Alejandra', 'Herrera',   'Gómez',    'mherrera@villahermosa.tecnm.mx',  '9932000003', NULL, TRUE),  -- 9
(3, 'Jorge Luis',       'Domínguez', 'Arias',    'jdominguez@villahermosa.tecnm.mx','9933000001', NULL, TRUE),  -- 10 vigilante
(3, 'Claudia Patricia', 'Ortega',    'León',     'cortega@villahermosa.tecnm.mx',   '9933000002', NULL, TRUE),  -- 11
(3, 'Martín Alonso',    'Vera',      'Castro',   'mvera@villahermosa.tecnm.mx',     '9933000003', NULL, TRUE),  -- 12
(4, 'Raúl',             'Gómez',     'Pineda',   NULL, '9934000001', 'INE GOPR850412', TRUE),                    -- 13
(4, 'Silvia',           'Reyes',     'Chablé',   NULL, '9934000002', 'INE RECS900823', TRUE),                    -- 14
(5, 'Ana Karen',        'Torres',    'Zapata',   'akaren@correo.mx', '9935000001', 'INE TOZA980215', TRUE),     -- 15
(5, 'Gerardo Iván',     'Rivas',     'Solís',    NULL, '9935000002', 'Pasaporte G1234567', TRUE);                -- 16

INSERT INTO alumnos (id_persona, numero_control, id_carrera, semestre) VALUES
(1, '22301001', 1, 7), (2, '22301002', 1, 7), (3, '23301015', 3, 5),
(4, '21301120', 4, 9), (5, '24301033', 5, 3), (6, '20301077', 7, 11);

INSERT INTO empleados (id_persona, numero_empleado, id_departamento, puesto) VALUES
(7,  'D1045', 1, 'Docente de tiempo completo'),
(8,  'D1102', 2, 'Docente de asignatura'),
(9,  'D1188', 3, 'Jefa de departamento'),
(10, 'A2031', 4, 'Vigilante'),
(11, 'A2047', 5, 'Jefa de ventanilla'),
(12, 'A2060', 6, 'Bibliotecario');

INSERT INTO proveedores (id_persona, id_empresa) VALUES (13, 1), (14, 2);

-- Visitas: una para hoy y una de ayer -------------------------------------------------------
INSERT INTO visitas (id_persona, id_anfitrion, motivo, fecha, estado) VALUES
(15, 7, 'Entrevista para residencia profesional',  fecha_local(now()),     'programada'),  -- 1
(16, 9, 'Revisión de convenio de colaboración',    fecha_local(now()) - 1, 'realizada');   -- 2

-- Evento con pases genéricos -----------------------------------------------------------------
INSERT INTO eventos (nombre, lugar, inicio, fin, cupo) VALUES
('Semana de Ciencia y Tecnología 2026', 'Auditorio principal',
 (fecha_local(now()) + time '07:00') AT TIME ZONE zona_horaria(),
 (fecha_local(now()) + 2 + time '21:00') AT TIME ZONE zona_horaria(), 200);

-- Credenciales -----------------------------------------------------------------------------------
-- Alumnos: vigentes durante el semestre, con NIP 1234 para entrar sin QR
INSERT INTO credenciales (tipo, id_persona, id_perfil, nip_hash, vigencia_inicio, vigencia_fin, activa)
SELECT 'personal', p, 1, cifrar('1234'),
       timestamptz '2026-08-01 00:00-06', timestamptz '2027-01-31 23:59-06',
       p NOT IN (4, 6)                                   -- Carlos (extravío) y Diego (baja) desactivadas
  FROM generate_series(1, 6) p;

-- Docentes y administrativos: sin caducidad, con NIP 1234
INSERT INTO credenciales (tipo, id_persona, id_perfil, nip_hash, vigencia_inicio)
SELECT 'personal', p, CASE WHEN p <= 9 THEN 2 WHEN p = 10 THEN 4 ELSE 3 END, cifrar('1234'),
       timestamptz '2026-01-05 00:00-06'
  FROM generate_series(7, 12) p;

-- Proveedor vigente una semana y proveedora con pase vencido
INSERT INTO credenciales (tipo, id_persona, id_perfil, vigencia_inicio, vigencia_fin) VALUES
('personal', 13, 5, now() - interval '1 day', now() + interval '7 days'),
('personal', 14, 5, now() - interval '10 days', now() - interval '2 days');

-- Visitas: pase de un solo uso válido solo el día de la visita
INSERT INTO credenciales (tipo, id_persona, id_perfil, id_visita, vigencia_inicio, vigencia_fin, usos_maximos, usos_realizados) VALUES
('personal', 15, 6, 1, (fecha_local(now()) + time '07:00') AT TIME ZONE zona_horaria(),
                      (fecha_local(now()) + time '20:00') AT TIME ZONE zona_horaria(), 1, 0),
('personal', 16, 6, 2, (fecha_local(now()) - 1 + time '07:00') AT TIME ZONE zona_horaria(),
                      (fecha_local(now()) - 1 + time '20:00') AT TIME ZONE zona_horaria(), 1, 1);

-- Pases genéricos del evento: tres de un solo uso y uno grupal con 40 usos
INSERT INTO credenciales (tipo, descripcion, id_perfil, id_evento, vigencia_inicio, vigencia_fin, usos_maximos)
SELECT 'generica', 'Pase de evento #' || n, 7, 1, e.inicio, e.fin, 1
  FROM eventos e, generate_series(1, 3) n
UNION ALL
SELECT 'generica', 'Pase grupal – CBTIS invitado (40 personas)', 7, 1, e.inicio, e.fin, 40
  FROM eventos e;

-- Pase genérico compartido de mantenimiento (sin titular, uso ilimitado por 30 días)
INSERT INTO credenciales (tipo, descripcion, id_perfil, vigencia_inicio, vigencia_fin)
VALUES ('generica', 'Contratista eléctrico – cuadrilla de mantenimiento', 5,
        now() - interval '1 day', now() + interval '30 days');

UPDATE credenciales SET creada_por = 1;

-- Bitácora histórica: llegadas y salidas de los últimos 5 días hábiles ----------------------------
INSERT INTO registro_accesos (fecha_hora, id_punto, id_credencial, id_persona, metodo, evento, resultado, id_usuario)
SELECT (d + t.hora + make_interval(mins =>
            (p.id_persona * t.paso + (fecha_local(now()) - d) * 11) % t.rango)) AT TIME ZONE zona_horaria(),
       t.punto, c.id_credencial, p.id_persona, t.metodo, t.evento, 'permitido', 2
  FROM (SELECT fecha_local(now()) - g AS d FROM generate_series(1, 7) g) dias
 CROSS JOIN (VALUES (1), (2), (5), (7), (8), (10), (11), (12)) p(id_persona)
 JOIN credenciales c ON c.id_persona = p.id_persona
 CROSS JOIN (VALUES (time '06:50', 'entrada', 1, 'qr',   7, 45),     -- llegada entre 06:50 y 07:35
                    (time '13:45', 'salida',  1, 'nip', 13, 150)     -- salida entre 13:45 y 16:15
            ) t(hora, evento, punto, metodo, paso, rango)
 WHERE extract(isodow FROM d) BETWEEN 1 AND 5;

-- Un par de intentos denegados para que la bitácora tenga ejemplos
INSERT INTO registro_accesos (fecha_hora, id_punto, id_credencial, id_persona, metodo, resultado, motivo, id_usuario)
SELECT now() - interval '1 day', 1, c.id_credencial, 14, 'qr', 'denegado',
       'Pase vencido el ' || to_char(c.vigencia_fin AT TIME ZONE zona_horaria(), 'DD/MM/YYYY HH24:MI'), 2
  FROM credenciales c WHERE c.id_persona = 14;

-- La carga inicial no cuenta como cambios de usuarios
TRUNCATE auditoria;
