import sys

# ─────────────────────────────────────────────
# Verificación de dependencias al arrancar
# ─────────────────────────────────────────────
DEPENDENCIAS = {
    "customtkinter": "pip install customtkinter",
    "tkcalendar":    "pip install tkcalendar",
    "pandas":        "pip install pandas",
    "openpyxl":      "pip install openpyxl",
}

faltantes = []
for modulo, instalacion in DEPENDENCIAS.items():
    try:
        __import__(modulo)
    except ImportError:
        faltantes.append((modulo, instalacion))

if faltantes:
    print("Faltan dependencias. Instalalas con:")
    for mod, cmd in faltantes:
        print(f"   {cmd}")
    print("\nLuego vuelve a ejecutar main.py")
    sys.exit(1)

# ─────────────────────────────────────────────
# Arranque de la aplicación
# ─────────────────────────────────────────────
from base_datos import inicializar_bd, verificar_version_sqlite
from interfaz import AppCamisetas

if __name__ == "__main__":
    try:
        verificar_version_sqlite()
        inicializar_bd()
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")
        sys.exit(1)

    try:
        app = AppCamisetas()
        app.mainloop()
    except Exception as e:
        print(f"Error inesperado al iniciar la interfaz: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
