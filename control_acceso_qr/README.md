# Control de Acceso QR – Aplicación de escritorio (Python + PostgreSQL)

Aplicación de escritorio del **Sistema de Control de Acceso con Códigos QR de Grupo Solutions** (Taller de Bases de Datos, ITVH – Equipo 6 Magenta).
Lee la credencial QR con la cámara web, valida el acceso en PostgreSQL y registra la entrada o salida; además administra colaboradores, visitantes, credenciales, catálogos y usuarios.

**Tecnologías:** Python 3.10+ · PyQt6 · psycopg 3 · OpenCV · pyzbar · PostgreSQL 18 (sobre WSL)

---

## Arquitectura en capas

```
control_acceso_qr/
├── main.py                     Punto de entrada (login → ventana principal)
├── config.ini                  Servidor, puerto, base y datos del lector (sin contraseñas)
├── requirements.txt
├── database/                   Modelo v2 en PostgreSQL
│   ├── instalar.sql            Ejecuta todo en orden
│   ├── 01_esquema.sql          18 tablas en 3FN
│   ├── 02_datos.sql            Datos de prueba (migrados del modelo v1)
│   ├── 03_funciones.sql        sp_registrar_acceso, sp_crear_usuario, triggers
│   ├── 04_vistas.sql           Vistas que lee la aplicación
│   └── 05_seguridad.sql        Roles, GRANT y cuentas de demostración
├── control_acceso/
│   ├── models/                 Entidades (dataclasses) y descriptores de catálogos
│   ├── dao/                    TODO el SQL de la aplicación vive aquí
│   ├── views/                  Pantallas PyQt6 (ninguna contiene SQL)
│   └── utils/                  Configuración, sesión, errores, permisos y QR
├── recursos/estilo.qss         Tema visual (magenta)
└── pruebas/
    ├── verificar_instalacion.py
    └── generar_qr_demo.py
```

| Capa | Responsabilidad |
|---|---|
| `views` | Muestra datos y recibe acciones. Llama a los DAO; nunca escribe SQL. |
| `dao` | Consultas parametrizadas (`%s`); convierte los errores de PostgreSQL en mensajes en español. |
| `models` | Entidades con validaciones previas (campos obligatorios, formatos). |
| `utils` | Conexión de la sesión, traducción de `SQLSTATE`, permisos de la interfaz, QR. |

**Seguridad de la autenticación:** la aplicación **no guarda contraseñas**. Cada persona inicia sesión con su propia cuenta de PostgreSQL (contraseña cifrada por el servidor con SCRAM-SHA-256) y la base de datos aplica los permisos de su rol. La interfaz solo oculta lo que el rol no puede usar; la seguridad real está en los `GRANT`.

---

## Modelo v2 (18 tablas en 3FN)

| Grupo | Tablas |
|---|---|
| Estructura | `ubicaciones`, `departamentos`, `puestos` |
| Horarios | `dias_semana`, `horarios_laborales`, `horario_dias` (N:M) |
| Personas | `tipos_identificacion`, `empresas`, `colaboradores`, `visitantes`, `visitas` |
| Control de acceso | `roles_acceso`, `puntos_acceso`, `permisos_rol_punto` (N:M), `estados_credencial`, `credenciales`, `registro_accesos` |
| Aplicación | `usuarios_sistema` |

Mejoras respecto al modelo v1 de 9 tablas:

- **`visitantes` + `visitas`:** un visitante que regresa ya no duplica sus datos.
- **Catálogos en lugar de texto libre:** ubicaciones, días del turno, empresas, tipos de identificación y estados de credencial.
- **`permisos_rol_punto`:** define por qué puertas puede pasar cada rol de acceso.
- **La bitácora guarda también los intentos denegados**, con su motivo, y no se puede modificar ni borrar (trigger).
- **Reglas en la base de datos:**
  - Un colaborador solo puede tener una credencial activa.
  - Al darlo de baja se revocan sus credenciales.
  - Solo Seguridad emite credenciales de personal.

---

## Roles y cuentas de demostración

Todas las cuentas de demostración usan la contraseña **`GrupoSol#2026`**. Cámbienlas fuera del entorno escolar.

| Cuenta | Rol | Persona | Módulos |
|---|---|---|---|
| `gs_admin` | `rol_admin_bd` | Fernando Castillo (TI) | Todos, incluido **Usuarios** |
| `gs_seguridad` | `rol_seguridad` | Sergio Domínguez | Inicio, Lector QR, Bitácora, Credenciales, Catálogos |
| `gs_recepcion` | `rol_recepcion` | Paola Sánchez | Inicio, Visitantes y visitas, Credenciales, Catálogos |
| `gs_rrhh` | `rol_rrhh` | Roberto Jiménez | Inicio, Colaboradores, Catálogos |
| `gs_direccion` | `rol_consulta` | Mariana Torres | Inicio, Bitácora (solo lectura) |
| `gs_lector` | `rol_lector_qr` | Cuenta de servicio | Inicio y Lector QR (se abre solo al iniciar sesión) |

