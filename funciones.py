import sqlite3
import pandas as pd
from datetime import datetime
from base_datos import DB_NAME

# DB_NAME centralizado en base_datos.py para evitar abrir otra base por error.

# ──────────────────────────────────────────────────────────────
# UTILIDADES INTERNAS
# ──────────────────────────────────────────────────────────────

def conectar():
    """
    Conexión con FK activadas.
    Fix #4 (base_datos): PRAGMA foreign_keys = ON en cada conexión.
    """
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def parsear_monto(texto):
    """
    Fix #17 (COP): convierte texto de precio en pesos colombianos a float.
    Acepta: "45.000", "45,000", "45000", "45.000,50", "45,000.50"
    Rechaza cadenas no numéricas → retorna None.
    Regla: si hay AMBOS separadores, el último es el decimal.
              si hay solo punto o solo coma, se trata como separador de miles
              a menos que haya exactamente 2 dígitos después → decimal.
    """
    if not texto:
        return None
    texto = texto.strip().replace(" ", "").replace("$", "")
    if not texto:
        return None

    tiene_punto = "." in texto
    tiene_coma  = "," in texto

    try:
        if tiene_punto and tiene_coma:
            ultimo_punto = texto.rfind(".")
            ultima_coma  = texto.rfind(",")
            if ultimo_punto > ultima_coma:
                texto = texto.replace(",", "")
            else:
                texto = texto.replace(".", "").replace(",", ".")
        elif tiene_punto and not tiene_coma:
            partes = texto.split(".")
            decimales = partes[-1]
            if len(decimales) == 2 and len(partes) == 2:
                pass
            else:
                texto = texto.replace(".", "")
        elif tiene_coma and not tiene_punto:
            partes = texto.split(",")
            decimales = partes[-1]
            if len(decimales) == 2 and len(partes) == 2:
                texto = texto.replace(",", ".")
            else:
                texto = texto.replace(",", "")

        valor = float(texto)
        return valor if valor >= 0 else None
    except (ValueError, IndexError):
        return None

def parsear_entero(texto):
    """
    Fix #19: convierte texto a entero positivo.
    Rechaza decimales ("2.5", "2,5"), negativos y texto libre.
    Acepta separadores de miles COP: "1.000" → 1000, "10.000" → 10000.
    """
    import re
    if not texto:
        return None
    texto = texto.strip()
    if re.search(r'[.,]\d{1,2}$', texto):
        return None
    limpio = re.sub(r'[.,](?=\d{3})', '', texto)
    try:
        valor = int(limpio)
        return valor if valor > 0 else None
    except ValueError:
        return None


# ──────────────────────────────────────────────────────────────
# LIMPIEZA DE DUPLICADOS
# ──────────────────────────────────────────────────────────────

def limpiar_duplicados():
    """Elimina filas duplicadas de camisetas (misma categoria+talla), conserva la de menor id."""
    conn = conectar()
    c = conn.cursor()
    c.execute("""
        SELECT categoria_id, talla, MIN(id) as keep_id
        FROM camisetas
        GROUP BY categoria_id, talla
        HAVING COUNT(*) > 1
    """)
    dups = c.fetchall()
    for cat_id, talla, keep_id in dups:
        c.execute(
            "DELETE FROM camisetas WHERE categoria_id = ? AND talla = ? AND id != ?",
            (cat_id, talla, keep_id)
        )
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────────────────────
# RECÁLCULO FINANCIERO (núcleo de consistencia)
# ──────────────────────────────────────────────────────────────

def _recalcular_stock_camiseta(cursor, camiseta_id):
    """
    Recalcula el stock real de una camiseta a partir de sus movimientos.
    COMPRA y AJUSTE MANUAL suman/restan físicamente.
    VENTA descuenta. PAGO no afecta stock.
    También recalcula el costo promedio ponderado.
    """
    cursor.execute("""
        SELECT tipo, cantidad, precio_unitario
        FROM movimientos
        WHERE camiseta_id = ?
        ORDER BY id ASC
    """, (camiseta_id,))
    movimientos = cursor.fetchall()

    stock = 0
    costo_promedio = 0.0

    for tipo, cantidad, precio_unit in movimientos:
        if tipo == 'COMPRA':
            nuevo_stock = stock + cantidad
            if nuevo_stock > 0:
                costo_promedio = ((stock * costo_promedio) + (cantidad * precio_unit)) / nuevo_stock
            stock = nuevo_stock
        elif tipo == 'VENTA':
            stock = max(0, stock - cantidad)
        elif tipo == 'AJUSTE MANUAL':
            stock = max(0, stock + cantidad)
            # costo promedio no cambia en ajuste manual

    cursor.execute(
        "UPDATE camisetas SET stock = ?, precio_compra = ? WHERE id = ?",
        (stock, round(costo_promedio, 2), camiseta_id)
    )
    return stock, round(costo_promedio, 2)


def _recalcular_saldo_venta(cursor, venta_id):
    """
    Recalcula pagado, saldo y estado_pago de una venta
    sumando todos sus movimientos de tipo PAGO.
    """
    cursor.execute("SELECT total FROM ventas WHERE id = ?", (venta_id,))
    row = cursor.fetchone()
    if not row:
        return
    total = row[0]

    cursor.execute(
        "SELECT COALESCE(SUM(total), 0) FROM movimientos WHERE venta_id = ? AND tipo = 'PAGO'",
        (venta_id,)
    )
    pagado = cursor.fetchone()[0]
    saldo  = max(0.0, round(total - pagado, 2))

    if pagado >= total:
        estado_pago = "pagado"
        saldo = 0.0
    elif pagado > 0:
        estado_pago = "parcial"
    else:
        estado_pago = "pendiente"

    cursor.execute(
        "UPDATE ventas SET pagado = ?, saldo = ?, estado_pago = ? WHERE id = ?",
        (round(pagado, 2), saldo, estado_pago, venta_id)
    )


