
import os
import json
import sqlite3
import shutil
import hashlib
import secrets
from pathlib import Path
from datetime import datetime, timedelta
from io import BytesIO
from typing import Dict, Any, List, Optional

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from fpdf import FPDF

# ============================================================
# SISTEMA DE INSUMOS AL MAYOR V1
# Streamlit + SQLite + WooCommerce solo para stock e imagen
#
# Funciones:
# - Login admin/comprador
# - Categorías editables
# - Productos editables
# - Precios unidad/docena/bulto
# - Bulto configurable por producto
# - Peso interno por unidad base
# - Tasa proveedor manual
# - Tasa BCV manual/automática estilo BCV web
# - Stock e imagen desde WooCommerce por SKU
# - Catálogo tipo e-commerce con categorías, búsqueda, imagen 250x250
# - Ampliar imagen 500x500
# - Carrito
# - Generar cotización PDF sin descontar inventario
#
# IMPORTANTE:
# - WooCommerce se usa como fuente de stock e imagen, NO de precios.
# - El perfil Cliente BCV queda preparado pero inactivo/oculto por ahora.
# ============================================================

APP_NAME = "Sistema de Insumos al Mayor V56 Precio Especial por Presentación"
DB_NAME = "insumos_mayor_v1.db"

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
PDF_DIR = STATIC_DIR / "cotizaciones"
PAGOS_DIR = STATIC_DIR / "pagos"
BACKUP_DIR = STATIC_DIR / "backups"
for d in [STATIC_DIR, PDF_DIR, PAGOS_DIR, BACKUP_DIR]:
    d.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")

WC_URL = (os.getenv("WC_URL") or "").rstrip("/")
WC_KEY = os.getenv("WC_KEY") or ""
WC_SECRET = os.getenv("WC_SECRET") or ""

st.set_page_config(page_title=APP_NAME, layout="wide", page_icon="📦")

# -----------------------------
# ESTILOS
# -----------------------------
st.markdown("""
<style>
.block-container {padding-top: 1rem; padding-bottom: 2rem;}
.stApp {background:#ffffff !important;color:#111827;}
section[data-testid="stSidebar"] {background:#f8fafc !important;}
div[data-testid="stHeader"] {background:#ffffff !important;}

.card {
    border:1px solid #e5e7eb;
    border-radius:18px;
    padding:14px;
    background:#ffffff;
    box-shadow:0 2px 10px rgba(0,0,0,.05);
    margin-bottom:16px;
}
.product-card {
    border:1px solid #e5e7eb;
    border-radius:18px;
    padding:12px;
    background:#fff;
    box-shadow:0 2px 10px rgba(0,0,0,.045);
    height:100%;
}
.product-title {
    font-size:1rem;
    font-weight:850;
    color:#111827;
    line-height:1.2;
    min-height:42px;
}
.muted {color:#6b7280;font-size:.82rem;}
.price-main {font-size:1.15rem;font-weight:900;color:#111827;margin-top:4px;}
.price-bs {font-size:.85rem;color:#047857;font-weight:700;}
.badge {
    display:inline-block;
    padding:3px 8px;
    border-radius:999px;
    font-size:.75rem;
    font-weight:800;
}
.badge-ok {background:#dcfce7;color:#166534;}
.badge-no {background:#fee2e2;color:#991b1b;}
.badge-info {background:#e0f2fe;color:#075985;}
.sidebar-box {
    border:1px solid #e5e7eb;
    border-radius:14px;
    padding:12px;
    background:#fff;
}
.total-box {
    background:#f9fafb;
    border:1px solid #e5e7eb;
    border-radius:16px;
    padding:14px;
}
.admin-only {
    background:#fff7ed;
    border:1px solid #fed7aa;
    border-radius:12px;
    padding:10px;
    color:#9a3412;
}
button[kind="primary"] {border-radius:10px;}
div[data-testid="stDialog"] div[role="dialog"] {
    width: 90vw !important;
    max-width: 720px !important;
}
@media (max-width: 768px) {
    .block-container {padding-left:.7rem;padding-right:.7rem;}
}

/* Campos siempre visibles, pero solo widgets reales de Streamlit.
   Evita pintar bordes en elementos internos del catálogo/imágenes. */
div[data-testid="stTextInput"] div[data-baseweb="input"] > div,
div[data-testid="stNumberInput"] div[data-baseweb="input"] > div,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stTextArea"] div[data-baseweb="textarea"] > div,
div[data-testid="stDateInput"] div[data-baseweb="input"] > div {
    background-color: #ffffff !important;
    border: 1.4px solid #cbd5e1 !important;
    border-radius: 10px !important;
    box-shadow: none !important;
}

div[data-testid="stTextInput"] div[data-baseweb="input"] > div:hover,
div[data-testid="stNumberInput"] div[data-baseweb="input"] > div:hover,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover,
div[data-testid="stTextArea"] div[data-baseweb="textarea"] > div:hover,
div[data-testid="stDateInput"] div[data-baseweb="input"] > div:hover {
    border-color: #94a3b8 !important;
}

div[data-testid="stTextInput"] div[data-baseweb="input"] > div:focus-within,
div[data-testid="stNumberInput"] div[data-baseweb="input"] > div:focus-within,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within,
div[data-testid="stTextArea"] div[data-baseweb="textarea"] > div:focus-within,
div[data-testid="stDateInput"] div[data-baseweb="input"] > div:focus-within {
    border-color: #2a42ed !important;
    box-shadow: 0 0 0 2px rgba(42, 66, 237, 0.12) !important;
}

/* Number input buttons más limpios */
button[data-testid="stNumberInputStepUp"],
button[data-testid="stNumberInputStepDown"] {
    border-left: 1px solid #e2e8f0 !important;
    background: #f8fafc !important;
}

/* Checkboxes más visibles */
label[data-testid="stWidgetLabel"] {
    color: #0f172a !important;
    font-weight: 600 !important;
}

/* Contenedores de formularios */
div[data-testid="stForm"] {
    border: 1px solid #e2e8f0 !important;
    border-radius: 14px !important;
    background: #ffffff !important;
}

/* Botones con borde suave */
.stButton > button {
    border-radius: 10px !important;
    border: 1px solid #cbd5e1 !important;
}

/* Evita que elementos vacíos del layout se vean como separadores */
.product-card div:empty {
    border: none !important;
    background: transparent !important;
}


/* Burbuja ecommerce del carrito */
.cart-bubble-box {
    position: relative;
    border: 1px solid #dbeafe;
    background: linear-gradient(135deg, #eff6ff 0%, #ffffff 100%);
    border-radius: 16px;
    padding: 10px 12px;
    min-height: 76px;
    box-shadow: 0 2px 10px rgba(37, 99, 235, 0.08);
}

.cart-bubble-icon {
    font-size: 1.45rem;
    font-weight: 900;
    color: #1d4ed8;
    line-height: 1.1;
}

.cart-bubble-count {
    position: absolute;
    top: -9px;
    right: -7px;
    min-width: 26px;
    height: 26px;
    padding: 0 7px;
    border-radius: 999px;
    background: #ef4444;
    color: white;
    font-size: .78rem;
    font-weight: 900;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2px solid #ffffff;
    box-shadow: 0 2px 8px rgba(239, 68, 68, 0.35);
}

.cart-bubble-muted {
    color: #64748b;
    font-size: .78rem;
    font-weight: 600;
}

.cart-bubble-total {
    color: #047857;
    font-size: .95rem;
    font-weight: 900;
}

.cart-bubble-last {
    margin-top: 3px;
    color: #334155;
    font-size: .72rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}


/* ===== Catálogo en lista horizontal ===== */
.catalog-list-card {
    border: 1px solid #e2e8f0;
    border-radius: 18px;
    background: #ffffff;
    padding: 14px;
    margin-bottom: 14px;
    box-shadow: 0 2px 10px rgba(15, 23, 42, 0.045);
}

.catalog-list-card:hover {
    border-color: #bfdbfe;
    box-shadow: 0 8px 24px rgba(37, 99, 235, 0.08);
}

.catalog-image-frame {
    border: 1px solid #eef2f7;
    background: #fbfdff;
    border-radius: 14px;
    padding: 8px;
}

.catalog-list-title {
    font-size: 1.12rem;
    font-weight: 900;
    color: #0f172a;
    line-height: 1.16;
    margin-bottom: 4px;
}

.catalog-list-meta {
    color: #64748b;
    font-size: .84rem;
    margin-bottom: 8px;
}

.catalog-list-prices {
    border-top: 1px solid #f1f5f9;
    margin-top: 8px;
    padding-top: 8px;
}

.catalog-list-actions {
    border-left: 1px solid #eef2f7;
    padding-left: 14px;
}

.catalog-selection-box {
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    background: #f8fafc;
    padding: 8px 10px;
    margin: 8px 0;
}

.catalog-selection-title {
    font-size: .78rem;
    font-weight: 800;
    color: #64748b;
}

.catalog-selection-value {
    font-size: 1.08rem;
    font-weight: 900;
    color: #111827;
}

@media (max-width: 900px) {
    .catalog-list-actions {
        border-left: none;
        padding-left: 0;
    }
}


.actions-foot-note {
    margin-top: 8px;
    color: #64748b;
    font-size: .82rem;
    line-height: 1.3;
}

</style>
""", unsafe_allow_html=True)

# -----------------------------
# DB
# -----------------------------
@st.cache_resource
def get_conn():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def q(sql, params=(), fetch=False, many=False):
    conn = get_conn()
    cur = conn.cursor()
    if many:
        cur.executemany(sql, params)
    else:
        cur.execute(sql, params)
    conn.commit()
    if fetch:
        return cur.fetchall()
    return cur

def now():
    return datetime.now().strftime("%d/%m/%Y %H:%M")

def now_file():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def toast_ok(msg: str):
    try:
        st.toast(msg, icon="✅")
    except Exception:
        st.success(msg)

def set_feedback(msg: str, kind: str = "success"):
    st.session_state["_feedback_msg"] = msg
    st.session_state["_feedback_kind"] = kind

def show_feedback():
    msg = st.session_state.pop("_feedback_msg", None)
    kind = st.session_state.pop("_feedback_kind", "success")
    if not msg:
        return
    if kind == "warning":
        st.warning(msg)
    elif kind == "error":
        st.error(msg)
    elif kind == "info":
        st.info(msg)
    else:
        st.success(msg)

def carrito_resumen_texto(username: str):
    carrito = cargar_carrito(username)
    total_unidades = sum(int(i.get("unidades_base_total", 0) or 0) for i in carrito.values())
    total_usd = sum(float(i.get("precio_total", 0) or 0) for i in carrito.values())
    return len(carrito), total_unidades, total_usd

def texto_agregado_presentacion(presentacion: str, cantidad_presentacion: int, unidades_base_total: int):
    presentacion = str(presentacion or "unidad")
    cantidad_presentacion = int(cantidad_presentacion or 1)
    unidades_base_total = int(unidades_base_total or 0)

    if presentacion == "unidad":
        if unidades_base_total == 1:
            return "1 unidad"
        return f"{unidades_base_total} unidades"

    if presentacion == "docena":
        if cantidad_presentacion == 1:
            return "1 docena"
        return f"{cantidad_presentacion} docenas"

    if presentacion == "bulto":
        if cantidad_presentacion == 1:
            return "1 bulto"
        return f"{cantidad_presentacion} bultos"

    return f"{cantidad_presentacion} {presentacion}"

def set_last_cart_action(producto: str, presentacion: str, cantidad_presentacion: int, unidades_base_total: int):
    st.session_state["_cart_last_added"] = {
        "producto": str(producto or ""),
        "presentacion": presentacion,
        "cantidad_presentacion": int(cantidad_presentacion or 1),
        "unidades_base_total": int(unidades_base_total or 0),
        "texto": texto_agregado_presentacion(presentacion, cantidad_presentacion, unidades_base_total),
    }

def resumen_producto_en_carrito(username: str, sku: str):
    carrito = cargar_carrito(username)
    resumen = {
        "lineas": 0,
        "unidades": 0,
        "unidad": 0,
        "docena": 0,
        "bulto": 0,
        "total_usd": 0.0,
    }
    for item in carrito.values():
        if item.get("sku") != sku:
            continue
        resumen["lineas"] += 1
        resumen["unidades"] += int(item.get("unidades_base_total", 0) or 0)
        resumen["total_usd"] += float(item.get("precio_total", 0) or 0)
        pres = item.get("presentacion", "unidad")
        cant = int(item.get("cantidad_presentacion", 0) or 0)
        if pres in resumen:
            resumen[pres] += cant
    return resumen

def texto_resumen_producto_en_carrito(resumen):
    partes = []
    if resumen.get("unidad", 0):
        u = int(resumen["unidad"])
        partes.append(f"{u} unidad" if u == 1 else f"{u} unidades")
    if resumen.get("docena", 0):
        d = int(resumen["docena"])
        partes.append(f"{d} docena" if d == 1 else f"{d} docenas")
    if resumen.get("bulto", 0):
        b = int(resumen["bulto"])
        partes.append(f"{b} bulto" if b == 1 else f"{b} bultos")
    if not partes:
        return ""
    return " + ".join(partes)

