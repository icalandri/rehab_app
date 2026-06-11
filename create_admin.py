"""
Crea (o actualiza) un usuario en la tabla 'usuarios' con contraseña hasheada.
Se corre UNA vez para dar de alta el primer admin.

Uso:
    python create_admin.py

Lee la conexión desde la variable de entorno DATABASE_URL, por ejemplo:
    export DATABASE_URL="postgresql+psycopg2://USER:PASS@HOST:6543/postgres?sslmode=require"
    python create_admin.py
"""
import getpass
import os
import sys

import bcrypt
from sqlalchemy import create_engine, text


def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Definí DATABASE_URL primero. Ejemplo:")
        print('  export DATABASE_URL="postgresql+psycopg2://postgres.REF:PASS'
              '@aws-0-...pooler.supabase.com:6543/postgres?sslmode=require"')
        sys.exit(1)

    usuario = input("Usuario (login): ").strip()
    nombre = input("Nombre completo: ").strip()
    rol = (input("Rol [admin/cargador/lector] (admin): ").strip() or "admin")
    p1 = getpass.getpass("Contraseña: ")
    p2 = getpass.getpass("Repetir contraseña: ")
    if p1 != p2:
        print("Las contraseñas no coinciden."); sys.exit(1)
    if len(p1) < 8:
        print("Usá al menos 8 caracteres."); sys.exit(1)

    hashed = bcrypt.hashpw(p1.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    eng = create_engine(url, connect_args={"options": "-csearch_path=rehab,public"})
    with eng.begin() as c:
        c.execute(text("""
            INSERT INTO usuarios (usuario, nombre, password_hash, rol)
            VALUES (:u, :n, :h, :r)
            ON CONFLICT (usuario) DO UPDATE
              SET nombre = EXCLUDED.nombre,
                  password_hash = EXCLUDED.password_hash,
                  rol = EXCLUDED.rol,
                  activo = true
        """), {"u": usuario, "n": nombre, "h": hashed, "r": rol})
    print(f"✅ Usuario '{usuario}' creado/actualizado con rol '{rol}'.")


if __name__ == "__main__":
    main()