# ──────────────────────────────────────────────────────────────
# CATEGORÍAS
# ──────────────────────────────────────────────────────────────

def crear_categoria(nombre, equipo="", temporada="General"):
    nombre = nombre.strip() if nombre else ""
    if not nombre:
        return False, "El nombre no puede estar vacío"
    if len(nombre) < 2:
        return False, "El nombre debe tener al menos 2 caracteres"
    conn = conectar()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO categorias (nombre) VALUES (?)", (nombre,))
        cat_id = cursor.lastrowid
        tallas = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
        for t in tallas:
            cursor.execute("""
                INSERT INTO camisetas (categoria_id, equipo, temporada, talla, stock, precio_compra, precio_venta)
                VALUES (?, ?, ?, ?, 0, 0, 0)
            """, (cat_id, equipo if equipo else nombre, temporada, t))
        conn.commit()
        return True, f"Categoría '{nombre}' creada con sus 6 tallas"
    except sqlite3.IntegrityError:
        conn.rollback()
        return False, f"Ya existe una categoría llamada '{nombre}'"
    except Exception as e:
        conn.rollback()
        return False, f"Error al crear categoría: {e}"
    finally:
        conn.close()

def obtener_categorias():
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT id, nombre FROM categorias ORDER BY nombre")
    r = c.fetchall()
    conn.close()
    return r

def eliminar_categoria(categoria_id, forzar=False):
    """
    Elimina una categoría y, si forzar=True, elimina también todos sus datos
    asociados (camisetas, movimientos, ventas) y recalcula el estado financiero.
    Si forzar=False, solo elimina si no tiene datos.
    """
    conn = conectar()
    c = conn.cursor()
    try:
        # Obtener nombre para el mensaje
        c.execute("SELECT nombre FROM categorias WHERE id = ?", (categoria_id,))
        row = c.fetchone()
        if not row:
            return False, "Categoría no encontrada"
        nombre_cat = row[0]

        # Verificar si tiene datos
        c.execute("""
            SELECT COUNT(*) FROM movimientos m
            JOIN camisetas cam ON m.camiseta_id = cam.id
            WHERE cam.categoria_id = ?
        """, (categoria_id,))
        tiene_movimientos = c.fetchone()[0] > 0

        c.execute("SELECT COUNT(*) FROM ventas WHERE categoria_id = ?", (categoria_id,))
        tiene_ventas = c.fetchone()[0] > 0

        if (tiene_movimientos or tiene_ventas) and not forzar:
            detalles = []
            if tiene_movimientos:
                detalles.append("movimientos de inventario")
            if tiene_ventas:
                detalles.append("ventas registradas")
            return (
                False,
                f"La categoría tiene {' y '.join(detalles)}. "
                f"Usa la eliminación forzada para borrarla junto con todos sus datos.",
                True  # señal: tiene_datos=True para que la UI muestre opción forzar
            )

        # Eliminación en cascada manual controlada
        # 1. Obtener camisetas de esta categoría
        c.execute("SELECT id FROM camisetas WHERE categoria_id = ?", (categoria_id,))
        camisetas_ids = [r[0] for r in c.fetchall()]

        if camisetas_ids:
            placeholders = ",".join("?" * len(camisetas_ids))
            # 2. Obtener ventas asociadas a estas camisetas
            c.execute(
                f"SELECT id FROM ventas WHERE camiseta_id IN ({placeholders})",
                camisetas_ids
            )
            ventas_ids = [r[0] for r in c.fetchall()]
            # También ventas por categoria_id directamente
            c.execute("SELECT id FROM ventas WHERE categoria_id = ?", (categoria_id,))
            ventas_ids += [r[0] for r in c.fetchall()]
            ventas_ids = list(set(ventas_ids))

            # 3. Eliminar movimientos de estas camisetas/ventas
            c.execute(
                f"DELETE FROM movimientos WHERE camiseta_id IN ({placeholders})",
                camisetas_ids
            )
            if ventas_ids:
                vp = ",".join("?" * len(ventas_ids))
                c.execute(f"DELETE FROM movimientos WHERE venta_id IN ({vp})", ventas_ids)
                c.execute(f"DELETE FROM ventas WHERE id IN ({vp})", ventas_ids)

            # 4. Eliminar camisetas
            c.execute(
                f"DELETE FROM camisetas WHERE categoria_id = ?",
                (categoria_id,)
            )

        # 5. Eliminar ventas restantes por categoria_id
        c.execute("DELETE FROM ventas WHERE categoria_id = ?", (categoria_id,))

        # 6. Eliminar la categoría
        c.execute("DELETE FROM categorias WHERE id = ?", (categoria_id,))

        conn.commit()
        return True, f"Categoría '{nombre_cat}' y todos sus datos eliminados correctamente", False

    except Exception as e:
        conn.rollback()
        return False, f"Error al eliminar: {e}", False
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# COMPRAS
# ──────────────────────────────────────────────────────────────

