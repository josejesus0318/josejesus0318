# Guía de despliegue en la nube (gratis)

Cómo publicar el **Control de Acceso Campus ITVH** en internet:

- **Neon** guarda la base de datos PostgreSQL.
- **Render** ejecuta la aplicación web y le da una dirección `https://…onrender.com`.

Los dos tienen plan gratuito y se puede entrar con la cuenta de GitHub.

```
Celular o PC ──https──► Render (Flask) ──SSL──► Neon (PostgreSQL)
```

**Tiempo aproximado:** 20 minutos.

> **Limitaciones del plan gratuito:**
> - **Render:** si nadie usa la aplicación durante 15 minutos, se "duerme". La primera visita tarda cerca de un minuto en despertarla. Antes de una demostración, ábranla un par de minutos antes.
> - **Neon:** también se duerme a los 5 minutos sin uso, pero despierta en segundos.
> - No usen la base de datos gratuita de Render: se borra a los 30 días.

---

## Paso 1. Crear la base de datos en Neon

1. Entren a **neon.com** y elijan **Sign up → Continue with GitHub**.
2. Creen un proyecto:
   - **Project name:** `control-acceso-itvh`
   - **Postgres version:** la más reciente
   - **Region:** **AWS US East 2 (Ohio)**, la misma región que usaremos en Render.
3. En el proyecto, presionen **Connect**. Aparece la **cadena de conexión**:

   ```
   postgresql://neondb_owner:<SU-CONTRASEÑA>@<SU-SERVIDOR>-pooler.<región>.aws.neon.tech/neondb?sslmode=require&channel_binding=require
   ```

   Cópienla completa **desde Neon** (botón **Copy snippet**). No copien el ejemplo de arriba: es solo para mostrar la forma. La aplicación funciona con la cadena *pooled* (la que muestra por omisión) y con la directa.

> **Esa cadena incluye la contraseña.** No la pongan en GitHub ni en chats. Si se filtra, en Neon vayan a **Roles → Reset password** y actualicen la cadena en Render.

## Paso 2. Instalar las tablas y los datos

Elijan **una** de estas dos opciones.

### Opción A: desde Neon, sin instalar nada

1. En Neon abran **SQL Editor**.
2. Copien, peguen y ejecuten (**Run**) el contenido de cada archivo de `control_acceso_web/database/`, **en este orden**:
   1. `01_esquema.sql`
   2. `02_funciones.sql`
   3. `03_vistas.sql`
   4. `04_datos.sql`
   5. `05_seguridad.sql`
3. Ejecuten `SELECT count(*) FROM campus.personas;` para comprobar. Debe dar **16**.

### Opción B: con el instalador de Python, desde su computadora

En **PowerShell**, dentro de la carpeta del repositorio:

```powershell
cd control_acceso_web
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.ejemplo .env
notepad .env
```

En el Bloc de notas, peguen su cadena en la línea `DATABASE_URL=` y guarden. Después ejecuten:

```powershell
.venv\Scripts\python.exe herramientas\instalar_bd.py
```

Debe terminar con `>> Instalación terminada` y los totales: 16 personas, 21 credenciales y 4 usuarios.

> Cualquiera de las dos opciones **borra y vuelve a crear** el esquema `campus`. Úsenlas solo para instalar o para regresar a los datos de demostración.

## Paso 3. Publicar la aplicación en Render

1. Entren a **render.com** y elijan **Get Started → GitHub**.
2. Presionen **New → Web Service** y elijan el repositorio **josejesus0318**. Si no aparece, den clic en **Configure GitHub** y denle acceso a ese repositorio.
3. Llenen el formulario:

   | Campo | Valor |
   |---|---|
   | Name | `control-acceso-itvh` (será parte de la dirección) |
   | Region | **Ohio (US East)** |
   | Branch | `main` |
   | Root Directory | `control_acceso_web` |
   | Runtime / Language | Python 3 |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `gunicorn wsgi:app --workers 1 --threads 8 --timeout 60` |
   | Instance Type | **Free** |

