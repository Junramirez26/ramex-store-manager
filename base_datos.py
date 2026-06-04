import sqlite3
from pathlib import Path

DB_NAME = str(Path(__file__).resolve().parent / "camisetas_deportivas.db")

def conectar():
    """
    Retorna una conexión con FK activadas.
    SIEMPRE usar esta función, nunca sqlite3.connect() directo.
    """
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")   # Fix #4: FK desactivadas por defecto en SQLite
    return conn

def inicializar_bd():
    """
    Crea todas las tablas si no existen.
    Se llama UNA SOLA VEZ desde main.py al arrancar.
    Fix #1: eliminada la función inicializar() duplicada en funciones.py
    Fix #3: columnas calculadas (saldo) manejadas en Python, no como GENERATED ALWAYS
             (compatibilidad con SQLite < 3.31)
    Fix #2: cada bloque de cambios usa transacción explícita con rollback en caso de error
    """
    conn = conectar()
    cursor = conn.cursor()

    try:
        # Tabla de categorías
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Tabla de camisetas (inventario)
        # Fix #3: sin GENERATED ALWAYS — más compatible y sin riesgo de crash
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS camisetas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria_id INTEGER NOT NULL,
            equipo TEXT DEFAULT '',
            temporada TEXT DEFAULT 'General',
            talla TEXT NOT NULL CHECK(talla IN ('XS','S','M','L','XL','XXL')),
            stock INTEGER DEFAULT 0 CHECK(stock >= 0),
            precio_compra REAL DEFAULT 0.0 CHECK(precio_compra >= 0),
            precio_venta REAL DEFAULT 0.0 CHECK(precio_venta >= 0),
            FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE RESTRICT,
            UNIQUE(categoria_id, talla)
        )
        """)

        # Tabla de movimientos
        # Fix #3: total como columna normal (calculado en Python al insertar)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camiseta_id INTEGER,
            tipo TEXT NOT NULL CHECK(tipo IN ('COMPRA','VENTA','PAGO','AJUSTE MANUAL')),
            cantidad INTEGER NOT NULL,
            precio_unitario REAL NOT NULL,
            total REAL NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            venta_id INTEGER,
            FOREIGN KEY (camiseta_id) REFERENCES camisetas(id) ON DELETE CASCADE,
            FOREIGN KEY (venta_id) REFERENCES ventas(id) ON DELETE CASCADE
        )
        """)

        # Tabla de ventas
        # Fix #3: saldo como columna normal (calculado en Python al insertar/actualizar)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cliente TEXT NOT NULL,
            camiseta_id INTEGER,
            categoria_id INTEGER NOT NULL,
            talla TEXT NOT NULL,
            cantidad INTEGER NOT NULL CHECK(cantidad > 0),
            precio_unitario REAL NOT NULL CHECK(precio_unitario > 0),
            total REAL NOT NULL CHECK(total > 0),
            pagado REAL DEFAULT 0 CHECK(pagado >= 0),
            saldo REAL NOT NULL DEFAULT 0,
            costo_unitario REAL NOT NULL DEFAULT 0 CHECK(costo_unitario >= 0),
            costo_total REAL NOT NULL DEFAULT 0 CHECK(costo_total >= 0),
            estado_pago TEXT DEFAULT 'pendiente' CHECK(estado_pago IN ('pagado','parcial','pendiente')),
            estado_envio TEXT DEFAULT 'no_enviado' CHECK(estado_envio IN ('enviado','no_enviado')),
            FOREIGN KEY (camiseta_id) REFERENCES camisetas(id),
            FOREIGN KEY (categoria_id) REFERENCES categorias(id)
        )
        """)

        # Migraciones ligeras para bases creadas con versiones anteriores.
        # Se agregan columnas faltantes sin romper instalaciones antiguas.
        cursor.execute("PRAGMA table_info(ventas)")
        columnas_ventas = {row[1] for row in cursor.fetchall()}

        def asegurar_columna_ventas(nombre, definicion):
            if nombre not in columnas_ventas:
                cursor.execute(f"ALTER TABLE ventas ADD COLUMN {nombre} {definicion}")
                columnas_ventas.add(nombre)

        asegurar_columna_ventas("camiseta_id", "INTEGER")
        asegurar_columna_ventas("pagado", "REAL NOT NULL DEFAULT 0")
        asegurar_columna_ventas("saldo", "REAL NOT NULL DEFAULT 0")
        asegurar_columna_ventas("costo_unitario", "REAL NOT NULL DEFAULT 0")
        asegurar_columna_ventas("costo_total", "REAL NOT NULL DEFAULT 0")
        asegurar_columna_ventas("estado_pago", "TEXT NOT NULL DEFAULT 'pendiente'")
        asegurar_columna_ventas("estado_envio", "TEXT NOT NULL DEFAULT 'no_enviado'")

        cursor.execute("PRAGMA table_info(movimientos)")
        columnas_mov = {row[1] for row in cursor.fetchall()}

        def asegurar_columna_movimientos(nombre, definicion):
            if nombre not in columnas_mov:
                cursor.execute(f"ALTER TABLE movimientos ADD COLUMN {nombre} {definicion}")
                columnas_mov.add(nombre)

        asegurar_columna_movimientos("camiseta_id", "INTEGER")
        asegurar_columna_movimientos("venta_id", "INTEGER")

        cursor.execute("""
            UPDATE ventas
            SET camiseta_id = (
                    SELECT cam.id
                    FROM camisetas cam
                    WHERE cam.categoria_id = ventas.categoria_id
                      AND cam.talla = ventas.talla
                    LIMIT 1
                )
            WHERE camiseta_id IS NULL
        """)
        cursor.execute("""
            UPDATE ventas
            SET pagado = COALESCE(pagado, 0),
                saldo = COALESCE(saldo, total - COALESCE(pagado, 0)),
                estado_pago = CASE
                    WHEN COALESCE(pagado, 0) >= total THEN 'pagado'
                    WHEN COALESCE(pagado, 0) > 0 THEN 'parcial'
                    ELSE 'pendiente'
                END,
                estado_envio = COALESCE(estado_envio, 'no_enviado'),
                costo_unitario = COALESCE((
                    SELECT cam.precio_compra
                    FROM camisetas cam
                    WHERE cam.id = ventas.camiseta_id
                ), 0),
                costo_total = cantidad * COALESCE((
                    SELECT cam.precio_compra
                    FROM camisetas cam
                    WHERE cam.id = ventas.camiseta_id
                ), 0)
            WHERE 1=1
        """)

        # Índices para rendimiento en búsquedas frecuentes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_fecha ON movimientos(fecha)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_tipo ON movimientos(tipo)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_camiseta ON movimientos(camiseta_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_movimientos_venta ON movimientos(venta_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_camisetas_categoria ON camisetas(categoria_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas(fecha)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ventas_cliente ON ventas(cliente)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ventas_estado_pago ON ventas(estado_pago)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ventas_camiseta ON ventas(camiseta_id)")

        conn.commit()
        print("Base de datos inicializada correctamente.")

    except Exception as e:
        conn.rollback()
        print(f"Error al inicializar la base de datos: {e}")
        raise
    finally:
        conn.close()

def verificar_version_sqlite():
    """Informa la versión de SQLite instalada. Útil para diagnóstico."""
    import sqlite3 as _sq
    version = _sq.sqlite_version
    print(f"SQLite version: {version}")
    partes = [int(x) for x in version.split(".")]
    if partes[0] < 3 or (partes[0] == 3 and partes[1] < 31):
        print("Version < 3.31: columnas GENERATED no soportadas (ya corregido en este sistema).")
    return version

if __name__ == "__main__":
    verificar_version_sqlite()
    inicializar_bd()