def show_producto_carrito_badge(username: str, sku: str):
    resumen = resumen_producto_en_carrito(username, sku)
    texto = texto_resumen_producto_en_carrito(resumen)
    if not texto:
        st.markdown(
            """
            <div style="border:1px dashed #cbd5e1;border-radius:10px;padding:7px 9px;
                        color:#64748b;background:#f8fafc;font-size:.82rem;font-weight:700;text-align:center;">
                🛒 No agregado
            </div>
            """,
            unsafe_allow_html=True
        )
        return

    st.markdown(
        f"""
        <div style="border:1px solid #bbf7d0;border-radius:10px;padding:7px 9px;
                    color:#166534;background:#ecfdf5;font-size:.82rem;font-weight:900;text-align:center;">
            🛒 En carrito: {texto}<br>
            <span style="font-size:.76rem;color:#047857;">{resumen['unidades']} unidad(es) · {money_usd(resumen['total_usd'])}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

def show_last_cart_action():
    data = st.session_state.get("_cart_last_added")
    if not data:
        return
    texto = data.get("texto", "")
    producto = data.get("producto", "")
    unidades = int(data.get("unidades_base_total", 0) or 0)
    st.markdown(
        f"""
        <div style="margin: .35rem 0 1rem 0; padding: .75rem 1rem; border-radius: 12px;
                    background: #ecfdf5; border: 1px solid #a7f3d0; color: #065f46;">
            <div style="font-weight: 900; font-size: 1rem;">🛒 Agregado al carrito: {texto}</div>
            <div style="font-size: .92rem; margin-top: 2px;">{producto} · {unidades} unidad(es) base</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def show_cart_bubble(username: str):
    carrito = cargar_carrito(username)
    n_items, n_unidades, total_usd = carrito_resumen_texto(username)
    last = st.session_state.get("_cart_last_added") or {}
    last_txt = last.get("texto", "")
    last_prod = last.get("producto", "")

    if last_txt and last_prod:
        last_line = f"Último: {last_txt} · {last_prod}"
    elif n_items:
        last_line = "Listo para revisar pedido"
    else:
        last_line = "Sin productos agregados"

    st.markdown(
        f"""
        <div class="cart-bubble-box">
            <div class="cart-bubble-count">{n_items}</div>
            <div class="cart-bubble-icon">🛒 Carrito</div>
            <div class="cart-bubble-muted">{n_unidades} unidad(es) en total</div>
            <div class="cart-bubble-total">{money_usd(total_usd)}</div>
            <div class="cart-bubble-last">{last_line}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 180000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"

def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    if not stored.startswith("pbkdf2_sha256$"):
        return password == stored
    try:
        _, salt, hex_digest = stored.split("$", 2)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 180000).hex()
        return secrets.compare_digest(digest, hex_digest)
    except Exception:
        return False

def init_db():
    q("""
    CREATE TABLE IF NOT EXISTS usuarios (
        username TEXT PRIMARY KEY,
        password_hash TEXT,
        nombre TEXT,
        rol TEXT DEFAULT 'comprador',
        telefono TEXT,
        rif TEXT,
        direccion TEXT,
        ciudad TEXT,
        activo INTEGER DEFAULT 1,
        tipo_precio TEXT DEFAULT 'proveedor',
        creado_en TEXT
    )
    """)
    q("""
    CREATE TABLE IF NOT EXISTS categorias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT UNIQUE,
        descripcion TEXT,
        activa INTEGER DEFAULT 1,
        orden INTEGER DEFAULT 0,
        creado_en TEXT
    )
    """)
    q("""
    CREATE TABLE IF NOT EXISTS productos (
        sku TEXT PRIMARY KEY,
        descripcion TEXT,
        categoria_id INTEGER,
        unidad_base TEXT DEFAULT 'unidad',
        precio_unidad REAL DEFAULT 0,
        precio_docena REAL DEFAULT 0,
        precio_bulto REAL DEFAULT 0,
        bulto_contiene INTEGER DEFAULT 1,
        maneja_docena INTEGER DEFAULT 1,
        maneja_bulto INTEGER DEFAULT 1,
        peso_unidad_kg REAL DEFAULT 0,
        activo INTEGER DEFAULT 1,
        wc_product_id INTEGER,
        wc_nombre TEXT,
        wc_stock INTEGER DEFAULT 0,
        wc_stock_status TEXT,
        wc_imagen_url TEXT,
        wc_permalink TEXT,
        ultima_sync TEXT,
        creado_en TEXT,
        actualizado_en TEXT
    )
    """)
    q("""
    CREATE TABLE IF NOT EXISTS carritos (
        username TEXT PRIMARY KEY,
        data TEXT
    )
    """)
    q("""
    CREATE TABLE IF NOT EXISTS cotizaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        username TEXT,
        cliente_nombre TEXT,
        cliente_rif TEXT,
        cliente_telefono TEXT,
        cliente_direccion TEXT,
        items TEXT,
        subtotal_usd REAL DEFAULT 0,
        envio_usd REAL DEFAULT 0,
        total_usd REAL DEFAULT 0,
        tasa_proveedor REAL DEFAULT 0,
        tasa_bcv REAL DEFAULT 0,
        total_bs_proveedor REAL DEFAULT 0,
        peso_total_kg REAL DEFAULT 0,
        validez_dias INTEGER DEFAULT 1,
        status TEXT DEFAULT 'Pendiente',
        notas TEXT
    )
    """)

    q("""
    CREATE TABLE IF NOT EXISTS pedidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        username TEXT,
        cliente_nombre TEXT,
        cliente_rif TEXT,
        cliente_telefono TEXT,
        cliente_direccion TEXT,
        items TEXT,
        tipo_pago TEXT DEFAULT 'contado',
        metodo_pago TEXT,
        subtotal_usd REAL DEFAULT 0,
        envio_usd REAL DEFAULT 0,
        total_usd REAL DEFAULT 0,
        tasa_proveedor REAL DEFAULT 0,
        total_bs_proveedor REAL DEFAULT 0,
        peso_total_kg REAL DEFAULT 0,
        status TEXT DEFAULT 'Pendiente',
        credito_id INTEGER,
        notas TEXT
    )
    """)
    q("""
    CREATE TABLE IF NOT EXISTS creditos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_id INTEGER,
        username TEXT,
        cliente_nombre TEXT,
        fecha_inicio TEXT,
        fecha_vencimiento TEXT,
        monto_usd REAL DEFAULT 0,
        saldo_usd REAL DEFAULT 0,
        tasa_proveedor REAL DEFAULT 0,
        status TEXT DEFAULT 'Pendiente',
        notas TEXT
    )
    """)
    q("""
    CREATE TABLE IF NOT EXISTS abonos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        credito_id INTEGER,
        pedido_id INTEGER,
        username TEXT,
        fecha TEXT,
        monto_usd REAL DEFAULT 0,
        monto_bs REAL DEFAULT 0,
        metodo TEXT,
        referencia TEXT,
        comprobante_path TEXT,
        status TEXT DEFAULT 'Pendiente de validar',
        validado_por TEXT,
        fecha_validacion TEXT,
        notas TEXT
    )
    """)
    q("""
    CREATE TABLE IF NOT EXISTS configuracion (
        clave TEXT PRIMARY KEY,
        valor TEXT
    )
    """)

    q("""
    CREATE TABLE IF NOT EXISTS productos_vendedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT,
        vendedor_username TEXT,
        fecha_asignacion TEXT,
        notas TEXT,
        UNIQUE(sku, vendedor_username)
    )
    """)

    def set_default(clave, valor):
        exists = q("SELECT clave FROM configuracion WHERE clave=?", (clave,), fetch=True)
        if not exists:
            q("INSERT INTO configuracion (clave, valor) VALUES (?,?)", (clave, str(valor)))

    set_default("tasa_bcv", "0")
    set_default("tasa_proveedor", "0")
    set_default("fecha_tasa_bcv", "Sin actualizar")
    set_default("fuente_tasa_bcv", "Manual")
    set_default("nombre_empresa", "Sistema de Insumos al Mayor")
    set_default("telefono_empresa", "04127757053")
    set_default("instagram_empresa", "@color.insumos")
    set_default("validez_cotizacion_dias", "1")
    set_default("envio_ml_10_40_usd", "10")
    set_default("cliente_bcv_activo", "0")
    set_default("comision_mercadolibre_pct", "16")

    set_default("backup_folder", str(BACKUP_DIR))
    set_default("backup_auto_diario", "1")
    set_default("backup_ultima_fecha", "")
    set_default("dias_credito_default", "10")

    # Migraciones suaves
    def add_col(table, column, definition):
        cols = q(f"PRAGMA table_info({table})", fetch=True)
        if not any(c[1] == column for c in cols):
            q(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    add_col("usuarios", "credito_habilitado", "INTEGER DEFAULT 0")
    add_col("usuarios", "limite_credito_usd", "REAL DEFAULT 0")
    add_col("usuarios", "dias_credito", "INTEGER DEFAULT 10")
    add_col("usuarios", "ml_envio", "INTEGER DEFAULT 0")
    add_col("usuarios", "credito_bcv_habilitado", "INTEGER DEFAULT 0")
    add_col("usuarios", "cliente_especial", "INTEGER DEFAULT 0")
    add_col("usuarios", "id_usuario", "INTEGER DEFAULT 0")
    add_col("usuarios", "email", "TEXT")
    # Asignar id_usuario automático a usuarios existentes/importados que no lo tengan.
    rows_sin_id = q("SELECT username FROM usuarios WHERE COALESCE(id_usuario,0)=0 ORDER BY creado_en, username", fetch=True)
    if rows_sin_id:
        max_row = q("SELECT COALESCE(MAX(id_usuario),0) AS m FROM usuarios", fetch=True)[0]
        next_id = int(max_row["m"] or 0) + 1
        for _u in rows_sin_id:
            q("UPDATE usuarios SET id_usuario=? WHERE username=?", (next_id, _u["username"]))
            next_id += 1
    # Compatibilidad: si email está vacío, usar username cuando parezca correo.
    q("UPDATE usuarios SET email=username WHERE (email IS NULL OR email='') AND username LIKE '%@%'")
    add_col("productos", "costo_proveedor_unitario", "REAL DEFAULT 0")
    add_col("productos", "envio_costo_bulto", "REAL DEFAULT 0")
    add_col("productos", "otros_costos_bulto", "REAL DEFAULT 0")
    add_col("productos", "margen_minimo_pct", "REAL DEFAULT 25")
    add_col("productos", "pub_instagram", "INTEGER DEFAULT 0")
    add_col("productos", "pub_mercadolibre", "INTEGER DEFAULT 0")
    add_col("productos", "pub_marketplace", "INTEGER DEFAULT 0")
    add_col("productos", "pub_whatsapp", "INTEGER DEFAULT 0")
    add_col("productos", "pub_web", "INTEGER DEFAULT 0")
    add_col("productos", "maneja_precio_especial", "INTEGER DEFAULT 0")
    add_col("productos", "precio_especial_unidad", "REAL DEFAULT 0")
    add_col("productos", "precio_especial_docena", "REAL DEFAULT 0")
    add_col("productos", "precio_especial_bulto", "REAL DEFAULT 0")
    add_col("productos", "link_instagram", "TEXT")
    add_col("productos", "link_mercadolibre", "TEXT")
    add_col("productos", "link_marketplace", "TEXT")
    add_col("productos", "link_whatsapp", "TEXT")
    add_col("productos", "notas_publicacion", "TEXT")
    add_col("pedidos", "pos_procesado", "INTEGER DEFAULT 0")
    add_col("pedidos", "pos_fecha", "TEXT")
    add_col("pedidos", "pos_usuario", "TEXT")
    add_col("pedidos", "pos_notas", "TEXT")

    # Fix38: Crédito BCV + presentación intermedia flexible
    add_col("productos", "presentacion_intermedia_nombre", "TEXT DEFAULT 'Docena'")
    add_col("productos", "presentacion_intermedia_cantidad", "INTEGER DEFAULT 12")

    add_col("pedidos", "tasa_bcv", "REAL DEFAULT 0")
    add_col("pedidos", "credito_tipo", "TEXT DEFAULT 'usd'")
    add_col("pedidos", "total_bcv_credito", "REAL DEFAULT 0")

    add_col("creditos", "tipo_credito", "TEXT DEFAULT 'usd'")
    add_col("creditos", "tasa_bcv_creacion", "REAL DEFAULT 0")
    add_col("creditos", "monto_bcv", "REAL DEFAULT 0")
    add_col("creditos", "saldo_bcv", "REAL DEFAULT 0")
    add_col("creditos", "total_bs_base", "REAL DEFAULT 0")

    add_col("abonos", "tipo_credito", "TEXT DEFAULT 'usd'")
    add_col("abonos", "monto_bcv", "REAL DEFAULT 0")
    add_col("abonos", "tasa_bcv", "REAL DEFAULT 0")
    add_col("abonos", "monto_bs_esperado", "REAL DEFAULT 0")

    set_default("stock_auto_sync_minutos", "60")

    # Categorías iniciales:
    # Se crean una sola vez. Antes se recreaban en cada arranque si el admin las borraba.
    categorias_flag = q("SELECT valor FROM configuracion WHERE clave='categorias_iniciales_creadas'", fetch=True)
    if not categorias_flag:
        existentes = q("SELECT COUNT(*) AS n FROM categorias", fetch=True)[0]["n"]
        if int(existentes or 0) == 0:
            for i, cat in enumerate(["Papeles", "Stickers", "Sublimación", "Tintas", "Rollos", "Equipos", "General"], start=1):
                q("INSERT OR IGNORE INTO categorias (nombre, descripcion, activa, orden, creado_en) VALUES (?,?,?,?,?)",
                  (cat, "", 1, i, now()))
        q("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?,?)", ("categorias_iniciales_creadas", "1"))

    # Admin inicial
    admin = q("SELECT username FROM usuarios WHERE username=?", ("colorinsumos@gmail.com",), fetch=True)
    if not admin:
        q("""INSERT INTO usuarios (username,password_hash,nombre,rol,telefono,activo,tipo_precio,creado_en)
             VALUES (?,?,?,?,?,?,?,?)""",
          ("colorinsumos@gmail.com", hash_password("20880157"), "Administrador", "admin", "04127757053", 1, "proveedor", now()))

init_db()

# -----------------------------
# CONFIG / MONEY
# -----------------------------
def get_config(clave, default=""):
    row = q("SELECT valor FROM configuracion WHERE clave=?", (clave,), fetch=True)
    return row[0]["valor"] if row else default

def set_config(clave, valor):
    q("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?,?)", (clave, str(valor)))

def parse_float(v, default=0.0):
    try:
        if v is None:
            return default
        s = str(v).replace("$", "").replace("Bs", "").strip()
        if s.count(",") == 1 and s.count(".") > 1:
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", ".")
        return float(s)
    except Exception:
        return default

def money_usd(x):
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return "$0.00"

def money_bs(x):
    """Formato venezolano: puntos para miles y coma para decimales. Ej: Bs. 1.224,00"""
    try:
        s = f"{float(x):,.2f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"Bs. {s}"
    except Exception:
        return "Bs. 0,00"

def get_tasa_proveedor():
    return parse_float(get_config("tasa_proveedor", "0"), 0)

def get_tasa_bcv():
    return parse_float(get_config("tasa_bcv", "0"), 0)


def calc_costos_margen(prod):
    bulto_contiene = max(1, int(prod["bulto_contiene"] or 1))
    costo_unit = float(prod["costo_proveedor_unitario"] or 0)
    envio_bulto = float(prod["envio_costo_bulto"] or 0)
    otros_bulto = float(prod["otros_costos_bulto"] or 0)
    costo_logistico_unit = (envio_bulto + otros_bulto) / bulto_contiene
    costo_real_unit = costo_unit + costo_logistico_unit

    def margen(precio_unit):
        precio_unit = float(precio_unit or 0)
        gan = precio_unit - costo_real_unit
        pct = (gan / precio_unit * 100) if precio_unit > 0 else 0
        return {"precio": precio_unit, "ganancia": gan, "margen_pct": pct}

    unidad = margen(prod["precio_unidad"])
    docena = margen(prod["precio_docena"])
    bulto = margen(prod["precio_bulto"])

    ingreso_bulto = float(prod["precio_bulto"] or 0) * bulto_contiene
    costo_bulto = costo_unit * bulto_contiene + envio_bulto + otros_bulto
    gan_bulto_total = ingreso_bulto - costo_bulto
    margen_bulto_total = (gan_bulto_total / ingreso_bulto * 100) if ingreso_bulto > 0 else 0

    return {
        "bulto_contiene": bulto_contiene,
        "costo_proveedor_unitario": costo_unit,
        "envio_bulto": envio_bulto,
        "otros_bulto": otros_bulto,
        "costo_logistico_unitario": costo_logistico_unit,
        "costo_real_unitario": costo_real_unit,
        "unidad": unidad,
        "docena": docena,
        "bulto": bulto,
        "ingreso_bulto": ingreso_bulto,
        "costo_bulto": costo_bulto,
        "ganancia_bulto_total": gan_bulto_total,
        "margen_bulto_total": margen_bulto_total,
    }


def calcular_valor_inventario_producto(prod):
    stock = int(prod["wc_stock"] or 0)
    m = calc_costos_margen(prod)
    costo_real = float(m["costo_real_unitario"] or 0)

    valor_costo = stock * costo_real
    valor_venta_unidad = stock * float(prod["precio_unidad"] or 0)
    valor_venta_docena = stock * float(prod["precio_docena"] or 0)
    valor_venta_bulto = stock * float(prod["precio_bulto"] or 0)

    bulto_contiene = max(1, int(prod["bulto_contiene"] or 1))
    return {
        "stock": stock,
        "bulto_contiene": bulto_contiene,
        "bultos_disp": stock // bulto_contiene,
        "resto": stock % bulto_contiene,
        "costo_real_unitario": costo_real,
        "valor_costo": valor_costo,
        "valor_venta_unidad": valor_venta_unidad,
        "valor_venta_docena": valor_venta_docena,
        "valor_venta_bulto": valor_venta_bulto,
        "gan_unidad": valor_venta_unidad - valor_costo,
        "gan_docena": valor_venta_docena - valor_costo,
        "gan_bulto": valor_venta_bulto - valor_costo,
    }

def etiqueta_margen(pct, minimo=25):
    pct = float(pct or 0)
    minimo = float(minimo or 0)
    if pct < minimo:
        return "⚠️ Bajo"
    if pct < minimo + 10:
        return "🟡 Aceptable"
    return "✅ Saludable"


def precio_sugerido_por_margen(costo_real_unitario, margen_objetivo_pct):
    """
    Precio sugerido usando margen sobre precio de venta:
    margen = (precio - costo) / precio
    precio = costo / (1 - margen)
    """
    costo = float(costo_real_unitario or 0)
    pct = max(0.0, min(95.0, float(margen_objetivo_pct or 0))) / 100
    if costo <= 0:
        return 0.0
    if pct >= 0.95:
        pct = 0.95
    return costo / (1 - pct)


def get_comision_ml_pct():
    return parse_float(get_config("comision_mercadolibre_pct", "16"), 16)

def precio_ml_bs(precio_divisas):
    """
    Fórmula MercadoLibre:
    Precio divisas x tasa proveedor = base Bs
    base Bs + % comisión ML = precio sugerido Bs para publicar.
    """
    tasa = get_tasa_proveedor()
    comision = get_comision_ml_pct() / 100
    base_bs = float(precio_divisas or 0) * tasa
    return base_bs * (1 + comision)

def precio_ml_resumen(precio_divisas):
    bs = precio_ml_bs(precio_divisas)
    tasa_bcv = get_tasa_bcv()
    usd_bcv_equiv = bs / tasa_bcv if tasa_bcv > 0 else 0
    return bs, usd_bcv_equiv

def resumen_publicacion_icons(prod):
    return " ".join([
        "🌐" if int(prod["pub_web"] or 0) else "▫️",
        "📸" if int(prod["pub_instagram"] or 0) else "▫️",
        "🛒" if int(prod["pub_mercadolibre"] or 0) else "▫️",
        "📍" if int(prod["pub_marketplace"] or 0) else "▫️",
        "💬" if int(prod["pub_whatsapp"] or 0) else "▫️",
    ])

def pendientes_publicacion(prod):
    pend = []
    if not int(prod["pub_instagram"] or 0): pend.append("Instagram")
    if not int(prod["pub_mercadolibre"] or 0): pend.append("MercadoLibre")
    if not int(prod["pub_marketplace"] or 0): pend.append("Marketplace")
    if not int(prod["pub_whatsapp"] or 0): pend.append("WhatsApp")
    if not int(prod["pub_web"] or 0): pend.append("Web")
    return pend

def pedido_items_rows(pedido_row):
    """Convierte el JSON de items de pedido/cotización en filas legibles."""
    rows = []
    try:
        items = json.loads(pedido_row["items"] or "{}")
    except Exception:
        items = {}
    for _, it in items.items():
        rows.append({
            "SKU": it.get("sku", ""),
            "Producto": it.get("desc", ""),
            "Presentación": it.get("presentacion", ""),
            "Cantidad": int(it.get("cantidad_presentacion", 0) or 0),
            "Unidades": int(it.get("unidades_base_total", 0) or 0),
            "Subtotal USD": float(it.get("precio_total", 0) or 0),
        })
    return rows

def productos_mas_comprados_por_usuario(username):
    pedidos = q("SELECT * FROM pedidos WHERE username=? AND status NOT IN ('Cancelado','Anulado')", (username,), fetch=True)
    acum = {}
    for p in pedidos:
        for it in pedido_items_rows(p):
            sku = it["SKU"]
            if not sku:
                continue
            if sku not in acum:
                acum[sku] = {"SKU": sku, "Producto": it["Producto"], "Unidades": 0, "Total USD": 0.0, "Veces": 0}
            acum[sku]["Unidades"] += int(it["Unidades"] or 0)
            acum[sku]["Total USD"] += float(it["Subtotal USD"] or 0)
            acum[sku]["Veces"] += 1
    return sorted(acum.values(), key=lambda x: x["Total USD"], reverse=True)

def productos_alertas_margen():
    rows = q("""SELECT p.*, c.nombre AS categoria
                FROM productos p LEFT JOIN categorias c ON p.categoria_id=c.id
                WHERE p.activo=1
                ORDER BY c.nombre, p.descripcion""", fetch=True)
    data = []
    for p in rows:
        m = calc_costos_margen(p)
        minimo = float(p["margen_minimo_pct"] or 25)
        problemas = []
        if float(p["costo_proveedor_unitario"] or 0) <= 0:
            problemas.append("Sin costo proveedor")
        if int(p["maneja_docena"] or 0) and float(p["precio_docena"] or 0) <= 0:
            problemas.append("Sin precio docena")
        if int(p["maneja_bulto"] or 0) and float(p["precio_bulto"] or 0) <= 0:
            problemas.append("Sin precio bulto")
        if m["unidad"]["margen_pct"] < minimo and float(p["precio_unidad"] or 0) > 0:
            problemas.append("Margen unidad bajo")
        if int(p["maneja_docena"] or 0) and m["docena"]["margen_pct"] < minimo and float(p["precio_docena"] or 0) > 0:
            problemas.append("Margen docena bajo")
        if int(p["maneja_bulto"] or 0) and m["bulto"]["margen_pct"] < minimo and float(p["precio_bulto"] or 0) > 0:
            problemas.append("Margen bulto bajo")
        if not p["wc_imagen_url"]:
            problemas.append("Sin foto")
        if int(p["wc_stock"] or 0) <= 0:
            problemas.append("Sin stock web")

        if problemas:
            data.append({
                "Categoría": p["categoria"] or "Sin categoría",
                "SKU": p["sku"],
                "Producto": p["descripcion"],
                "Costo real c/u": round(m["costo_real_unitario"], 2),
                "Unidad %": round(m["unidad"]["margen_pct"], 1),
                "Docena %": round(m["docena"]["margen_pct"], 1),
                "Bulto %": round(m["bulto"]["margen_pct"], 1),
                "Mínimo %": minimo,
                "Alertas": ", ".join(problemas),
            })
    return data

# -----------------------------
# WOO
# -----------------------------
def wc_ready():
    return bool(WC_URL and WC_KEY and WC_SECRET)

def wc_get_by_sku(sku: str) -> Optional[Dict[str, Any]]:
    if not wc_ready():
        raise RuntimeError("Faltan WC_URL, WC_KEY o WC_SECRET en .env")
    url = f"{WC_URL}/wp-json/wc/v3/products"
    params = {
        "consumer_key": WC_KEY,
        "consumer_secret": WC_SECRET,
        "sku": sku.strip(),
        "per_page": 20,
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list) or not data:
        return None
    return data[0]

def first_image_url(product):
    images = product.get("images") or []
    if images and isinstance(images, list):
        return images[0].get("src")
    return None

def sync_producto_wc(sku: str):
    p = wc_get_by_sku(sku)
    if not p:
        return False, "No encontrado en WooCommerce"
    stock_q = p.get("stock_quantity")
    stock = 0 if stock_q is None else int(float(stock_q))
    q("""UPDATE productos
         SET wc_product_id=?, wc_nombre=?, wc_stock=?, wc_stock_status=?, wc_imagen_url=?, wc_permalink=?, ultima_sync=?, actualizado_en=?
         WHERE sku=?""",
      (p.get("id"), p.get("name") or "", stock, p.get("stock_status") or "", first_image_url(p), p.get("permalink") or "", now(), now(), sku))
    return True, f"Sincronizado: stock {stock}"

def sync_todos_productos(progress_bar=None, status_box=None):
    rows = q("SELECT sku FROM productos WHERE activo=1", fetch=True)
    total = len(rows)
    ok = 0
    no = 0
    errors = []
    for i, r in enumerate(rows, start=1):
        try:
            if status_box is not None:
                status_box.info(f"Sincronizando stock WooCommerce {i}/{total}: {r['sku']}")
            if progress_bar is not None and total:
                progress_bar.progress(min(i / total, 1.0))
            success, msg = sync_producto_wc(r["sku"])
            if success:
                ok += 1
            else:
                no += 1
        except Exception as e:
            no += 1
            errors.append(f"{r['sku']}: {e}")
    return ok, no, errors[:10]

# -----------------------------
# BCV SIMPLE
# -----------------------------
def obtener_bcv_web():
    # Método simple compatible con BCV actual del sistema Pointer.
    import re
    from bs4 import BeautifulSoup
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    headers = {"User-Agent": "Mozilla/5.0"}
    urls = [
        "https://www.bcv.org.ve/",
        "https://www.bcv.org.ve/seccionportal/tipo-de-cambio-oficial-del-bcv",
        "http://www.bcv.org.ve/",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=headers, verify=False, timeout=15)
            if not r.ok:
                continue
            if not r.encoding or r.encoding.lower() == "iso-8859-1":
                r.encoding = r.apparent_encoding or "utf-8"
            soup = BeautifulSoup(r.text, "html.parser")
            box = soup.find("div", {"id": "dolar"})
            if box:
                strong = box.find("strong")
                if strong:
                    val = parse_float(strong.get_text(strip=True), 0)
                    if val > 1:
                        return val, "BCV oficial"
            m = re.search(r'id=["\']dolar["\'][\s\S]{0,3000}?<strong[^>]*>\s*([0-9\.,]+)\s*</strong>', r.text, re.I)
            if m:
                val = parse_float(m.group(1), 0)
                if val > 1:
                    return val, "BCV oficial"
        except Exception:
            continue
    return None, "No se pudo consultar BCV"

# -----------------------------
# DATA HELPERS
# -----------------------------
def get_user(username):
    rows = q("SELECT * FROM usuarios WHERE username=?", (username,), fetch=True)
    return rows[0] if rows else None

def categorias_activas():
    return q("SELECT * FROM categorias WHERE activa=1 ORDER BY orden, nombre", fetch=True)

def categorias_todas():
    return q("SELECT * FROM categorias ORDER BY activa DESC, orden, nombre", fetch=True)

def categoria_nombre(cat_id):
    if not cat_id:
        return "Sin categoría"
    rows = q("SELECT nombre FROM categorias WHERE id=?", (cat_id,), fetch=True)
    return rows[0]["nombre"] if rows else "Sin categoría"

def cargar_carrito(username):
    row = q("SELECT data FROM carritos WHERE username=?", (username,), fetch=True)
    if not row or not row[0]["data"]:
        return {}
    try:
        return json.loads(row[0]["data"])
    except Exception:
        return {}

def guardar_carrito(username, data):
    q("INSERT OR REPLACE INTO carritos (username, data) VALUES (?,?)", (username, json.dumps(data, ensure_ascii=False)))

def limpiar_carrito(username):
    q("DELETE FROM carritos WHERE username=?", (username,))


def usuario_siguiente_id():
    row = q("SELECT COALESCE(MAX(id_usuario),0) AS m FROM usuarios", fetch=True)[0]
    return int(row["m"] or 0) + 1

def username_existe(username, excluir_username=None):
    username = (username or "").strip()
    if not username:
        return False
    if excluir_username:
        rows = q("SELECT username FROM usuarios WHERE username=? AND username<>?", (username, excluir_username), fetch=True)
    else:
        rows = q("SELECT username FROM usuarios WHERE username=?", (username,), fetch=True)
    return bool(rows)

def email_existe(email, excluir_username=None):
    email = (email or "").strip()
    if not email:
        return False
    if excluir_username:
        rows = q("SELECT username FROM usuarios WHERE email=? AND username<>?", (email, excluir_username), fetch=True)
    else:
        rows = q("SELECT username FROM usuarios WHERE email=?", (email,), fetch=True)
    return bool(rows)

def actualizar_referencias_username(username_old, username_new):
    """Actualiza referencias históricas cuando admin cambia el username."""
    username_old = (username_old or "").strip()
    username_new = (username_new or "").strip()
    if not username_old or not username_new or username_old == username_new:
        return
    tablas = ["pedidos", "creditos", "abonos", "cotizaciones", "carritos"]
    for tabla in tablas:
        try:
            q(f"UPDATE {tabla} SET username=? WHERE username=?", (username_new, username_old))
        except Exception:
            pass
    try:
        q("UPDATE productos_vendedores SET vendedor_username=? WHERE vendedor_username=?", (username_new, username_old))
    except Exception:
        pass
    # Si el usuario editado es el que está conectado, refrescar sesión.
    try:
        if st.session_state.user and st.session_state.user.get("username") == username_old:
            st.session_state.user["username"] = username_new
    except Exception:
        pass

def crear_usuario_admin(username, password, nombre, rol, telefono, rif, ciudad, direccion, email, cliente_especial, credito_hab, credito_bcv_hab, ml_envio, limite, dias, activo):
    username = (username or "").strip()
    email = (email or "").strip()
    if not username or not nombre:
        return False, "Usuario y nombre son obligatorios."
    if username_existe(username):
        return False, "Ese usuario ya existe. Usa Actualizar usuario existente si deseas editarlo."
    if email and email_existe(email):
        return False, "Ese correo ya está usado por otro usuario."
    q("""INSERT INTO usuarios
         (id_usuario,username,password_hash,nombre,rol,telefono,rif,ciudad,direccion,email,activo,tipo_precio,cliente_especial,credito_habilitado,credito_bcv_habilitado,ml_envio,limite_credito_usd,dias_credito,creado_en)
         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (usuario_siguiente_id(), username, hash_password(password or "1234"), nombre, rol, telefono, rif, ciudad, direccion, email, 1 if activo else 0, "proveedor", 1 if cliente_especial else 0, 1 if credito_hab else 0, 1 if credito_bcv_hab else 0, 1 if ml_envio else 0, limite, int(dias), now()))
    return True, f"Usuario creado: {nombre} ({username})."

