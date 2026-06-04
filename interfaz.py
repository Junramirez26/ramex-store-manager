import customtkinter as ctk
import funciones as fn
from tkinter import filedialog, messagebox
from tkcalendar import Calendar
from datetime import date

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

# ─────────────────────────────────────────────────────────────
# UTILIDAD: parsear cantidad desde entry en la interfaz
# ─────────────────────────────────────────────────────────────
def _parsear_cant_entry(texto):
    """Wrapper de fn.parsear_entero para usar en la UI."""
    return fn.parsear_entero(texto)

def _parsear_monto_entry(texto):
    """Wrapper de fn.parsear_monto para usar en la UI."""
    return fn.parsear_monto(texto)


class AppCamisetas(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Gestión de Ventas — Camisetas Deportivas")
        self.geometry("1300x780")
        self.minsize(1100, 680)
        self.configure(fg_color="#F8FAFC")

        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=40, pady=(15, 5))
        ctk.CTkLabel(
            self.header_frame, text="Sistema de Gestión de Ventas",
            font=("Helvetica", 24, "bold"), text_color="#0F172A"
        ).pack(anchor="w")
        ctk.CTkLabel(
            self.header_frame, text="Camisetas Deportivas",
            font=("Helvetica", 13), text_color="#64748B"
        ).pack(anchor="w")

        self.menu_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.menu_frame.pack(fill="x", padx=40, pady=(15, 5))
        self.pestanas = ["Dashboard", "Ventas", "Compras", "Historial", "Inventario", "Categorías"]
        self.botones_menu = {}
        self.pestana_activa = "Dashboard"
        for p in self.pestanas:
            btn = ctk.CTkButton(
                self.menu_frame, text=p,
                font=("Helvetica", 13, "bold" if p == "Dashboard" else "normal"),
                text_color="#1E3A8A" if p == "Dashboard" else "#64748B",
                fg_color="transparent", hover_color="#E2E8F0",
                width=100, height=35,
                command=lambda q=p: self.cambiar_pestana(q)
            )
            btn.pack(side="left", padx=5)
            self.botones_menu[p] = btn

        ctk.CTkFrame(self, height=2, fg_color="#E2E8F0").pack(fill="x", padx=40, pady=(0, 15))
        self.contenedor_principal = ctk.CTkFrame(self, fg_color="transparent")
        self.contenedor_principal.pack(fill="both", expand=True, padx=40, pady=(0, 15))

        # Inicializar atributos de historial para que existan aunque la pestaña
        # no se haya abierto aún (evita AttributeError en callbacks con after()).
        self.historial_tab = "VENTAS"
        self.historial_container = None

        self.cargar_pestana("Dashboard")

    # ─────────────────────────────────────────────────────────
    # NAVEGACIÓN
    # ─────────────────────────────────────────────────────────
    def cambiar_pestana(self, nombre):
        self.botones_menu[self.pestana_activa].configure(
            font=("Helvetica", 13, "normal"), text_color="#64748B"
        )
        self.pestana_activa = nombre
        self.botones_menu[nombre].configure(
            font=("Helvetica", 13, "bold"), text_color="#1E3A8A"
        )
        for w in self.contenedor_principal.winfo_children():
            w.destroy()
        self.cargar_pestana(nombre)

    def cargar_pestana(self, nombre):
        metodos = {
            "Dashboard":  self.mostrar_dashboard,
            "Ventas":     self.mostrar_ventas,
            "Compras":    self.mostrar_compras,
            "Historial":  self.mostrar_historial,
            "Inventario": self.mostrar_inventario,
            "Categorías": self.mostrar_categorias,
        }
        metodos.get(nombre, lambda: None)()

    # ─────────────────────────────────────────────────────────
    # DASHBOARD
    # ─────────────────────────────────────────────────────────
    def mostrar_dashboard(self):
        scroll = ctk.CTkScrollableFrame(self.contenedor_principal, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        r = fn.obtener_resumen()

        ctk.CTkLabel(
            scroll, text="Resumen de Indicadores Clave",
            font=("Helvetica", 20, "bold"), text_color="#0F172A"
        ).pack(anchor="w", pady=(0, 15))

        cards = ctk.CTkFrame(scroll, fg_color="transparent")
        cards.pack(fill="x", pady=(0, 12))
        for i in range(3):
            cards.columnconfigure(i, weight=1)

        self._crear_tarjeta(cards, 0, "💰 Ingresos cobrados",
            self._fmt(r['cobrado_total']), "#22C55E", "#14532D")
        self._crear_tarjeta(cards, 1, "📦 Egresos por compras",
            self._fmt(r['egresos_compras']), "#F87171", "#7F1D1D")
        gan = r['ganancia_real']
        color_gan = "#22C55E" if gan >= 0 else "#F87171"
        self._crear_tarjeta(cards, 2, "📈 Resultado real",
            (self._fmt(gan) if gan >= 0 else f"-{self._fmt(abs(gan))}"),
            color_gan, "#1E3A8A")

        metrics = ctk.CTkFrame(scroll, fg_color="transparent")
        metrics.pack(fill="x", pady=(0, 12))
        for i in range(5):
            metrics.columnconfigure(i, weight=1)

        self._crear_metrica(metrics, 0, "📋 Total facturado",
                            self._fmt(r['ventas_facturadas']), "#3B82F6")
        self._crear_metrica(metrics, 1, "⏳ Por cobrar",
                            self._fmt(r['por_cobrar']),
                            "#EF4444" if r['por_cobrar'] > 0 else "#22C55E")
        self._crear_metrica(metrics, 2, "🏷️ Valor inventario",
                            self._fmt(r['capital_inventario']), "#8B5CF6")
        self._crear_metrica(metrics, 3, "📦 Unidades en stock",
                            f"{r['unidades_stock']} uds", "#EC4899")

        margen = r.get('utilidad_bruta', 0)
        self._crear_metrica(metrics, 4, "📊 Utilidad bruta",
                            (self._fmt(margen) if margen >= 0 else f"-{self._fmt(abs(margen))}"),
                            "#22C55E" if margen >= 0 else "#EF4444")

        hoy = ctk.CTkFrame(scroll, fg_color="transparent")
        hoy.pack(fill="x", pady=(0, 12))
        for i in range(2):
            hoy.columnconfigure(i, weight=1)
        self._crear_metrica(hoy, 0, "🛒 Ventas hoy",
                            f"{r['ventas_hoy_cantidad']} pedido{'s' if r['ventas_hoy_cantidad'] != 1 else ''}",
                            "#0EA5E9")
        self._crear_metrica(hoy, 1, "💵 Cobrado hoy",
                            self._fmt(r['cobrado_hoy']), "#0EA5E9")

        self._mostrar_distribucion(scroll)

        if r['bajo_stock']:
            alert = ctk.CTkFrame(scroll, fg_color="#FEF2F2", corner_radius=10,
                                 border_color="#FCA5A5", border_width=1)
            alert.pack(fill="x", pady=(0, 10))
            ctk.CTkLabel(alert, text="⚠️  Productos con bajo stock (< 5 uds)",
                         font=("Helvetica", 12, "bold"), text_color="#991B1B").pack(anchor="w", padx=15, pady=(10, 4))
            for prod, talla, stock in r['bajo_stock'][:8]:
                ctk.CTkLabel(
                    alert,
                    text=f"  • {prod} — Talla {talla}: {stock} ud{'s' if stock != 1 else ''}",
                    font=("Helvetica", 11), text_color="#7F1D1D"
                ).pack(anchor="w", padx=15)
            ctk.CTkLabel(alert, text="").pack(pady=4)

    def _fmt(self, valor):
        """Formatea un número como pesos colombianos: $45.000"""
        return f"${int(valor):,}".replace(",", ".")

    def _crear_tarjeta(self, parent, col, titulo, valor, color_txt, color_fondo):
        card = ctk.CTkFrame(parent, fg_color=color_fondo, corner_radius=12)
        card.grid(row=0, column=col, padx=8, sticky="nsew")
        card.configure(height=100)
        card.grid_propagate(False)
        ctk.CTkLabel(card, text=titulo, font=("Helvetica", 11),
                     text_color="#E2E8F0").pack(anchor="w", padx=15, pady=(15, 5))
        ctk.CTkLabel(card, text=valor, font=("Helvetica", 22, "bold"),
                     text_color=color_txt).pack(anchor="w", padx=15, pady=(0, 15))

    def _crear_metrica(self, parent, col, titulo, valor, color):
        card = ctk.CTkFrame(parent, fg_color="white", corner_radius=10,
                            border_color="#E2E8F0", border_width=1)
        card.grid(row=0, column=col, padx=6, sticky="nsew")
        card.configure(height=70)
        card.grid_propagate(False)
        ctk.CTkLabel(card, text=titulo, font=("Helvetica", 10),
                     text_color="#64748B").pack(anchor="w", padx=12, pady=(12, 2))
        ctk.CTkLabel(card, text=valor, font=("Helvetica", 15, "bold"),
                     text_color=color).pack(anchor="w", padx=12, pady=(0, 12))

    def _mostrar_distribucion(self, parent):
        frame = ctk.CTkFrame(parent, fg_color="white", corner_radius=12,
                             border_color="#E2E8F0", border_width=1)
        frame.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(frame, text="📊 Distribución de inventario por categoría",
                     font=("Helvetica", 14, "bold"), text_color="#0F172A").pack(anchor="w", padx=20, pady=(15, 10))
        dist = fn.obtener_distribucion_inventario()
        if not dist or all(s == 0 for _, s in dist):
            ctk.CTkLabel(frame, text="Sin stock registrado", text_color="#64748B").pack(pady=20)
            return
        max_stock = max(s for _, s in dist) or 1
        cont = ctk.CTkFrame(frame, fg_color="transparent")
        cont.pack(fill="x", padx=20, pady=(0, 15))
        for cat, stock in dist:
            if stock == 0:
                continue
            fila = ctk.CTkFrame(cont, fg_color="transparent", height=30)
            fila.pack(fill="x", pady=3)
            ctk.CTkLabel(fila, text=cat, font=("Helvetica", 11), text_color="#475569",
                         width=200, anchor="w").pack(side="left", padx=(0, 10))
            bg = ctk.CTkFrame(fila, fg_color="#E2E8F0", height=24, corner_radius=4)
            bg.pack(side="left", fill="x", expand=True)
            ancho = max(4, int((stock / max_stock) * 250))
            ctk.CTkFrame(bg, fg_color="#3B82F6", height=24, corner_radius=4, width=ancho).pack(side="left")
            ctk.CTkLabel(fila, text=f"{stock} uds", font=("Helvetica", 11, "bold"),
                         text_color="#1E3A8A", width=65, anchor="e").pack(side="right", padx=(10, 0))

    # ─────────────────────────────────────────────────────────
    # CATEGORÍAS — con eliminación forzada y recálculo
    # ─────────────────────────────────────────────────────────
    def mostrar_categorias(self):
        main = ctk.CTkFrame(self.contenedor_principal, fg_color="white", corner_radius=12,
                            border_color="#E2E8F0", border_width=1)
        main.pack(fill="both", expand=True)

        izq = ctk.CTkFrame(main, fg_color="transparent", width=350)
        izq.pack(side="left", fill="both", padx=20, pady=20)
        izq.pack_propagate(False)

        ctk.CTkLabel(izq, text="Agregar nueva categoría",
                     font=("Helvetica", 16, "bold"), text_color="#0F172A").pack(anchor="w", pady=(0, 15))
        ctk.CTkLabel(izq, text="Nombre de la categoría",
                     font=("Helvetica", 12, "bold"), text_color="#334155").pack(anchor="w")
        entry = ctk.CTkEntry(izq, placeholder_text="Ej: Camiseta Chelsea", height=36)
        entry.pack(fill="x", pady=(5, 15))
        lbl_status = ctk.CTkLabel(izq, text="", wraplength=300)
        lbl_status.pack()

        def guardar():
            texto = entry.get().strip()
            if not texto:
                lbl_status.configure(text="❌ El nombre no puede estar vacío", text_color="#EF4444")
                return
            ok, msg = fn.crear_categoria(texto)
            lbl_status.configure(text=msg, text_color="#22C55E" if ok else "#EF4444")
            if ok:
                entry.delete(0, "end")
                actualizar_lista()

        ctk.CTkButton(izq, text="+ Agregar categoría",
                      font=("Helvetica", 13, "bold"), fg_color="#1D4ED8",
                      command=guardar).pack(fill="x", pady=15)

        der = ctk.CTkFrame(main, fg_color="transparent")
        der.pack(side="right", fill="both", expand=True, padx=(0, 20), pady=20)
        ctk.CTkLabel(der, text="Categorías existentes",
                     font=("Helvetica", 16, "bold"), text_color="#0F172A").pack(anchor="w", pady=(0, 10))
        scroll = ctk.CTkScrollableFrame(der, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        def actualizar_lista():
            for w in scroll.winfo_children():
                w.destroy()
            cats = fn.obtener_categorias()
            if not cats:
                ctk.CTkLabel(scroll, text="No hay categorías creadas",
                             text_color="#64748B").pack(pady=40)
                return
            for cid, nom in cats:
                item = ctk.CTkFrame(scroll, fg_color="#F8FAFC", height=42, corner_radius=6)
                item.pack(fill="x", pady=3)
                item.pack_propagate(False)
                ctk.CTkLabel(item, text=nom, font=("Helvetica", 13),
                             text_color="#334155").pack(side="left", padx=15)

                def eliminar(c_id=cid, nombre=nom):
                    # Intento normal primero
                    resultado = fn.eliminar_categoria(c_id, forzar=False)
                    # resultado puede ser (ok, msg) o (ok, msg, tiene_datos)
                    ok = resultado[0]
                    msg = resultado[1]
                    tiene_datos = resultado[2] if len(resultado) > 2 else False

                    if ok:
                        lbl_status.configure(text=msg, text_color="#22C55E")
                        actualizar_lista()
                        return

                    if tiene_datos:
                        # Ofrecer eliminación forzada
                        confirmar = messagebox.askyesno(
                            "⚠️ Eliminación con datos",
                            f"La categoría '{nombre}' tiene movimientos y/o ventas registradas.\n\n"
                            f"¿Deseas eliminarla junto con TODOS sus datos?\n\n"
                            f"Esta acción es IRREVERSIBLE. El inventario, las ventas y los movimientos "
                            f"asociados a esta categoría se borrarán permanentemente.",
                            icon="warning"
                        )
                        if not confirmar:
                            return
                        resultado2 = fn.eliminar_categoria(c_id, forzar=True)
                        ok2, msg2 = resultado2[0], resultado2[1]
                        lbl_status.configure(text=msg2, text_color="#22C55E" if ok2 else "#EF4444")
                        if ok2:
                            actualizar_lista()
                    else:
                        lbl_status.configure(text=msg, text_color="#EF4444")

                ctk.CTkButton(item, text="🗑", width=35, height=28,
                              fg_color="transparent", text_color="#EF4444",
                              hover_color="#FEE2E2", command=eliminar).pack(side="right", padx=10)

        actualizar_lista()

    # ─────────────────────────────────────────────────────────
    # COMPRAS
    # ─────────────────────────────────────────────────────────
    def mostrar_compras(self):
        frame = ctk.CTkFrame(self.contenedor_principal, fg_color="white", corner_radius=12,
                             border_color="#E2E8F0", border_width=1)
        frame.pack(fill="both", expand=True)
        ctk.CTkLabel(frame, text="Registrar compra al por mayor",
                     font=("Helvetica", 18, "bold"), text_color="#0F172A").pack(anchor="w", padx=30, pady=(20, 15))

        campos = ctk.CTkFrame(frame, fg_color="transparent")
        campos.pack(fill="x", padx=30, pady=(0, 10))
        campos.columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(campos, text="Categoría",
                     font=("Helvetica", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")

        categorias = fn.obtener_categorias()
        nombres = [c[1] for c in categorias] if categorias else ["Primero crea una categoría"]
        combo_cat = ctk.CTkComboBox(campos, values=nombres, state="readonly")
        combo_cat.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 12))
        if nombres:
            combo_cat.set(nombres[0])

        ctk.CTkLabel(campos, text="Costo unitario ($)",
                     font=("Helvetica", 11, "bold")).grid(row=2, column=0, sticky="w")
        entry_costo = ctk.CTkEntry(campos, placeholder_text="Ej: 45.000 o 45000")
        entry_costo.grid(row=3, column=0, sticky="ew", padx=(0, 15), pady=(4, 12))

        ctk.CTkLabel(campos, text="Precio de venta ($)",
                     font=("Helvetica", 11, "bold")).grid(row=2, column=1, sticky="w")
        entry_venta = ctk.CTkEntry(campos, placeholder_text="Ej: 80.000 o 80000")
        entry_venta.grid(row=3, column=1, sticky="ew", padx=(15, 0), pady=(4, 12))

        ctk.CTkLabel(frame, text="Cantidades por talla",
                     font=("Helvetica", 11, "bold")).pack(anchor="w", padx=30)
        tallas_frame = ctk.CTkFrame(frame, fg_color="transparent")
        tallas_frame.pack(fill="x", padx=30, pady=8)
        tallas = ["XS", "S", "M", "L", "XL", "XXL"]
        entries_tallas = {}
        for i, t in enumerate(tallas):
            tallas_frame.columnconfigure(i, weight=1)
            sub = ctk.CTkFrame(tallas_frame, fg_color="#F8FAFC",
                               border_width=1, border_color="#E2E8F0", corner_radius=6)
            sub.grid(row=0, column=i, padx=3, sticky="ew")
            ctk.CTkLabel(sub, text=t, font=("Helvetica", 10, "bold")).pack(pady=4)
            ent = ctk.CTkEntry(sub, placeholder_text="0", justify="center")
            ent.pack(pady=(0, 4), fill="x", padx=6)
            entries_tallas[t] = ent

        resumen_frame = ctk.CTkFrame(frame, fg_color="transparent")
        resumen_frame.pack(fill="x", padx=30, pady=10)
        lbl_total_uds = ctk.CTkLabel(resumen_frame, text="Unidades totales: 0",
                                     font=("Helvetica", 12))
        lbl_total_uds.pack(anchor="w")
        lbl_total_inv = ctk.CTkLabel(resumen_frame, text="Total inversión: $0",
                                     font=("Helvetica", 16, "bold"), text_color="#1E3A8A")
        lbl_total_inv.pack(anchor="w")

        lbl_msg = ctk.CTkLabel(frame, text="", wraplength=600)
        lbl_msg.pack(pady=5)

        def recalcular(*args):
            costo = _parsear_monto_entry(entry_costo.get()) or 0
            total_uds = 0
            for ent in entries_tallas.values():
                try:
                    v = _parsear_cant_entry(ent.get())
                    total_uds += v if v else 0
                except Exception:
                    pass
            lbl_total_uds.configure(text=f"Unidades totales: {total_uds}")
            lbl_total_inv.configure(text=f"Total inversión: {self._fmt(total_uds * costo)}")

        entry_costo.bind("<KeyRelease>", recalcular)
        for ent in entries_tallas.values():
            ent.bind("<KeyRelease>", recalcular)

        def cargar_precios():
            if not categorias or combo_cat.get() == "Primero crea una categoría":
                return
            cat_id = next((c[0] for c in categorias if c[1] == combo_cat.get()), None)
            if not cat_id:
                return
            c_hist, v_hist = fn.obtener_precios_referencia(cat_id)
            if c_hist:
                entry_costo.delete(0, "end")
                entry_costo.insert(0, str(int(c_hist)))
                entry_venta.delete(0, "end")
                entry_venta.insert(0, str(int(v_hist)))

        combo_cat.configure(command=lambda _: (cargar_precios(), recalcular()))
        cargar_precios()

        def registrar():
            if not categorias or combo_cat.get() == "Primero crea una categoría":
                lbl_msg.configure(text="❌ Cree una categoría primero", text_color="#EF4444")
                return

            costo_txt = entry_costo.get().strip()
            venta_txt = entry_venta.get().strip()

            if not costo_txt:
                lbl_msg.configure(text="❌ Ingrese el costo unitario", text_color="#EF4444")
                return
            if not venta_txt:
                lbl_msg.configure(text="❌ Ingrese el precio de venta", text_color="#EF4444")
                return

            cantidades = {}
            for t, ent in entries_tallas.items():
                texto = ent.get().strip()
                if not texto or texto == "0":
                    continue
                v = _parsear_cant_entry(texto)
                if v is None:
                    lbl_msg.configure(
                        text=f"❌ Cantidad inválida en talla {t} (use números enteros, ej: 5)",
                        text_color="#EF4444"
                    )
                    return
                cantidades[t] = v

            if not cantidades:
                lbl_msg.configure(text="❌ Ingrese al menos una talla con cantidad mayor a 0",
                                  text_color="#EF4444")
                return

            cat_id = next((c[0] for c in categorias if c[1] == combo_cat.get()), None)
            ok, msg = fn.registrar_compra(cat_id, costo_txt, venta_txt, cantidades)
            lbl_msg.configure(text=msg, text_color="#22C55E" if ok else "#EF4444")
            if ok:
                for ent in entries_tallas.values():
                    ent.delete(0, "end")
                recalcular()
                cargar_precios()

        ctk.CTkButton(frame, text="Registrar compra",
                      font=("Helvetica", 13, "bold"), fg_color="#1D4ED8",
                      height=42, command=registrar).pack(pady=15)

    # ─────────────────────────────────────────────────────────
    # VENTAS
    # ─────────────────────────────────────────────────────────
    def mostrar_ventas(self):
        frame = ctk.CTkFrame(self.contenedor_principal, fg_color="white", corner_radius=12,
                             border_color="#E2E8F0", border_width=1)
        frame.pack(fill="both", expand=True)
        ctk.CTkLabel(frame, text="Registrar nueva venta",
                     font=("Helvetica", 18, "bold"), text_color="#0F172A").pack(anchor="w", padx=30, pady=(20, 15))

        grid = ctk.CTkFrame(frame, fg_color="transparent")
        grid.pack(fill="x", padx=30)
        grid.columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(grid, text="Nombre del cliente",
                     font=("Helvetica", 11, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        entry_cli = ctk.CTkEntry(grid, placeholder_text="Ej: Carlos Rodríguez")
        entry_cli.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 12))

        ctk.CTkLabel(grid, text="Categoría",
                     font=("Helvetica", 11, "bold")).grid(row=2, column=0, sticky="w")
        ctk.CTkLabel(grid, text="Talla",
                     font=("Helvetica", 11, "bold")).grid(row=2, column=1, sticky="w")

        categorias = fn.obtener_categorias()
        nombres = [c[1] for c in categorias] if categorias else ["Primero crea una categoría"]
        combo_cat = ctk.CTkComboBox(grid, values=nombres, state="readonly")
        combo_cat.grid(row=3, column=0, sticky="ew", padx=(0, 15), pady=(4, 12))
        if nombres:
            combo_cat.set(nombres[0])

        tallas = ["XS", "S", "M", "L", "XL", "XXL"]
        combo_talla = ctk.CTkComboBox(grid, values=tallas, state="readonly")
        combo_talla.grid(row=3, column=1, sticky="ew", padx=(15, 0), pady=(4, 12))
        combo_talla.set("M")

        ctk.CTkLabel(grid, text="Cantidad",
                     font=("Helvetica", 11, "bold")).grid(row=4, column=0, sticky="w")
        ctk.CTkLabel(grid, text="Estado de pago",
                     font=("Helvetica", 11, "bold")).grid(row=4, column=1, sticky="w")

        entry_cant = ctk.CTkEntry(grid, placeholder_text="Ej: 3")
        entry_cant.grid(row=5, column=0, sticky="ew", padx=(0, 15), pady=(4, 12))
        entry_cant.insert(0, "1")

        opciones_pago = ["Pagado completo", "Pendiente", "Pago parcial"]
        combo_pago = ctk.CTkComboBox(grid, values=opciones_pago, state="readonly")
        combo_pago.grid(row=5, column=1, sticky="ew", padx=(15, 0), pady=(4, 12))
        combo_pago.set("Pagado completo")

        ctk.CTkLabel(grid, text="Monto parcial",
                     font=("Helvetica", 11, "bold")).grid(row=6, column=0, columnspan=2, sticky="w")
        entry_pagado = ctk.CTkEntry(grid, placeholder_text="Solo si el pago es parcial")
        entry_pagado.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(4, 12))
        entry_pagado.configure(state="disabled")

        info_frame = ctk.CTkFrame(grid, fg_color="#F8FAFC", corner_radius=8, border_width=1,
                                  border_color="#E2E8F0")
        info_frame.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        lbl_total = ctk.CTkLabel(info_frame, text="Total: $0",
                                 font=("Helvetica", 16, "bold"), text_color="#22C55E")
        lbl_total.pack(side="left", padx=15, pady=8)
        lbl_stock = ctk.CTkLabel(info_frame, text="Stock disponible: —",
                                 font=("Helvetica", 11), text_color="#64748B")
        lbl_stock.pack(side="right", padx=15, pady=8)

        lbl_msg = ctk.CTkLabel(frame, text="", wraplength=700)
        lbl_msg.pack(pady=5)

        def actualizar(*args):
            if not categorias or combo_cat.get() == "Primero crea una categoría":
                return
            cat_id = next((c[0] for c in categorias if c[1] == combo_cat.get()), None)
            if not cat_id:
                return
            stock, precio = fn.obtener_stock_y_precio(cat_id, combo_talla.get())
            lbl_stock.configure(text=f"Stock disponible: {stock} uds")
            cant = _parsear_cant_entry(entry_cant.get()) or 0
            total = cant * precio
            lbl_total.configure(text=f"Total: {self._fmt(total)}")

        def actualizar_pago(_=None):
            if combo_pago.get() == "Pago parcial":
                entry_pagado.configure(state="normal")
            else:
                entry_pagado.configure(state="normal")
                entry_pagado.delete(0, "end")
                entry_pagado.configure(state="disabled")

        combo_cat.configure(command=lambda _: actualizar())
        combo_talla.configure(command=lambda _: actualizar())
        combo_pago.configure(command=actualizar_pago)
        entry_cant.bind("<KeyRelease>", actualizar)
        actualizar_pago()
        actualizar()

        def vender():
            cliente = entry_cli.get().strip()
            if not cliente:
                lbl_msg.configure(text="❌ Ingrese el nombre del cliente", text_color="#EF4444")
                return
            if len(cliente) < 2:
                lbl_msg.configure(text="❌ El nombre debe tener al menos 2 caracteres", text_color="#EF4444")
                return
            if not categorias or combo_cat.get() == "Primero crea una categoría":
                lbl_msg.configure(text="❌ Cree una categoría primero", text_color="#EF4444")
                return

            cant = _parsear_cant_entry(entry_cant.get())
            if cant is None:
                lbl_msg.configure(text="❌ Cantidad inválida (use un número entero positivo, ej: 3)",
                                  text_color="#EF4444")
                return

            cat_id = next((c[0] for c in categorias if c[1] == combo_cat.get()), None)

            modo_pago = combo_pago.get()
            if modo_pago == "Pagado completo":
                monto_txt = ""
            elif modo_pago == "Pendiente":
                monto_txt = "0"
            else:
                monto_txt = entry_pagado.get().strip()
                if not monto_txt:
                    lbl_msg.configure(text="❌ Ingrese el monto parcial pagado", text_color="#EF4444")
                    return

            ok, msg, venta_id = fn.registrar_venta(
                cat_id, combo_talla.get(), cant, cliente, monto_txt
            )
            lbl_msg.configure(text=msg, text_color="#22C55E" if ok else "#EF4444")
            if ok:
                entry_cli.delete(0, "end")
                entry_cant.delete(0, "end")
                entry_cant.insert(0, "1")
                combo_pago.set("Pagado completo")
                entry_pagado.configure(state="normal")
                entry_pagado.delete(0, "end")
                actualizar_pago()
                actualizar()

        ctk.CTkButton(frame, text="Registrar venta",
                      font=("Helvetica", 13, "bold"), fg_color="#1D4ED8",
                      height=42, command=vender).pack(pady=15)

    # ─────────────────────────────────────────────────────────
    # INVENTARIO — eliminación forzada y recálculo automático
    # ─────────────────────────────────────────────────────────
    def mostrar_inventario(self):
        for w in self.contenedor_principal.winfo_children():
            w.destroy()

        fn.limpiar_duplicados()
        frame = ctk.CTkFrame(self.contenedor_principal, fg_color="white", corner_radius=12,
                             border_color="#E2E8F0", border_width=1)
        frame.pack(fill="both", expand=True)
        ctk.CTkLabel(frame, text="Inventario de productos disponibles",
                     font=("Helvetica", 18, "bold"), text_color="#0F172A").pack(anchor="w", padx=25, pady=15)

        productos = fn.obtener_inventario()
        if not productos:
            ctk.CTkLabel(frame, text="Inventario vacío. Registra compras primero.",
                         font=("Helvetica", 14), text_color="#64748B").pack(pady=60)
            return

        scroll = ctk.CTkScrollableFrame(frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=25, pady=(0, 15))

        headers  = ["Categoría", "Talla", "Stock", "Costo prom.", "P. venta", "Valor total", "Acciones"]
        anchos   = [230, 60, 75, 120, 120, 140, 110]
        header_f = ctk.CTkFrame(scroll, fg_color="#F1F5F9", height=35)
        header_f.pack(fill="x", pady=(0, 5))
        for i, (h, w) in enumerate(zip(headers, anchos)):
            ctk.CTkLabel(header_f, text=h, font=("Helvetica", 11, "bold"),
                         text_color="#475569", width=w,
                         anchor="w" if i == 0 else "center").grid(
                row=0, column=i, padx=5, pady=5, sticky="ew")

        for pid, cat, talla, stock, costo, venta, valor in productos:
            fila = ctk.CTkFrame(scroll, fg_color="#F8FAFC", height=40)
            fila.pack(fill="x", pady=2)
            color_s = "#EF4444" if stock == 0 else ("#F59E0B" if stock < 5 else "#475569")
            ctk.CTkLabel(fila, text=cat, width=anchos[0], anchor="w").grid(row=0, column=0, padx=5)
            ctk.CTkLabel(fila, text=talla, width=anchos[1], anchor="center").grid(row=0, column=1, padx=5)
            ctk.CTkLabel(fila, text=str(stock), width=anchos[2], anchor="center",
                         font=("Helvetica", 12, "bold"), text_color=color_s).grid(row=0, column=2, padx=5)
            ctk.CTkLabel(fila, text=self._fmt(costo), width=anchos[3], anchor="center").grid(row=0, column=3, padx=5)
            ctk.CTkLabel(fila, text=self._fmt(venta), width=anchos[4], anchor="center",
                         font=("Helvetica", 12, "bold"), text_color="#1D4ED8").grid(row=0, column=4, padx=5)
            ctk.CTkLabel(fila, text=self._fmt(valor), width=anchos[5], anchor="center").grid(row=0, column=5, padx=5)
            acc = ctk.CTkFrame(fila, fg_color="transparent")
            acc.grid(row=0, column=6, padx=5)
            ctk.CTkButton(acc, text="✏️", width=32, fg_color="transparent",
                          command=lambda p=pid, c=cat, t=talla, s=stock, cp=costo, pv=venta:
                          self._editar_stock(p, c, t, s, cp, pv)).pack(side="left", padx=2)
            ctk.CTkButton(acc, text="🗑", width=32, fg_color="transparent", text_color="#EF4444",
                          command=lambda p=pid, c=cat, t=talla:
                          self._eliminar_producto(p, c, t)).pack(side="left", padx=2)

    def _editar_stock(self, producto_id, categoria, talla, stock_actual, costo_prom, precio_venta):
        ventana = ctk.CTkToplevel(self)
        ventana.title("Corregir stock")
        ventana.geometry("440x360")
        ventana.resizable(False, False)
        ventana.grab_set()

        main = ctk.CTkFrame(ventana, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=20, pady=15)

        info = ctk.CTkFrame(main, fg_color="#F1F5F9", corner_radius=8)
        info.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(info, text=f"📦 {categoria} — Talla {talla}",
                     font=("Helvetica", 14, "bold")).pack(pady=(10, 5))
        ctk.CTkLabel(info, text=f"Stock actual: {stock_actual} uds",
                     font=("Helvetica", 12), text_color="#1D4ED8").pack()
        ctk.CTkLabel(info, text=f"Costo promedio: {self._fmt(costo_prom)}",
                     font=("Helvetica", 11), text_color="#64748B").pack()
        ctk.CTkLabel(info, text=f"Precio venta: {self._fmt(precio_venta)}",
                     font=("Helvetica", 11), text_color="#22C55E").pack(pady=(0, 10))

        aviso = ctk.CTkFrame(main, fg_color="#FFFBEB", corner_radius=8,
                             border_color="#FDE68A", border_width=1)
        aviso.pack(fill="x", pady=(0, 15))
        ctk.CTkLabel(
            aviso,
            text="Las entradas de mercancía deben registrarse en Compras. Esta opción solo corrige pérdidas, errores de conteo o bajas de inventario.",
            font=("Helvetica", 10), text_color="#92400E", wraplength=360,
            justify="left"
        ).pack(padx=12, pady=10)

        ctk.CTkLabel(main, text="Cantidad a reducir:",
                     font=("Helvetica", 12, "bold")).pack(anchor="w")
        entry_cant = ctk.CTkEntry(main, placeholder_text="Ej: 3")
        entry_cant.pack(pady=6, fill="x")
        lbl_msg = ctk.CTkLabel(main, text="", wraplength=360)
        lbl_msg.pack(pady=8)

        def confirmar():
            cant = _parsear_cant_entry(entry_cant.get())
            if cant is None:
                lbl_msg.configure(text="❌ Cantidad inválida (número entero positivo)",
                                  text_color="#EF4444")
                return
            ok, msg = fn.agregar_stock_con_precio(producto_id, -cant, None)
            lbl_msg.configure(text=msg, text_color="#22C55E" if ok else "#EF4444")
            if ok:
                ventana.after(1200, lambda: (ventana.destroy(), self.mostrar_inventario()))

        ctk.CTkButton(main, text="Aplicar corrección", fg_color="#EF4444",
                      command=confirmar).pack(fill="x", pady=(5, 8))
        ctk.CTkButton(main, text="Cerrar", fg_color="#64748B",
                      command=ventana.destroy).pack(pady=10)

    def _eliminar_producto(self, producto_id, cat_nombre="", talla=""):
        # Intento sin forzar primero
        resultado = fn.eliminar_producto(producto_id, forzar=False)
        ok = resultado[0]
        msg = resultado[1]
        tiene_datos = resultado[2] if len(resultado) > 2 else False

        if ok:
            self.mostrar_inventario()
            return

        if tiene_datos:
            confirmar = messagebox.askyesno(
                "⚠️ Producto con historial",
                f"El producto '{cat_nombre} – {talla}' tiene movimientos y/o ventas asociadas.\n\n"
                f"¿Deseas eliminar este producto y TODOS sus registros históricos?\n\n"
                f"El stock se recalculará automáticamente. Esta acción es IRREVERSIBLE.",
                icon="warning"
            )
            if not confirmar:
                return
            resultado2 = fn.eliminar_producto(producto_id, forzar=True)
            ok2, msg2 = resultado2[0], resultado2[1]
            if ok2:
                self.mostrar_inventario()
            else:
                messagebox.showerror("No se pudo eliminar", msg2)
        else:
            messagebox.showerror("No se pudo eliminar", msg)

    def _abrir_calendario(self, entry_destino):
        ventana = ctk.CTkToplevel(self)
        ventana.title("Seleccionar fecha")
        ventana.geometry("330x360")
        ventana.resizable(False, False)
        ventana.grab_set()

        try:
            fecha_actual = date.fromisoformat(entry_destino.get().strip())
        except ValueError:
            fecha_actual = date.today()

        cal = Calendar(
            ventana,
            selectmode="day",
            year=fecha_actual.year,
            month=fecha_actual.month,
            day=fecha_actual.day,
            date_pattern="yyyy-mm-dd"
        )
        cal.pack(fill="both", expand=True, padx=15, pady=(15, 8))

        acciones = ctk.CTkFrame(ventana, fg_color="transparent")
        acciones.pack(fill="x", padx=15, pady=(0, 15))

        def aceptar():
            entry_destino.delete(0, "end")
            entry_destino.insert(0, cal.selection_get().strftime("%Y-%m-%d"))
            ventana.destroy()

        ctk.CTkButton(acciones, text="Aceptar", command=aceptar).pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkButton(acciones, text="Cancelar", fg_color="#64748B",
                      command=ventana.destroy).pack(side="left", expand=True, fill="x", padx=(5, 0))

    # ─────────────────────────────────────────────────────────
    # HISTORIAL — con abonos, historial de pagos y eliminación de ventas
    # ─────────────────────────────────────────────────────────
    def mostrar_historial(self):
        frame = ctk.CTkFrame(self.contenedor_principal, fg_color="white", corner_radius=12,
                             border_color="#E2E8F0", border_width=1)
        frame.pack(fill="both", expand=True)
        ctk.CTkLabel(frame, text="Historial de transacciones",
                     font=("Helvetica", 18, "bold"), text_color="#0F172A").pack(anchor="w", padx=25, pady=15)

        # Barra de exportación
        export_frame = ctk.CTkFrame(frame, fg_color="#F8FAFC", corner_radius=8)
        export_frame.pack(fill="x", padx=25, pady=(0, 10))
        ctk.CTkLabel(export_frame, text="Exportar a Excel:",
                     font=("Helvetica", 12, "bold")).pack(side="left", padx=10)
        ctk.CTkLabel(export_frame, text="Desde:").pack(side="left", padx=(20, 5))
        entry_desde = ctk.CTkEntry(export_frame, width=105)
        entry_desde.insert(0, date.today().strftime("%Y-%m-%d"))
        entry_desde.pack(side="left", padx=5)
        ctk.CTkButton(export_frame, text="📅", width=34,
                      command=lambda: self._abrir_calendario(entry_desde)).pack(side="left")

        ctk.CTkLabel(export_frame, text="Hasta:").pack(side="left", padx=(10, 5))
        entry_hasta = ctk.CTkEntry(export_frame, width=105)
        entry_hasta.insert(0, date.today().strftime("%Y-%m-%d"))
        entry_hasta.pack(side="left", padx=5)
        ctk.CTkButton(export_frame, text="📅", width=34,
                      command=lambda: self._abrir_calendario(entry_hasta)).pack(side="left")
        lbl_export_status = ctk.CTkLabel(export_frame, text="")
        lbl_export_status.pack(side="left", padx=10)

        def exportar():
            tipo  = self.historial_tab.lower()
            desde = entry_desde.get().strip()
            hasta = entry_hasta.get().strip()
            try:
                date.fromisoformat(desde)
                date.fromisoformat(hasta)
            except ValueError:
                lbl_export_status.configure(text="❌ Fecha inválida (use AAAA-MM-DD)",
                                            text_color="#EF4444")
                return
            archivo = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx")],
                title="Guardar exportación"
            )
            if not archivo:
                return
            try:
                ok, msg = fn.exportar_a_excel(tipo, desde, hasta, archivo)
                lbl_export_status.configure(
                    text="✅ Exportado" if ok else f"❌ {msg}",
                    text_color="#22C55E" if ok else "#EF4444"
                )
                self.after(3500, lambda: lbl_export_status.configure(text=""))
            except Exception as e:
                lbl_export_status.configure(text=f"Error: {e}", text_color="#EF4444")

        ctk.CTkButton(export_frame, text="📎 Exportar", command=exportar).pack(side="left", padx=10)

        # Pestañas ventas / compras
        tabs = ctk.CTkFrame(frame, fg_color="transparent")
        tabs.pack(fill="x", padx=25, pady=(0, 10))
        self.historial_tab = "VENTAS"
        self.btn_tab_ventas  = ctk.CTkButton(tabs, text="📋 Ventas", width=120,
                                              fg_color="#1D4ED8",
                                              command=lambda: self._cambiar_tab("VENTAS"))
        self.btn_tab_ventas.pack(side="left", padx=5)
        self.btn_tab_compras = ctk.CTkButton(tabs, text="📦 Compras", width=120,
                                              fg_color="#64748B",
                                              command=lambda: self._cambiar_tab("COMPRAS"))
        self.btn_tab_compras.pack(side="left", padx=5)

        self.historial_container = ctk.CTkFrame(frame, fg_color="transparent")
        self.historial_container.pack(fill="both", expand=True, padx=25, pady=(0, 15))
        self._actualizar_historial()

    def _cambiar_tab(self, tab):
        self.historial_tab = tab
        self.btn_tab_ventas.configure(fg_color="#1D4ED8" if tab == "VENTAS" else "#64748B")
        self.btn_tab_compras.configure(fg_color="#1D4ED8" if tab == "COMPRAS" else "#64748B")
        self._actualizar_historial()

    def _actualizar_historial(self):
        # Verificar que el contenedor sigue existiendo (puede haberse destruido
        # si el usuario cambió de pestaña antes de que se ejecutara el after()).
        if self.historial_container is None:
            return
        try:
            self.historial_container.winfo_exists()
        except Exception:
            return
        if not self.historial_container.winfo_exists():
            return

        for w in self.historial_container.winfo_children():
            w.destroy()

        if self.historial_tab == "VENTAS":
            datos = fn.obtener_historial_ventas()
            if not datos:
                ctk.CTkLabel(self.historial_container, text="No hay ventas registradas",
                             text_color="#64748B").pack(pady=40)
                return

            total_cobrado   = sum(row[8]  for row in datos)
            total_facturado = sum(row[7]  for row in datos)
            total_saldo     = sum(row[9]  for row in datos)

            tot_frame = ctk.CTkFrame(self.historial_container, fg_color="#F0FDF4", corner_radius=8)
            tot_frame.pack(fill="x", pady=(0, 8))
            resumen_txt = (
                f"💰 Cobrado: {self._fmt(total_cobrado)}   |   "
                f"📋 Facturado: {self._fmt(total_facturado)}   |   "
                f"⏳ Por cobrar: {self._fmt(total_saldo)}"
            )
            ctk.CTkLabel(tot_frame, text=resumen_txt,
                         font=("Helvetica", 13, "bold"), text_color="#166534").pack(pady=8)

            # ── Diseño de 2 filas por venta ──────────────────────────
            # Fila 1 (principal): ID · Fecha · Cliente · Producto · Talla
            #                     Cant · Total · Pagado · Saldo · Est.Pago · Acciones
            # Fila 2 (detalle):   P.Unit · Costo · Utilidad · Est.Envío
            # Anchos calibrados para caber en ~1050 px (1300 px ventana - márgenes).
            # ─────────────────────────────────────────────────────────
            H  = ["ID",   "Fecha", "Cliente", "Producto", "Talla",
                  "Cant", "Total", "Pagado",  "Saldo",    "Estado pago", "Acciones"]
            AW = [38,     85,      120,        125,        48,
                  42,     82,      82,         82,         100,           140]
            # Suma: 944 px + 11*8 px padding ≈ 1032 px  ✓

            scroll = ctk.CTkScrollableFrame(self.historial_container, fg_color="transparent")
            scroll.pack(fill="both", expand=True)

            # Encabezado
            head = ctk.CTkFrame(scroll, fg_color="#F1F5F9", height=32)
            head.pack(fill="x", pady=(0, 4))
            head.grid_columnconfigure(10, weight=1)
            for i, (h, w) in enumerate(zip(H, AW)):
                ctk.CTkLabel(head, text=h, font=("Helvetica", 10, "bold"),
                             text_color="#475569", width=w,
                             anchor="w" if i <= 1 else "center").grid(
                    row=0, column=i, padx=4, pady=5, sticky="ew")

            for row in datos:
                vid, fecha, cliente, producto, talla, cant, p_unit, total, pagado, saldo, costo, utilidad, est_pago, est_envio = row

                # Contenedor de las 2 filas
                bloque = ctk.CTkFrame(scroll, fg_color="#F8FAFC", corner_radius=6)
                bloque.pack(fill="x", pady=2)
                bloque.grid_columnconfigure(10, weight=1)

                # ── FILA 1: datos de pago + acciones ──────────────
                ep_color = {"pagado": "#22C55E", "parcial": "#F59E0B",
                            "pendiente": "#EF4444"}.get(est_pago, "#64748B")
                ep_txt   = {"pagado": "✅ Pagado", "parcial": "🟡 Parcial",
                            "pendiente": "🔴 Pendiente"}.get(est_pago, est_pago)
                saldo_color = "#EF4444" if saldo > 0 else "#22C55E"

                ctk.CTkLabel(bloque, text=f"#{vid}", width=AW[0], anchor="w",
                             font=("Helvetica", 9), text_color="#94A3B8").grid(
                    row=0, column=0, padx=4, pady=(5, 1))
                ctk.CTkLabel(bloque, text=fecha, width=AW[1], anchor="w",
                             font=("Helvetica", 10)).grid(row=0, column=1, padx=4, pady=(5, 1))
                ctk.CTkLabel(bloque, text=cliente, width=AW[2], anchor="w",
                             font=("Helvetica", 10, "bold")).grid(row=0, column=2, padx=4, pady=(5, 1))
                ctk.CTkLabel(bloque, text=producto, width=AW[3], anchor="w",
                             font=("Helvetica", 10)).grid(row=0, column=3, padx=4, pady=(5, 1))
                ctk.CTkLabel(bloque, text=talla, width=AW[4], anchor="center",
                             font=("Helvetica", 10)).grid(row=0, column=4, padx=4, pady=(5, 1))
                ctk.CTkLabel(bloque, text=str(cant), width=AW[5], anchor="center",
                             font=("Helvetica", 10)).grid(row=0, column=5, padx=4, pady=(5, 1))
                ctk.CTkLabel(bloque, text=self._fmt(total), width=AW[6], anchor="center",
                             font=("Helvetica", 11, "bold")).grid(row=0, column=6, padx=4, pady=(5, 1))
                ctk.CTkLabel(bloque, text=self._fmt(pagado), width=AW[7], anchor="center",
                             font=("Helvetica", 10), text_color="#22C55E").grid(
                    row=0, column=7, padx=4, pady=(5, 1))
                ctk.CTkLabel(bloque, text=self._fmt(saldo), width=AW[8], anchor="center",
                             font=("Helvetica", 10, "bold"), text_color=saldo_color).grid(
                    row=0, column=8, padx=4, pady=(5, 1))
                ctk.CTkLabel(bloque, text=ep_txt, width=AW[9], anchor="center",
                             font=("Helvetica", 10, "bold"), text_color=ep_color).grid(
                    row=0, column=9, padx=4, pady=(5, 1))

                # Acciones — siempre a la derecha, nunca se cortan
                acc = ctk.CTkFrame(bloque, fg_color="transparent")
                acc.grid(row=0, column=10, padx=(4, 8), pady=(4, 1), sticky="e")

                if saldo > 0:
                    ctk.CTkButton(
                        acc, text="💰 Abonar", width=80, height=26,
                        font=("Helvetica", 11, "bold"),
                        fg_color="#16A34A", hover_color="#15803D",
                        command=lambda v=vid, s=saldo: self._registrar_abono(v, s)
                    ).pack(side="left", padx=2)

                ctk.CTkButton(
                    acc, text="📜", width=30, height=26,
                    fg_color="#8B5CF6", hover_color="#7C3AED",
                    command=lambda v=vid, cl=cliente, tot=total: self._ver_historial_abonos(v, cl, tot)
                ).pack(side="left", padx=2)

                envio_nuevo = "no_enviado" if est_envio == "enviado" else "enviado"
                envio_label = "↩️" if est_envio == "enviado" else "📬"
                envio_color = "#64748B" if est_envio == "enviado" else "#3B82F6"
                ctk.CTkButton(
                    acc, text=envio_label, width=30, height=26,
                    fg_color=envio_color,
                    command=lambda v=vid, e=envio_nuevo: self._cambiar_envio(v, e)
                ).pack(side="left", padx=2)

                ctk.CTkButton(
                    acc, text="🗑", width=30, height=26,
                    fg_color="transparent", text_color="#EF4444",
                    hover_color="#FEE2E2",
                    command=lambda v=vid: self._eliminar_venta(v)
                ).pack(side="left", padx=2)

                # ── FILA 2: detalle financiero secundario ──────────
                env_txt  = "📦 Enviado" if est_envio == "enviado" else "⏳ No enviado"
                util_color = "#22C55E" if utilidad >= 0 else "#EF4444"
                det = ctk.CTkFrame(bloque, fg_color="transparent")
                det.grid(row=1, column=0, columnspan=11, padx=8, pady=(0, 4), sticky="w")
                ctk.CTkLabel(det,
                             text=f"P.Unit: {self._fmt(p_unit)}   Costo: {self._fmt(costo)}   "
                                  f"Utilidad: {self._fmt(utilidad)}   Envío: {env_txt}",
                             font=("Helvetica", 9), text_color="#94A3B8").pack(side="left")

        else:  # COMPRAS
            datos = fn.obtener_historial_compras()
            if not datos:
                ctk.CTkLabel(self.historial_container, text="No hay compras registradas",
                             text_color="#64748B").pack(pady=40)
                return

            # datos: (mov_id, fecha, producto, talla, cantidad, precio_unit, total)
            total_compras = sum(row[6] for row in datos)
            tot_frame = ctk.CTkFrame(self.historial_container, fg_color="#FEF2F2", corner_radius=8)
            tot_frame.pack(fill="x", pady=(0, 8))
            ctk.CTkLabel(tot_frame,
                         text=f"📦 Total invertido en compras: {self._fmt(total_compras)}",
                         font=("Helvetica", 13, "bold"), text_color="#991B1B").pack(pady=8)

            headers = ["ID", "Fecha", "Producto", "Talla", "Cantidad", "Costo unit.", "Total", ""]
            anchos  = [55, 100, 200, 65, 85, 130, 130, 60]
            scroll  = ctk.CTkScrollableFrame(self.historial_container, fg_color="transparent")
            scroll.pack(fill="both", expand=True)
            head = ctk.CTkFrame(scroll, fg_color="#F1F5F9", height=35)
            head.pack(fill="x", pady=(0, 5))
            for i, (h, w) in enumerate(zip(headers, anchos)):
                ctk.CTkLabel(head, text=h, font=("Helvetica", 11, "bold"),
                             text_color="#475569", width=w,
                             anchor="w" if i <= 1 else "center").grid(
                    row=0, column=i, padx=5, pady=5, sticky="ew")

            for row in datos:
                mov_id, fecha, prod, talla, cant, costo_u, total = row
                fila = ctk.CTkFrame(scroll, fg_color="#F8FAFC", height=38)
                fila.pack(fill="x", pady=2)
                ctk.CTkLabel(fila, text=f"#{mov_id}", width=anchos[0], anchor="w",
                             font=("Helvetica", 10), text_color="#94A3B8").grid(row=0, column=0, padx=5)
                ctk.CTkLabel(fila, text=fecha, width=anchos[1], anchor="w").grid(row=0, column=1, padx=5)
                ctk.CTkLabel(fila, text=prod, width=anchos[2], anchor="w").grid(row=0, column=2, padx=5)
                ctk.CTkLabel(fila, text=talla, width=anchos[3], anchor="center").grid(row=0, column=3, padx=5)
                ctk.CTkLabel(fila, text=str(cant), width=anchos[4], anchor="center").grid(row=0, column=4, padx=5)
                ctk.CTkLabel(fila, text=self._fmt(costo_u), width=anchos[5], anchor="center").grid(row=0, column=5, padx=5)
                ctk.CTkLabel(fila, text=self._fmt(total), width=anchos[6], anchor="center").grid(row=0, column=6, padx=5)
                ctk.CTkButton(fila, text="🗑", width=32, height=28,
                              fg_color="transparent", text_color="#EF4444",
                              hover_color="#FEE2E2",
                              command=lambda mid=mov_id: self._eliminar_movimiento_compra(mid)).grid(
                    row=0, column=7, padx=5)

    def _registrar_abono(self, venta_id, saldo_pendiente):
        """
        Ventana para registrar un abono a una venta pendiente o parcial.
        - El saldo se reconsulta desde la BD al abrir la ventana (no usa valor estático).
        - Después de un abono exitoso se refresca inmediatamente sin delay.
        - Permite registrar abonos sucesivos sin cerrar la ventana.
        """
        ventana = ctk.CTkToplevel(self)
        ventana.title(f"Registrar abono — Venta #{venta_id}")
        ventana.geometry("460x340")
        ventana.grab_set()

        ctk.CTkLabel(ventana, text=f"Registrar abono — Venta #{venta_id}",
                     font=("Helvetica", 14, "bold")).pack(pady=(15, 8))

        # Panel de estado: se actualiza después de cada abono
        estado_frame = ctk.CTkFrame(ventana, fg_color="#FEF2F2", corner_radius=8)
        estado_frame.pack(fill="x", padx=20, pady=(0, 12))
        lbl_estado = ctk.CTkLabel(estado_frame, text="",
                                  font=("Helvetica", 12, "bold"), text_color="#991B1B")
        lbl_estado.pack(pady=8)

        def refrescar_estado():
            """Reconsulta la BD y actualiza el panel de estado en tiempo real."""
            datos = fn.obtener_saldo_venta(venta_id)
            if not datos:
                lbl_estado.configure(text="Venta no encontrada")
                return None
            total, pagado, saldo, estado = datos
            ep = {"pagado": "✅ Pagado", "parcial": "🟡 Parcial",
                  "pendiente": "🔴 Pendiente"}.get(estado, estado)
            lbl_estado.configure(
                text=f"Total: {self._fmt(total)}  |  Pagado: {self._fmt(pagado)}  |  Saldo: {self._fmt(saldo)}  |  {ep}",
                text_color="#166534" if estado == "pagado" else "#991B1B"
            )
            estado_frame.configure(fg_color="#F0FDF4" if estado == "pagado" else "#FEF2F2")
            return saldo

        # Construir el formulario de abono
        form = ctk.CTkFrame(ventana, fg_color="transparent")
        form.pack(fill="x", padx=20)
        ctk.CTkLabel(form, text="Monto a abonar ($):",
                     font=("Helvetica", 12, "bold")).pack(anchor="w")
        entry_monto = ctk.CTkEntry(form, placeholder_text="Ej: 50000")
        entry_monto.pack(fill="x", pady=(4, 0))

        lbl_msg = ctk.CTkLabel(ventana, text="", wraplength=400, font=("Helvetica", 11))
        lbl_msg.pack(pady=10)

        btn_registrar = ctk.CTkButton(ventana, text="✅ Registrar abono",
                                      fg_color="#22C55E", font=("Helvetica", 13, "bold"))
        btn_registrar.pack(pady=(0, 8), padx=20, fill="x")
        ctk.CTkButton(ventana, text="Cerrar", fg_color="#64748B",
                      command=ventana.destroy).pack(padx=20, fill="x")

        def aplicar():
            texto = entry_monto.get().strip()
            if not texto:
                lbl_msg.configure(text="❌ Ingrese el monto a abonar", text_color="#EF4444")
                return

            ok, msg = fn.registrar_pago(venta_id, texto)
            lbl_msg.configure(text=msg, text_color="#22C55E" if ok else "#EF4444")

            if ok:
                entry_monto.delete(0, "end")
                saldo_restante = refrescar_estado()
                # Actualizar el historial de fondo inmediatamente
                self._actualizar_historial()
                # Si ya está pagado, deshabilitar el formulario
                if saldo_restante is not None and saldo_restante <= 0:
                    entry_monto.configure(state="disabled")
                    btn_registrar.configure(state="disabled",
                                            text="✅ Venta completamente pagada",
                                            fg_color="#64748B")

        btn_registrar.configure(command=aplicar)
        entry_monto.bind("<Return>", lambda _: aplicar())

        # Cargar el estado inicial desde la BD (no el parámetro estático)
        refrescar_estado()

    def _ver_historial_abonos(self, venta_id, cliente, total_venta):
        """Muestra el historial completo de abonos de una venta."""
        ventana = ctk.CTkToplevel(self)
        ventana.title(f"Historial de pagos — Venta #{venta_id}")
        ventana.geometry("520x420")
        ventana.grab_set()

        ctk.CTkLabel(ventana, text=f"Historial de pagos — {cliente}",
                     font=("Helvetica", 14, "bold")).pack(pady=(15, 5))

        # Info de la venta
        info_row = fn.obtener_saldo_venta(venta_id)
        if info_row:
            total, pagado, saldo, estado = info_row
            estado_txt = {"pagado": "✅ Pagado", "parcial": "🟡 Parcial", "pendiente": "🔴 Pendiente"}.get(estado, estado)

            resumen = ctk.CTkFrame(ventana, fg_color="#F0FDF4" if estado == "pagado" else "#FEF2F2",
                                   corner_radius=8)
            resumen.pack(fill="x", padx=20, pady=(0, 10))
            ctk.CTkLabel(resumen,
                         text=f"Total: {self._fmt(total)}  |  Pagado: {self._fmt(pagado)}  |  Saldo: {self._fmt(saldo)}  |  {estado_txt}",
                         font=("Helvetica", 12, "bold"),
                         text_color="#166534" if estado == "pagado" else "#991B1B").pack(pady=8)

        # Tabla de abonos
        abonos = fn.obtener_historial_abonos(venta_id)

        if not abonos:
            ctk.CTkLabel(ventana, text="Sin pagos registrados para esta venta.",
                         text_color="#64748B").pack(pady=20)
        else:
            ctk.CTkLabel(ventana, text=f"{len(abonos)} pago(s) registrado(s):",
                         font=("Helvetica", 11, "bold")).pack(anchor="w", padx=20)

            scroll = ctk.CTkScrollableFrame(ventana, fg_color="transparent", height=200)
            scroll.pack(fill="both", expand=True, padx=20, pady=5)

            # Encabezados
            head = ctk.CTkFrame(scroll, fg_color="#F1F5F9", height=30)
            head.pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(head, text="#", width=35, font=("Helvetica", 10, "bold"),
                         text_color="#475569").grid(row=0, column=0, padx=8, pady=5)
            ctk.CTkLabel(head, text="Fecha y hora", width=160, font=("Helvetica", 10, "bold"),
                         text_color="#475569", anchor="w").grid(row=0, column=1, padx=8, pady=5)
            ctk.CTkLabel(head, text="Monto abonado", width=140, font=("Helvetica", 10, "bold"),
                         text_color="#475569", anchor="center").grid(row=0, column=2, padx=8, pady=5)

            acumulado = 0
            for i, (fecha_fmt, monto) in enumerate(abonos, start=1):
                acumulado += monto
                fila = ctk.CTkFrame(scroll, fg_color="#F8FAFC", height=32)
                fila.pack(fill="x", pady=2)
                ctk.CTkLabel(fila, text=str(i), width=35, font=("Helvetica", 10),
                             text_color="#94A3B8").grid(row=0, column=0, padx=8)
                ctk.CTkLabel(fila, text=fecha_fmt, width=160, anchor="w",
                             font=("Helvetica", 11)).grid(row=0, column=1, padx=8)
                ctk.CTkLabel(fila, text=self._fmt(monto), width=140, anchor="center",
                             font=("Helvetica", 11, "bold"),
                             text_color="#22C55E").grid(row=0, column=2, padx=8)

            # Total acumulado
            total_frame = ctk.CTkFrame(ventana, fg_color="#E0F2FE", corner_radius=6)
            total_frame.pack(fill="x", padx=20, pady=(5, 0))
            ctk.CTkLabel(total_frame,
                         text=f"Total abonado: {self._fmt(acumulado)}",
                         font=("Helvetica", 12, "bold"), text_color="#0369A1").pack(pady=6)

        ctk.CTkButton(ventana, text="Cerrar", fg_color="#64748B",
                      command=ventana.destroy).pack(pady=12)

    def _eliminar_venta(self, venta_id):
        """Elimina una venta y recalcula stock e indicadores."""
        confirmar = messagebox.askyesno(
            "⚠️ Eliminar venta",
            f"¿Eliminar la venta #{venta_id} y todos sus pagos registrados?\n\n"
            f"El stock se recalculará automáticamente para reflejar la devolución del inventario.\n\n"
            f"Esta acción es IRREVERSIBLE.",
            icon="warning"
        )
        if not confirmar:
            return
        ok, msg = fn.eliminar_venta(venta_id)
        if ok:
            self._actualizar_historial()
        else:
            messagebox.showerror("Error al eliminar", msg)

    def _eliminar_movimiento_compra(self, movimiento_id):
        """Elimina un movimiento de compra y recalcula el stock."""
        confirmar = messagebox.askyesno(
            "⚠️ Eliminar registro de compra",
            f"¿Eliminar este registro de compra (#{movimiento_id})?\n\n"
            f"El stock de la talla correspondiente se recalculará automáticamente.\n\n"
            f"Esta acción es IRREVERSIBLE.",
            icon="warning"
        )
        if not confirmar:
            return
        ok, msg = fn.eliminar_movimiento(movimiento_id)
        if ok:
            self._actualizar_historial()
        else:
            messagebox.showerror("Error al eliminar", msg)

    def _cambiar_envio(self, venta_id, estado):
        ok, msg = fn.cambiar_estado_envio(venta_id, estado)
        if ok:
            self._actualizar_historial()
        else:
            messagebox.showerror("Error", msg)


if __name__ == "__main__":
    app = AppCamisetas()
    app.mainloop()