def obtener_precios_referencia(categoria_id):
    """Retorna (precio_compra_promedio, precio_venta_promedio) de tallas ya configuradas."""
    conn = conectar()
    c = conn.cursor()
    c.execute("""
        SELECT AVG(precio_compra), AVG(precio_venta)
        FROM camisetas
        WHERE categoria_id = ? AND (precio_compra > 0 OR precio_venta > 0)
    """, (categoria_id,))
    r = c.fetchone()
    conn.close()
    if r and r[0]:
        return round(r[0], 2), round(r[1], 2)
    return None, None

def registrar_compra(categoria_id, costo_texto, precio_venta_texto, cantidades_por_talla):
    """
    Fix #9 + #17: los precios llegan como texto y se parsean con parsear_monto()
                   para manejar correctamente los puntos como separadores de miles COP.
    Fix #2: transacción atómica — si falla alguna talla, se revierte todo.
    Fix #8: las cantidades ya vienen validadas como enteros desde la interfaz.
    """
    costo = parsear_monto(str(costo_texto))
    precio_venta = parsear_monto(str(precio_venta_texto))

    if costo is None or costo <= 0:
        return False, "El costo debe ser un número mayor a 0 (ej: 45000)"
    if precio_venta is None or precio_venta <= 0:
        return False, "El precio de venta debe ser un número mayor a 0 (ej: 80000)"
    if precio_venta <= costo:
        return False, f"El precio de venta (${precio_venta:,.0f}) debe ser mayor al costo (${costo:,.0f})"

    cantidades_validas = {t: c for t, c in cantidades_por_talla.items() if isinstance(c, int) and c > 0}
    if not cantidades_validas:
        return False, "Ingrese al menos una talla con cantidad mayor a 0"

    conn = conectar()
    c = conn.cursor()
    try:
        for talla, cantidad in cantidades_validas.items():
            c.execute(
                "SELECT id, stock, precio_compra FROM camisetas WHERE categoria_id = ? AND talla = ?",
                (categoria_id, talla)
            )
            exist = c.fetchone()
            if exist:
                pid, stock_act, costo_act = exist
                new_stock = stock_act + cantidad
                new_costo = ((stock_act * costo_act) + (cantidad * costo)) / new_stock
                c.execute(
                    "UPDATE camisetas SET stock = ?, precio_compra = ?, precio_venta = ? WHERE id = ?",
                    (new_stock, round(new_costo, 2), precio_venta, pid)
                )
            else:
                c.execute("""
                    INSERT INTO camisetas (categoria_id, talla, stock, precio_compra, precio_venta)
                    VALUES (?, ?, ?, ?, ?)
                """, (categoria_id, talla, cantidad, costo, precio_venta))
                pid = c.lastrowid

            total_mov = cantidad * costo
            c.execute("""
                INSERT INTO movimientos (camiseta_id, tipo, cantidad, precio_unitario, total)
                VALUES (?, 'COMPRA', ?, ?, ?)
            """, (pid, cantidad, costo, total_mov))

        conn.commit()
        total_uds = sum(cantidades_validas.values())
        total_inv  = total_uds * costo
        return True, f"✅ Compra registrada: {total_uds} uds por ${total_inv:,.0f}"
    except Exception as e:
        conn.rollback()
        return False, f"Error al registrar compra: {e}"
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# VENTAS
# ──────────────────────────────────────────────────────────────

def obtener_stock_y_precio(categoria_id, talla):
    conn = conectar()
    c = conn.cursor()
    c.execute(
        "SELECT stock, precio_venta FROM camisetas WHERE categoria_id = ? AND talla = ?",
        (categoria_id, talla)
    )
    r = c.fetchone()
    conn.close()
    return r if r else (0, 0)