def actualizar_usuario_admin(username_original, username_new, nombre, rol, telefono, rif, ciudad, direccion, email, cliente_especial, credito_hab, credito_bcv_hab, ml_envio, limite, dias, activo, password=""):
    username_original = (username_original or "").strip()
    username_new = (username_new or "").strip()
    email = (email or "").strip()
    if not username_original:
        return False, "Selecciona un usuario existente para actualizar."
    if not username_new or not nombre:
        return False, "Usuario y nombre son obligatorios."
    if username_new != username_original and username_existe(username_new, excluir_username=username_original):
        return False, "El nuevo username ya existe en otro usuario."
    if email and email_existe(email, excluir_username=username_original):
        return False, "Ese correo ya está usado por otro usuario."

    if username_new != username_original:
        q("UPDATE usuarios SET username=? WHERE username=?", (username_new, username_original))
        actualizar_referencias_username(username_original, username_new)

    if password:
        q("""UPDATE usuarios SET password_hash=?, nombre=?, rol=?, telefono=?, rif=?, ciudad=?, direccion=?, email=?,
             cliente_especial=?, credito_habilitado=?, credito_bcv_habilitado=?, ml_envio=?, limite_credito_usd=?, dias_credito=?, activo=? WHERE username=?""",
          (hash_password(password), nombre, rol, telefono, rif, ciudad, direccion, email,
           1 if cliente_especial else 0, 1 if credito_hab else 0, 1 if credito_bcv_hab else 0, 1 if ml_envio else 0, limite, int(dias), 1 if activo else 0, username_new))
    else:
        q("""UPDATE usuarios SET nombre=?, rol=?, telefono=?, rif=?, ciudad=?, direccion=?, email=?,
             cliente_especial=?, credito_habilitado=?, credito_bcv_habilitado=?, ml_envio=?, limite_credito_usd=?, dias_credito=?, activo=? WHERE username=?""",
          (nombre, rol, telefono, rif, ciudad, direccion, email,
           1 if cliente_especial else 0, 1 if credito_hab else 0, 1 if credito_bcv_hab else 0, 1 if ml_envio else 0, limite, int(dias), 1 if activo else 0, username_new))
    return True, f"Usuario actualizado: {nombre} ({username_new})."