4. En **Environment Variables** agreguen estas tres variables:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | la cadena de Neon del paso 1 |
   | `SECRET_KEY` | un texto largo y aleatorio, o el botón **Generate** |
   | `PYTHON_VERSION` | `3.12.10` |

5. Presionen **Deploy Web Service**. Tarda de 2 a 4 minutos. Cuando diga **Live**, abran la dirección `https://control-acceso-itvh.onrender.com`, o la que les asigne Render.
6. Entren con el usuario `admin` y la contraseña `Campus#2026`.

> **Alternativa con Blueprint:** en la raíz del repositorio está `render.yaml`. En Render elijan **New → Blueprint**, seleccionen el repositorio y escriban la `DATABASE_URL` cuando la pida. Crea el servicio con la misma configuración.

**A partir de aquí**, cada vez que suban cambios a GitHub (`main`), Render vuelve a publicar la aplicación solo.

## Paso 4. Cambiar las contraseñas de demostración

En la aplicación, vayan a **Administración → Usuarios de la aplicación**:
- Cambien la contraseña de `admin`, `vigilancia`, `recepcion` y `consulta`.
- O creen usuarios nuevos y desactiven los de demostración.

## Paso 5. Probar el lector con el celular

1. En el celular, abran la dirección de Render y entren con el usuario `vigilancia`. Se abre directamente la **Caseta**.
2. Presionen **Iniciar cámara** y acepten el permiso.
3. En una computadora entren como `admin`. Vayan a **Credenciales**, abran cualquiera y apunten la cámara del celular al QR de la pantalla.
4. La caseta del celular se pone en **verde** con "Acceso permitido". Si vuelven a leerlo después de 10 segundos, registra la **salida**.

**Para probar otros casos:**
- **NIP:** pestaña **No. control + NIP**, número `22301001` y NIP `1234`.
- **Pase de un solo uso:** en **Pase de visita / proveedor**, creen un pase y léanlo dos veces para registrar entrada y salida. A la tercera lectura dice *"Pase de un solo uso ya utilizado"*.
- **Horario:** fuera del horario del perfil (por ejemplo, un alumno en domingo) dice *"Fuera del horario permitido"*.

---

## Opcional: conectar la aplicación con un rol de mínimo privilegio

Por omisión, la aplicación usa el rol dueño de la base (`neondb_owner`). Es más seguro que use `app_campus`, que ya creó `05_seguridad.sql`. Con ese rol la aplicación:
- no puede escribir directamente en la bitácora;
- no puede leer las contraseñas cifradas;
- no puede borrar personas.

1. En el **SQL Editor** de Neon ejecuten esto, con una contraseña larga inventada por ustedes:

   ```sql
   ALTER ROLE app_campus LOGIN PASSWORD 'una-contraseña-larga-de-al-menos-20-caracteres';
   ```

2. En Render, cambien `DATABASE_URL` para que use ese usuario: en la cadena reemplacen `neondb_owner:XXXX` por `app_campus:su-contraseña`.
3. Guarden. Render reinicia la aplicación sola.

## Problemas comunes

| Síntoma | Solución |
|---|---|
| La página tarda un minuto en abrir | Es el plan gratuito despertando. Es normal |
| *No fue posible conectar con la base de datos* | Revisen que `DATABASE_URL` en Render esté completa, con `?sslmode=require` |
| `relation "campus.…" does not exist` o páginas vacías | Falta el paso 2 (instalar las tablas) |
| La cámara no abre | Debe ser `https://`. En iPhone, usen Safari. Revisen los permisos de cámara del navegador |
| *La página caducó* al enviar un formulario | La sesión expiró o se abrió en otra pestaña. Recarguen la página |
| Se cierran todas las sesiones al reiniciar | Falta la variable `SECRET_KEY` en Render |
| Render dice *Build failed* | Revisen que **Root Directory** sea `control_acceso_web` y que `PYTHON_VERSION` sea `3.12.10` |