`rol_lector_qr` no puede leer ni escribir la bitácora directamente: todo pasa por la función `sp_registrar_acceso`, que valida y registra dentro de la base de datos.

---

## Instalación

### 1. Base de datos (en WSL)

```bash
sudo service postgresql start
cd /mnt/c/Users/TU_USUARIO/ruta/al/repositorio/control_acceso_qr
sudo -u postgres psql -f database/instalar.sql
```

Debe terminar con `>> Instalación terminada` y una tabla con las 6 cuentas `gs_*`. El script se puede volver a ejecutar: reconstruye las tablas y reutiliza los roles y las cuentas que ya existan.

> Si `postgres` no puede leer la carpeta de Windows, copien antes la carpeta `database` a `/tmp` y ejecuten `sudo -u postgres psql -f /tmp/database/instalar.sql`.

### 2. Aplicación (en Windows)

```powershell
cd ruta\al\repositorio\control_acceso_qr
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python pruebas\verificar_instalacion.py
python main.py
```

El verificador revisa las librerías, la conexión con una cuenta (por omisión `gs_admin`), los roles, la cámara y la lectura de un QR. Si todo sale `[OK]`, la aplicación está lista.

La aplicación corre en Windows (donde está la cámara) y se conecta a PostgreSQL de WSL por `127.0.0.1:5432`, como indica `config.ini`. Estos datos también se pueden cambiar en **Opciones de conexión** del login.

---

## Lector QR

1. Seguridad o la cuenta `gs_lector` abre **Lector QR**, elige el **punto de acceso** y presiona **Iniciar cámara**.
2. Un hilo en segundo plano (`QThread`) captura video con OpenCV y busca códigos QR con pyzbar; si pyzbar no carga, usa el detector de OpenCV.
3. Al detectar un código, la lectura se pausa y la base de datos (`sp_registrar_acceso`) revisa, en este orden:
   - que el código exista;
   - que el estado de la credencial permita el acceso;
   - que no esté vencida;
   - que el colaborador siga activo o que la visita sea de hoy y no esté cancelada;
   - que el rol tenga permiso en ese punto.
4. La pantalla se pone **verde** (permitido), **roja** (denegado) o **amarilla** (lectura repetida), con sonido. A los 2.5 segundos vuelve a leer.

**Entrada o salida:** alterna con el último evento del mismo día. Si el punto es solo de entrada o solo de salida, se respeta. Una segunda lectura en menos de 10 segundos se ignora.

**Captura manual:** si no hay cámara, se puede escribir el código, por ejemplo `QR-COL-0001`.

**QR de prueba:** `python pruebas\generar_qr_demo.py` crea la carpeta `qr_demo/` con credenciales de ejemplo para mostrarlas desde el celular. Dentro del script se explica qué resultado debe dar cada una.

---

## Problemas comunes

| Mensaje | Solución |
|---|---|
| *No fue posible conectar con el servidor* | En WSL: `sudo service postgresql start`. Revisen el puerto en `config.ini`. |
| *Usuario o contraseña incorrectos* | Las cuentas `gs_*` usan `GrupoSol#2026`. Tras 3 intentos fallidos, el login se bloquea 30 segundos. |
| *La base de datos indicada no existe* | Ejecuten `database/instalar.sql`. |
| El verificador dice que pyzbar no está disponible | Instalen el «Visual C++ Redistributable 2013» de Microsoft, o sigan así: OpenCV lee los QR igual. |
| *No se pudo abrir la cámara 0* | Cierren otras apps que usen la cámara (Zoom, Teams, Cámara de Windows) o prueben el índice 1. |
| *La visita no corresponde al día de hoy* | La visita de prueba de Óscar se crea con la fecha de instalación. Programen otra desde Recepción. |

---

## Estado de las pruebas

Validado en el entorno de desarrollo con PostgreSQL 16 y autenticación `scram-sha-256` por TCP:

- **Base de datos:** instalación desde cero y reinstalación, 18 tablas, todos los casos del lector (permitido, repetido, vencida, revocada, sin permiso, visita de hoy, código inexistente, punto inválido), creación y bloqueo de cuentas e intento de inyección SQL en el nombre de cuenta.
- **Capa DAO:** 77 pruebas automáticas ejecutadas con cada una de las 6 cuentas, incluyendo que cada rol reciba *permiso denegado* donde corresponde.
- **QR:** generación y lectura con OpenCV, incluida una imagen girada y con ruido.
- **Código Python:** compila sin errores y pasa la revisión de tipos (pyright) contra las definiciones de PyQt6 y psycopg.

**Pendiente de probar en sus computadoras:** la interfaz gráfica y la cámara real. En el entorno de desarrollo no fue posible instalar PyQt6 ni había cámara. Si una pantalla falla, copien el mensaje de **Mostrar detalles** del error.