def save_uploaded_file(uploaded, folder: Path, prefix="file"):
    if uploaded is None:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    ext = Path(uploaded.name).suffix.lower()
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", Path(uploaded.name).stem)
    path = folder / f"{prefix}_{now_file()}_{safe}{ext}"
    with open(path, "wb") as f:
        f.write(uploaded.getbuffer())
    return str(path)

def crear_respaldo(destino=None):
    """
    Crea respaldo JSON + copia .db.
    Si destino apunta a una carpeta sincronizada de Google Drive Desktop,
    Drive lo subirá automáticamente.
    """
    destino = Path(destino or get_config("backup_folder", str(BACKUP_DIR)))
    destino.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    tablas = ["usuarios", "categorias", "productos", "cotizaciones", "pedidos", "creditos", "abonos", "configuracion"]
    data = {}
    for t in tablas:
        try:
            df = pd.read_sql_query(f"SELECT * FROM {t}", get_conn())
            data[t] = df.to_dict(orient="records")
        except Exception as e:
            data[t] = {"error": str(e)}

    json_path = destino / f"backup_insumos_mayor_{stamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    db_path = destino / f"backup_insumos_mayor_{stamp}.db"
    try:
        shutil.copy2(DB_NAME, db_path)
    except Exception:
        db_path = None

    set_config("backup_ultima_fecha", datetime.now().strftime("%Y-%m-%d"))
    return str(json_path), str(db_path) if db_path else ""


def importar_respaldo_json(uploaded_file, modo="fusionar"):
    """
    Importa un respaldo JSON generado por crear_respaldo.
    modo='fusionar': inserta/actualiza por claves naturales cuando aplica.
    modo='reemplazar': limpia tablas comerciales antes de importar.
    """
    if uploaded_file is None:
        return False, "No se seleccionó archivo."

    data = json.load(uploaded_file)

    tablas = ["categorias", "usuarios", "productos", "cotizaciones", "pedidos", "creditos", "abonos", "configuracion"]

    if modo == "reemplazar":
        for t in ["abonos", "creditos", "pedidos", "cotizaciones", "productos", "categorias"]:
            try:
                q(f"DELETE FROM {t}")
            except Exception:
                pass
        # usuarios y configuración se fusionan para no bloquear acceso admin.

    contadores = {}
    for tabla in tablas:
        rows = data.get(tabla, [])
        if not isinstance(rows, list):
            continue
        contadores[tabla] = 0
        for row in rows:
            if not isinstance(row, dict) or not row:
                continue
            cols = list(row.keys())
            vals = [row[c] for c in cols]
            placeholders = ",".join(["?"] * len(cols))
            col_sql = ",".join(cols)
            update_sql = ",".join([f"{c}=excluded.{c}" for c in cols])

            # INSERT OR REPLACE sería peligroso con ids; usamos ON CONFLICT si la tabla tiene PK compatible.
            try:
                if tabla == "usuarios" and "username" in row:
                    sql = f"INSERT INTO {tabla} ({col_sql}) VALUES ({placeholders}) ON CONFLICT(username) DO UPDATE SET {update_sql}"
                elif tabla == "productos" and "sku" in row:
                    sql = f"INSERT INTO {tabla} ({col_sql}) VALUES ({placeholders}) ON CONFLICT(sku) DO UPDATE SET {update_sql}"
                elif tabla == "categorias" and "nombre" in row:
                    sql = f"INSERT INTO {tabla} ({col_sql}) VALUES ({placeholders}) ON CONFLICT(nombre) DO UPDATE SET {update_sql}"
                elif tabla == "configuracion" and "clave" in row:
                    sql = f"INSERT INTO {tabla} ({col_sql}) VALUES ({placeholders}) ON CONFLICT(clave) DO UPDATE SET {update_sql}"
                elif "id" in row:
                    sql = f"INSERT OR REPLACE INTO {tabla} ({col_sql}) VALUES ({placeholders})"
                else:
                    sql = f"INSERT INTO {tabla} ({col_sql}) VALUES ({placeholders})"
                q(sql, vals)
                contadores[tabla] += 1
            except Exception as e:
                # Sigue con los demás registros para no abortar todo por una fila vieja.
                pass

    return True, "Importación completada: " + ", ".join([f"{k}: {v}" for k, v in contadores.items()])

def exportar_json_actual():
    destino = BACKUP_DIR
    json_path, db_path = crear_respaldo(destino)
    with open(json_path, "rb") as f:
        content = f.read()
    return content, Path(json_path).name

def backup_auto_si_corresponde():
    if get_config("backup_auto_diario", "1") != "1":
        return
    hoy = datetime.now().strftime("%Y-%m-%d")
    if get_config("backup_ultima_fecha", "") != hoy:
        try:
            crear_respaldo()
        except Exception:
            pass

def usuarios_visibles_para(user):
    if user["rol"] == "admin":
        rows = q("SELECT username FROM usuarios", fetch=True)
        return [r["username"] for r in rows]
    return [user["username"]]

