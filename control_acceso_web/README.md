# Control de Acceso Campus ITVH – Aplicación web

Sistema web de control de acceso y bitácora para el **Instituto Tecnológico de Villahermosa**. Registra entradas y salidas de alumnos, docentes, personal, proveedores y visitantes con **código QR, NIP o registro manual**, y emite pases con caducidad, de un solo uso o para eventos.

- **Aplicación:** Python + Flask.
- **Base de datos:** PostgreSQL. Las reglas de acceso viven en la base de datos.
- **Despliegue en la nube:** Render para la aplicación y Neon para la base de datos, ambos gratuitos.

> **Para publicarla en internet:** sigan la [Guía de despliegue en la nube](GUIA_DESPLIEGUE.md).

---

## Requisitos del proyecto y cómo se cumplen

| Requisito | Cómo funciona |
|---|---|
| **Acceso programado** | Cada **perfil** (Alumno, Docente, Proveedor…) tiene un **horario**: franjas por día con hora de inicio y fin, por ejemplo *Alumnos: L–V 06:30–21:30 y sábado 07:00–15:00*. Un pase puede tener un horario propio distinto al de su perfil. Fuera de horario se niega la **entrada**; la salida siempre se permite. |
| **Llegada y salida** | La caseta decide sola si es entrada o salida. **Llegadas y salidas** muestra por persona y por día la primera entrada, la última salida y el tiempo en el campus, y se puede descargar en CSV. |
| **Ingreso sin QR** | Hay dos alternativas al QR: **No. de control o de empleado + NIP**, para quien olvidó la credencial, y **registro manual**, en el que el vigilante busca a la persona y verifica su identificación. Las dos aplican las mismas reglas y la bitácora guarda el método usado. |
| **QR de visita o proveedor con caducidad** | **Pase de visita / proveedor** registra en un paso a la persona, su visita, el anfitrión y un QR con fecha y hora de inicio y de fin. |
| **Activar y desactivar** | Hay un botón para credenciales, personas, puntos de acceso y usuarios. Dar de baja a una persona desactiva sus credenciales (trigger). Si un QR se pierde, se genera uno nuevo y el anterior deja de servir. Cada cambio queda en la **auditoría** con el usuario que lo hizo. |
| **QR de un solo uso** | `usos_maximos = 1`. La entrada consume el uso y la salida no. Si dos casetas leen el mismo pase a la vez, `SELECT … FOR UPDATE` garantiza que solo una lo acepte. |
| **Acceso personal y genérico** | Las **credenciales personales** tienen un titular. Los **pases genéricos** no tienen titular: tienen una descripción y un número de usos. Se usan para eventos (pases individuales o un pase grupal de 40 personas), cuadrillas de mantenimiento o pases de préstamo. |
| **En la nube con PostgreSQL** | La aplicación va en Render y la base de datos PostgreSQL en Neon. |
| **Kiosco de alumnos** | Una computadora fija con cámara en el acceso. El alumno teclea su número de control (o muestra el código de su credencial) y aparece su **foto** para que el guardia la compare. A diferencia de la computadora que hay hoy en el ITVH, la entrada **queda registrada** en la bitácora. Ver [Kiosco de alumnos](#kiosco-de-alumnos). |

**Otras reglas:**
- Lecturas repetidas: se ignora una segunda lectura del mismo pase en menos de 10 segundos.
- NIP: se bloquea tras 5 intentos fallidos.
- Puertas: cada perfil tiene las suyas.
- Accesos y áreas internas:
  - Los accesos **perimetrales** (principal y vehicular) marcan la entrada y la salida del campus.
  - Las **áreas internas** (biblioteca, centro de cómputo, auditorio) solo registran el paso.
  - Un pase de un solo uso puede entrar después al auditorio sin gastar otro uso.

---

## SQL procedural en PostgreSQL

| Tipo | Objeto | Qué hace | Dónde lo usa la aplicación |
|---|---|---|---|
| Procedimiento (`CALL`) | `sp_crear_pase_visita` | **Alta:** persona, visita y QR con caducidad en una transacción | Pase de visita / proveedor |
| Procedimiento | `sp_generar_pases_evento` | **Alta masiva:** pases genéricos respetando el cupo (`FOR UPDATE`) | Eventos → Generar |
| Procedimiento | `sp_cambiar_estado_credencial` | **Modificación:** activar o desactivar un QR | Botón Activar/Desactivar |
| Procedimiento | `sp_baja_persona` | **Baja lógica:** nunca se borra a nadie | Personas → Dar de baja |
| Función | `fn_registrar_acceso` | **Consulta + alta:** valida reglas y registra entrada/salida | Caseta (QR, NIP, manual) |
| Función | `fn_kiosco_registrar` | **Consulta + alta:** identifica al alumno, valida reglas y registra su entrada | Kiosco de alumnos |
| Función | `fn_login` | Verifica la contraseña cifrada (bcrypt) | Iniciar sesión |
| Funciones | `horario_permite`, `estado_credencial`, `fecha_local` | Reglas de horario y estado | Validaciones y vistas |
| Trigger | `trg_bitacora_inmutable` | Impide modificar o borrar la bitácora | Siempre |
| Trigger | `trg_baja_persona` | Al dar de baja, desactiva sus credenciales | Siempre |
| Triggers | `trg_auditoria_*` | Guardan quién activó, desactivó o dio de alta | Administración → Auditoría |

Python llama a estos objetos con psycopg (`CALL …` y `SELECT … FROM fn_…`); las reglas no se repiten en el código de la aplicación.

---

## Pantallas

| Pantalla | Para qué sirve | Roles |
|---|---|---|
| **Panel** | Personas dentro del campus, entradas, salidas y accesos denegados de hoy, y pases por vencer | Todos |
| **Kiosco de alumnos** | Pantalla completa para la computadora del acceso: número de control o cámara, foto del alumno y resultado en verde o rojo | Kiosco, admin |
| **Caseta / Lector QR** | Cámara del celular o la computadora, código tecleado o lector USB, NIP y registro manual. Resultado en verde o rojo con sonido | Vigilancia, admin |
| **Personas** | Alta y edición de alumnos, docentes, personal, proveedores y visitantes; historial y asistencia de cada persona | Recepción, admin (los demás solo consultan) |
| **Credenciales** | QR personales y genéricos: vigencia, horario, usos, NIP, activar y desactivar, impresión de gafetes de 86 × 54 mm y descarga del QR | Recepción, admin; vigilancia puede activar y desactivar |
| **Pase de visita / proveedor** | Alta rápida con caducidad y opción de un solo uso | Recepción, admin |
| **Eventos** | Crea eventos y genera pases genéricos, con control de cupo, e imprime la hoja de pases | Recepción, admin |
| **Bitácora** | Todos los movimientos e intentos denegados, con filtros y descarga en CSV | Todos |
| **Llegadas y salidas** | Asistencia por día, con descarga en CSV | Todos |
| **Horarios y perfiles** | Horarios programados y puertas permitidas por perfil | Admin |
| **Administración** | Usuarios de la aplicación, puntos de acceso, configuración y auditoría | Admin |

**Cuentas de demostración:** `admin`, `vigilancia`, `recepcion`, `consulta` y `kiosco`, todas con la contraseña `Campus#2026`. Cámbienlas en **Administración** antes de usar la aplicación en serio.

Los datos de demostración son ficticios:
- **Personas:** 6 alumnos, 3 docentes, 3 administrativos, 2 proveedores y 2 visitantes. Los alumnos y el personal tienen NIP `1234`.
- **Evento:** la Semana de Ciencia y Tecnología, con sus pases.
- **Bitácora:** una semana de llegadas y salidas.

---

## Kiosco de alumnos

Hoy, en los accesos del ITVH hay una computadora donde el alumno teclea su número de control: aparece su perfil y el guardia revisa la credencial, pero **no se guarda nada**. El kiosco hace lo mismo y además registra la entrada.

**Cómo se usa en el acceso:**
1. La computadora (con cámara web) inicia sesión una vez con un usuario de rol **Kiosco** y elige su acceso. Solo puede abrir esta pantalla.
2. El alumno **teclea su número de control** y presiona Enter. También puede mostrar a la cámara el QR o el código de barras de su credencial, o usar un lector de códigos USB.
3. Aparece su **foto**, nombre, número de control, carrera y semestre, con el resultado en **verde** (entrada registrada) o **rojo** (motivo). El guardia compara la foto con la persona. Después de unos segundos la pantalla vuelve a la bienvenida.

**Reglas (en `fn_kiosco_registrar`, PostgreSQL):**
- No pide NIP: la foto sustituye esa verificación.
- **Solo alumnos.** El personal, los proveedores y las visitas siguen pasando por la caseta.
- **Solo entradas**, nunca salidas. Un segundo registro del mismo alumno en menos de 60 segundos se ignora.
- Aplica las mismas reglas que la caseta: credencial desactivada, alumno dado de baja, vigencia, puertas del perfil y horario.
- Solo se puede usar en un acceso de entrada al campus (no en áreas internas).
- La bitácora guarda el método **Kiosco** y el panel cuenta las entradas por kiosco.

**Fotografías:** recepción o el administrador las suben desde la ficha de cada persona (JPG, PNG o WEBP de hasta 900 KB). Se guardan en la base de datos, en la tabla `fotos_personas`. Mientras alguien no tenga foto, se muestra una **imagen de ejemplo** (una ilustración generada por la aplicación, marcada como "Foto de ejemplo").

> Como el kiosco solo registra entradas, un alumno que entró por el kiosco aparece como "dentro" en el panel durante el resto del día, salvo que registre su salida en la caseta.

---

## Tecnologías

| Pieza | Elección | Por qué |
|---|---|---|
| Base de datos | **PostgreSQL 15+** | Requisito del proyecto. Las reglas importantes van en la base de datos, así se cumplen aunque alguien use otra aplicación: funciones, triggers, `CHECK`, `FOR UPDATE` y roles. |
| Backend | **Python 3.12 + Flask** | El equipo ya conoce Python. Flask es pequeño, muy documentado y basta para una aplicación de formularios. |
| Conexión | **psycopg 3** | Es el controlador oficial de PostgreSQL para Python y toda la SQL usa parámetros (`%s`). |
| Interfaz | HTML generado en el servidor (Jinja2) + CSS y JavaScript propios | Funciona en computadora y celular sin compilar nada ni depender de frameworks. |
| Lector QR | [html5-qrcode](https://github.com/mebjas/html5-qrcode) | Usa la cámara desde el navegador, sin instalar nada. Requiere https, que la nube ya da. |
| Generación de QR | [QRCode.js](https://github.com/davidshimjs/qrcodejs) | Dibuja el QR en el navegador y se puede descargar como PNG. |
| Hosting web | **Render**, plan gratuito | Se conecta a GitHub y publica cada cambio solo, con https incluido. |
| Hosting BD | **Neon**, plan gratuito | PostgreSQL administrado, sin caducidad, con 1 GB por proyecto. |

---

## Estructura

```
control_acceso_web/
├── wsgi.py                    Punto de entrada (local: python wsgi.py · nube: gunicorn wsgi:app)
├── requirements.txt           Flask, psycopg, gunicorn
├── .env.ejemplo               Plantilla de configuración (copiar como .env)
├── database/
│   ├── instalar.sql           Instalación con psql
│   ├── 01_esquema.sql         20 tablas en 3FN (esquema "campus")
│   ├── 02_funciones.sql       fn_registrar_acceso, fn_login, horarios, triggers de bitácora y auditoría
│   ├── 03_vistas.sql          Personas, credenciales, bitácora, asistencia, presentes, resumen
│   ├── 04_datos.sql           Datos de demostración
│   ├── 05_seguridad.sql       Rol app_campus de mínimo privilegio
│   ├── 06_procedimientos.sql  Procedimientos almacenados (CALL) que usa la aplicación
│   └── 07_kiosco.sql          Módulo del kiosco de alumnos (se puede aplicar sin borrar datos)
├── app/
│   ├── __init__.py            Configuración y registro de módulos
│   ├── db.py                  Conexión y traducción de errores de PostgreSQL al español
│   ├── seguridad.py           Inicio de sesión, permisos por rol y protección CSRF
│   ├── rutas/                 Un archivo por módulo (caseta, personas, credenciales, pases…)
│   ├── templates/             Pantallas HTML
│   └── static/                CSS, JavaScript y librerías QR
├── herramientas/instalar_bd.py  Instala la base sin psql (útil en Windows)
└── pruebas/                   52 pruebas automáticas (base de datos y web)
```

Para **agregar una función nueva**:
1. Agreguen sus tablas o funciones en `database/`.
2. Creen su archivo en `app/rutas/` y sus plantillas en `app/templates/`.
3. Registren el módulo en `app/__init__.py` y denle permiso en `app/seguridad.py`.

### Modelo de datos (21 tablas y 7 vistas)

| Grupo | Tablas |
|---|---|
| Catálogos | `tipos_persona`, `carreras`, `departamentos`, `empresas`, `configuracion` |
| Personas | `personas` + `alumnos` / `empleados` / `proveedores` (datos propios de cada tipo), `fotos_personas` |
| Acceso programado | `horarios`, `horario_franjas`, `perfiles_acceso`, `perfil_puntos`, `puntos_acceso` |
| Pases | `credenciales` (personal o genérica, vigencia, usos, NIP), `visitas`, `eventos` |
| Registro | `registro_accesos` (no se puede modificar ni borrar), `auditoria`, `usuarios` |

---

## Ejecutarla en su computadora

Necesitan Python 3.10 o superior y una base PostgreSQL: la de Neon, o una local en WSL.

```powershell
cd control_acceso_web
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.ejemplo .env          # y escriban su DATABASE_URL en .env
.venv\Scripts\python.exe herramientas\instalar_bd.py
.venv\Scripts\python.exe wsgi.py
```

Abran **http://127.0.0.1:5000**. En `localhost` la cámara funciona aunque no haya https.

## Pruebas automáticas

```powershell
set TEST_DATABASE_URL=postgresql://...      # una base de PRUEBA: se borra en cada prueba
.venv\Scripts\python.exe -m pip install pytest
.venv\Scripts\python.exe -m pytest pruebas -v
```

Son 52 pruebas en total:
- **26 de reglas en PostgreSQL:**
  - horarios, un solo uso, vencidos y pases genéricos;
  - NIP con bloqueo y registro manual;
  - dos lectores al mismo tiempo, bitácora inmutable y rol de mínimo privilegio;
  - los cuatro procedimientos almacenados;
  - kiosco: solo entradas, solo alumnos, doble registro, reglas de acceso y QR de la credencial.
- **26 de la aplicación web:**
  - permisos por rol, CSRF y caseta;
  - altas, pases y cupo de eventos;
  - auditoría, horarios y CSV;
  - pantalla y permisos del kiosco, foto de ejemplo y subida de fotografías.

**Pendiente de probar en sus computadoras:** la cámara real. En el entorno de desarrollo no había cámara, así que la lectura del QR se probó tecleando el código.