def registrar_venta(categoria_id, talla, cantidad, cliente, monto_pagado_texto):
    """
    Fix #18: validación de cliente más robusta.
    Fix #17: monto_pagado llega como texto y se parsea con parsear_monto().
    Fix #2:  transacción atómica.
    Fix #7:  movimiento PAGO registrado con cantidad=1 y precio=monto.
    """
    cliente = cliente.strip() if cliente else ""
    if not cliente:
        return False, "El nombre del cliente es obligatorio", None
    if len(cliente) < 2:
        return False, "El nombre del cliente debe tener al menos 2 caracteres", None

    if not isinstance(cantidad, int) or cantidad <= 0:
        return False, "La cantidad debe ser un número entero mayor a 0", None

    conn = conectar()
    c = conn.cursor()
    try:
        c.execute("BEGIN IMMEDIATE")
        c.execute(
            "SELECT id, stock, precio_venta, precio_compra FROM camisetas WHERE categoria_id = ? AND talla = ?",
            (categoria_id, talla)
        )
        datos = c.fetchone()
        if not datos:
            conn.rollback()
            return False, "Producto no encontrado en inventario", None
        pid, stock_act, precio, costo_unitario = datos

        if precio <= 0:
            conn.rollback()
            return False, "Este producto no tiene precio de venta configurado. Registra una compra primero.", None
        if stock_act < cantidad:
            conn.rollback()
            return False, f"Stock insuficiente. Disponible: {stock_act} ud{'s' if stock_act != 1 else ''}", None

        total = round(cantidad * precio, 2)
        costo_total = round(cantidad * costo_unitario, 2)

        if monto_pagado_texto is None or str(monto_pagado_texto).strip() == "":
            monto_pagado = total
        else:
            monto_pagado = parsear_monto(str(monto_pagado_texto))
            if monto_pagado is None:
                conn.rollback()
                return False, "El monto pagado no es un número válido", None
            if monto_pagado > total:
                conn.rollback()
                return False, f"El monto pagado no puede superar el total de la venta (${total:,.0f})", None

        monto_pagado = max(0.0, monto_pagado)
        saldo = round(total - monto_pagado, 2)

        if monto_pagado >= total:
            estado_pago = "pagado"
        elif monto_pagado > 0:
            estado_pago = "parcial"
        else:
            estado_pago = "pendiente"

        c.execute("""
            INSERT INTO ventas
                (cliente, camiseta_id, categoria_id, talla, cantidad, precio_unitario,
                 total, pagado, saldo, costo_unitario, costo_total, estado_pago)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cliente, pid, categoria_id, talla, cantidad, precio, total, monto_pagado,
            saldo, costo_unitario, costo_total, estado_pago
        ))
        venta_id = c.lastrowid

        c.execute(
            "UPDATE camisetas SET stock = stock - ? WHERE id = ? AND stock >= ?",
            (cantidad, pid, cantidad)
        )
        if c.rowcount != 1:
            conn.rollback()
            return False, "Stock insuficiente. Otro movimiento modificó el inventario.", None

        c.execute("""
            INSERT INTO movimientos (camiseta_id, tipo, cantidad, precio_unitario, total, venta_id)
            VALUES (?, 'VENTA', ?, ?, ?, ?)
        """, (pid, cantidad, precio, total, venta_id))

        if monto_pagado > 0:
            c.execute("""
                INSERT INTO movimientos (camiseta_id, tipo, cantidad, precio_unitario, total, venta_id)
                VALUES (?, 'PAGO', 1, ?, ?, ?)
            """, (pid, monto_pagado, monto_pagado, venta_id))

        # La venta queda sincronizada con sus movimientos para evitar desvíos
        # entre el estado guardado y el historial real de pagos.
        _recalcular_saldo_venta(c, venta_id)
        c.execute("SELECT pagado, saldo, estado_pago FROM ventas WHERE id = ?", (venta_id,))
        pagado_guardado, saldo_guardado, estado_guardado = c.fetchone()

        conn.commit()

        saldo_txt = f"Saldo pendiente: ${saldo_guardado:,.0f}" if saldo_guardado > 0 else "✅ Pagado completo"
        return (
            True,
            f"Venta registrada. Total: ${total:,.0f} | Pagado: ${pagado_guardado:,.0f} | {saldo_txt}",
            venta_id
        )
    except Exception as e:
        conn.rollback()
        return False, f"Error al registrar venta: {e}", None
    finally:
        conn.close()

def registrar_pago(venta_id, monto_texto):
    """
    Registra un abono a una venta pendiente o parcial.
    Actualiza pagado, saldo y estado_pago.
    Fix #20: muestra el saldo pendiente al usuario antes de abonar.
    Fix #17: monto llega como texto y se parsea correctamente.
    Fix #2:  transacción atómica.
    """
    monto = parsear_monto(str(monto_texto))
    if monto is None or monto <= 0:
        return False, "El monto debe ser un número positivo (ej: 50000)"

    conn = conectar()
    c = conn.cursor()
    try:
        c.execute(
            "SELECT id, total, pagado, saldo, categoria_id, talla, camiseta_id FROM ventas WHERE id = ?",
            (venta_id,)
        )
        venta = c.fetchone()
        if not venta:
            return False, "Venta no encontrada"

        _, total, pagado_actual, saldo_actual, cat_id, talla, camiseta_id = venta

        if saldo_actual <= 0:
            return False, "Esta venta ya está completamente pagada"

        if monto > saldo_actual:
            return False, f"El abono no puede superar el saldo pendiente (${saldo_actual:,.0f})"

        nuevo_pagado = round(pagado_actual + monto, 2)
        nuevo_saldo  = round(total - nuevo_pagado, 2)

        if nuevo_pagado >= total:
            nuevo_estado = "pagado"
            nuevo_saldo  = 0.0
        else:
            nuevo_estado = "parcial"

        c.execute(
            "UPDATE ventas SET pagado = ?, saldo = ?, estado_pago = ? WHERE id = ?",
            (nuevo_pagado, nuevo_saldo, nuevo_estado, venta_id)
        )

        # Registrar movimiento de pago ligado a la venta
        pid = camiseta_id
        if not pid:
            c.execute(
                "SELECT id FROM camisetas WHERE categoria_id = ? AND talla = ?",
                (cat_id, talla)
            )
            cam = c.fetchone()
            pid = cam[0] if cam else None

        if pid:
            c.execute("""
                INSERT INTO movimientos (camiseta_id, tipo, cantidad, precio_unitario, total, venta_id)
                VALUES (?, 'PAGO', 1, ?, ?, ?)
            """, (pid, monto, monto, venta_id))

        # Recalcula la venta a partir de sus movimientos para que pagado/saldo
        # siempre coincidan con el historial real de abonos.
        _recalcular_saldo_venta(c, venta_id)
        c.execute("SELECT pagado, saldo, estado_pago FROM ventas WHERE id = ?", (venta_id,))
        pagado_guardado, saldo_guardado, estado_guardado = c.fetchone()

        conn.commit()

        if estado_guardado == "pagado":
            return True, f"✅ Abono de ${monto:,.0f} registrado. Venta completamente pagada."
        else:
            return True, f"✅ Abono de ${monto:,.0f} registrado. Saldo restante: ${saldo_guardado:,.0f}"
    except Exception as e:
        conn.rollback()
        return False, f"Error al registrar abono: {e}"
    finally:
        conn.close()

def obtener_saldo_venta(venta_id):
    """Fix #20: permite que la interfaz muestre el saldo pendiente antes de pedir el monto."""
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT total, pagado, saldo, estado_pago FROM ventas WHERE id = ?", (venta_id,))
    r = c.fetchone()
    conn.close()
    return r

def obtener_historial_abonos(venta_id):
    """
    Retorna el historial completo de pagos de una venta específica.
    Devuelve: [(fecha_formato, monto), ...]
    """
    conn = conectar()
    c = conn.cursor()
    c.execute("""
        SELECT strftime('%d/%m/%Y %H:%M', fecha) as fecha_fmt,
               total as monto
        FROM movimientos
        WHERE venta_id = ? AND tipo = 'PAGO'
        ORDER BY fecha ASC
    """, (venta_id,))
    r = c.fetchall()
    conn.close()
    return r

def cambiar_estado_envio(venta_id, nuevo_estado):
    if nuevo_estado not in ('enviado', 'no_enviado'):
        return False, "Estado de envío inválido"
    conn = conectar()
    c = conn.cursor()
    try:
        c.execute("UPDATE ventas SET estado_envio = ? WHERE id = ?", (nuevo_estado, venta_id))
        conn.commit()
        return True, "Estado de envío actualizado"
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()

def eliminar_venta(venta_id):
    """
    Elimina una venta y todos sus movimientos asociados.
    Luego recalcula stock e indicadores financieros de la camiseta afectada.
    Deja el sistema como si la venta nunca hubiera existido.
    """
    conn = conectar()
    c = conn.cursor()
    try:
        # Obtener datos de la venta antes de borrar
        c.execute("SELECT camiseta_id, cantidad, total, pagado FROM ventas WHERE id = ?", (venta_id,))
        row = c.fetchone()
        if not row:
            return False, "Venta no encontrada"
        camiseta_id, cantidad, total, pagado = row

        # Eliminar todos los movimientos de esta venta (VENTA + PAGOs)
        c.execute("DELETE FROM movimientos WHERE venta_id = ?", (venta_id,))

        # Eliminar la venta
        c.execute("DELETE FROM ventas WHERE id = ?", (venta_id,))

        # Recalcular stock desde cero para la camiseta afectada
        if camiseta_id:
            _recalcular_stock_camiseta(c, camiseta_id)

        conn.commit()
        return True, f"✅ Venta #{venta_id} eliminada. Stock recalculado automáticamente."
    except Exception as e:
        conn.rollback()
        return False, f"Error al eliminar venta: {e}"
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# INVENTARIO (AJUSTE MANUAL)
# ──────────────────────────────────────────────────────────────

def obtener_inventario():
    conn = conectar()
    c = conn.cursor()
    c.execute("""
        SELECT c.id, cat.nombre, c.talla, c.stock, c.precio_compra, c.precio_venta,
               ROUND(c.stock * c.precio_compra, 0) as valor
        FROM camisetas c
        JOIN categorias cat ON c.categoria_id = cat.id
        WHERE c.stock > 0 OR c.precio_compra > 0
        ORDER BY cat.nombre, 
                 CASE c.talla
                     WHEN 'XS' THEN 1 WHEN 'S' THEN 2 WHEN 'M' THEN 3
                     WHEN 'L'  THEN 4 WHEN 'XL' THEN 5 WHEN 'XXL' THEN 6
                 END
    """)
    r = c.fetchall()
    conn.close()
    return r

def obtener_producto_por_id(producto_id):
    conn = conectar()
    c = conn.cursor()
    c.execute("""
        SELECT c.id, cat.nombre, c.talla, c.stock, c.precio_compra, c.precio_venta
        FROM camisetas c
        JOIN categorias cat ON c.categoria_id = cat.id
        WHERE c.id = ?
    """, (producto_id,))
    r = c.fetchone()
    conn.close()
    return r

def agregar_stock_con_precio(producto_id, cantidad_ajuste, nuevo_costo_unitario_texto=None):
    """
    Fix #10 + #2: transacción atómica para que stock y movimiento siempre sean consistentes.
    Fix #17: costo llega como texto y se parsea con parsear_monto().
    """
    if not isinstance(cantidad_ajuste, int) or cantidad_ajuste == 0:
        return False, "La cantidad no puede ser 0"
    if cantidad_ajuste > 0:
        return False, "Para aumentar inventario registre una compra desde el módulo Compras"

    nuevo_costo = None
    if nuevo_costo_unitario_texto and str(nuevo_costo_unitario_texto).strip():
        nuevo_costo = parsear_monto(str(nuevo_costo_unitario_texto))
        if nuevo_costo is None or nuevo_costo <= 0:
            return False, "El costo debe ser un número mayor a 0"

    conn = conectar()
    c = conn.cursor()
    try:
        c.execute("SELECT id, stock, precio_compra FROM camisetas WHERE id = ?", (producto_id,))
        datos = c.fetchone()
        if not datos:
            return False, "Producto no encontrado"
        pid, stock_act, costo_act = datos

        new_stock = stock_act + cantidad_ajuste
        if new_stock < 0:
            return False, f"No se puede reducir: stock actual es {stock_act} ud{'s' if stock_act != 1 else ''}"

        tipo_mov  = "AJUSTE MANUAL"
        costo_mov = costo_act
        new_costo_prom = costo_act
        total_mov = round(abs(cantidad_ajuste) * costo_act, 2)

        c.execute(
            "UPDATE camisetas SET stock = ?, precio_compra = ? WHERE id = ?",
            (new_stock, new_costo_prom, pid)
        )
        c.execute("""
            INSERT INTO movimientos (camiseta_id, tipo, cantidad, precio_unitario, total)
            VALUES (?, ?, ?, ?, ?)
        """, (pid, tipo_mov, cantidad_ajuste, costo_mov, total_mov))

        conn.commit()
        signo = "+" if cantidad_ajuste > 0 else ""
        return True, f"✅ Ajuste aplicado: {signo}{cantidad_ajuste} uds → Stock actual: {new_stock}"
    except Exception as e:
        conn.rollback()
        return False, f"Error al ajustar stock: {e}"
    finally:
        conn.close()

def eliminar_producto(producto_id, forzar=False):
    """
    Elimina un producto (camiseta) del inventario.
    Si forzar=False y tiene movimientos/ventas, informa al usuario.
    Si forzar=True, elimina en cascada y recalcula la categoría.
    """
    conn = conectar()
    c = conn.cursor()
    try:
        c.execute("""
            SELECT cam.id, cat.nombre, cam.talla
            FROM camisetas cam
            JOIN categorias cat ON cam.categoria_id = cat.id
            WHERE cam.id = ?
        """, (producto_id,))
        row = c.fetchone()
        if not row:
            return False, "Producto no encontrado"
        _, cat_nombre, talla = row

        c.execute("SELECT COUNT(*) FROM movimientos WHERE camiseta_id = ?", (producto_id,))
        tiene_movimientos = c.fetchone()[0] > 0

        c.execute("SELECT COUNT(*) FROM ventas WHERE camiseta_id = ?", (producto_id,))
        tiene_ventas = c.fetchone()[0] > 0

        if (tiene_movimientos or tiene_ventas) and not forzar:
            detalles = []
            if tiene_movimientos:
                detalles.append("movimientos")
            if tiene_ventas:
                detalles.append("ventas")
            return (
                False,
                f"El producto tiene {' y '.join(detalles)} asociados. "
                f"Usa la eliminación forzada para borrarlo con todos sus datos.",
                True  # tiene_datos=True
            )

        # Obtener ventas ligadas a este producto
        c.execute("SELECT id FROM ventas WHERE camiseta_id = ?", (producto_id,))
        ventas_ids = [r[0] for r in c.fetchall()]

        # Eliminar movimientos
        c.execute("DELETE FROM movimientos WHERE camiseta_id = ?", (producto_id,))
        if ventas_ids:
            vp = ",".join("?" * len(ventas_ids))
            c.execute(f"DELETE FROM movimientos WHERE venta_id IN ({vp})", ventas_ids)
            c.execute(f"DELETE FROM ventas WHERE id IN ({vp})", ventas_ids)

        # Eliminar el producto
        c.execute("DELETE FROM camisetas WHERE id = ?", (producto_id,))

        conn.commit()
        return True, f"✅ Producto {cat_nombre} – {talla} eliminado correctamente.", False

    except Exception as e:
        conn.rollback()
        return False, f"Error al eliminar: {e}", False
    finally:
        conn.close()

def eliminar_movimiento(movimiento_id):
    """
    Elimina un movimiento específico (COMPRA o AJUSTE MANUAL) y recalcula
    el stock de la camiseta afectada desde cero para mantener consistencia.
    No permite eliminar movimientos de tipo VENTA o PAGO directamente
    (deben eliminarse vía eliminar_venta).
    """
    conn = conectar()
    c = conn.cursor()
    try:
        c.execute("SELECT camiseta_id, tipo, venta_id FROM movimientos WHERE id = ?", (movimiento_id,))
        row = c.fetchone()
        if not row:
            return False, "Movimiento no encontrado"
        camiseta_id, tipo, venta_id = row

        if tipo in ('VENTA', 'PAGO'):
            return False, "Los movimientos de VENTA y PAGO se eliminan desde el historial de ventas."

        # Eliminar el movimiento
        c.execute("DELETE FROM movimientos WHERE id = ?", (movimiento_id,))

        # Recalcular stock de la camiseta desde cero
        if camiseta_id:
            _recalcular_stock_camiseta(c, camiseta_id)

        conn.commit()
        return True, f"✅ Movimiento eliminado. Stock recalculado automáticamente."
    except Exception as e:
        conn.rollback()
        return False, f"Error al eliminar movimiento: {e}"
    finally:
        conn.close()

def actualizar_precio_venta(producto_id, nuevo_precio_texto):
    """Permite actualizar solo el precio de venta de un producto desde inventario."""
    nuevo_precio = parsear_monto(str(nuevo_precio_texto))
    if nuevo_precio is None or nuevo_precio <= 0:
        return False, "El precio debe ser un número mayor a 0"
    conn = conectar()
    c = conn.cursor()
    try:
        c.execute("SELECT precio_compra FROM camisetas WHERE id = ?", (producto_id,))
        row = c.fetchone()
        if not row:
            return False, "Producto no encontrado"
        if nuevo_precio <= row[0]:
            return False, f"El precio de venta debe ser mayor al costo (${row[0]:,.0f})"
        c.execute("UPDATE camisetas SET precio_venta = ? WHERE id = ?", (nuevo_precio, producto_id))
        conn.commit()
        return True, f"✅ Precio de venta actualizado a ${nuevo_precio:,.0f}"
    except Exception as e:
        conn.rollback()
        return False, f"Error: {e}"
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────
# DASHBOARD Y FINANZAS
# ──────────────────────────────────────────────────────────────

def obtener_totales_financieros():
    """
    Fix #5 + #6: separación clara de métricas financieras.

    - ventas_facturadas: valor total de todas las ventas registradas (lo que se debería cobrar)
    - cobrado_total:     suma de todos los PAGOs recibidos (efectivo real en caja)
    - por_cobrar:        saldo total pendiente en ventas no completamente pagadas
    - egresos_compras:   suma de todas las COMPRAs (lo que se pagó por el inventario)
    - resultado_real:    cobrado_total − egresos_compras (flujo real del negocio)
    - resultado_potencial: ventas_facturadas − egresos_compras (si todo se cobrara)
    - utilidad_bruta:    ventas_facturadas − costo_de_lo_vendido (margen de ventas)
    """
    conn = conectar()
    c = conn.cursor()

    c.execute("SELECT COALESCE(SUM(total), 0) FROM movimientos WHERE tipo = 'PAGO'")
    cobrado_total = c.fetchone()[0]

    c.execute("SELECT COALESCE(SUM(total), 0) FROM ventas")
    ventas_facturadas = c.fetchone()[0]

    c.execute("SELECT COALESCE(SUM(saldo), 0) FROM ventas WHERE estado_pago != 'pagado'")
    por_cobrar = c.fetchone()[0]

    c.execute("SELECT COALESCE(SUM(total), 0) FROM movimientos WHERE tipo = 'COMPRA'")
    egresos_compras = c.fetchone()[0]

    c.execute("SELECT COALESCE(SUM(costo_total), 0) FROM ventas")
    costo_vendido = c.fetchone()[0]

    conn.close()

    ganancia_real      = round(cobrado_total - egresos_compras, 2)
    ganancia_potencial = round(ventas_facturadas - egresos_compras, 2)
    utilidad_bruta     = round(ventas_facturadas - costo_vendido, 2)

    return {
        'cobrado_total':      cobrado_total,
        'ventas_facturadas':  ventas_facturadas,
        'por_cobrar':         por_cobrar,
        'egresos_compras':    egresos_compras,
        'costo_vendido':      costo_vendido,
        'ganancia_real':      ganancia_real,
        'ganancia_potencial': ganancia_potencial,
        'utilidad_bruta':     utilidad_bruta,
    }

def obtener_resumen():
    """
    Fix #5: el dashboard ahora diferencia claramente entre:
      - Lo cobrado (caja real)
      - Lo facturado (ventas totales incluyendo deudas)
      - Ganancia real vs potencial
    """
    conn = conectar()
    c = conn.cursor()

    c.execute("SELECT COALESCE(SUM(stock * precio_compra), 0) FROM camisetas")
    capital_inventario = c.fetchone()[0]

    c.execute("SELECT COALESCE(SUM(stock), 0) FROM camisetas")
    unidades_stock = c.fetchone()[0]

    fin = obtener_totales_financieros()

    c.execute("SELECT COUNT(*) FROM ventas WHERE DATE(fecha) = DATE('now')")
    ventas_hoy_cantidad = c.fetchone()[0]

    c.execute("""
        SELECT COALESCE(SUM(total), 0) FROM movimientos
        WHERE tipo = 'PAGO' AND DATE(fecha) = DATE('now')
    """)
    cobrado_hoy = c.fetchone()[0]

    c.execute("""
        SELECT cat.nombre, cam.talla, cam.stock
        FROM camisetas cam
        JOIN categorias cat ON cam.categoria_id = cat.id
        WHERE cam.stock > 0 AND cam.stock < 5
        ORDER BY cam.stock ASC
    """)
    bajo_stock = c.fetchall()

    conn.close()

    return {
        'capital_inventario':  capital_inventario,
        'unidades_stock':      unidades_stock,
        'cobrado_total':       fin['cobrado_total'],
        'ventas_facturadas':   fin['ventas_facturadas'],
        'por_cobrar':          fin['por_cobrar'],
        'egresos_compras':     fin['egresos_compras'],
        'ganancia_real':       fin['ganancia_real'],
        'ganancia_potencial':  fin['ganancia_potencial'],
        'utilidad_bruta':      fin['utilidad_bruta'],
        'ventas_hoy_cantidad': ventas_hoy_cantidad,
        'cobrado_hoy':         cobrado_hoy,
        'bajo_stock':          bajo_stock,
    }


# ──────────────────────────────────────────────────────────────
# HISTORIAL
# ──────────────────────────────────────────────────────────────

def obtener_historial_ventas():
    conn = conectar()
    c = conn.cursor()
    c.execute("""
        SELECT v.id,
               strftime('%d/%m/%Y', v.fecha) as fecha,
               v.cliente,
               cat.nombre as producto,
               v.talla,
               v.cantidad,
               v.precio_unitario,
               v.total,
               v.pagado,
               v.saldo,
               v.costo_total,
               (v.total - v.costo_total) as utilidad,
               v.estado_pago,
               v.estado_envio
        FROM ventas v
        JOIN categorias cat ON v.categoria_id = cat.id
        ORDER BY v.fecha DESC
    """)
    r = c.fetchall()
    conn.close()
    return r

def obtener_historial_compras():
    conn = conectar()
    c = conn.cursor()
    c.execute("""
        SELECT m.id,
               strftime('%d/%m/%Y', m.fecha) as fecha,
               cat.nombre,
               cam.talla,
               m.cantidad,
               m.precio_unitario,
               m.total
        FROM movimientos m
        JOIN camisetas cam ON m.camiseta_id = cam.id
        JOIN categorias cat ON cam.categoria_id = cat.id
        WHERE m.tipo = 'COMPRA'
        ORDER BY m.fecha DESC
    """)
    r = c.fetchall()
    conn.close()
    return r

def obtener_historial_ventas_fecha(desde=None, hasta=None):
    conn = conectar()
    c = conn.cursor()
    query = """
        SELECT strftime('%d/%m/%Y', v.fecha) as fecha,
               v.cliente,
               cat.nombre,
               v.talla,
               v.cantidad,
               v.precio_unitario,
               v.total,
               v.pagado,
               v.saldo,
               v.costo_total,
               (v.total - v.costo_total) as utilidad,
               v.estado_pago,
               v.estado_envio,
               v.id
        FROM ventas v
        JOIN categorias cat ON v.categoria_id = cat.id
        WHERE 1=1
    """
    params = []
    if desde:
        query += " AND DATE(v.fecha) >= ?"
        params.append(desde)
    if hasta:
        query += " AND DATE(v.fecha) <= ?"
        params.append(hasta)
    query += " ORDER BY v.fecha DESC"
    c.execute(query, params)
    r = c.fetchall()
    conn.close()
    return r

def obtener_historial_compras_fecha(desde=None, hasta=None):
    conn = conectar()
    c = conn.cursor()
    query = """
        SELECT strftime('%d/%m/%Y', m.fecha) as fecha,
               cat.nombre,
               cam.talla,
               m.cantidad,
               m.precio_unitario,
               m.total
        FROM movimientos m
        JOIN camisetas cam ON m.camiseta_id = cam.id
        JOIN categorias cat ON cam.categoria_id = cat.id
        WHERE m.tipo = 'COMPRA'
    """
    params = []
    if desde:
        query += " AND DATE(m.fecha) >= ?"
        params.append(desde)
    if hasta:
        query += " AND DATE(m.fecha) <= ?"
        params.append(hasta)
    query += " ORDER BY m.fecha DESC"
    c.execute(query, params)
    r = c.fetchall()
    conn.close()
    return r


# ──────────────────────────────────────────────────────────────
# EXPORTAR A EXCEL
# ──────────────────────────────────────────────────────────────

def exportar_a_excel(tipo, desde, hasta, archivo_salida):
    """
    Fix #11: columnas explícitas y orden fijo — no depende del orden del SELECT.
    Los montos se formatean en COP con puntos como separador de miles.
    """
    def fmt_cop(x):
        if pd.isnull(x):
            return ""
        return f"${int(x):,}".replace(",", ".")

    if tipo == 'ventas':
        datos = obtener_historial_ventas_fecha(desde, hasta)
        if not datos:
            return False, "No hay datos de ventas en el rango seleccionado"
        columnas = ['Fecha', 'Cliente', 'Producto', 'Talla', 'Cantidad',
                    'Precio Unitario', 'Total', 'Pagado', 'Saldo',
                    'Costo', 'Utilidad', 'Estado Pago', 'Estado Envío', 'ID Venta']
        df = pd.DataFrame(datos, columns=columnas)
        for col in ['Precio Unitario', 'Total', 'Pagado', 'Saldo', 'Costo', 'Utilidad']:
            df[col] = df[col].apply(fmt_cop)
        df['Estado Pago']  = df['Estado Pago'].map({'pagado': 'Pagado', 'parcial': 'Parcial', 'pendiente': 'Pendiente'})
        df['Estado Envío'] = df['Estado Envío'].map({'enviado': 'Enviado', 'no_enviado': 'No enviado'})
    else:
        datos = obtener_historial_compras_fecha(desde, hasta)
        if not datos:
            return False, "No hay datos de compras en el rango seleccionado"
        columnas = ['Fecha', 'Producto', 'Talla', 'Cantidad', 'Costo Unitario', 'Total']
        df = pd.DataFrame(datos, columns=columnas)
        for col in ['Costo Unitario', 'Total']:
            df[col] = df[col].apply(fmt_cop)

    try:
        df.to_excel(archivo_salida, index=False, engine='openpyxl')
        return True, f"✅ Exportado correctamente a {archivo_salida}"
    except Exception as e:
        return False, f"Error al exportar: {e}"


# ──────────────────────────────────────────────────────────────
# DISTRIBUCIÓN INVENTARIO (para dashboard)
# ──────────────────────────────────────────────────────────────

def obtener_distribucion_inventario():
    conn = conectar()
    c = conn.cursor()
    c.execute("""
        SELECT cat.nombre, COALESCE(SUM(cam.stock), 0) as total_stock
        FROM categorias cat
        LEFT JOIN camisetas cam ON cat.id = cam.categoria_id
        GROUP BY cat.id, cat.nombre
        ORDER BY total_stock DESC
    """)
    r = c.fetchall()
    conn.close()
    return r
