# Guía de deploy — Formulario de Admisión a Rehabilitación

Sos vos quien ejecuta cada paso; yo no puedo crear tus cuentas. Seguilo en orden. Tiempo estimado: 30–40 min la primera vez.

**Arquitectura:** Supabase (Postgres gestionado) + Streamlit Community Cloud (la app). El centro abre un link, se loguea y carga. Vos sos el dueño de la base y de la seguridad.

---

## Parte A — Base de datos en Supabase

### A1. Crear el proyecto
1. Entrá a https://supabase.com y registrate (gratis).
2. **New project**. Elegí un nombre (ej. `rehab-admision`), una región cercana (ej. *South America (São Paulo)*) y definí una **Database Password** fuerte. **Guardala**: es la que va en los secrets.
3. Esperá 1–2 min a que el proyecto quede listo.

### A2. Crear el esquema
1. En el menú lateral: **SQL Editor** → **New query**.
2. Abrí `schema.sql`, copiá **todo** el contenido y pegalo en el editor.
3. **Run** (▶). Debe decir *Success*. Esto crea el esquema `rehab`, todas las tablas, ENUMs, la vista y siembra los catálogos (40 antecedentes + 10 factores de riesgo).
4. Verificá en **Table Editor** → seleccioná el esquema `rehab` (arriba a la izquierda) → deberías ver `pacientes`, `admisiones`, `usuarios`, etc.

### A3. Datos de conexión (para los secrets)
1. **Project Settings** (engranaje) → **Database**.
2. Buscá la sección **Connection pooling** / **Connection string**. Usá el **pooler en modo Session** (puerto **6543**). Anotá:
   - **Host** (algo como `aws-0-sa-east-1.pooler.supabase.com`)
   - **Port** = `6543`
   - **Database name** = `postgres`
   - **User** (algo como `postgres.abcdefghijklmnop` — incluye el ref del proyecto)
   - **Password** = la que definiste en A1.

> Por qué el pooler y no el puerto 5432: las apps web abren/cierran muchas conexiones; el pooler lo maneja mejor y es lo recomendado para Streamlit Cloud.

### A4. Crear tu usuario de login (admin)
Esto da de alta el primer usuario con contraseña hasheada. Dos opciones:

**Opción rápida (desde tu compu, con Python):**
```bash
pip install sqlalchemy psycopg2-binary bcrypt
export DATABASE_URL="postgresql+psycopg2://USER:PASSWORD@HOST:6543/postgres?sslmode=require"
python create_admin.py
```
Reemplazá `USER`, `PASSWORD`, `HOST` por los de A3. El script te pide usuario, nombre y contraseña.

**Opción sin Python (generar el hash a mano):** decímelo y te genero un `INSERT` con el hash bcrypt ya calculado para pegar en el SQL Editor.

---

## Parte B — La app en Streamlit Community Cloud

### B1. Subir el código a GitHub
1. Creá un repo en https://github.com (puede ser **privado**).
2. Subí el contenido de la carpeta `rehab_app/` **excepto** `secrets.toml` (el `.gitignore` ya lo bloquea). Deben quedar: `app.py`, `db.py`, `auth.py`, `requirements.txt`, `create_admin.py`, `.gitignore` y la carpeta `.streamlit/` (solo con el `.example`, no con secretos reales).
   - Si usás la web de GitHub: **Add file → Upload files** y arrastrá los archivos.

### B2. Deploy
1. Entrá a https://share.streamlit.io e iniciá sesión con GitHub.
2. **Create app** → elegí tu repo, branch `main`, **Main file path** = `app.py`.
3. Antes de *Deploy*, abrí **Advanced settings → Secrets** y pegá esto (con tus datos de A3):
   ```toml
   [postgres]
   host = "aws-0-sa-east-1.pooler.supabase.com"
   port = "6543"
   dbname = "postgres"
   user = "postgres.abcdefghijklmnop"
   password = "TU_PASSWORD"
   sslmode = "require"
   ```
4. **Deploy**. En 1–2 min tenés la URL pública (algo como `https://rehab-admision.streamlit.app`).

### B3. Probar
1. Abrí la URL → te pide login → entrá con el usuario de A4.
2. Cargá una evaluación de prueba (mínimo DNI + nombre) y guardá. Debe aparecer "✅ Evaluación guardada".
3. Verificá en Supabase → Table Editor → `rehab.admisiones` que llegó la fila.

### B4. Repartir el acceso al centro
- Pasale la URL a cada persona.
- Para cada una, creá un usuario propio (corré `create_admin.py` otra vez con rol `cargador`). Así sabés quién cargó qué (`admisiones.creado_por`).

---

## Seguridad — imprescindible para datos de pacientes
- El repo de GitHub **privado**; nunca subas `secrets.toml`.
- Contraseñas siempre vía bcrypt (ya lo hace `create_admin.py`). No hay claves en texto plano en la base.
- En Supabase, la base **no** es pública: solo se accede con las credenciales del pooler.
- Activá backups en Supabase (Project Settings → Database → Backups). En el plan free hay backups diarios limitados; si el estudio es serio, considerá el plan Pro.
- Conviene un aviso de confidencialidad y, si corresponde, aval del comité de ética para el almacenamiento de DNI.

## Análisis posterior (R / Python)
Para tus modelos de sobrevida, conectá directo y leé la vista plana:

**R**
```r
library(DBI); library(RPostgres)
con <- dbConnect(Postgres(), host=..., port=6543, dbname="postgres",
                 user=..., password=..., sslmode="require")
df <- dbGetQuery(con, "SELECT * FROM rehab.v_admisiones_plano")
```

**Python**
```python
import pandas as pd, sqlalchemy as sa
eng = sa.create_engine("postgresql+psycopg2://USER:PASS@HOST:6543/postgres?sslmode=require")
df = pd.read_sql("SELECT * FROM rehab.v_admisiones_plano", eng)
```

---

## Si algo falla
- **La app no conecta:** revisá que los secrets sean exactamente los de A3 y que el puerto sea `6543`.
- **"relation does not exist":** no corriste `schema.sql` o estás mirando el esquema `public` en vez de `rehab`.
- **Login falla siempre:** todavía no creaste el usuario (A4), o la contraseña no coincide.
- Escribime el error y lo resolvemos.