def crear_pedido_desde_carrito(user, carrito, tipo_pago, metodo_pago, envio_usd, notas, cliente_extra=None, tipo_credito="usd", cliente_target_username=None):
    if not carrito:
        return None, "Carrito vacío."

    cliente_extra = cliente_extra or {}
    target_user = get_user(cliente_target_username) if cliente_target_username else user
    if not target_user:
        target_user = user

    # Recalcular precios con el cliente final antes de crear el pedido.
    # Esto permite aplicar Precio Especial si el pedido lo arma admin para un cliente especial.
    carrito_recalc = {}
    for k, v in carrito.items():
        carrito_recalc[k] = recalcular_item_carrito(v, user=target_user)
    carrito = carrito_recalc

    ok_stock, stock_msgs = validar_stock_carrito_woocommerce(carrito)
    if not ok_stock:
        return None, "No se puede crear pedido por stock insuficiente:\n" + "\n".join(stock_msgs)

    t = calcular_carrito(carrito)
    subtotal = float(t["subtotal"])
    total = subtotal + float(envio_usd or 0)
    tasa = get_tasa_proveedor()
    tasa_bcv = get_tasa_bcv()

    username = target_user["username"]
    cliente_nombre = cliente_extra.get("cliente_nombre") or target_user["nombre"] or username
    cliente_rif = cliente_extra.get("cliente_rif") or target_user["rif"] or ""
    cliente_tel = cliente_extra.get("cliente_telefono") or target_user["telefono"] or ""
    cliente_dir = cliente_extra.get("cliente_direccion") or target_user["direccion"] or ""

    credito_tipo = "bcv" if tipo_pago == "credito" and str(tipo_credito).lower() == "bcv" else "usd"
    total_bs_base = total * tasa
    total_bcv_credito = (total_bs_base / tasa_bcv) if credito_tipo == "bcv" and tasa_bcv > 0 else 0.0

    if tipo_pago == "credito" and user["rol"] != "admin" and int(target_user["credito_habilitado"] or 0) != 1:
        return None, "Este cliente no tiene crédito habilitado."
    if credito_tipo == "bcv":
        if int(target_user["credito_bcv_habilitado"] if "credito_bcv_habilitado" in target_user.keys() and target_user["credito_bcv_habilitado"] is not None else 0) != 1 and user["rol"] != "admin":
            return None, "Este cliente no tiene Crédito BCV habilitado."
        if tasa_bcv <= 0:
            return None, "No se puede crear Crédito BCV porque la tasa BCV está en cero. Actualiza la tasa BCV primero."

    q("""INSERT INTO pedidos
         (fecha, username, cliente_nombre, cliente_rif, cliente_telefono, cliente_direccion, items,
          tipo_pago, metodo_pago, subtotal_usd, envio_usd, total_usd, tasa_proveedor, tasa_bcv,
          total_bs_proveedor, peso_total_kg, status, notas, credito_tipo, total_bcv_credito)
         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (now(), username, cliente_nombre, cliente_rif, cliente_tel, cliente_dir, json.dumps(carrito, ensure_ascii=False),
       tipo_pago, metodo_pago, subtotal, float(envio_usd or 0), total, tasa, tasa_bcv,
       total_bs_base, t["peso_total_kg"],
       "Crédito / Pendiente de pago" if tipo_pago == "credito" else "Pendiente de pago",
       notas, credito_tipo, total_bcv_credito))
    pedido_id = q("SELECT last_insert_rowid() AS id", fetch=True)[0]["id"]

    credito_id = None
    if tipo_pago == "credito":
        dias = int(target_user["dias_credito"] or parse_float(get_config("dias_credito_default", "10"), 10))
        venc = (datetime.now() + timedelta(days=dias)).strftime("%d/%m/%Y")
        if credito_tipo == "bcv":
            nota_credito = (
                "Crédito BCV creado desde pedido. "
                "El saldo se expresa en $ BCV y se cancela en bolívares a la tasa BCV vigente del día en que se registre cada pago."
            )
            q("""INSERT INTO creditos
                 (pedido_id, username, cliente_nombre, fecha_inicio, fecha_vencimiento,
                  monto_usd, saldo_usd, tasa_proveedor, status, notas,
                  tipo_credito, tasa_bcv_creacion, monto_bcv, saldo_bcv, total_bs_base)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (pedido_id, username, cliente_nombre, now(), venc,
               total_bcv_credito, total_bcv_credito, tasa, "Pendiente", nota_credito,
               "bcv", tasa_bcv, total_bcv_credito, total_bcv_credito, total_bs_base))
        else:
            q("""INSERT INTO creditos
                 (pedido_id, username, cliente_nombre, fecha_inicio, fecha_vencimiento,
                  monto_usd, saldo_usd, tasa_proveedor, status, notas,
                  tipo_credito, tasa_bcv_creacion, monto_bcv, saldo_bcv, total_bs_base)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (pedido_id, username, cliente_nombre, now(), venc,
               total, total, tasa, "Pendiente", "Crédito creado desde pedido.",
               "usd", tasa_bcv, 0, 0, total_bs_base))
        credito_id = q("SELECT last_insert_rowid() AS id", fetch=True)[0]["id"]
        q("UPDATE pedidos SET credito_id=?, status='Crédito / Pendiente de pago' WHERE id=?", (credito_id, pedido_id))
    else:
        q("UPDATE pedidos SET status='Pendiente de pago' WHERE id=?", (pedido_id,))

    limpiar_carrito(user["username"])
    return pedido_id, "Pedido creado."

def aplicar_abono_validado(abono_id, admin_username):
    rows = q("SELECT * FROM abonos WHERE id=?", (abono_id,), fetch=True)
    if not rows:
        return False, "Abono no encontrado."
    ab = rows[0]
    if ab["status"] == "Validado":
        return False, "El abono ya fue validado."

    cr_rows = q("SELECT * FROM creditos WHERE id=?", (ab["credito_id"],), fetch=True)
    if not cr_rows:
        return False, "Crédito no encontrado."
    cr = cr_rows[0]

    tipo = str(cr["tipo_credito"] if "tipo_credito" in cr.keys() and cr["tipo_credito"] else "usd").lower()
    if tipo == "bcv":
        abono_bcv = float(ab["monto_bcv"] or ab["monto_usd"] or 0)
        nuevo_saldo_bcv = max(0.0, float(cr["saldo_bcv"] or cr["saldo_usd"] or 0) - abono_bcv)
        nuevo_status = "Pagado" if nuevo_saldo_bcv <= 0.009 else "Parcial"
        q("""UPDATE abonos SET status='Validado', validado_por=?, fecha_validacion=? WHERE id=?""",
          (admin_username, now(), abono_id))
        q("UPDATE creditos SET saldo_bcv=?, saldo_usd=?, status=? WHERE id=?",
          (nuevo_saldo_bcv, nuevo_saldo_bcv, nuevo_status, cr["id"]))
        if nuevo_status == "Pagado":
            q("UPDATE pedidos SET status='Finalizado / Pagado' WHERE id=?", (cr["pedido_id"],))
        else:
            q("UPDATE pedidos SET status='Crédito / Pendiente de pago' WHERE id=?", (cr["pedido_id"],))
        return True, f"Abono BCV validado. Saldo actual: {money_usd(nuevo_saldo_bcv)} BCV"

    nuevo_saldo = max(0.0, float(cr["saldo_usd"] or 0) - float(ab["monto_usd"] or 0))
    nuevo_status = "Pagado" if nuevo_saldo <= 0.009 else "Parcial"
    q("""UPDATE abonos SET status='Validado', validado_por=?, fecha_validacion=? WHERE id=?""",
      (admin_username, now(), abono_id))
    q("UPDATE creditos SET saldo_usd=?, status=? WHERE id=?", (nuevo_saldo, nuevo_status, cr["id"]))
    if nuevo_status == "Pagado":
        q("UPDATE pedidos SET status='Finalizado / Pagado' WHERE id=?", (cr["pedido_id"],))
    else:
        q("UPDATE pedidos SET status='Crédito / Pendiente de pago' WHERE id=?", (cr["pedido_id"],))
    return True, f"Abono validado. Saldo actual: {money_usd(nuevo_saldo)}"


def producto_precio_presentacion(prod, presentacion):
    if presentacion == "unidad":
        return float(prod["precio_unidad"] or 0), 1
    if presentacion == "docena":
        # Campo histórico precio_docena ahora funciona como precio unitario de la presentación intermedia.
        cantidad_intermedia = producto_intermedia_cantidad(prod)
        return float(prod["precio_docena"] or 0) * cantidad_intermedia, cantidad_intermedia
    if presentacion == "bulto":
        bulto_contiene = int(prod["bulto_contiene"] or 1)
        return float(prod["precio_bulto"] or 0) * bulto_contiene, bulto_contiene
    return float(prod["precio_unidad"] or 0), 1

def calcular_precio_inteligente(prod, presentacion, cantidad_presentacion):
    cantidad_presentacion = int(cantidad_presentacion or 1)
    precio_unidad = float(prod["precio_unidad"] or 0)
    precio_intermedia = float(prod["precio_docena"] or 0)
    precio_bulto = float(prod["precio_bulto"] or 0)
    maneja_intermedia = bool(int(prod["maneja_docena"] or 0))
    maneja_bulto = bool(int(prod["maneja_bulto"] or 0))
    intermedia_cant = producto_intermedia_cantidad(prod)
    intermedia_nombre = producto_intermedia_nombre(prod)
    bulto_contiene = max(1, int(prod["bulto_contiene"] or 1))

    precio_pres, equivalencia = producto_precio_presentacion(prod, presentacion)
    unidades_base_total = cantidad_presentacion * int(equivalencia)

    if presentacion != "unidad":
        nombre = intermedia_nombre if presentacion == "docena" else presentacion
        return {
            "precio_total": precio_pres * cantidad_presentacion,
            "unidades_base_total": unidades_base_total,
            "precio_presentacion": precio_pres,
            "equivalencia": equivalencia,
            "escala_aplicada": nombre.lower(),
            "detalle_precio": f"{cantidad_presentacion} {nombre}(s)",
            "presentacion_nombre": nombre,
            "presentacion_label": f"{nombre} x{equivalencia}",
        }

    restante = unidades_base_total
    total = 0.0
    partes = []

    if maneja_bulto and precio_bulto > 0 and restante >= bulto_contiene:
        n_bultos = restante // bulto_contiene
        total += n_bultos * precio_bulto * bulto_contiene
        restante -= n_bultos * bulto_contiene
        partes.append(f"{n_bultos} bulto(s)")

    if maneja_intermedia and precio_intermedia > 0 and restante >= intermedia_cant:
        n_inter = restante // intermedia_cant
        total += n_inter * precio_intermedia * intermedia_cant
        restante -= n_inter * intermedia_cant
        partes.append(f"{n_inter} {intermedia_nombre.lower()}(s)")

    if restante > 0:
        total += restante * precio_unidad
        partes.append(f"{restante} unidad(es)")

    escala = " + ".join(partes) if partes else "unidad"
    precio_promedio = total / unidades_base_total if unidades_base_total else precio_unidad

    return {
        "precio_total": total,
        "unidades_base_total": unidades_base_total,
        "precio_presentacion": precio_promedio,
        "equivalencia": 1,
        "escala_aplicada": escala,
        "detalle_precio": escala,
        "presentacion_nombre": "Unidad",
        "presentacion_label": "Unidad",
    }

def disponibilidad(prod):
    stock = int(prod["wc_stock"] or 0)
    bulto_contiene = int(prod["bulto_contiene"] or 1)
    intermedia_cant = producto_intermedia_cantidad(prod)
    return {
        "unidades": stock,
        "docenas": stock // intermedia_cant if intermedia_cant > 0 and int(prod["maneja_docena"] or 0) else 0,
        "bultos": stock // bulto_contiene if bulto_contiene > 0 and int(prod["maneja_bulto"] or 0) else 0,
        "resto_bulto": stock % bulto_contiene if bulto_contiene > 0 and int(prod["maneja_bulto"] or 0) else stock,
    }

def calcular_carrito(carrito):
    tasa = get_tasa_proveedor()
    subtotal = 0.0
    peso = 0.0
    unidades_total = 0
    for sku, item in carrito.items():
        subtotal += float(item.get("precio_total", 0) or 0)
        peso += float(item.get("peso_total_kg", 0) or 0)
        unidades_total += int(item.get("unidades_base_total", 0) or 0)
    envio = sugerir_envio(peso)
    return {
        "subtotal": subtotal,
        "peso_total_kg": peso,
        "unidades_total": unidades_total,
        "envio": envio,
        "total": subtotal + envio,
        "total_bs": (subtotal + envio) * tasa,
    }

def sugerir_envio(peso_kg):
    # Regla inicial: por encima de 10kg hasta 40kg = $10.
    costo = parse_float(get_config("envio_ml_10_40_usd", "10"), 10)
    if peso_kg > 10 and peso_kg <= 40:
        return costo
    return 0.0


def cliente_usa_ml_envio(user):
    """Define si se debe sugerir/cobrar envío por tabulador interno."""
    try:
        return int(user["ml_envio"] or 0) == 1
    except Exception:
        return False

def usuario_es_cliente_especial(user):
    try:
        return int(user["cliente_especial"] if "cliente_especial" in user.keys() and user["cliente_especial"] is not None else 0) == 1
    except Exception:
        try:
            return int(user.get("cliente_especial") or 0) == 1
        except Exception:
            return False

def producto_maneja_precio_especial(prod):
    try:
        return int(prod["maneja_precio_especial"] if "maneja_precio_especial" in prod.keys() and prod["maneja_precio_especial"] is not None else 0) == 1
    except Exception:
        try:
            return int(prod.get("maneja_precio_especial") or 0) == 1
        except Exception:
            return False

def producto_con_precio_para_usuario(prod, user=None):
    """
    Devuelve una copia dict del producto con precios efectivos.
    Regla V56:
    - Precio especial unidad = precio por unidad.
    - Precio especial presentación intermedia = precio TOTAL de la presentación.
    - Precio especial bulto = precio TOTAL del bulto.
    Internamente se convierte a precio unitario para no romper cálculos existentes.
    """
    try:
        data = dict(prod)
    except Exception:
        data = {k: prod[k] for k in prod.keys()}

    data["_precio_especial_aplicado"] = False
    data["_precio_especial_intermedia_total"] = 0.0
    data["_precio_especial_bulto_total"] = 0.0
    if user is None:
        return data

    if usuario_es_cliente_especial(user) and producto_maneja_precio_especial(prod):
        try:
            pu = float(data.get("precio_especial_unidad") or 0)
            pinter_total = float(data.get("precio_especial_docena") or 0)
            pbulto_total = float(data.get("precio_especial_bulto") or 0)

            inter_cant = max(1, int(data.get("presentacion_intermedia_cantidad") or 12))
            bulto_cant = max(1, int(data.get("bulto_contiene") or 1))

            if pu > 0:
                data["precio_unidad"] = pu
                data["_precio_especial_aplicado"] = True

            # En precio especial, el campo intermedio representa el TOTAL del pack/docena/caja.
            if pinter_total > 0:
                data["precio_docena"] = pinter_total / inter_cant
                data["_precio_especial_intermedia_total"] = pinter_total
                data["_precio_especial_aplicado"] = True

            # En precio especial, el campo bulto representa el TOTAL del bulto.
            if pbulto_total > 0:
                data["precio_bulto"] = pbulto_total / bulto_cant
                data["_precio_especial_bulto_total"] = pbulto_total
                data["_precio_especial_aplicado"] = True
        except Exception:
            pass
    return data


def cliente_activo_para_venta(user):
    """
    Cliente comercial usado para mostrar precios y recalcular carrito.
    En admin permite preparar carrito para un cliente específico.
    """
    if user["rol"] == "admin":
        uname = st.session_state.get("cliente_venta_activo_username")
        if uname:
            u = get_user(uname)
            if u:
                return u
    return user

def selector_cliente_venta_admin(user, key="cliente_venta_selector"):
    if user["rol"] != "admin":
        return user
    usuarios_cliente = q("SELECT username,nombre FROM usuarios WHERE activo=1 ORDER BY nombre,username", fetch=True)
    if not usuarios_cliente:
        return user
    opts = ["Usar mi usuario admin"] + [f"{u['nombre'] or u['username']} — {u['username']}" for u in usuarios_cliente]
    mapa = {f"{u['nombre'] or u['username']} — {u['username']}": u["username"] for u in usuarios_cliente}
    actual = st.session_state.get("cliente_venta_activo_username")
    index = 0
    if actual:
        for i, label in enumerate(opts):
            if mapa.get(label) == actual:
                index = i
                break
    sel = st.selectbox("Ver/preparar pedido para cliente", opts, index=index, key=key)
    if sel == "Usar mi usuario admin":
        st.session_state["cliente_venta_activo_username"] = None
        return user
    st.session_state["cliente_venta_activo_username"] = mapa[sel]
    return get_user(mapa[sel]) or user


def render_card_producto(prod, user, cliente_precio=None):
    cliente_precio = cliente_precio or user
    prod = producto_con_precio_para_usuario(prod, cliente_precio)
    tasa = get_tasa_proveedor()
    stock = int(prod["wc_stock"] or 0)
    disp = disponibilidad(prod)
    img = prod["wc_imagen_url"]
    try:
        categoria_txt = prod["categoria"] if "categoria" in prod.keys() and prod["categoria"] else categoria_nombre(prod["categoria_id"])
    except Exception:
        categoria_txt = categoria_nombre(prod["categoria_id"])

    st.markdown('<div class="catalog-list-card">', unsafe_allow_html=True)
    col_img, col_info, col_actions = st.columns([1.15, 3.15, 1.55], vertical_alignment="top")

    with col_img:
        if img:
            pad1, pad2, pad3 = st.columns([0.05, 0.90, 0.05])
            with pad2:
                st.image(img, width=175)
        else:
            st.markdown(
                "<div class='catalog-image-frame' style='height:175px;display:flex;align-items:center;justify-content:center;'>"
                "<div style='height:145px;width:145px;border-radius:12px;background:#f3f4f6;display:flex;align-items:center;justify-content:center;font-size:38px'>📦</div>"
                "</div>",
                unsafe_allow_html=True
            )

        if st.button("🔍 Ver imagen", key=f"zoom_{prod['sku']}", help="Ampliar imagen", use_container_width=True):
            dialog_imagen(prod["descripcion"], prod["sku"], img)

    with col_info:
        st.markdown(f'<div class="catalog-list-title">{prod["descripcion"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="catalog-list-meta">SKU: {prod["sku"]} · {categoria_txt}</div>', unsafe_allow_html=True)

        if stock > 0 and prod["wc_stock_status"] != "outofstock":
            st.markdown(f'<span class="badge badge-ok">Disponible: {stock} {prod["unidad_base"]}</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge badge-no">Sin stock</span>', unsafe_allow_html=True)

        if prod.get("_precio_especial_aplicado"):
            st.markdown('<span class="badge badge-ok">⭐ Precio especial aplicado</span>', unsafe_allow_html=True)

        st.markdown('<div class="catalog-list-prices">', unsafe_allow_html=True)
        titulo_precio = "⭐ Precio especial unidad" if prod.get("_precio_especial_aplicado") else "Unidad"
        st.markdown(f"<div class='price-main'>{titulo_precio}: {money_usd(prod['precio_unidad'])}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='price-bs'>{money_bs(float(prod['precio_unidad'] or 0) * tasa)}</div>", unsafe_allow_html=True)

        price_lines = []
        etiqueta = " especial" if prod.get("_precio_especial_aplicado") else ""
        if int(prod["maneja_docena"] or 0):
            inter_cant = producto_intermedia_cantidad(prod)
            if prod.get("_precio_especial_aplicado") and float(prod.get("_precio_especial_intermedia_total") or 0) > 0:
                total_inter_usd = float(prod.get("_precio_especial_intermedia_total") or 0)
                price_lines.append(f"{producto_intermedia_label(prod)} especial TOTAL: <b>{money_usd(total_inter_usd)}</b> · {money_bs(total_inter_usd * tasa)} <span class='muted'>({money_usd(prod['precio_docena'])} c/u)</span>")
            else:
                price_lines.append(f"{producto_intermedia_label(prod)}{etiqueta}: <b>{money_usd(prod['precio_docena'])}</b> c/u · {money_bs(float(prod['precio_docena'] or 0) * tasa)} c/u")
        if int(prod["maneja_bulto"] or 0):
            bulto_contiene = int(prod["bulto_contiene"] or 1)
            precio_bulto_unitario = float(prod["precio_bulto"] or 0)
            total_bulto_usd = float(prod.get("_precio_especial_bulto_total") or 0) if prod.get("_precio_especial_aplicado") and float(prod.get("_precio_especial_bulto_total") or 0) > 0 else precio_bulto_unitario * bulto_contiene
            total_bulto_bs = total_bulto_usd * tasa
            if prod.get("_precio_especial_aplicado") and float(prod.get("_precio_especial_bulto_total") or 0) > 0:
                price_lines.append(f"Bulto especial TOTAL ({bulto_contiene} {prod['unidad_base']}): <b>{money_usd(total_bulto_usd)}</b> · {money_bs(total_bulto_bs)} <span class='muted'>({money_usd(precio_bulto_unitario)} c/u)</span>")
            else:
                price_lines.append(f"Bulto{etiqueta}: <b>{money_usd(precio_bulto_unitario)}</b> c/u · {money_bs(precio_bulto_unitario * tasa)} c/u")
                price_lines.append(f"<span style='color:#047857;font-weight:800'>Bulto Total ({bulto_contiene} {prod['unidad_base']}): {money_usd(total_bulto_usd)} · {money_bs(total_bulto_bs)}</span>")
        if price_lines:
            st.markdown("<div class='muted'>" + "<br>".join(price_lines) + "</div>", unsafe_allow_html=True)
        if prod.get("_precio_especial_aplicado"):
            st.caption("Se muestran solo los precios especiales aplicados para este cliente.")
        st.markdown("</div>", unsafe_allow_html=True)

        if user["rol"] in ["admin", "vendedor_mercadolibre"]:
            com_ml = get_comision_ml_pct()
            ml_u_bs, ml_u_bcv = precio_ml_resumen(prod["precio_unidad"])
            ml_d_bs, ml_d_bcv = precio_ml_resumen(prod["precio_docena"])
            ml_b_bs, ml_b_bcv = precio_ml_resumen(prod["precio_bulto"])
            st.markdown(
                f"""
                <div style="margin-top:8px;border:1px solid #dbeafe;background:#eff6ff;border-radius:12px;padding:8px;">
                  <div style="font-weight:900;color:#1d4ed8;">Sugerido MercadoLibre (+{com_ml:.1f}%)</div>
                  <div class="muted">Unidad: <b>{money_bs(ml_u_bs)}</b> · Eq. BCV ${ml_u_bcv:,.2f}</div>
                  <div class="muted">{producto_intermedia_nombre(prod)} c/u: <b>{money_bs(ml_d_bs)}</b> · Eq. BCV ${ml_d_bcv:,.2f}</div>
                  <div class="muted">Bulto c/u: <b>{money_bs(ml_b_bs)}</b> · Eq. BCV ${ml_b_bcv:,.2f}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

    with col_actions:
        st.markdown('<div class="catalog-list-actions">', unsafe_allow_html=True)

        opciones = ["unidad"]
        if int(prod["maneja_docena"] or 0):
            opciones.append("docena")
        if int(prod["maneja_bulto"] or 0):
            opciones.append("bulto")

        labels_pres = {
            "unidad": "Unidad",
            "docena": producto_intermedia_label(prod),
            "bulto": "Bulto"
        }
        presentacion = st.selectbox("Presentación", opciones, key=f"pres_{prod['sku']}", label_visibility="collapsed", format_func=lambda x: labels_pres.get(x, x))

        if presentacion == "unidad":
            cantidad = st.number_input("Cantidad", min_value=1, max_value=9999, value=1, step=1, key=f"cant_{prod['sku']}", label_visibility="collapsed")
        else:
            cantidad = 1
            st.number_input("Cantidad", min_value=1, max_value=1, value=1, step=1, key=f"cant_locked_{prod['sku']}_{presentacion}", label_visibility="collapsed", disabled=True)

        precio_calc = calcular_precio_inteligente(prod, presentacion, int(cantidad))
        precio_pres = float(precio_calc["precio_presentacion"])
        eq = int(precio_calc["equivalencia"])
        unidades_base_total = int(precio_calc["unidades_base_total"])
        precio_total_calc = float(precio_calc["precio_total"])
        escala_aplicada = precio_calc["escala_aplicada"]

        st.markdown(
            f"""
            <div class="catalog-selection-box">
              <div class="catalog-selection-title">Selección actual</div>
              <div class="catalog-selection-value">{money_usd(precio_total_calc)}</div>
              <div class="muted">{unidades_base_total} unidad(es) base</div>
              <div class="muted">{"⭐ precio especial aplicado" if prod.get("_precio_especial_aplicado") else ""}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if unidades_base_total > stock:
            st.warning(f"No alcanza stock. Requiere {unidades_base_total}, disponible {stock}.")
            disabled = True
        else:
            disabled = False

        show_producto_carrito_badge(user["username"], prod["sku"])

        if st.button("🛒 Agregar", key=f"add_{prod['sku']}", type="primary", use_container_width=True, disabled=disabled):
            carrito = cargar_carrito(user["username"])
            key = f"{prod['sku']}::{presentacion}"
            cantidad_final = int(cantidad)
            if key in carrito:
                cantidad_final = int(carrito[key].get("cantidad_presentacion", 0) or 0) + int(cantidad)

            item_tmp = {
                "sku": prod["sku"],
                "desc": prod["descripcion"],
                "presentacion": presentacion,
                "escala_aplicada": escala_aplicada,
                "detalle_precio": precio_calc.get("detalle_precio", escala_aplicada),
                "presentacion_nombre": precio_calc.get("presentacion_nombre", producto_intermedia_nombre(prod) if presentacion == "docena" else presentacion.title()),
                "presentacion_label": precio_calc.get("presentacion_label", producto_intermedia_label(prod) if presentacion == "docena" else presentacion.title()),
                "cantidad_presentacion": cantidad_final,
                "equivalencia": int(eq),
                "unidades_base_total": int(unidades_base_total),
                "precio_presentacion": float(precio_pres),
                "precio_total": precio_total_calc,
                "peso_total_kg": float(prod["peso_unidad_kg"] or 0) * int(unidades_base_total),
                "imagen_url": prod["wc_imagen_url"],
                "cliente_precio_username": cliente_precio["username"],
                "cliente_precio_nombre": cliente_precio["nombre"] or cliente_precio["username"],
            }
            carrito[key] = recalcular_item_carrito(item_tmp, cantidad_final, user=cliente_precio)
            guardar_carrito(user["username"], carrito)
            n_items, n_unidades, total_carrito = carrito_resumen_texto(user["username"])
            cantidad_presentacion_agregada = int(cantidad)
            set_last_cart_action(prod["descripcion"], presentacion, cantidad_presentacion_agregada, unidades_base_total)
            agregado_txt = texto_agregado_presentacion(presentacion, cantidad_presentacion_agregada, unidades_base_total)
            set_feedback(
                f"Agregado al carrito: {agregado_txt}. "
                f"Carrito: {n_items} línea(s), {n_unidades} unidad(es), {money_usd(total_carrito)}.",
                "success"
            )
            st.rerun()

        st.markdown(
            f'<div class="actions-foot-note">Docenas: <b>{disp["docenas"]}</b> · Bultos: <b>{disp["bultos"]}</b></div>',
            unsafe_allow_html=True
        )

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def tienda():
    st.markdown("## 🛍️ Tienda / Catálogo")
    st.caption("Vista en lista horizontal: imagen, información y acciones por producto.")
    show_last_cart_action()
    user = get_user(st.session_state.user["username"])
    cliente_precio = selector_cliente_venta_admin(user, key="cliente_venta_tienda")
    if user["rol"] == "admin" and cliente_precio["username"] != user["username"]:
        st.success(f"Mostrando precios y preparando carrito para: {cliente_precio['nombre'] or cliente_precio['username']}")
    tasa = get_tasa_proveedor()
    carrito = cargar_carrito(user["username"])
    carrito_preview = {k: recalcular_item_carrito(v, user=cliente_precio) for k, v in carrito.items()}
    t = calcular_carrito(carrito_preview)

    cats = categorias_activas()
    cat_names = ["Todas"] + [c["nombre"] for c in cats]
    cat_ids = {"Todas": None}
    cat_ids.update({c["nombre"]: c["id"] for c in cats})

    # Encabezado compacto para ganar espacio horizontal.
    st.markdown('<div class="card">', unsafe_allow_html=True)
    top1, top2, top3, top4 = st.columns([2.2, 3.2, 1.3, 1.5])

    with top1:
        cat_sel = st.selectbox("Categoría", cat_names, label_visibility="collapsed")

    with top2:
        bus = st.text_input("Buscar producto", placeholder="Buscar por nombre o SKU...", label_visibility="collapsed")

    with top3:
        show_cart_bubble(user["username"])

    with top4:
        if st.button("🛒 Ver carrito", use_container_width=True):
            st.session_state.menu = "Carrito"
            st.rerun()
        if carrito:
            st.caption(f"{len(carrito)} línea(s) · {t['unidades_total']} unidad(es)")

    st.caption(f"Tasa proveedor: {tasa:,.2f} · Bolívares calculados a tasa proveedor vigente.")
    st.markdown("</div>", unsafe_allow_html=True)

    sql = """SELECT p.*, c.nombre AS categoria
             FROM productos p LEFT JOIN categorias c ON p.categoria_id=c.id
             WHERE p.activo=1"""
    params = []
    if cat_ids[cat_sel]:
        sql += " AND p.categoria_id=?"
        params.append(cat_ids[cat_sel])
    if bus:
        sql += " AND (p.descripcion LIKE ? OR p.sku LIKE ?)"
        params.extend([f"%{bus}%", f"%{bus}%"])
    sql += " ORDER BY c.orden, p.descripcion"
    rows = q(sql, params, fetch=True)

    rinfo1, rinfo2 = st.columns([3, 1])
    rinfo1.caption(f"{len(rows)} productos encontrados")
    if rinfo2.button("🔄 Actualizar stock", use_container_width=True):
        with st.spinner("Sincronizando WooCommerce..."):
            ok, no, errors = sync_todos_productos()
        st.success(f"Sincronizados: {ok}. No sincronizados: {no}.")
        if errors:
            st.warning("Algunos errores:")
            st.code("\\n".join(errors))
        st.rerun()

    if not rows:
        st.info("No hay productos para mostrar.")
        return

    # Vista horizontal: una card por fila, sin cuadrícula.
    for prod in rows:
        render_card_producto(prod, user)



def pedido_permite_edicion(pedido):
    status = str(pedido["status"] or "").lower()
    bloqueados = ["finalizado", "pagado", "procesado en pos", "cancelado", "anulado"]
    return not any(b in status for b in bloqueados)

def cliente_resumen_para_pedido(username):
    u = get_user(username)
    if not u:
        return {"username": username, "cliente_nombre": username, "cliente_rif": "", "cliente_telefono": "", "cliente_direccion": ""}
    return {
        "username": u["username"],
        "cliente_nombre": u["nombre"] or u["username"],
        "cliente_rif": u["rif"] or "",
        "cliente_telefono": u["telefono"] or "",
        "cliente_direccion": u["direccion"] or "",
    }

def transferir_pedido_a_cliente(pedido_id, username_destino):
    rows = q("SELECT * FROM pedidos WHERE id=?", (int(pedido_id),), fetch=True)
    if not rows:
        return False, "Pedido no encontrado."
    ped = rows[0]
    dest = get_user(username_destino)
    if not dest:
        return False, "Cliente destino no encontrado."

    datos = cliente_resumen_para_pedido(username_destino)
    q("""UPDATE pedidos SET username=?, cliente_nombre=?, cliente_rif=?, cliente_telefono=?, cliente_direccion=? WHERE id=?""",
      (datos["username"], datos["cliente_nombre"], datos["cliente_rif"], datos["cliente_telefono"], datos["cliente_direccion"], int(pedido_id)))

    if ped["credito_id"]:
        q("UPDATE creditos SET username=?, cliente_nombre=? WHERE id=?",
          (datos["username"], datos["cliente_nombre"], int(ped["credito_id"])))
        q("UPDATE abonos SET username=? WHERE pedido_id=?", (datos["username"], int(pedido_id)))

    return True, f"Pedido #{pedido_id} transferido a {datos['cliente_nombre']}."

def recalcular_pedido_y_credito(pedido_id, items, envio_usd, metodo_pago=None, notas=None, recalcular_credito=True):
    rows = q("SELECT * FROM pedidos WHERE id=?", (int(pedido_id),), fetch=True)
    if not rows:
        return False, "Pedido no encontrado."
    ped = rows[0]
    if not pedido_permite_edicion(ped):
        return False, "Este pedido no puede editarse por su estado actual."

    # Recalcular cada item para respetar precios vigentes y condición comercial del cliente del pedido.
    pedido_user = get_user(ped["username"])
    carrito_tmp = {}
    for k, item in items.items():
        try:
            nuevo = recalcular_item_carrito(item, user=pedido_user)
            if int(nuevo.get("cantidad_presentacion", 1)) > 0:
                carrito_tmp[k] = nuevo
        except Exception:
            pass
    if not carrito_tmp:
        return False, "El pedido no puede quedar sin items."

    t = calcular_carrito(carrito_tmp)
    subtotal = float(t["subtotal"])
    envio_usd = float(envio_usd or 0)
    total = subtotal + envio_usd
    tasa = float(ped["tasa_proveedor"] or get_tasa_proveedor())
    # Para edición se conserva tasa BCV original por defecto.
    tasa_bcv = float(ped["tasa_bcv"] or get_tasa_bcv())
    total_bs = total * tasa

    q("""UPDATE pedidos SET items=?, subtotal_usd=?, envio_usd=?, total_usd=?, total_bs_proveedor=?, peso_total_kg=?,
         metodo_pago=COALESCE(?, metodo_pago), notas=COALESCE(?, notas) WHERE id=?""",
      (json.dumps(carrito_tmp, ensure_ascii=False), subtotal, envio_usd, total, total_bs, t["peso_total_kg"],
       metodo_pago, notas, int(pedido_id)))

    if recalcular_credito and ped["credito_id"] and str(ped["tipo_pago"]).lower() == "credito":
        cr_rows = q("SELECT * FROM creditos WHERE id=?", (int(ped["credito_id"]),), fetch=True)
        if cr_rows:
            cr = cr_rows[0]
            validados = q("SELECT COALESCE(SUM(CASE WHEN COALESCE(tipo_credito,'usd')='bcv' THEN COALESCE(monto_bcv, monto_usd, 0) ELSE COALESCE(monto_usd,0) END),0) AS total FROM abonos WHERE credito_id=? AND status='Validado'", (int(cr["id"]),), fetch=True)[0]["total"]
            abonado = float(validados or 0)
            tipo_credito = str(cr["tipo_credito"] or ped["credito_tipo"] or "usd").lower()

            if tipo_credito == "bcv":
                nuevo_monto = (total_bs / tasa_bcv) if tasa_bcv > 0 else 0.0
                if nuevo_monto + 0.009 < abonado:
                    return False, "No se puede guardar: el nuevo total BCV queda por debajo de lo ya abonado/validado."
                nuevo_saldo = max(0.0, nuevo_monto - abonado)
                nuevo_status = "Pagado" if nuevo_saldo <= 0.009 else ("Parcial" if abonado > 0 else "Pendiente")
                q("""UPDATE creditos SET monto_usd=?, saldo_usd=?, monto_bcv=?, saldo_bcv=?, total_bs_base=?, tasa_proveedor=?, tasa_bcv_creacion=?, status=? WHERE id=?""",
                  (nuevo_monto, nuevo_saldo, nuevo_monto, nuevo_saldo, total_bs, tasa, tasa_bcv, nuevo_status, int(cr["id"])))
                q("UPDATE pedidos SET total_bcv_credito=? WHERE id=?", (nuevo_monto, int(pedido_id)))
            else:
                nuevo_monto = total
                if nuevo_monto + 0.009 < abonado:
                    return False, "No se puede guardar: el nuevo total queda por debajo de lo ya abonado/validado."
                nuevo_saldo = max(0.0, nuevo_monto - abonado)
                nuevo_status = "Pagado" if nuevo_saldo <= 0.009 else ("Parcial" if abonado > 0 else "Pendiente")
                q("UPDATE creditos SET monto_usd=?, saldo_usd=?, total_bs_base=?, tasa_proveedor=?, status=? WHERE id=?",
                  (nuevo_monto, nuevo_saldo, total_bs, tasa, nuevo_status, int(cr["id"])))
    return True, "Pedido recalculado correctamente."

def carrito_view():
    st.title("🛒 Carrito")
    user = get_user(st.session_state.user["username"])
    cliente_precio_carrito = cliente_activo_para_venta(user)
    if user["rol"] == "admin" and cliente_precio_carrito["username"] != user["username"]:
        st.success(f"Carrito calculado para cliente: {cliente_precio_carrito['nombre'] or cliente_precio_carrito['username']}")
    carrito = cargar_carrito(user["username"])
    tasa = get_tasa_proveedor()

    show_cart_bubble(user["username"])

    if not carrito:
        st.info("Tu carrito está vacío.")
        return

    for key, item in list(carrito.items()):
        # Recalcula silenciosamente para mantener precios actuales y corregir visual.
        item_user_precio = cliente_precio_carrito
        if item.get("cliente_precio_username") and item.get("cliente_precio_username") != user["username"]:
            item_user_guardado = get_user(item.get("cliente_precio_username"))
            if item_user_guardado:
                item_user_precio = item_user_guardado
        item = recalcular_item_carrito(item, user=item_user_precio)
        carrito[key] = item
        guardar_carrito(user["username"], carrito)

        c0, c1, c2, c3, c4 = st.columns([1,3,2.2,1.2,1])
        with c0:
            if item.get("imagen_url"):
                st.image(item["imagen_url"], width=90)
            else:
                st.write("📦")
        with c1:
            st.markdown(f"**{item['desc']}**")
            st.caption(f"SKU: {item['sku']} · {texto_linea_carrito(item)}")

        with c2:
            bmenos, bqty, bmas = st.columns([0.7,1.2,0.7])
            if bmenos.button("−", key=f"minus_{key}", use_container_width=True):
                nueva = max(1, int(item.get("cantidad_presentacion", 1)) - 1)
                carrito[key] = recalcular_item_carrito(item, nueva)
                guardar_carrito(user["username"], carrito)
                n_items, n_unidades, total_carrito = carrito_resumen_texto(user["username"])
                set_feedback(f"Cantidad actualizada. Carrito: {n_items} línea(s), {n_unidades} unidad(es), {money_usd(total_carrito)}.", "success")
                st.rerun()
            nueva_q = bqty.number_input("Cantidad", min_value=1, max_value=99999, value=int(item.get("cantidad_presentacion", 1)), key=f"qty_{key}", label_visibility="collapsed")
            if int(nueva_q) != int(item.get("cantidad_presentacion", 1)):
                carrito[key] = recalcular_item_carrito(item, int(nueva_q))
                guardar_carrito(user["username"], carrito)
                n_items, n_unidades, total_carrito = carrito_resumen_texto(user["username"])
                set_feedback(f"Cantidad actualizada. Carrito: {n_items} línea(s), {n_unidades} unidad(es), {money_usd(total_carrito)}.", "success")
                st.rerun()
            if bmas.button("+", key=f"plus_{key}", use_container_width=True):
                nueva = int(item.get("cantidad_presentacion", 1)) + 1
                carrito[key] = recalcular_item_carrito(item, nueva)
                guardar_carrito(user["username"], carrito)
                st.rerun()

        c3.write(f"**{money_usd(item['precio_total'])}**")
        c3.caption(money_bs(float(item["precio_total"]) * tasa))
        if c4.button("🗑️", key=f"del_{key}"):
            carrito.pop(key, None)
            guardar_carrito(user["username"], carrito)
            n_items, n_unidades, total_carrito = carrito_resumen_texto(user["username"])
            set_feedback(f"Item eliminado. Carrito: {n_items} línea(s), {n_unidades} unidad(es), {money_usd(total_carrito)}.", "warning")
            st.rerun()
        st.markdown("---")

    t = calcular_carrito(carrito)
    st.markdown('<div class="total-box">', unsafe_allow_html=True)
    st.markdown(f"### Subtotal productos: {money_usd(t['subtotal'])}")
    st.markdown(f"### Total Bs proveedor: {money_bs(t['subtotal'] * tasa)}")
    envio_sugerido_usuario = t["envio"] if cliente_usa_ml_envio(user) else 0.0
    if user["rol"] == "admin":
        st.markdown('<div class="admin-only">', unsafe_allow_html=True)
        st.markdown("**Vista interna admin**")
        st.write(f"Peso total estimado: **{t['peso_total_kg']:.2f} kg**")
        if cliente_usa_ml_envio(user):
            st.write(f"Envío sugerido ML / ENVÍO: **{money_usd(envio_sugerido_usuario)}**")
            st.write(f"Total con envío sugerido: **{money_usd(t['subtotal'] + envio_sugerido_usuario)}**")
        else:
            st.write("Envío sugerido: **No aplica**")
            st.caption("Este usuario no tiene activa la casilla ML / ENVÍO.")
        st.caption("El peso y la regla de envío no son visibles para el comprador.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")
    c1, c2 = st.columns(2)
    if c1.button("🧹 Vaciar carrito", use_container_width=True):
        limpiar_carrito(user["username"])
        set_feedback("Carrito vaciado correctamente.", "warning")
        st.rerun()

    st.markdown("---")
    st.subheader("Finalizar pedido")
    st.info("Selecciona el tipo de operación antes de crear el pedido. Así evitamos hacer doble paso.")

    st.markdown("### Procesar pedido")

    # Admin puede armar el carrito desde su usuario y asignar el pedido a un cliente final.
    cliente_pedido = cliente_precio_carrito
    if user["rol"] == "admin":
        usuarios_cliente = q("SELECT username,nombre,telefono,rif FROM usuarios WHERE activo=1 ORDER BY nombre,username", fetch=True)
        opts_cliente = ["Usar mi usuario admin"] + [f"{u['nombre'] or u['username']} — {u['username']}" for u in usuarios_cliente]
        mapa_cliente = {f"{u['nombre'] or u['username']} — {u['username']}": u["username"] for u in usuarios_cliente}
        actual_cliente = st.session_state.get("cliente_venta_activo_username")
        idx_cliente = 0
        if actual_cliente:
            for i, label in enumerate(opts_cliente):
                if mapa_cliente.get(label) == actual_cliente:
                    idx_cliente = i
                    break
        sel_cliente = st.selectbox("Pedido para cliente", opts_cliente, index=idx_cliente, key="pedido_para_cliente_admin")
        if sel_cliente != "Usar mi usuario admin":
            st.session_state["cliente_venta_activo_username"] = mapa_cliente[sel_cliente]
            cliente_pedido = get_user(mapa_cliente[sel_cliente]) or user
            st.success(f"El pedido se creará a nombre de: {cliente_pedido['nombre'] or cliente_pedido['username']}")
        else:
            st.session_state["cliente_venta_activo_username"] = None
            cliente_pedido = user
            st.caption("El pedido se creará a nombre del usuario admin actual.")
    else:
        st.caption(f"El pedido se creará a nombre de: {user['nombre'] or user['username']}")

    if "_credito_bcv_calc" not in st.session_state:
        st.session_state["_credito_bcv_calc"] = None

    st.markdown('<div class="card">', unsafe_allow_html=True)

    opciones_tipo_operacion = ["Contado"]
    credito_normal_activo = user["rol"] == "admin" or int(cliente_pedido["credito_habilitado"] or 0) == 1
    credito_bcv_activo = user["rol"] == "admin" or int(cliente_pedido["credito_bcv_habilitado"] if "credito_bcv_habilitado" in cliente_pedido.keys() and cliente_pedido["credito_bcv_habilitado"] is not None else 0) == 1

    if credito_normal_activo:
        opciones_tipo_operacion.append("Crédito en divisas")
    if credito_bcv_activo:
        opciones_tipo_operacion.append("Crédito BCV")

    tipo_actual_guardado = st.session_state.get("tipo_operacion_pedido", "Contado")
    if tipo_actual_guardado not in opciones_tipo_operacion:
        st.session_state["tipo_operacion_pedido"] = "Contado"

    tipo_operacion = st.radio(
        "Tipo de operación",
        opciones_tipo_operacion,
        horizontal=True,
        help="Selecciona el flujo exacto antes de crear el pedido.",
        key="tipo_operacion_pedido"
    )

    if user["rol"] != "admin" and not credito_bcv_activo:
        st.caption("Crédito BCV no está habilitado para tu usuario.")
    if user["rol"] == "admin":
        st.caption("Como admin puedes crear crédito para un cliente seleccionado. El pedido y el crédito quedarán a nombre de ese cliente.")

    metodo_pago = st.selectbox(
        "Método de pago",
        ["Por confirmar", "Divisas", "Transferencia", "Pago móvil", "Zelle", "Zinli", "Binance", "Otro"],
        key="metodo_pago_pedido"
    )

    if cliente_usa_ml_envio(cliente_pedido):
        envio_pedido = st.number_input(
            "Envío a cobrar USD",
            min_value=0.0,
            value=float(t["envio"]),
            step=0.5,
            key="envio_pedido_procesar"
        )
    else:
        envio_pedido = 0.0
        st.caption("Este cliente no tiene activa la casilla ML / ENVÍO, por eso no se muestra cobro de envío.")

    notas_pedido = st.text_area("Notas del pedido", key="notas_pedido_procesar")

    carrito_preview = {k: recalcular_item_carrito(v, user=cliente_pedido) for k, v in carrito.items()}
    t_preview = calcular_carrito(carrito_preview)
    total_preview_usd = float(t_preview["subtotal"]) + float(envio_pedido or 0)
    tasa_prov_preview = get_tasa_proveedor()
    tasa_bcv_preview = get_tasa_bcv()
    total_preview_bs = total_preview_usd * tasa_prov_preview
    credito_bcv_preview = total_preview_bs / tasa_bcv_preview if tasa_bcv_preview else 0
    if usuario_es_cliente_especial(cliente_pedido) and any(v.get("precio_especial_aplicado") for v in carrito_preview.values()):
        st.success("⭐ Precio especial aplicado para este cliente en uno o más productos del pedido.")

    metodo_ok = metodo_pago != "Por confirmar"
    credito_habilitado_ok = not (
        tipo_operacion in ["Crédito en divisas", "Crédito BCV"]
        and user["rol"] != "admin"
        and int(cliente_pedido["credito_habilitado"] or 0) != 1
    )

    st.markdown("### Revisión antes de continuar")

    if not metodo_ok:
        st.warning("Selecciona un método de pago para continuar.")

    if tipo_operacion == "Contado":
        if metodo_pago in ["Transferencia", "Pago móvil"]:
            st.info(
                f"Pago en Bs seleccionado.\n\n"
                f"Cliente: {cliente_pedido['nombre'] or cliente_pedido['username']}\n\n"
                f"Total del pedido: {money_usd(total_preview_usd)}\n\n"
                f"Tasa proveedor actual: {tasa_prov_preview:,.2f}\n\n"
                f"Cliente debe transferir: {money_bs(total_preview_bs)}"
            )
        elif metodo_pago in ["Divisas", "Zelle", "Zinli", "Binance"]:
            st.info(
                f"Pago en divisas seleccionado.\n\n"
                f"Cliente: {cliente_pedido['nombre'] or cliente_pedido['username']}\n\n"
                f"Total a cancelar: {money_usd(total_preview_usd)} por {metodo_pago}."
            )
        elif metodo_pago == "Otro":
            st.info(
                f"Método de pago Otro.\n\n"
                f"Cliente: {cliente_pedido['nombre'] or cliente_pedido['username']}\n\n"
                f"Total del pedido: {money_usd(total_preview_usd)}\n\n"
                f"Referencia en Bs a tasa proveedor: {money_bs(total_preview_bs)}"
            )

    elif tipo_operacion == "Crédito en divisas":
        if not credito_habilitado_ok:
            st.warning("Este cliente no tiene crédito habilitado.")
        st.info(
            f"Crédito en divisas reales.\n\n"
            f"Cliente: {cliente_pedido['nombre'] or cliente_pedido['username']}\n\n"
            f"Saldo que se generará: {money_usd(total_preview_usd)}\n\n"
            f"Referencia en Bs hoy: {money_bs(total_preview_usd * tasa_prov_preview)}"
        )

    else:
        if not credito_habilitado_ok:
            st.warning("Este cliente no tiene crédito habilitado.")
        if tasa_bcv_preview <= 0:
            st.error("La tasa BCV está en cero. Actualízala antes de calcular Crédito BCV.")
        st.warning(
            "Crédito BCV requiere doble paso:\n\n"
            "1. Presiona Calcular crédito BCV.\n\n"
            "2. Revisa el monto generado.\n\n"
            "3. Luego confirma con Crear pedido confirmado con Crédito BCV."
        )
        st.info(
            f"Vista previa del Crédito BCV:\n\n"
            f"Cliente: {cliente_pedido['nombre'] or cliente_pedido['username']}\n\n"
            f"Total real USD: {money_usd(total_preview_usd)}\n\n"
            f"Total Bs a tasa proveedor: {money_bs(total_preview_bs)}\n\n"
            f"Tasa BCV actual: {tasa_bcv_preview:,.2f}\n\n"
            f"Crédito estimado: {money_usd(credito_bcv_preview)} BCV"
        )

    puede_calcular_bcv = (
        tipo_operacion == "Crédito BCV"
        and metodo_ok
        and credito_habilitado_ok
        and tasa_bcv_preview > 0
    )
    puede_crear_normal = (
        tipo_operacion in ["Contado", "Crédito en divisas"]
        and metodo_ok
        and credito_habilitado_ok
    )

    col_accion1, col_accion2 = st.columns(2)
    calcular_bcv = col_accion1.button(
        "🧮 Calcular crédito BCV",
        type="secondary",
        disabled=not puede_calcular_bcv,
        use_container_width=True,
        key="btn_calcular_credito_bcv"
    )
    crear_pedido_normal = col_accion2.button(
        "✅ Crear pedido",
        type="primary",
        disabled=not puede_crear_normal,
        use_container_width=True,
        key="btn_crear_pedido_normal"
    )

    st.markdown("</div>", unsafe_allow_html=True)

    if calcular_bcv:
        st.session_state["_credito_bcv_calc"] = {
            "subtotal_usd": float(t["subtotal"]),
            "envio_usd": float(envio_pedido or 0),
            "total_usd": float(total_preview_usd),
            "tasa_proveedor": float(tasa_prov_preview),
            "total_bs": float(total_preview_bs),
            "tasa_bcv": float(tasa_bcv_preview),
            "credito_bcv": float(credito_bcv_preview),
            "metodo_pago": metodo_pago,
            "notas": notas_pedido,
            "cliente_target_username": cliente_pedido["username"],
            "cliente_nombre": cliente_pedido["nombre"] or cliente_pedido["username"],
            "cart_signature": json.dumps(carrito, sort_keys=True, ensure_ascii=False),
        }
        st.success("Crédito BCV calculado. Revisa el resumen y luego confirma el pedido.")

    if crear_pedido_normal:
        tipo_pago = "credito" if tipo_operacion == "Crédito en divisas" else "contado"
        pid, msg = crear_pedido_desde_carrito(
            user,
            carrito,
            tipo_pago,
            metodo_pago,
            envio_pedido,
            notas_pedido,
            tipo_credito="usd",
            cliente_target_username=cliente_pedido["username"]
        )
        if pid:
            st.success(f"{msg} Pedido #{pid}.")
            pdf = generar_pdf_pedido(pid)
            st.download_button("⬇️ Descargar PDF pedido", data=pdf, file_name=f"pedido_{pid:04d}.pdf", mime="application/pdf", use_container_width=True)
        else:
            st.error(msg)

    calc = st.session_state.get("_credito_bcv_calc")
    if calc:
        carrito_actual_sig = json.dumps(carrito, sort_keys=True, ensure_ascii=False)
        if calc.get("cart_signature") != carrito_actual_sig:
            st.warning("El carrito cambió después de calcular el Crédito BCV. Vuelve a calcular antes de crear el pedido.")
        else:
            st.markdown("---")
            st.subheader("Confirmar Crédito BCV")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total real", money_usd(calc["total_usd"]))
            c2.metric("Total Bs proveedor", money_bs(calc["total_bs"]))
            c3.metric("Tasa BCV", f"{calc['tasa_bcv']:,.2f}")
            c4.metric("Crédito BCV", f"{money_usd(calc['credito_bcv'])} BCV")
            st.caption(f"Cliente final: {calc.get('cliente_nombre','')}")

            st.info(
                "Al confirmar, se creará el pedido y la cuenta por cobrar en $ BCV. "
                "El cliente pagará sus abonos en $ BCV y el sistema calculará los Bs a transferir con la tasa BCV vigente del día del pago."
            )

            cc1, cc2 = st.columns(2)
            if cc1.button("✅ Crear pedido confirmado con Crédito BCV", type="primary", use_container_width=True, key="btn_confirmar_pedido_bcv"):
                pid, msg = crear_pedido_desde_carrito(
                    user,
                    carrito,
                    "credito",
                    calc["metodo_pago"],
                    calc["envio_usd"],
                    calc["notas"],
                    tipo_credito="bcv",
                    cliente_target_username=calc.get("cliente_target_username")
                )
                if pid:
                    st.session_state["_credito_bcv_calc"] = None
                    st.success(f"{msg} Pedido #{pid} creado con Crédito BCV.")
                    pdf = generar_pdf_pedido(pid)
                    st.download_button("⬇️ Descargar PDF pedido", data=pdf, file_name=f"pedido_{pid:04d}.pdf", mime="application/pdf", use_container_width=True)
                else:
                    st.error(msg)

            if cc2.button("Cancelar cálculo BCV", use_container_width=True, key="btn_cancelar_calc_bcv"):
                st.session_state["_credito_bcv_calc"] = None
                st.rerun()

    if user["rol"] == "admin":
        st.markdown("---")
        if st.button("📄 Generar cotización", use_container_width=True):
            st.session_state.generar_cotizacion = True

    if st.session_state.get("generar_cotizacion"):
        st.subheader("Datos para cotización")
        with st.form("form_cotizacion"):
            cliente_nombre = st.text_input("Cliente / proveedor", value=user["nombre"] or "")
            cliente_rif = st.text_input("RIF / CI", value=user["rif"] or "")
            cliente_tel = st.text_input("Teléfono", value=user["telefono"] or "")
            cliente_dir = st.text_area("Dirección", value=user["direccion"] or "")
            envio = st.number_input("Envío a cobrar USD", min_value=0.0, value=float(t["envio"] if cliente_usa_ml_envio(user) else 0), step=0.5)
            validez = st.number_input("Validez días", min_value=1, max_value=30, value=int(parse_float(get_config("validez_cotizacion_dias","1"), 1)))
            notas = st.text_area("Notas", value="")
            submit = st.form_submit_button("Crear cotización PDF", type="primary")
        if submit:
            subtotal = t["subtotal"]
            total = subtotal + envio
            cot_items = {}
            for k, v in carrito.items():
                cot_items[v["sku"] + "::" + v["presentacion"]] = v
            q("""INSERT INTO cotizaciones
                 (fecha, username, cliente_nombre, cliente_rif, cliente_telefono, cliente_direccion, items,
                  subtotal_usd, envio_usd, total_usd, tasa_proveedor, tasa_bcv, total_bs_proveedor,
                  peso_total_kg, validez_dias, status, notas)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (now(), user["username"], cliente_nombre, cliente_rif, cliente_tel, cliente_dir, json.dumps(cot_items, ensure_ascii=False),
               subtotal, envio, total, get_tasa_proveedor(), get_tasa_bcv(), total * get_tasa_proveedor(),
               t["peso_total_kg"], int(validez), "Pendiente", notas))
            cot_id = q("SELECT last_insert_rowid() AS id", fetch=True)[0]["id"]
            pdf = generar_pdf_cotizacion(cot_id)
            st.success(f"Cotización #{cot_id} creada. No descuenta inventario.")
            st.download_button("⬇️ Descargar PDF", data=pdf, file_name=f"cotizacion_{cot_id:04d}.pdf", mime="application/pdf", use_container_width=True)

# -----------------------------
# MAIN
# -----------------------------
if "auth" not in st.session_state:
    st.session_state.auth = False
if "user" not in st.session_state:
    st.session_state.user = None
if "menu" not in st.session_state:
    st.session_state.menu = "Tienda"

# Protección extra para Railway / reinicios de sesión:
# Puede ocurrir que auth quede True pero user sea None.
if not st.session_state.auth or st.session_state.user is None:
    st.session_state.auth = False
    st.session_state.user = None
    login_screen()
    st.stop()

try:
    username_actual = st.session_state.user.get("username")
except Exception:
    username_actual = None

if not username_actual:
    st.session_state.auth = False
    st.session_state.user = None
    login_screen()
    st.stop()

user = get_user(username_actual)

if user is None:
    st.session_state.auth = False
    st.session_state.user = None
    st.error("La sesión perdió el usuario o el usuario ya no existe. Inicia sesión nuevamente.")
    login_screen()
    st.stop()

show_feedback()
auto_sync_stock_si_corresponde(user)
if st.session_state.get("_auto_stock_sync_msg"):
    st.sidebar.caption(st.session_state.get("_auto_stock_sync_msg"))

with st.sidebar:
    st.title("📦 Insumos Mayor")
    st.write(f"**{user['nombre']}**")
    st.caption(f"{user['rol']} · {user['username']}")
    ultima_stock_sidebar = get_config("stock_auto_sync_ultima", "")
    if ultima_stock_sidebar:
        st.caption(f"📦 Stock actualizado: {ultima_stock_sidebar}")
    else:
        st.caption("📦 Stock todavía no sincronizado.")
    if user["rol"] == "admin":
        if st.button("🔄 Actualizar stock ahora", use_container_width=True):
            barra = st.progress(0)
            estado_sync = st.empty()
            try:
                ok, no, errors = sync_todos_productos(progress_bar=barra, status_box=estado_sync)
                set_config("stock_auto_sync_ultima", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                estado_sync.success(f"Stock actualizado: {ok} sincronizados, {no} sin actualizar.")
                if errors:
                    st.warning("\n".join(errors[:5]))
            except Exception as e:
                estado_sync.error(f"No se pudo actualizar stock: {e}")
    st.markdown("---")

    opciones = ["Tienda", "Carrito", "Mis pedidos", "Mis créditos", "Mi perfil"]
    if user["rol"] == "admin":
        opciones += ["Dashboard", "Control POS", "Rentabilidad", "Publicaciones", "Vendedores", "Productos", "Categorías", "Cotizaciones", "Usuarios", "Validar créditos", "Reportes", "Configuración", "Respaldo"]
    elif user["rol"] == "vendedor":
        opciones += ["Publicaciones", "Vendedores"]
    elif user["rol"] == "vendedor_mercadolibre":
        opciones += ["Publicaciones"]

    current = st.session_state.get("menu", "Tienda")
    if current not in opciones:
        current = "Tienda"

    menu = st.radio("Menú", opciones, index=opciones.index(current))
    st.session_state.menu = menu

    st.markdown("---")
    try:
        _ci, _cu, _ct = carrito_resumen_texto(user["username"])
        st.caption(f"🛒 Carrito: {_ci} línea(s) · {_cu} unidad(es) · {money_usd(_ct)}")
        _last = st.session_state.get("_cart_last_added")
        if _last:
            st.caption(f"Último agregado: {_last.get('texto','')} · {_last.get('producto','')}")
    except Exception:
        pass
    if st.button("Cerrar sesión", use_container_width=True):
        logout()

backup_auto_si_corresponde()

if menu == "Tienda":
    tienda()
elif menu == "Carrito":
    carrito_view()
elif menu == "Mis pedidos":
    mis_pedidos()
elif menu == "Mis créditos":
    mis_creditos()
elif menu == "Mi perfil":
    mi_perfil()
elif menu == "Dashboard":
    dashboard_admin()
elif menu == "Control POS":
    control_pos()
elif menu == "Rentabilidad":
    rentabilidad_productos()
elif menu == "Publicaciones":
    publicaciones()
elif menu == "Vendedores":
    vendedores_asignaciones()
elif menu == "Productos":
    admin_productos()
elif menu == "Categorías":
    admin_categorias()
elif menu == "Cotizaciones":
    admin_cotizaciones()
elif menu == "Usuarios":
    admin_usuarios()
elif menu == "Validar créditos":
    validar_creditos()
elif menu == "Reportes":
    reportes()
elif menu == "Configuración":
    admin_config()
elif menu == "Respaldo":
    respaldo()
