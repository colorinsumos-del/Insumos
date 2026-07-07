
import os
import json
import sqlite3
import shutil
import zipfile
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

APP_NAME = "Sistema de Insumos al Mayor V79 Fix3 Pago Sugerido en Cero Fix4 Crédito Residual"
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
        visible_tienda INTEGER DEFAULT 1,
        es_variante INTEGER DEFAULT 0,
        grupo_variantes TEXT,
        nombre_visible_grupo TEXT,
        atributo_medida TEXT,
        atributo_color TEXT,
        orden_variante INTEGER DEFAULT 0,
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
    CREATE TABLE IF NOT EXISTS nomina_trabajadores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        cedula TEXT,
        cargo TEXT,
        fecha_ingreso TEXT,
        salario_mensual_usd REAL DEFAULT 250,
        activo INTEGER DEFAULT 1,
        telefono TEXT,
        metodo_pago TEXT,
        banco TEXT,
        titular_pago TEXT,
        cedula_rif_pago TEXT,
        telefono_pago_movil TEXT,
        tipo_cuenta_pago TEXT,
        notas TEXT,
        creado_en TEXT,
        actualizado_en TEXT
    )
    """)

    q("""
    CREATE TABLE IF NOT EXISTS nomina_adelantos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trabajador_id INTEGER,
        fecha TEXT,
        monto_usd REAL DEFAULT 0,
        tasa_proveedor REAL DEFAULT 0,
        monto_bs REAL DEFAULT 0,
        saldo_usd REAL DEFAULT 0,
        estado TEXT DEFAULT 'Pendiente',
        motivo TEXT,
        pago_id INTEGER DEFAULT 0,
        creado_en TEXT
    )
    """)

    q("""
    CREATE TABLE IF NOT EXISTS nomina_pagos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trabajador_id INTEGER,
        fecha TEXT,
        periodo TEXT,
        base_usd REAL DEFAULT 0,
        bono_usd REAL DEFAULT 0,
        utilidad_usd REAL DEFAULT 0,
        descuento_adelanto_usd REAL DEFAULT 0,
        total_usd REAL DEFAULT 0,
        tasa_proveedor REAL DEFAULT 0,
        total_bs REAL DEFAULT 0,
        metodo_pago TEXT,
        referencia TEXT,
        notas TEXT,
        creado_por TEXT,
        creado_en TEXT
    )
    """)

    q("""
    CREATE TABLE IF NOT EXISTS configuracion (
        clave TEXT PRIMARY KEY,
        valor TEXT
    )
    """)

    q("""
    CREATE TABLE IF NOT EXISTS metodos_pago (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT,
        tipo TEXT,
        banco TEXT,
        titular TEXT,
        cuenta TEXT,
        cedula_rif TEXT,
        tipo_cuenta TEXT,
        telefono TEXT,
        correo TEXT,
        apodo TEXT,
        activo INTEGER DEFAULT 1,
        notas TEXT,
        creado_en TEXT,
        actualizado_en TEXT
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
    set_default("envio_ml_3_5_bcv", "0")
    set_default("envio_ml_5_10_bcv", "0")
    set_default("envio_ml_10_40_bcv", "0")
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
    # V77: producto visible en tienda y variantes agrupadas.
    add_col("productos", "visible_tienda", "INTEGER DEFAULT 1")
    add_col("productos", "es_variante", "INTEGER DEFAULT 0")
    add_col("productos", "grupo_variantes", "TEXT")
    add_col("productos", "nombre_visible_grupo", "TEXT")
    add_col("productos", "atributo_medida", "TEXT")
    add_col("productos", "atributo_color", "TEXT")
    add_col("productos", "orden_variante", "INTEGER DEFAULT 0")
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
    add_col("pedidos", "pedido_token", "TEXT")
    try:
        q("CREATE UNIQUE INDEX IF NOT EXISTS idx_pedidos_pedido_token ON pedidos(pedido_token) WHERE pedido_token IS NOT NULL AND pedido_token<>''")
    except Exception:
        pass

    add_col("creditos", "tipo_credito", "TEXT DEFAULT 'usd'")
    add_col("creditos", "tasa_bcv_creacion", "REAL DEFAULT 0")
    add_col("creditos", "monto_bcv", "REAL DEFAULT 0")
    add_col("creditos", "saldo_bcv", "REAL DEFAULT 0")
    add_col("creditos", "total_bs_base", "REAL DEFAULT 0")

    add_col("abonos", "tipo_credito", "TEXT DEFAULT 'usd'")
    add_col("abonos", "monto_bcv", "REAL DEFAULT 0")
    add_col("abonos", "tasa_bcv", "REAL DEFAULT 0")
    add_col("abonos", "monto_bs_esperado", "REAL DEFAULT 0")
    add_col("abonos", "tasa_proveedor", "REAL DEFAULT 0")
    add_col("abonos", "metodo_pago_id", "INTEGER DEFAULT 0")

    # V75: migraciones suaves nómina.
    try:
        add_col("nomina_trabajadores", "telefono", "TEXT")
        add_col("nomina_trabajadores", "metodo_pago", "TEXT")
        add_col("nomina_trabajadores", "banco", "TEXT")
        add_col("nomina_trabajadores", "titular_pago", "TEXT")
        add_col("nomina_trabajadores", "cedula_rif_pago", "TEXT")
        add_col("nomina_trabajadores", "telefono_pago_movil", "TEXT")
        add_col("nomina_trabajadores", "tipo_cuenta_pago", "TEXT")
        add_col("nomina_trabajadores", "notas", "TEXT")
        add_col("nomina_trabajadores", "actualizado_en", "TEXT")
        add_col("nomina_adelantos", "pago_id", "INTEGER DEFAULT 0")
        add_col("nomina_pagos", "utilidad_usd", "REAL DEFAULT 0")
        add_col("nomina_pagos", "bono_usd", "REAL DEFAULT 0")
    except Exception:
        pass

    # V71: separar POS del estado comercial y normalizar créditos activos.
    try:
        q("UPDATE creditos SET status='En curso' WHERE status='Pendiente'")
        q("UPDATE pedidos SET status='Crédito en curso' WHERE status='Crédito / Pendiente de pago'")
        q("UPDATE pedidos SET status='Confirmado' WHERE status='Procesado en POS'")
    except Exception:
        pass

    set_default("stock_auto_sync_minutos", "0")
    set_default("nomina_dias_utilidades", "30")

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

    tablas = ["usuarios", "categorias", "productos", "cotizaciones", "pedidos", "creditos", "abonos", "metodos_pago", "carritos", "productos_vendedores", "nomina_trabajadores", "nomina_adelantos", "nomina_pagos", "configuracion"]
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

    tablas = ["categorias", "usuarios", "productos", "cotizaciones", "pedidos", "creditos", "abonos", "metodos_pago", "carritos", "productos_vendedores", "nomina_trabajadores", "nomina_adelantos", "nomina_pagos", "configuracion"]

    if modo == "reemplazar":
        for t in ["abonos", "creditos", "pedidos", "cotizaciones", "productos", "categorias", "metodos_pago", "carritos", "productos_vendedores", "nomina_pagos", "nomina_adelantos", "nomina_trabajadores"]:
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
                elif tabla == "carritos" and "username" in row:
                    sql = f"INSERT INTO {tabla} ({col_sql}) VALUES ({placeholders}) ON CONFLICT(username) DO UPDATE SET {update_sql}"
                elif tabla == "productos_vendedores" and "sku" in row and "vendedor_username" in row:
                    sql = f"INSERT INTO {tabla} ({col_sql}) VALUES ({placeholders}) ON CONFLICT(sku,vendedor_username) DO UPDATE SET {update_sql}"
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

def crear_respaldo_zip(destino=None, incluir_pagos=True, incluir_pdfs=True):
    """
    Crea un ZIP completo con JSON + DB + archivos físicos opcionales.
    Ideal para migrar o proteger comprobantes subidos por web.
    """
    destino = Path(destino or get_config("backup_folder", str(BACKUP_DIR)))
    destino.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path, db_path = crear_respaldo(destino)
    zip_path = destino / f"backup_insumos_mayor_completo_{stamp}.zip"

    readme_txt = f"""RESPALDO COMPLETO - SISTEMA INSUMOS MAYOR

Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Incluye:
- backup.json: datos principales del sistema.
- backup.db: copia completa de la base de datos SQLite.
- static/pagos: comprobantes físicos subidos por clientes/admin, si se incluyeron.
- static/cotizaciones: PDFs generados, si se incluyeron.

Nota:
El JSON guarda la referencia del comprobante, pero el archivo físico vive en static/pagos.
Por eso este ZIP es el respaldo más completo cuando usas carga web de comprobantes.
"""

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        if json_path and Path(json_path).exists():
            z.write(json_path, arcname="backup.json")
        if db_path and Path(db_path).exists():
            z.write(db_path, arcname="backup.db")

        z.writestr("README_RESPALDO.txt", readme_txt)

        if incluir_pagos and PAGOS_DIR.exists():
            for f in PAGOS_DIR.rglob("*"):
                if f.is_file():
                    z.write(f, arcname=str(Path("static") / "pagos" / f.relative_to(PAGOS_DIR)))

        if incluir_pdfs and PDF_DIR.exists():
            for f in PDF_DIR.rglob("*"):
                if f.is_file():
                    z.write(f, arcname=str(Path("static") / "cotizaciones" / f.relative_to(PDF_DIR)))

    return str(zip_path)

def exportar_zip_actual(incluir_pagos=True, incluir_pdfs=True):
    destino = BACKUP_DIR
    zip_path = crear_respaldo_zip(destino, incluir_pagos=incluir_pagos, incluir_pdfs=incluir_pdfs)
    with open(zip_path, "rb") as f:
        content = f.read()
    return content, Path(zip_path).name

def archivo_size_mb(path):
    try:
        return round(Path(path).stat().st_size / (1024 * 1024), 3)
    except Exception:
        return 0.0

def comprobantes_referenciados():
    refs = set()
    try:
        rows = q("SELECT comprobante_path FROM abonos WHERE comprobante_path IS NOT NULL AND comprobante_path<>''", fetch=True)
    except Exception:
        rows = []
    for r in rows:
        try:
            p = Path(r["comprobante_path"])
            refs.add(str(p.resolve()))
            refs.add(str(p))
        except Exception:
            pass
    return refs

def listar_archivos_limpieza_pagos(dias=60, solo_no_referenciados=True):
    dias = int(dias or 60)
    limite = datetime.now() - timedelta(days=dias)
    refs = comprobantes_referenciados()
    data = []
    total_mb = 0.0

    if not PAGOS_DIR.exists():
        return data, total_mb

    for f in PAGOS_DIR.rglob("*"):
        if not f.is_file():
            continue
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime > limite:
                continue
            ref_abs = str(f.resolve())
            ref_rel = str(f)
            referenciado = ref_abs in refs or ref_rel in refs
            if solo_no_referenciados and referenciado:
                continue
            size_mb = archivo_size_mb(f)
            total_mb += size_mb
            data.append({
                "archivo": str(f),
                "nombre": f.name,
                "modificado": mtime.strftime("%Y-%m-%d %H:%M:%S"),
                "mb": size_mb,
                "referenciado_en_abonos": referenciado
            })
        except Exception:
            pass

    return data, round(total_mb, 3)

def borrar_archivos_limpieza_pagos(dias=60, solo_no_referenciados=True):
    archivos, total_mb = listar_archivos_limpieza_pagos(dias=dias, solo_no_referenciados=solo_no_referenciados)
    borrados = 0
    errores = []
    for row in archivos:
        try:
            Path(row["archivo"]).unlink(missing_ok=True)
            borrados += 1
        except Exception as e:
            errores.append(f"{row['archivo']}: {e}")
    return borrados, total_mb, errores


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

def registrar_pago_contado_pendiente(pedido_id, username, monto_usd, monto_bs, metodo, referencia="", comprobante=None, notas="", metodo_pago_id=0):
    """
    Registra una notificación de pago contado como abono sin crédito asociado.
    Queda pendiente para que admin lo valide desde Centro admin / Validar créditos.
    """
    try:
        path = save_uploaded_file(comprobante, PAGOS_DIR, prefix=f"pago_contado_pedido_{pedido_id}") if comprobante is not None else None
    except Exception:
        path = None

    q("""INSERT INTO abonos
         (credito_id,pedido_id,username,fecha,monto_usd,monto_bs,metodo,referencia,comprobante_path,status,notas,
          tipo_credito,monto_bcv,tasa_bcv,tasa_proveedor,monto_bs_esperado,metodo_pago_id)
         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (0, int(pedido_id), username, now(), float(monto_usd or 0), float(monto_bs or 0), metodo, referencia, path,
       "Pendiente de validar", notas, "contado", 0, get_tasa_bcv(), get_tasa_proveedor(), float(monto_bs or 0), int(metodo_pago_id or 0)))
    try:
        q("UPDATE pedidos SET status='Pago por verificar' WHERE id=? AND tipo_pago='contado' AND status NOT IN ('Finalizado / Pagado','Cancelado','Anulado')", (int(pedido_id),))
    except Exception:
        pass
    return True


def crear_pedido_desde_carrito(user, carrito, tipo_pago, metodo_pago, envio_usd, notas, cliente_extra=None, tipo_credito="usd", cliente_target_username=None, pedido_token=None):
    pedido_token = (pedido_token or "").strip()
    if pedido_token:
        ya_creado = q("SELECT id FROM pedidos WHERE pedido_token=?", (pedido_token,), fetch=True)
        if ya_creado:
            return int(ya_creado[0]["id"]), "Este pedido ya estaba creado. No se duplicó."

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
          total_bs_proveedor, peso_total_kg, status, notas, credito_tipo, total_bcv_credito, pedido_token)
         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (now(), username, cliente_nombre, cliente_rif, cliente_tel, cliente_dir, json.dumps(carrito, ensure_ascii=False),
       tipo_pago, metodo_pago, subtotal, float(envio_usd or 0), total, tasa, tasa_bcv,
       total_bs_base, t["peso_total_kg"],
       "Crédito en curso" if tipo_pago == "credito" else "Pendiente de pago",
       notas, credito_tipo, total_bcv_credito, pedido_token))
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
               total_bcv_credito, total_bcv_credito, tasa, "En curso", nota_credito,
               "bcv", tasa_bcv, total_bcv_credito, total_bcv_credito, total_bs_base))
        else:
            q("""INSERT INTO creditos
                 (pedido_id, username, cliente_nombre, fecha_inicio, fecha_vencimiento,
                  monto_usd, saldo_usd, tasa_proveedor, status, notas,
                  tipo_credito, tasa_bcv_creacion, monto_bcv, saldo_bcv, total_bs_base)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (pedido_id, username, cliente_nombre, now(), venc,
               total, total, tasa, "En curso", "Crédito creado desde pedido.",
               "usd", tasa_bcv, 0, 0, total_bs_base))
        credito_id = q("SELECT last_insert_rowid() AS id", fetch=True)[0]["id"]
        q("UPDATE pedidos SET credito_id=?, status='Crédito en curso' WHERE id=?", (credito_id, pedido_id))
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
    if ab["status"] not in ["Pendiente de validar", "Rechazado"]:
        return False, f"El abono no está disponible para validar. Estado actual: {ab['status']}."

    credito_id = int(ab["credito_id"] or 0)
    if credito_id <= 0:
        q("""UPDATE abonos SET status='Validado', validado_por=?, fecha_validacion=? WHERE id=?""",
          (admin_username, now(), abono_id))
        if int(ab["pedido_id"] or 0) > 0:
            q("UPDATE pedidos SET status='Finalizado / Pagado' WHERE id=?", (int(ab["pedido_id"]),))
        return True, f"Pago contado validado. Pedido #{int(ab['pedido_id'] or 0)} marcado como Finalizado / Pagado."

    cr_rows = q("SELECT * FROM creditos WHERE id=?", (credito_id,), fetch=True)
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
            q("UPDATE pedidos SET status='Crédito en curso' WHERE id=?", (cr["pedido_id"],))
        return True, f"Abono BCV validado. Saldo actual: {money_usd(nuevo_saldo_bcv)} BCV"

    nuevo_saldo = max(0.0, float(cr["saldo_usd"] or 0) - float(ab["monto_usd"] or 0))
    nuevo_status = "Pagado" if nuevo_saldo <= 0.009 else "Parcial"
    q("""UPDATE abonos SET status='Validado', validado_por=?, fecha_validacion=? WHERE id=?""",
      (admin_username, now(), abono_id))
    q("UPDATE creditos SET saldo_usd=?, status=? WHERE id=?", (nuevo_saldo, nuevo_status, cr["id"]))
    if nuevo_status == "Pagado":
        q("UPDATE pedidos SET status='Finalizado / Pagado' WHERE id=?", (cr["pedido_id"],))
    else:
        q("UPDATE pedidos SET status='Crédito en curso' WHERE id=?", (cr["pedido_id"],))
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

def sugerir_envio_detalle(peso_kg):
    """
    Envío ML/ENVÍO por rangos configurados en bolívares.
    Se convierte internamente a USD equivalente usando tasa proveedor para mantener
    compatibilidad con totales/pedidos históricos.
    """
    peso_kg = float(peso_kg or 0)
    tasa = float(get_tasa_proveedor() or 0)
    tasa_bcv = float(get_tasa_bcv() or 0)

    rango = "Sin envío sugerido"
    envio_bs = 0.0

    if 3 <= peso_kg <= 5:
        rango = "3 a 5 kg"
        envio_bs = parse_float(get_config("envio_ml_3_5_bcv", "0"), 0)
    elif 5 < peso_kg <= 10:
        rango = "5 a 10 kg"
        envio_bs = parse_float(get_config("envio_ml_5_10_bcv", "0"), 0)
    elif 10 < peso_kg <= 40:
        rango = "10 a 40 kg"
        envio_bs = parse_float(get_config("envio_ml_10_40_bcv", "0"), 0)
        if envio_bs <= 0 and tasa_bcv > 0:
            # Compatibilidad con la configuración vieja: $10 BCV para 10 a 40 kg.
            envio_bs = parse_float(get_config("envio_ml_10_40_usd", "10"), 10) * tasa_bcv
    elif peso_kg > 40:
        rango = "Más de 40 kg"

    envio_usd = (envio_bs / tasa) if tasa > 0 else 0.0
    return {
        "peso_kg": peso_kg,
        "rango": rango,
        "envio_bs": float(envio_bs or 0),
        "envio_usd": float(envio_usd or 0),
    }

def sugerir_envio(peso_kg):
    return sugerir_envio_detalle(peso_kg)["envio_usd"]

def calcular_carrito(carrito):
    tasa = get_tasa_proveedor()
    subtotal = 0.0
    peso = 0.0
    unidades_total = 0
    for sku, item in carrito.items():
        subtotal += float(item.get("precio_total", 0) or 0)
        peso += float(item.get("peso_total_kg", 0) or 0)
        unidades_total += int(item.get("unidades_base_total", 0) or 0)

    envio_detalle = sugerir_envio_detalle(peso)
    envio = float(envio_detalle["envio_usd"] or 0)
    return {
        "subtotal": subtotal,
        "peso_total_kg": peso,
        "unidades_total": unidades_total,
        "envio": envio,
        "envio_bs": float(envio_detalle["envio_bs"] or 0),
        "envio_rango": envio_detalle["rango"],
        "total": subtotal + envio,
        "total_bs": (subtotal + envio) * tasa,
    }


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
    Regla V58 optimizada:
    - Precio especial unidad = precio por unidad.
    - Precio especial presentación intermedia = precio por unidad dentro del pack/docena/caja.
    - Precio especial bulto = precio por unidad dentro del bulto.

    Ejemplo:
    Si un bulto trae 50 y el total especial deseado es $11,
    cargar precio especial bulto c/u = 11 / 50 = 0.22.
    """
    try:
        data = dict(prod)
    except Exception:
        data = {k: prod[k] for k in prod.keys()}

    data["_precio_especial_aplicado"] = False
    if user is None:
        return data

    if usuario_es_cliente_especial(user) and producto_maneja_precio_especial(prod):
        try:
            pu = float(data.get("precio_especial_unidad") or 0)
            pd = float(data.get("precio_especial_docena") or 0)
            pb = float(data.get("precio_especial_bulto") or 0)
            if pu > 0:
                data["precio_unidad"] = pu
                data["_precio_especial_aplicado"] = True
            if pd > 0:
                data["precio_docena"] = pd
                data["_precio_especial_aplicado"] = True
            if pb > 0:
                data["precio_bulto"] = pb
                data["_precio_especial_aplicado"] = True
        except Exception:
            pass
    return data


def producto_intermedia_nombre(prod):
    """Nombre comercial de la presentación intermedia: Docena, Pack, Caja, Paquete."""
    try:
        nombre = prod["presentacion_intermedia_nombre"]
    except Exception:
        nombre = None
    nombre = str(nombre or "Docena").strip()
    return nombre if nombre else "Docena"

def producto_intermedia_cantidad(prod):
    """Cantidad de unidades base de la presentación intermedia."""
    try:
        val = int(prod["presentacion_intermedia_cantidad"] or 12)
    except Exception:
        val = 12
    return max(1, val)

def producto_intermedia_label(prod):
    return f"{producto_intermedia_nombre(prod)} x{producto_intermedia_cantidad(prod)}"

def presentacion_display_item(item):
    p = str(item.get("presentacion", "unidad"))
    if p == "docena":
        return item.get("presentacion_nombre") or item.get("presentacion_label") or "Docena"
    if p == "bulto":
        return "Bulto"
    return "Unidad"

def money_credito(cr, campo="saldo"):
    tipo = str(cr["tipo_credito"] if "tipo_credito" in cr.keys() and cr["tipo_credito"] else "usd").lower()
    if tipo == "bcv":
        valor = float(cr["saldo_bcv"] if campo == "saldo" else cr["monto_bcv"] or 0)
        return f"{money_usd(valor)} BCV"
    valor = float(cr["saldo_usd"] if campo == "saldo" else cr["monto_usd"] or 0)
    return money_usd(valor)

def credito_bs_hoy(cr):
    tipo = str(cr["tipo_credito"] if "tipo_credito" in cr.keys() and cr["tipo_credito"] else "usd").lower()
    if tipo == "bcv":
        return float(cr["saldo_bcv"] or 0) * get_tasa_bcv()
    return float(cr["saldo_usd"] or 0) * get_tasa_proveedor()

def auto_sync_stock_si_corresponde(user=None):
    """Sincroniza stock automáticamente solo para admin y respetando intervalo mínimo."""
    if not wc_ready():
        return
    try:
        minutos = int(parse_float(get_config("stock_auto_sync_minutos", "180"), 180))
    except Exception:
        minutos = 180
    if minutos <= 0:
        return

    clave = "stock_auto_sync_ultima"
    ultima = get_config(clave, "")

    # Los clientes/vendedores no quedan bloqueados por sincronización al entrar.
    if user is not None and user["rol"] != "admin":
        if ultima:
            st.session_state["_auto_stock_sync_msg"] = f"Stock local usado. Última actualización: {ultima}."
        return

    debe = True
    try:
        if ultima:
            dt = datetime.strptime(ultima, "%Y-%m-%d %H:%M:%S")
            debe = (datetime.now() - dt).total_seconds() >= minutos * 60
    except Exception:
        debe = True

    if st.session_state.get("_auto_stock_sync_done") == ultima and ultima:
        debe = False

    if debe:
        try:
            with st.spinner("Actualizando stock con WooCommerce... puedes esperar unos segundos."):
                ok, no, errors = sync_todos_productos()
            set_config(clave, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            st.session_state["_auto_stock_sync_done"] = get_config(clave, "")
            st.session_state["_auto_stock_sync_msg"] = f"Stock actualizado automáticamente: {ok} sincronizados."
        except Exception as e:
            st.session_state["_auto_stock_sync_msg"] = f"No se pudo actualizar stock automáticamente: {e}"
    else:
        if ultima:
            st.session_state["_auto_stock_sync_msg"] = f"Stock actualizado: {ultima}."


def get_producto_row(sku):
    rows = q("SELECT * FROM productos WHERE sku=?", (sku,), fetch=True)
    return rows[0] if rows else None

def recalcular_item_carrito(item, nueva_cantidad=None, user=None):
    """
    Recalcula un item del carrito usando precios actuales del producto.
    Si se pasa user y el user es cliente especial, aplica precio especial del producto.
    Si no se pasa user, intenta usar el cliente de precio guardado en el item.
    """
    sku = item.get("sku")
    prod = get_producto_row(sku)
    if not prod:
        return item

    if user is None and item.get("cliente_precio_username"):
        user = get_user(item.get("cliente_precio_username"))

    prod_precio = producto_con_precio_para_usuario(prod, user)

    cantidad = int(nueva_cantidad if nueva_cantidad is not None else item.get("cantidad_presentacion", 1))
    cantidad = max(1, cantidad)
    presentacion = item.get("presentacion", "unidad")

    precio_calc = calcular_precio_inteligente(prod_precio, presentacion, cantidad)
    item["cantidad_presentacion"] = cantidad
    item["equivalencia"] = int(precio_calc["equivalencia"])
    item["unidades_base_total"] = int(precio_calc["unidades_base_total"])
    item["precio_presentacion"] = float(precio_calc["precio_presentacion"])
    item["precio_total"] = float(precio_calc["precio_total"])
    item["escala_aplicada"] = precio_calc["escala_aplicada"]
    item["detalle_precio"] = precio_calc.get("detalle_precio", precio_calc["escala_aplicada"])
    item["presentacion_nombre"] = precio_calc.get("presentacion_nombre", producto_intermedia_nombre(prod_precio) if presentacion == "docena" else presentacion.title())
    item["presentacion_label"] = precio_calc.get("presentacion_label", producto_intermedia_label(prod_precio) if presentacion == "docena" else presentacion.title())
    item["peso_total_kg"] = float(prod["peso_unidad_kg"] or 0) * int(precio_calc["unidades_base_total"])
    item["imagen_url"] = prod["wc_imagen_url"]
    item["desc"] = prod["descripcion"]
    item["precio_especial_aplicado"] = bool(prod_precio.get("_precio_especial_aplicado", False))
    if user is not None:
        item["cliente_precio_username"] = user["username"]
        item["cliente_precio_nombre"] = user["nombre"] or user["username"]
    if item["precio_especial_aplicado"]:
        item["detalle_precio"] = f"{item['detalle_precio']} · precio especial"
    return item


def texto_linea_carrito(item):
    """Resumen limpio para cliente en carrito. El detalle operativo queda para Packing List."""
    presentacion = item.get("presentacion", "unidad")
    cantidad = int(item.get("cantidad_presentacion", 1) or 1)
    unidades = int(item.get("unidades_base_total", cantidad) or cantidad)
    nombre = presentacion_display_item(item)
    extra = " · ⭐ precio especial" if item.get("precio_especial_aplicado") else ""

    if presentacion == "unidad":
        return f"{unidades} unidad(es){extra}"
    return f"{cantidad} {nombre}(s) · {unidades} unidad(es){extra}"



def resumen_presentacion_catalogo(prod, presentacion, cantidad):
    """Devuelve texto de ayuda para la card antes de agregar al carrito."""
    calc = calcular_precio_inteligente(prod, presentacion, cantidad)
    unidades = int(calc["unidades_base_total"])
    total = float(calc["precio_total"])
    if presentacion == "unidad":
        return f"{unidades} unidad(es) · Precio aplicado: {calc['escala_aplicada']} · Total: {money_usd(total)}"
    if cantidad == 1:
        return f"1 {presentacion} = {unidades} unidad(es) · Total {presentacion}: {money_usd(total)}"
    return f"{cantidad} {presentacion}(s) = {unidades} unidad(es) · Total: {money_usd(total)}"


def formato_cantidad_pdf(item):
    import re
    presentacion = str(item.get("presentacion", "unidad")).lower()
    escala = str(item.get("escala_aplicada", "")).lower()
    unidades = int(item.get("unidades_base_total", item.get("cantidad_presentacion", 1)) or 1)
    cantidad_pres = int(item.get("cantidad_presentacion", 1) or 1)

    if presentacion == "bulto":
        cant = "BULTO" if cantidad_pres == 1 else f"BULTO x{cantidad_pres}"
        return cant, f"{unidades} und"

    if presentacion == "docena":
        nombre = str(item.get("presentacion_nombre") or item.get("presentacion_label") or "DOC").upper()
        nombre = nombre.split(" X")[0].strip()
        if nombre == "DOCENA":
            nombre = "DOC"
        cant = nombre if cantidad_pres == 1 else f"{nombre} x{cantidad_pres}"
        return cant, f"{unidades} und"

    # Para unidad con precio inteligente: solo mostrar DOC/BULTO si la escala es cerrada y exacta.
    if "bulto" in escala and "+" not in escala:
        n = unidades  # fallback
        m = re.search(r"(\\d+)\\s*bulto", escala)
        if m:
            n = int(m.group(1))
        return ("BULTO" if n == 1 else f"BULTO x{n}"), f"{unidades} und"

    # Presentación intermedia por compra en unidades: docena, pack, caja, etc.
    for palabra, etiqueta in [("docena", "DOC"), ("pack", "PACK"), ("caja", "CAJA"), ("paquete", "PAQ")]:
        if palabra in escala and "+" not in escala:
            m = re.search(r"(\d+)\s*" + palabra, escala)
            n = int(m.group(1)) if m else 1
            return (etiqueta if n == 1 else f"{etiqueta} x{n}"), f"{unidades} und"

    return str(unidades), "und"

def sku_limpio_pdf(sku_text):
    return str(sku_text or "").split("::")[0]


def eliminar_pedido_seguro(pedido_id):
    rows = q("SELECT * FROM pedidos WHERE id=?", (int(pedido_id),), fetch=True)
    if not rows:
        return False, "Pedido no encontrado."
    ped = rows[0]
    if ped["credito_id"]:
        return False, "Este pedido tiene crédito asociado. Elimina/anula primero el crédito para no perder trazabilidad."
    q("DELETE FROM pedidos WHERE id=?", (int(pedido_id),))
    reset_sqlite_sequence("pedidos")
    return True, "Pedido eliminado."

def eliminar_credito_y_abonos(credito_id):
    rows = q("SELECT * FROM creditos WHERE id=?", (int(credito_id),), fetch=True)
    if not rows:
        return False, "Crédito no encontrado."
    cr = rows[0]
    q("DELETE FROM abonos WHERE credito_id=?", (int(credito_id),))
    q("UPDATE pedidos SET credito_id=NULL, status='Anulado' WHERE credito_id=?", (int(credito_id),))
    q("DELETE FROM creditos WHERE id=?", (int(credito_id),))
    return True, "Crédito eliminado, abonos eliminados y pedido asociado marcado como Anulado."


def reset_sqlite_sequence(table_name):
    """
    Reinicia el consecutivo AUTOINCREMENT al máximo ID actual.
    Así, si se elimina el último registro, el próximo retoma el número anterior.
    """
    try:
        rows = q(f"SELECT COALESCE(MAX(id),0) AS max_id FROM {table_name}", fetch=True)
        max_id = int(rows[0]["max_id"] or 0)
        exists = q("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'", fetch=True)
        if exists:
            q("UPDATE sqlite_sequence SET seq=? WHERE name=?", (max_id, table_name))
    except Exception:
        pass

def eliminar_cotizacion(cot_id):
    q("DELETE FROM cotizaciones WHERE id=?", (int(cot_id),))
    reset_sqlite_sequence("cotizaciones")


def anular_credito_de_pedido(pedido_id, motivo="Pedido cancelado"):
    rows = q("SELECT * FROM pedidos WHERE id=?", (int(pedido_id),), fetch=True)
    if not rows:
        return False, "Pedido no encontrado."
    ped = rows[0]
    if ped["credito_id"]:
        q("UPDATE creditos SET saldo_usd=0, status='Anulado', notas=COALESCE(notas,'') || ? WHERE id=?",
          (f"\n[{now()}] {motivo}", int(ped["credito_id"])))
        q("UPDATE abonos SET status='Anulado' WHERE credito_id=? AND status='Pendiente de validar'", (int(ped["credito_id"]),))
    q("UPDATE pedidos SET status='Cancelado' WHERE id=?", (int(pedido_id),))
    return True, "Pedido cancelado y crédito asociado anulado."

def marcar_credito_pagado(credito_id, actor="admin"):
    rows = q("SELECT * FROM creditos WHERE id=?", (int(credito_id),), fetch=True)
    if not rows:
        return False, "Crédito no encontrado."
    cr = rows[0]
    tipo = str(cr["tipo_credito"] if "tipo_credito" in cr.keys() and cr["tipo_credito"] else "usd").lower()
    if tipo == "bcv":
        saldo = float(cr["saldo_bcv"] or cr["saldo_usd"] or 0)
        if saldo > 0.009:
            tasa_bcv = get_tasa_bcv()
            q("""INSERT INTO abonos
                 (credito_id,pedido_id,username,fecha,monto_usd,monto_bs,metodo,referencia,comprobante_path,status,validado_por,fecha_validacion,notas,
                  tipo_credito,monto_bcv,tasa_bcv,monto_bs_esperado)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (cr["id"], cr["pedido_id"], cr["username"], now(), saldo, saldo*tasa_bcv, "Cierre administrativo", "CREDITO-BCV-PAGADO", None, "Validado", actor, now(), "Cierre manual de crédito BCV como pagado.",
               "bcv", saldo, tasa_bcv, saldo*tasa_bcv))
        q("UPDATE creditos SET saldo_bcv=0, saldo_usd=0, status='Pagado' WHERE id=?", (int(credito_id),))
    else:
        saldo = float(cr["saldo_usd"] or 0)
        if saldo > 0.009:
            tasa = get_tasa_proveedor()
            q("""INSERT INTO abonos
                 (credito_id,pedido_id,username,fecha,monto_usd,monto_bs,metodo,referencia,comprobante_path,status,validado_por,fecha_validacion,notas,
                  tipo_credito,monto_bcv,tasa_bcv,monto_bs_esperado)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (cr["id"], cr["pedido_id"], cr["username"], now(), saldo, saldo*tasa, "Cierre administrativo", "CREDITO-PAGADO", None, "Validado", actor, now(), "Cierre manual de crédito como pagado.",
               "usd", 0, get_tasa_bcv(), saldo*tasa))
        q("UPDATE creditos SET saldo_usd=0, status='Pagado' WHERE id=?", (int(credito_id),))
    q("UPDATE pedidos SET status='Finalizado / Pagado' WHERE id=?", (int(cr["pedido_id"]),))
    return True, "Crédito marcado como Pagado y pedido como Finalizado / Pagado."

def validar_stock_carrito_woocommerce(carrito):
    """
    Reconsulta WooCommerce antes de crear pedido.
    Devuelve (ok, mensajes).
    """
    mensajes = []
    requeridos = {}
    for k, item in carrito.items():
        sku = item.get("sku")
        requeridos[sku] = requeridos.get(sku, 0) + int(item.get("unidades_base_total", 0) or 0)

    for sku, req in requeridos.items():
        try:
            p = wc_get_by_sku(sku)
            if not p:
                mensajes.append(f"{sku}: no encontrado en WooCommerce.")
                continue
            stock_q = p.get("stock_quantity")
            stock = 0 if stock_q is None else int(float(stock_q))
            status = p.get("stock_status") or ""
            # Actualiza cache local también.
            q("""UPDATE productos SET wc_stock=?, wc_stock_status=?, wc_imagen_url=?, wc_permalink=?, ultima_sync=?, actualizado_en=? WHERE sku=?""",
              (stock, status, first_image_url(p), p.get("permalink") or "", now(), now(), sku))
            if status == "outofstock" or stock < req:
                mensajes.append(f"{sku}: stock insuficiente. Requiere {req}, disponible {stock}.")
        except Exception as e:
            mensajes.append(f"{sku}: error consultando stock web: {e}")
    return len(mensajes) == 0, mensajes

def formato_cantidad_pdf_simple(item):
    """
    Cant. compacto para PDF sin columna Pres:
    DOC, DOC x2, BULTO, BULTO x2 o 15 und.
    """
    cant, pres = formato_cantidad_pdf(item)
    if cant in ["DOC", "BULTO"] or "x" in cant:
        return cant
    return f"{cant} {pres}".strip()

# -----------------------------
# PDF
# -----------------------------
def pdf_clean(text):
    """
    Limpia texto para FPDF clásico, que trabaja con Latin-1.
    Evita errores en Railway/Python 3.13 al generar PDF con caracteres especiales.
    """
    import unicodedata
    text = str(text or "")
    repl = {
        "á":"a","é":"e","í":"i","ó":"o","ú":"u","ü":"u","ñ":"n",
        "Á":"A","É":"E","Í":"I","Ó":"O","Ú":"U","Ü":"U","Ñ":"N",
        "–":"-","—":"-","“":"\"","”":"\"","’":"'",
        "•":"-","→":"->","×":"x","º":"o","ª":"a",
        "📦":"","💵":"","🧱":"","✅":"","❌":"","🔎":"","🛒":"",
        "📄":"","🧾":"","💳":"","📈":"","📊":"","⚙️":"","💾":"",
        "🗂️":"","👥":"","🛍️":"","👤":"","📢":"","💰":"","🌐":"",
        "📸":"","📍":"","💬":"","⚠️":"","🟡":""
    }
    for a, b in repl.items():
        text = text.replace(a, b)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.encode("latin-1", "replace").decode("latin-1")

def pdf_force_latin1(pdf):
    """
    FPDF 1.x codifica páginas completas en latin1 al cerrar.
    Esta limpieza final evita que cualquier carácter no Latin-1 sobreviviente rompa pdf.output().
    """
    try:
        for n in list(pdf.pages.keys()):
            pdf.pages[n] = pdf.pages[n].encode("latin-1", "replace").decode("latin-1")
    except Exception:
        pass
    return pdf

def generar_pdf_cotizacion(cot_id):
    rows = q("SELECT * FROM cotizaciones WHERE id=?", (cot_id,), fetch=True)
    if not rows:
        return b""
    cot = rows[0]
    items = json.loads(cot["items"] or "{}")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 8, pdf_clean(get_config("nombre_empresa", "Sistema de Insumos al Mayor")), ln=1, align="C")
    pdf.set_font("Arial", "", 9)
    pdf.cell(190, 5, pdf_clean(f"Contacto: {get_config('telefono_empresa','')} | Instagram: {get_config('instagram_empresa','')}"), ln=1, align="C")
    pdf.ln(4)

    pdf.set_font("Arial", "B", 13)
    pdf.cell(190, 8, pdf_clean(f"COTIZACION #{cot_id}"), ln=1)
    pdf.set_font("Arial", "", 9)
    vence = ""
    try:
        fecha_dt = datetime.strptime(cot["fecha"], "%d/%m/%Y %H:%M")
        vence = (fecha_dt + timedelta(days=int(cot["validez_dias"] or 1))).strftime("%d/%m/%Y")
    except Exception:
        vence = "N/A"
    pdf.cell(95, 6, pdf_clean(f"Fecha: {cot['fecha']}"), ln=0)
    pdf.cell(95, 6, pdf_clean(f"Valida hasta: {vence}"), ln=1)
    pdf.cell(95, 6, pdf_clean(f"Cliente: {cot['cliente_nombre'] or cot['username']}"), ln=0)
    pdf.cell(95, 6, pdf_clean(f"RIF/CI: {cot['cliente_rif'] or 'N/A'}"), ln=1)
    pdf.cell(95, 6, pdf_clean(f"Telefono: {cot['cliente_telefono'] or 'N/A'}"), ln=0)
    pdf.cell(95, 6, pdf_clean(f"Tasa proveedor: {cot['tasa_proveedor']}"), ln=1)
    if cot["cliente_direccion"]:
        pdf.multi_cell(190, 5, pdf_clean(f"Direccion: {cot['cliente_direccion']}"))
    pdf.ln(4)

    pdf.set_fill_color(230, 230, 230)
    # Columnas ajustadas para evitar que la presentación invada el SKU.
    headers = [("Cant.",28),("SKU",42),("Descripcion",78),("Precio",21),("Total",21)]
    pdf.set_font("Arial", "B", 8)
    for h,w in headers:
        pdf.cell(w, 7, pdf_clean(h), 1, 0, "C", True)
    pdf.ln()

    pdf.set_font("Arial", "", 8)
    for sku, d in items.items():
        desc = pdf_clean(d.get("desc", ""))[:45]
        cant_txt = formato_cantidad_pdf_simple(d)
        sku_txt = sku_limpio_pdf(d.get("sku", sku))
        vals = [
            cant_txt[:16],
            sku_txt[:26],
            desc,
            money_usd(d.get("precio_total", 0)),
            money_usd(d.get("precio_total", 0)),
        ]
        for val, (_, w) in zip(vals, headers):
            align = "R" if val.startswith("$") else "L"
            pdf.cell(w, 7, pdf_clean(val), 1, 0, align)
        pdf.ln()

    pdf.ln(4)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(140, 7, "", ln=0)
    pdf.cell(28, 7, "Subtotal:", 1, 0, "R")
    pdf.cell(22, 7, money_usd(cot["subtotal_usd"]), 1, 1, "R")
    pdf.cell(140, 7, "", ln=0)
    pdf.cell(28, 7, "Envio:", 1, 0, "R")
    pdf.cell(22, 7, money_usd(cot["envio_usd"]), 1, 1, "R")
    pdf.cell(140, 8, "", ln=0)
    pdf.cell(28, 8, "TOTAL:", 1, 0, "R")
    pdf.cell(22, 8, money_usd(cot["total_usd"]), 1, 1, "R")
    pdf.set_font("Arial", "", 9)
    pdf.cell(190, 7, pdf_clean(f"Equivalente Bs: {money_bs(cot['total_bs_proveedor'])}"), ln=1, align="R")

    if cot["notas"]:
        pdf.ln(4)
        pdf.set_font("Arial", "", 9)
        pdf.multi_cell(190, 5, pdf_clean(f"Notas: {cot['notas']}"))

    pdf.ln(5)
    pdf.set_font("Arial", "I", 8)
    pdf.multi_cell(190, 5, pdf_clean("Cotizacion sujeta a disponibilidad al momento de confirmar el pedido. Precios y tasa sujetos a cambio luego del vencimiento."))
    pdf_force_latin1(pdf)
    out = pdf.output(dest="S")
    if isinstance(out, str):
        return out.encode("latin-1", "replace")
    return bytes(out)


def generar_pdf_pedido(pedido_id):
    rows = q("SELECT * FROM pedidos WHERE id=?", (pedido_id,), fetch=True)
    if not rows:
        return b""
    ped = rows[0]
    items = json.loads(ped["items"] or "{}")
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 8, pdf_clean(get_config("nombre_empresa", "Sistema de Insumos al Mayor")), ln=1, align="C")
    pdf.set_font("Arial", "", 9)
    pdf.cell(190, 5, pdf_clean(f"Contacto: {get_config('telefono_empresa','')} | Instagram: {get_config('instagram_empresa','')}"), ln=1, align="C")
    pdf.ln(4)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(190, 8, pdf_clean(f"PEDIDO / NOTA #{pedido_id}"), ln=1)
    pdf.set_font("Arial", "", 9)
    pdf.cell(95, 6, pdf_clean(f"Fecha: {ped['fecha']}"), ln=0)
    pdf.cell(95, 6, pdf_clean(f"Estado: {ped['status']}"), ln=1)
    pdf.cell(95, 6, pdf_clean(f"Cliente: {ped['cliente_nombre'] or ped['username']}"), ln=0)
    pdf.cell(95, 6, pdf_clean(f"RIF/CI: {ped['cliente_rif'] or 'N/A'}"), ln=1)
    pdf.cell(95, 6, pdf_clean(f"Tipo pago: {ped['tipo_pago']}"), ln=0)
    pdf.cell(95, 6, pdf_clean(f"Metodo: {ped['metodo_pago'] or 'N/A'}"), ln=1)
    if ped["cliente_direccion"]:
        pdf.multi_cell(190, 5, pdf_clean(f"Direccion: {ped['cliente_direccion']}"))
    pdf.ln(4)

    pdf.set_fill_color(230, 230, 230)
    # Columnas ajustadas para evitar que la presentación invada el SKU.
    headers = [("Cant.",28),("SKU",42),("Descripcion",78),("Precio",21),("Total",21)]
    pdf.set_font("Arial", "B", 8)
    for h,w in headers:
        pdf.cell(w, 7, pdf_clean(h), 1, 0, "C", True)
    pdf.ln()
    pdf.set_font("Arial", "", 8)
    for k, d in items.items():
        cant_txt = formato_cantidad_pdf_simple(d)
        sku_txt = sku_limpio_pdf(d.get("sku", k))
        vals = [
            cant_txt[:16],
            sku_txt[:26],
            pdf_clean(d.get("desc", ""))[:50],
            money_usd(d.get("precio_total", 0)),
            money_usd(d.get("precio_total", 0)),
        ]
        for val, (_, w) in zip(vals, headers):
            pdf.cell(w, 7, pdf_clean(val), 1, 0, "R" if str(val).startswith("$") else "L")
        pdf.ln()

    pdf.ln(4)
    pdf.set_font("Arial", "B", 10)
    for label, val in [("Subtotal:", ped["subtotal_usd"]), ("Envio:", ped["envio_usd"]), ("TOTAL:", ped["total_usd"])]:
        pdf.cell(140, 7, "", ln=0)
        pdf.cell(28, 7, label, 1, 0, "R")
        pdf.cell(22, 7, money_usd(val), 1, 1, "R")
    pdf.set_font("Arial", "", 9)
    pdf.cell(190, 7, pdf_clean(f"Equivalente Bs proveedor: {money_bs(ped['total_bs_proveedor'])}"), ln=1, align="R")
    try:
        if str(ped["credito_tipo"] or "").lower() == "bcv":
            pdf.ln(2)
            pdf.set_font("Arial", "B", 9)
            pdf.multi_cell(190, 5, pdf_clean("NOTA CREDITO BCV: Este credito se expresa en $ BCV. Cada abono se cancelara en bolivares a la tasa BCV vigente del dia en que el cliente registre el pago. La tasa BCV puede variar diariamente."))
            pdf.set_font("Arial", "", 9)
            pdf.cell(190, 6, pdf_clean(f"Monto credito BCV inicial: {money_usd(ped['total_bcv_credito'])} BCV | Tasa BCV creacion: {float(ped['tasa_bcv'] or 0):,.2f}"), ln=1)
    except Exception:
        pass
    if ped["notas"]:
        pdf.ln(3)
        pdf.multi_cell(190, 5, pdf_clean(f"Notas: {ped['notas']}"))
    pdf_force_latin1(pdf)
    out = pdf.output(dest="S")
    if isinstance(out, str):
        return out.encode("latin-1", "replace")
    return bytes(out)

def generar_pdf_packing_list_pedido(pedido_id):
    rows = q("SELECT * FROM pedidos WHERE id=?", (int(pedido_id),), fetch=True)
    if not rows:
        return b""
    ped = rows[0]
    try:
        items = json.loads(ped["items"] or "{}")
    except Exception:
        items = {}

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 8, pdf_clean(get_config("nombre_empresa", "Sistema de Insumos al Mayor")), ln=1, align="C")
    pdf.set_font("Arial", "", 9)
    pdf.cell(190, 5, pdf_clean("PACKING LIST / LISTA DE PREPARACION"), ln=1, align="C")
    pdf.ln(4)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 7, pdf_clean(f"Pedido #{pedido_id}"), ln=1)
    pdf.set_font("Arial", "", 9)
    pdf.cell(95, 6, pdf_clean(f"Fecha: {ped['fecha']}"), ln=0)
    pdf.cell(95, 6, pdf_clean(f"Cliente: {ped['cliente_nombre'] or ped['username']}"), ln=1)
    pdf.cell(95, 6, pdf_clean(f"Estado: {ped['status']}"), ln=0)
    pdf.cell(95, 6, pdf_clean(f"Telefono: {ped['cliente_telefono'] or 'N/A'}"), ln=1)
    if ped["cliente_direccion"]:
        pdf.multi_cell(190, 5, pdf_clean(f"Direccion: {ped['cliente_direccion']}"))
    pdf.ln(4)

    headers = [("Preparar", 30), ("Unid.", 20), ("SKU", 38), ("Producto", 82), ("Check", 20)]
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", "B", 8)
    for h, w in headers:
        pdf.cell(w, 7, pdf_clean(h), 1, 0, "C", True)
    pdf.ln()

    pdf.set_font("Arial", "", 8)
    for k, d in items.items():
        preparar = formato_cantidad_pdf_simple(d)
        unidades = str(int(d.get("unidades_base_total", d.get("cantidad_presentacion", 0)) or 0))
        sku_txt = sku_limpio_pdf(d.get("sku", k))
        producto = pdf_clean(d.get("desc", ""))[:58]
        vals = [preparar[:18], unidades[:8], sku_txt[:22], producto, "[  ]"]
        for val, (_, w) in zip(vals, headers):
            align = "C" if val == "[  ]" else "L"
            pdf.cell(w, 7, pdf_clean(val), 1, 0, align)
        pdf.ln()

    pdf.ln(5)
    pdf.set_font("Arial", "", 9)
    pdf.multi_cell(190, 5, pdf_clean("Uso interno: marcar cada linea al preparar el pedido. Este documento no reemplaza la nota/PDF comercial."))
    if ped["notas"]:
        pdf.ln(2)
        pdf.multi_cell(190, 5, pdf_clean(f"Notas del pedido: {ped['notas']}"))

    pdf_force_latin1(pdf)
    out = pdf.output(dest="S")
    if isinstance(out, str):
        return out.encode("latin-1", "replace")
    return bytes(out)



def generar_pdf_estado_cuenta(username):
    user = get_user(username)
    if not user:
        return b""
    creditos = pd.read_sql_query("SELECT * FROM creditos WHERE username=? ORDER BY id DESC", get_conn(), params=(username,))
    abonos = pd.read_sql_query("SELECT * FROM abonos WHERE username=? ORDER BY id DESC", get_conn(), params=(username,))
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 8, pdf_clean(get_config("nombre_empresa", "Sistema de Insumos al Mayor")), ln=1, align="C")
    pdf.ln(4)
    pdf.set_font("Arial", "B", 13)
    pdf.cell(190, 8, "ESTADO DE CUENTA", ln=1)
    pdf.set_font("Arial", "", 9)
    pdf.cell(95, 6, pdf_clean(f"Cliente: {user['nombre'] or username}"), ln=0)
    pdf.cell(95, 6, pdf_clean(f"Fecha: {now()}"), ln=1)
    saldo_total = float(creditos["saldo_usd"].sum()) if not creditos.empty else 0.0
    pdf.set_font("Arial", "B", 11)
    pdf.cell(190, 8, pdf_clean(f"Saldo pendiente: {money_usd(saldo_total)}"), ln=1)
    pdf.ln(3)
    pdf.set_font("Arial", "B", 8)
    headers = [("Credito",18),("Pedido",18),("Inicio",32),("Vence",28),("Monto",28),("Saldo",28),("Estado",38)]
    for h,w in headers:
        pdf.cell(w, 7, h, 1, 0, "C", True)
    pdf.ln()
    pdf.set_font("Arial", "", 8)
    if creditos.empty:
        pdf.cell(190, 7, "Sin creditos.", 1, 1)
    else:
        for _, cr in creditos.iterrows():
            vals = [f"#{int(cr['id'])}", f"#{int(cr['pedido_id'])}", cr["fecha_inicio"], cr["fecha_vencimiento"], money_usd(cr["monto_usd"]), money_usd(cr["saldo_usd"]), cr["status"]]
            for val, (_,w) in zip(vals, headers):
                pdf.cell(w, 7, pdf_clean(val), 1, 0, "C")
            pdf.ln()
    pdf.ln(5)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(190, 7, "ABONOS", ln=1)
    pdf.set_font("Arial", "", 8)
    if abonos.empty:
        pdf.cell(190, 7, "Sin abonos registrados.", 1, 1)
    else:
        for _, ab in abonos.iterrows():
            pdf.cell(190, 6, pdf_clean(f"#{int(ab['id'])} Credito #{int(ab['credito_id'])} | {ab['fecha']} | {money_usd(ab['monto_usd'])} | {ab['metodo']} | {ab['status']}"), ln=1)
    pdf_force_latin1(pdf)
    out = pdf.output(dest="S")
    if isinstance(out, str):
        return out.encode("latin-1", "replace")
    return bytes(out)


# -----------------------------
# AUTH
# -----------------------------
def login_screen():
    st.title("🔐 Sistema de Insumos al Mayor")
    st.caption("Acceso para administradores y compradores")
    with st.form("login"):
        u = st.text_input("Usuario / correo")
        p = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Entrar", type="primary", use_container_width=True)
    if submit:
        row = get_user(u.strip())
        if row and int(row["activo"] or 0) == 1 and verify_password(p, row["password_hash"]):
            st.session_state.auth = True
            st.session_state.user = {"username": row["username"], "nombre": row["nombre"], "rol": row["rol"]}
            st.rerun()
        else:
            st.error("Credenciales incorrectas o usuario inactivo.")

def logout():
    st.session_state.auth = False
    st.session_state.user = None
    st.rerun()

# -----------------------------
# ADMIN
# -----------------------------
def admin_config():
    st.title("⚙️ Configuración")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Tasas")
        tasa_prov = st.number_input("Tasa proveedor", min_value=0.0, value=get_tasa_proveedor(), step=0.01)
        tasa_bcv = st.number_input("Tasa BCV", min_value=0.0, value=get_tasa_bcv(), step=0.01)
        if st.button("💾 Guardar tasas", type="primary"):
            set_config("tasa_proveedor", tasa_prov)
            set_config("tasa_bcv", tasa_bcv)
            set_config("fecha_tasa_bcv", now())
            st.success("Tasas guardadas.")
            st.rerun()
        if st.button("🌐 Obtener BCV desde web"):
            val, fuente = obtener_bcv_web()
            if val:
                set_config("tasa_bcv", val)
                set_config("fecha_tasa_bcv", now())
                set_config("fuente_tasa_bcv", fuente)
                st.success(f"BCV actualizado: {val}")
                st.rerun()
            else:
                st.error(fuente)

    with c2:
        st.subheader("Empresa y cotización")
        nombre = st.text_input("Nombre empresa", value=get_config("nombre_empresa", "Sistema de Insumos al Mayor"))
        tel = st.text_input("Teléfono", value=get_config("telefono_empresa", "04127757053"))
        ig = st.text_input("Instagram", value=get_config("instagram_empresa", "@color.insumos"))
        validez = st.number_input("Validez cotización en días", min_value=1, max_value=30, value=int(parse_float(get_config("validez_cotizacion_dias", "1"), 1)))
        comision_ml = st.number_input("% comisión MercadoLibre", min_value=0.0, max_value=80.0, value=get_comision_ml_pct(), step=0.5)

        st.markdown("#### Envío ML / ENVÍO por rangos")
        st.caption("Estos montos se cargan en bolívares. El sistema los convierte internamente a USD equivalente usando tasa proveedor para mantener el pedido cuadrado.")
        envio_3_5_bcv = st.number_input("Envío Bs rango 3 a 5 kg", min_value=0.0, value=parse_float(get_config("envio_ml_3_5_bcv", "0"), 0), step=100.0)
        envio_5_10_bcv = st.number_input("Envío Bs rango 5 a 10 kg", min_value=0.0, value=parse_float(get_config("envio_ml_5_10_bcv", "0"), 0), step=100.0)
        envio_10_40_bcv = st.number_input("Envío Bs rango 10 a 40 kg", min_value=0.0, value=parse_float(get_config("envio_ml_10_40_bcv", "0"), 0), step=100.0)

        if st.button("💾 Guardar configuración", type="primary", key="save_empresa"):
            set_config("nombre_empresa", nombre)
            set_config("telefono_empresa", tel)
            set_config("instagram_empresa", ig)
            set_config("validez_cotizacion_dias", validez)
            set_config("envio_ml_3_5_bcv", envio_3_5_bcv)
            set_config("envio_ml_5_10_bcv", envio_5_10_bcv)
            set_config("envio_ml_10_40_bcv", envio_10_40_bcv)
            set_config("comision_mercadolibre_pct", comision_ml)
            st.success("Configuración guardada.")

    st.markdown("---")
    st.subheader("WooCommerce")
    if wc_ready():
        st.success(f".env cargado. Sitio: {WC_URL}")
    else:
        st.error("Faltan WC_URL, WC_KEY o WC_SECRET en .env")
    if st.button("🔄 Sincronizar todos los productos activos con WooCommerce", type="primary"):
        with st.spinner("Sincronizando..."):
            ok, no, errors = sync_todos_productos()
        st.success(f"Sincronizados: {ok}. No sincronizados: {no}.")
        if errors:
            st.warning("Algunos errores:")
            st.code("\\n".join(errors))


def admin_categorias():
    st.title("🗂️ Categorías")
    st.caption("Las categorías eliminadas ya no se regeneran automáticamente al reiniciar la app.")
    with st.form("crear_cat"):
        c1, c2, c3 = st.columns([2,3,1])
        nombre = c1.text_input("Nueva categoría")
        descripcion = c2.text_input("Descripción")
        orden = c3.number_input("Orden", min_value=0, value=0)
        submit = st.form_submit_button("Crear categoría", type="primary")
    if submit:
        if not nombre.strip():
            st.error("Nombre requerido.")
        else:
            try:
                q("INSERT INTO categorias (nombre, descripcion, activa, orden, creado_en) VALUES (?,?,?,?,?)",
                  (nombre.strip(), descripcion, 1, int(orden), now()))
                set_feedback(f"Categoría creada correctamente: {nombre.strip()}.", "success")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo crear: {e}")

    st.subheader("Editar categorías")
    cats = categorias_todas()
    for cat in cats:
        with st.expander(f"{cat['nombre']} {'✅' if cat['activa'] else '🚫'}"):
            with st.form(f"edit_cat_{cat['id']}"):
                nombre_e = st.text_input("Nombre", value=cat["nombre"], key=f"catn_{cat['id']}")
                desc_e = st.text_input("Descripción", value=cat["descripcion"] or "", key=f"catd_{cat['id']}")
                orden_e = st.number_input("Orden", min_value=0, value=int(cat["orden"] or 0), key=f"cato_{cat['id']}")
                activa_e = st.checkbox("Activa", value=bool(cat["activa"]), key=f"cata_{cat['id']}")
                save = st.form_submit_button("Guardar cambios")
            if save:
                q("UPDATE categorias SET nombre=?, descripcion=?, activa=?, orden=? WHERE id=?",
                  (nombre_e.strip(), desc_e, 1 if activa_e else 0, int(orden_e), cat["id"]))
                st.success("Actualizada.")
                st.rerun()
            confirmar_del_cat = st.checkbox("Confirmar eliminación de categoría", key=f"confirm_del_cat_{cat['id']}")
            if st.button("🗑️ Eliminar categoría", key=f"del_cat_{cat['id']}", disabled=not confirmar_del_cat):
                usados = q("SELECT COUNT(*) AS n FROM productos WHERE categoria_id=?", (cat["id"],), fetch=True)[0]["n"]
                if usados:
                    st.error("No se puede eliminar: hay productos en esta categoría. Muévelos primero o desactiva la categoría.")
                else:
                    q("DELETE FROM categorias WHERE id=?", (cat["id"],))
                    st.success("Categoría eliminada.")
                    st.rerun()

def admin_productos():
    st.title("📦 Productos")
    tab_list, tab_form, tab_dup = st.tabs(["Listado", "Crear / Editar", "Duplicar producto"])

    with tab_list:
        bus = st.text_input("Buscar por SKU o descripción")
        sql = """SELECT p.*, c.nombre AS categoria
                 FROM productos p LEFT JOIN categorias c ON p.categoria_id=c.id
                 WHERE 1=1"""
        params = []
        if bus:
            sql += " AND (p.sku LIKE ? OR p.descripcion LIKE ?)"
            params.extend([f"%{bus}%", f"%{bus}%"])
        sql += " ORDER BY p.activo DESC, c.orden, p.descripcion"
        df = pd.read_sql_query(sql, get_conn(), params=params)
        cols_prod = ["sku","descripcion","categoria","precio_unidad","presentacion_intermedia_nombre","presentacion_intermedia_cantidad","precio_docena","precio_bulto","bulto_contiene","peso_unidad_kg","wc_stock","activo","visible_tienda","es_variante","grupo_variantes","nombre_visible_grupo","atributo_medida","atributo_color","orden_variante","ultima_sync"]
        st.dataframe(
            df[cols_prod],
            use_container_width=True,
            hide_index=True,
            column_config={
                "peso_unidad_kg": st.column_config.NumberColumn("peso_unidad_kg", format="%.4f kg")
            }
        )

        if not df.empty:
            st.markdown("#### Acciones rápidas del producto")
            opts_listado = {
                f"{r['descripcion']} — {r['sku']}": r["sku"]
                for _, r in df.head(300).iterrows()
            }
            sel_listado = st.selectbox("Seleccionar producto del listado", list(opts_listado.keys()), key="producto_listado_accion")
            sku_accion = opts_listado[sel_listado]
            prod_accion = q("SELECT * FROM productos WHERE sku=?", (sku_accion,), fetch=True)
            prod_accion = prod_accion[0] if prod_accion else None

            if prod_accion:
                a1, a2, a3, a4 = st.columns(4)
                if a1.button("✏️ Cargar en edición", use_container_width=True, key=f"load_edit_{sku_accion}"):
                    st.session_state["sku_producto_editar"] = sku_accion
                    st.success("Producto cargado. Abre la pestaña Crear / Editar para modificarlo.")
                activo_actual = int(prod_accion["activo"] or 0) == 1
                texto_toggle = "⏸️ Desactivar" if activo_actual else "▶️ Activar"
                if a2.button(texto_toggle, use_container_width=True, key=f"toggle_activo_{sku_accion}"):
                    q("UPDATE productos SET activo=?, actualizado_en=? WHERE sku=?", (0 if activo_actual else 1, now(), sku_accion))
                    st.success("Estado del producto actualizado.")
                    st.rerun()
                visible_actual = int(prod_accion["visible_tienda"] if "visible_tienda" in prod_accion.keys() and prod_accion["visible_tienda"] is not None else 1) == 1
                texto_visible = "🙈 Ocultar tienda" if visible_actual else "👁️ Mostrar tienda"
                if a3.button(texto_visible, use_container_width=True, key=f"toggle_visible_{sku_accion}"):
                    q("UPDATE productos SET visible_tienda=?, actualizado_en=? WHERE sku=?", (0 if visible_actual else 1, now(), sku_accion))
                    st.success("Visibilidad en tienda actualizada.")
                    st.rerun()
                if a4.button("🔄 Sync WC", use_container_width=True, key=f"sync_prod_{sku_accion}"):
                    ok, msg = sync_producto_wc(sku_accion)
                    st.success(msg) if ok else st.warning(msg)
                    st.rerun()

    with tab_form:
        st.subheader("Crear o editar producto")

        buscar_edit = st.text_input("Buscar producto para editar", placeholder="Escribe nombre o SKU del producto...")
        if buscar_edit:
            encontrados = q("""SELECT sku, descripcion FROM productos
                                WHERE sku LIKE ? OR descripcion LIKE ?
                                ORDER BY descripcion LIMIT 50""",
                             (f"%{buscar_edit}%", f"%{buscar_edit}%"), fetch=True)
            if encontrados:
                opts_prod = {f"{r['descripcion']} — {r['sku']}": r["sku"] for r in encontrados}
                sel_prod = st.selectbox("Resultados", list(opts_prod.keys()))
                if st.button("Cargar producto seleccionado", use_container_width=True):
                    st.session_state["sku_producto_editar"] = opts_prod[sel_prod]
                    st.rerun()
            else:
                st.info("No se encontraron productos con esa búsqueda.")

        sku_e = st.text_input("SKU", value=st.session_state.get("sku_producto_editar", ""))
        prod = q("SELECT * FROM productos WHERE sku=?", (sku_e.strip(),), fetch=True) if sku_e.strip() else []
        prod = prod[0] if prod else None

        cats = categorias_todas()
        cat_options = {f"{c['nombre']} {'(inactiva)' if not c['activa'] else ''}": c["id"] for c in cats}
        cat_names = list(cat_options.keys())

        current_cat_name = cat_names[0] if cat_names else None
        if prod:
            for name, cid in cat_options.items():
                if cid == prod["categoria_id"]:
                    current_cat_name = name
                    break

        with st.form("producto_form"):
            desc = st.text_input("Descripción", value=prod["descripcion"] if prod else "")
            cat_sel = st.selectbox("Categoría", cat_names, index=cat_names.index(current_cat_name) if current_cat_name in cat_names else 0)
            unidad_base = st.selectbox("Unidad base", ["unidad", "paquete", "rollo", "litro", "caja"], index=["unidad","paquete","rollo","litro","caja"].index(prod["unidad_base"]) if prod and prod["unidad_base"] in ["unidad","paquete","rollo","litro","caja"] else 0)

            c1, c2, c3 = st.columns(3)
            precio_unidad = c1.number_input("Precio unidad USD", min_value=0.0, value=float(prod["precio_unidad"] if prod else 0), step=0.01)
            precio_docena = c2.number_input("Precio presentación intermedia c/u USD", min_value=0.0, value=float(prod["precio_docena"] if prod else 0), step=0.01, help="Usa este campo para Docena, Pack x10, Caja, Paquete, etc. Es precio unitario dentro de esa presentación.")
            precio_bulto = c3.number_input("Precio bulto c/u USD", min_value=0.0, value=float(prod["precio_bulto"] if prod else 0), step=0.01)

            st.markdown("#### Precio especial opcional")
            pe0, pe1, pe2, pe3 = st.columns(4)
            maneja_precio_especial = pe0.checkbox("Maneja precio especial", value=bool(prod["maneja_precio_especial"]) if prod and "maneja_precio_especial" in prod.keys() else False)
            precio_especial_unidad = pe1.number_input("Especial unidad USD", min_value=0.0, value=float(prod["precio_especial_unidad"] if prod and "precio_especial_unidad" in prod.keys() else 0), step=0.01, disabled=not maneja_precio_especial)
            precio_especial_docena = pe2.number_input("Especial presentación c/u USD", min_value=0.0, value=float(prod["precio_especial_docena"] if prod and "precio_especial_docena" in prod.keys() else 0), step=0.01, disabled=not maneja_precio_especial, help="Precio por unidad dentro de la presentación intermedia.")
            precio_especial_bulto = pe3.number_input("Especial bulto c/u USD", min_value=0.0, value=float(prod["precio_especial_bulto"] if prod and "precio_especial_bulto" in prod.keys() else 0), step=0.01, disabled=not maneja_precio_especial, help="Precio por unidad dentro del bulto. Ej: si el bulto trae 50 y quieres total $11, coloca 0.22.")

            c4, c5, c6, c7 = st.columns(4)
            maneja_docena = c4.checkbox("Maneja presentación intermedia", value=bool(prod["maneja_docena"]) if prod else True)
            nombre_intermedio_actual = producto_intermedia_nombre(prod) if prod else "Docena"
            opciones_intermedias = ["Docena", "Pack", "Caja", "Paquete"]
            if nombre_intermedio_actual not in opciones_intermedias:
                opciones_intermedias.append(nombre_intermedio_actual)
            presentacion_intermedia_nombre = c5.selectbox("Nombre", opciones_intermedias, index=opciones_intermedias.index(nombre_intermedio_actual))
            presentacion_intermedia_cantidad = c6.number_input("Contiene unidades", min_value=1, max_value=9999, value=producto_intermedia_cantidad(prod) if prod else 12, step=1)
            maneja_bulto = c7.checkbox("Maneja bulto", value=bool(prod["maneja_bulto"]) if prod else True)

            c8, c9 = st.columns(2)
            bulto_contiene = c8.number_input("Bulto contiene unidades base", min_value=1, max_value=9999, value=int(prod["bulto_contiene"] if prod and prod["bulto_contiene"] else 1), step=1)

            c10, c11 = st.columns(2)
            peso = c10.number_input(
                "Peso por unidad base KG (interno admin)",
                min_value=0.0,
                value=float(prod["peso_unidad_kg"] if prod else 0),
                step=0.0001,
                format="%.4f",
                help="Se carga en kg. Ejemplo: 1.6 gramos = 0.0016 kg. 10 gramos = 0.0100 kg."
            )
            activo = c11.checkbox("Producto activo", value=bool(prod["activo"]) if prod else True)

            st.markdown("#### Visibilidad y variantes")
            vv1, vv2, vv3 = st.columns(3)
            visible_tienda = vv1.checkbox(
                "Visible en tienda",
                value=bool(prod["visible_tienda"] if prod and "visible_tienda" in prod.keys() and prod["visible_tienda"] is not None else 1),
                help="Si lo desmarcas, no se mostrará como publicación individual. Si es variante agrupada, puede seguir apareciendo dentro del grupo mientras esté activo."
            )
            es_variante = vv2.checkbox(
                "Es variante agrupada",
                value=bool(prod["es_variante"] if prod and "es_variante" in prod.keys() and prod["es_variante"] is not None else 0),
                help="Úsalo para productos con SKU propio que pertenecen a una familia, por ejemplo anillos por medida/color."
            )
            orden_variante = vv3.number_input(
                "Orden variante",
                min_value=0,
                max_value=9999,
                value=int(prod["orden_variante"] if prod and "orden_variante" in prod.keys() and prod["orden_variante"] is not None else 0),
                step=1
            )

            vg1, vg2 = st.columns(2)
            grupo_variantes = vg1.text_input(
                "Grupo variantes",
                value=prod["grupo_variantes"] if prod and "grupo_variantes" in prod.keys() and prod["grupo_variantes"] else "",
                placeholder="Ej: ANILLOS_AGENDA"
            )
            nombre_visible_grupo = vg2.text_input(
                "Nombre visible del grupo",
                value=prod["nombre_visible_grupo"] if prod and "nombre_visible_grupo" in prod.keys() and prod["nombre_visible_grupo"] else "",
                placeholder="Ej: Anillos para agenda"
            )

            va1, va2 = st.columns(2)
            atributo_medida = va1.text_input(
                "Medida",
                value=prod["atributo_medida"] if prod and "atributo_medida" in prod.keys() and prod["atributo_medida"] else "",
                placeholder='Ej: 7/8, 3/4, 1"'
            )
            atributo_color = va2.text_input(
                "Color",
                value=prod["atributo_color"] if prod and "atributo_color" in prod.keys() and prod["atributo_color"] else "",
                placeholder="Ej: Negro, Blanco, Dorado, Rosado"
            )

            st.markdown("#### Costos internos / rentabilidad")
            cc1, cc2, cc3, cc4 = st.columns(4)
            costo_proveedor_unitario = cc1.number_input("Costo proveedor unitario", min_value=0.0, value=float(prod["costo_proveedor_unitario"] if prod and "costo_proveedor_unitario" in prod.keys() else 0), step=0.01)
            envio_costo_bulto = cc2.number_input("Envío costo por bulto", min_value=0.0, value=float(prod["envio_costo_bulto"] if prod and "envio_costo_bulto" in prod.keys() else 0), step=0.01)
            otros_costos_bulto = cc3.number_input("Otros costos por bulto", min_value=0.0, value=float(prod["otros_costos_bulto"] if prod and "otros_costos_bulto" in prod.keys() else 0), step=0.01)
            margen_minimo_pct = cc4.number_input("Margen mínimo %", min_value=0.0, max_value=100.0, value=float(prod["margen_minimo_pct"] if prod and "margen_minimo_pct" in prod.keys() else 25), step=1.0)

            st.markdown("#### Seguimiento de publicación")
            pp1, pp2, pp3, pp4, pp5 = st.columns(5)
            pub_web = pp1.checkbox("Web", value=bool(prod["pub_web"]) if prod and "pub_web" in prod.keys() else False)
            pub_instagram = pp2.checkbox("Instagram", value=bool(prod["pub_instagram"]) if prod and "pub_instagram" in prod.keys() else False)
            pub_mercadolibre = pp3.checkbox("MercadoLibre", value=bool(prod["pub_mercadolibre"]) if prod and "pub_mercadolibre" in prod.keys() else False)
            pub_marketplace = pp4.checkbox("Marketplace", value=bool(prod["pub_marketplace"]) if prod and "pub_marketplace" in prod.keys() else False)
            pub_whatsapp = pp5.checkbox("WhatsApp", value=bool(prod["pub_whatsapp"]) if prod and "pub_whatsapp" in prod.keys() else False)
            link_instagram = st.text_input("Link Instagram", value=prod["link_instagram"] if prod and "link_instagram" in prod.keys() and prod["link_instagram"] else "")
            link_mercadolibre = st.text_input("Link MercadoLibre", value=prod["link_mercadolibre"] if prod and "link_mercadolibre" in prod.keys() and prod["link_mercadolibre"] else "")
            link_marketplace = st.text_input("Link Marketplace", value=prod["link_marketplace"] if prod and "link_marketplace" in prod.keys() and prod["link_marketplace"] else "")
            notas_publicacion = st.text_area("Notas de publicación", value=prod["notas_publicacion"] if prod and "notas_publicacion" in prod.keys() and prod["notas_publicacion"] else "")

            guardar = st.form_submit_button("💾 Guardar producto", type="primary")

        if guardar:
            if not sku_e.strip() or not desc.strip():
                st.error("SKU y descripción son obligatorios.")
            else:
                cat_id = cat_options[cat_sel]
                q("""INSERT INTO productos
                     (sku, descripcion, categoria_id, unidad_base, precio_unidad, precio_docena, precio_bulto,
                      bulto_contiene, maneja_docena, maneja_bulto, presentacion_intermedia_nombre, presentacion_intermedia_cantidad,
                      maneja_precio_especial, precio_especial_unidad, precio_especial_docena, precio_especial_bulto,
                      peso_unidad_kg, activo,
                      costo_proveedor_unitario, envio_costo_bulto, otros_costos_bulto, margen_minimo_pct,
                      pub_web, pub_instagram, pub_mercadolibre, pub_marketplace, pub_whatsapp,
                      link_instagram, link_mercadolibre, link_marketplace, notas_publicacion,
                      creado_en, actualizado_en)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(sku) DO UPDATE SET
                     descripcion=excluded.descripcion,
                     categoria_id=excluded.categoria_id,
                     unidad_base=excluded.unidad_base,
                     precio_unidad=excluded.precio_unidad,
                     precio_docena=excluded.precio_docena,
                     precio_bulto=excluded.precio_bulto,
                     bulto_contiene=excluded.bulto_contiene,
                     maneja_docena=excluded.maneja_docena,
                     maneja_bulto=excluded.maneja_bulto,
                     presentacion_intermedia_nombre=excluded.presentacion_intermedia_nombre,
                     presentacion_intermedia_cantidad=excluded.presentacion_intermedia_cantidad,
                     maneja_precio_especial=excluded.maneja_precio_especial,
                     precio_especial_unidad=excluded.precio_especial_unidad,
                     precio_especial_docena=excluded.precio_especial_docena,
                     precio_especial_bulto=excluded.precio_especial_bulto,
                     peso_unidad_kg=excluded.peso_unidad_kg,
                     activo=excluded.activo,
                     costo_proveedor_unitario=excluded.costo_proveedor_unitario,
                     envio_costo_bulto=excluded.envio_costo_bulto,
                     otros_costos_bulto=excluded.otros_costos_bulto,
                     margen_minimo_pct=excluded.margen_minimo_pct,
                     pub_web=excluded.pub_web,
                     pub_instagram=excluded.pub_instagram,
                     pub_mercadolibre=excluded.pub_mercadolibre,
                     pub_marketplace=excluded.pub_marketplace,
                     pub_whatsapp=excluded.pub_whatsapp,
                     link_instagram=excluded.link_instagram,
                     link_mercadolibre=excluded.link_mercadolibre,
                     link_marketplace=excluded.link_marketplace,
                     notas_publicacion=excluded.notas_publicacion,
                     actualizado_en=excluded.actualizado_en""",
                  (sku_e.strip(), desc.strip(), cat_id, unidad_base, precio_unidad, precio_docena, precio_bulto,
                   int(bulto_contiene), 1 if maneja_docena else 0, 1 if maneja_bulto else 0, presentacion_intermedia_nombre, int(presentacion_intermedia_cantidad),
                   1 if maneja_precio_especial else 0, precio_especial_unidad, precio_especial_docena, precio_especial_bulto,
                   peso, 1 if activo else 0,
                   costo_proveedor_unitario, envio_costo_bulto, otros_costos_bulto, margen_minimo_pct,
                   1 if pub_web else 0, 1 if pub_instagram else 0, 1 if pub_mercadolibre else 0, 1 if pub_marketplace else 0, 1 if pub_whatsapp else 0,
                   link_instagram, link_mercadolibre, link_marketplace, notas_publicacion,
                   now(), now()))
                q("""UPDATE productos
                     SET visible_tienda=?, es_variante=?, grupo_variantes=?, nombre_visible_grupo=?,
                         atributo_medida=?, atributo_color=?, orden_variante=?, actualizado_en=?
                     WHERE sku=?""",
                  (1 if visible_tienda else 0, 1 if es_variante else 0, grupo_variantes.strip(), nombre_visible_grupo.strip(),
                   atributo_medida.strip(), atributo_color.strip(), int(orden_variante), now(), sku_e.strip()))
                st.success("Producto guardado.")
                set_feedback(f"Producto guardado correctamente: {sku_e.strip()}.", "success")
                try:
                    ok, msg = sync_producto_wc(sku_e.strip())
                    if ok:
                        st.info(f"WooCommerce: {msg}")
                    else:
                        st.warning(f"WooCommerce: {msg}")
                except Exception as e:
                    st.warning(f"Guardado local, pero no se pudo sincronizar WooCommerce: {e}")
                st.rerun()

        if prod:
            st.markdown("---")
            st.subheader("Datos WooCommerce actuales")
            c1, c2, c3 = st.columns(3)
            c1.metric("Stock web", prod["wc_stock"] or 0)
            c2.write(f"Estado: **{prod['wc_stock_status'] or 'N/A'}**")
            c3.write(f"Última sync: **{prod['ultima_sync'] or 'Nunca'}**")
            if prod["wc_imagen_url"]:
                st.image(prod["wc_imagen_url"], width=250)
            if st.button("🔄 Sincronizar este SKU con WooCommerce"):
                try:
                    ok, msg = sync_producto_wc(prod["sku"])
                    if ok:
                        st.success(msg)
                    else:
                        st.warning(msg)
                    st.rerun()
                except Exception as e:
                    st.error(e)
            st.markdown("---")
            confirmar_prod = st.checkbox("Confirmar acción sobre este producto", key=f"confirm_prod_{prod['sku']}")
            cdel1, cdel2 = st.columns(2)
            if cdel1.button("🚫 Desactivar producto", disabled=not confirmar_prod, use_container_width=True):
                q("UPDATE productos SET activo=0 WHERE sku=?", (prod["sku"],))
                st.warning("Producto desactivado.")
                st.rerun()
            if cdel2.button("🗑️ Eliminar producto", disabled=not confirmar_prod, use_container_width=True):
                en_pedidos = q("SELECT COUNT(*) AS n FROM pedidos WHERE items LIKE ?", (f"%{prod['sku']}%",), fetch=True)[0]["n"]
                if en_pedidos:
                    st.error("Este producto aparece en pedidos. Desactívalo para conservar historial.")
                else:
                    q("DELETE FROM productos WHERE sku=?", (prod["sku"],))
                    st.success("Producto eliminado.")
                    st.rerun()

    with tab_dup:
        st.subheader("Duplicar producto")
        st.caption("Crea un producto nuevo copiando datos de otro. El producto original no se modifica.")

        bus_dup = st.text_input("Buscar producto a duplicar", placeholder="Nombre o SKU...", key="bus_dup_producto")
        rows_dup = []
        if bus_dup:
            rows_dup = q("""SELECT sku,descripcion FROM productos
                            WHERE sku LIKE ? OR descripcion LIKE ?
                            ORDER BY descripcion LIMIT 50""",
                         (f"%{bus_dup}%", f"%{bus_dup}%"), fetch=True)
        else:
            rows_dup = q("SELECT sku,descripcion FROM productos ORDER BY descripcion LIMIT 50", fetch=True)

        if not rows_dup:
            st.info("No hay productos para duplicar con esa búsqueda.")
        else:
            opts_dup = {f"{r['descripcion']} — {r['sku']}": r["sku"] for r in rows_dup}
            sel_dup = st.selectbox("Producto base", list(opts_dup.keys()), key="sel_dup_producto")
            sku_base = opts_dup[sel_dup]
            prod_base_rows = q("SELECT * FROM productos WHERE sku=?", (sku_base,), fetch=True)
            prod_base = prod_base_rows[0] if prod_base_rows else None

            if prod_base:
                nuevo_sku = st.text_input("Nuevo SKU", key="dup_nuevo_sku")
                nuevo_nombre = st.text_input("Nueva descripción", value=f"{prod_base['descripcion']} COPIA", key="dup_nuevo_nombre")
                copiar_imagen = st.checkbox("Copiar URL de imagen WooCommerce", value=True, key="dup_copiar_img")
                activo_nuevo = st.checkbox("Crear producto activo", value=False, key="dup_activo")
                st.info("Recomendación: créalo inactivo, revisa precios/peso/categoría y luego actívalo.")

                if st.button("📄 Duplicar producto", type="primary", use_container_width=True, key="btn_dup_producto"):
                    if not nuevo_sku.strip() or not nuevo_nombre.strip():
                        st.error("Nuevo SKU y nueva descripción son obligatorios.")
                    else:
                        existe = q("SELECT sku FROM productos WHERE sku=?", (nuevo_sku.strip(),), fetch=True)
                        if existe:
                            st.error("Ya existe un producto con ese SKU.")
                        else:
                            try:
                                data = dict(prod_base)
                            except Exception:
                                data = {k: prod_base[k] for k in prod_base.keys()}

                            data["sku"] = nuevo_sku.strip()
                            data["descripcion"] = nuevo_nombre.strip()
                            data["activo"] = 1 if activo_nuevo else 0
                            data["creado_en"] = now()
                            data["actualizado_en"] = now()
                            data["ultima_sync"] = ""
                            if not copiar_imagen:
                                data["wc_imagen_url"] = ""

                            # Duplicado seguro: usar solo columnas reales de productos y evitar valores raros.
                            cols = [c[1] for c in q("PRAGMA table_info(productos)", fetch=True)]
                            insert_cols = [c for c in cols if c in data]
                            placeholders = ",".join(["?"] * len(insert_cols))
                            col_sql = ",".join(insert_cols)
                            vals = tuple(data[c] for c in insert_cols)

                            try:
                                q(f"INSERT INTO productos ({col_sql}) VALUES ({placeholders})", vals)
                                st.session_state["sku_producto_editar"] = nuevo_sku.strip()
                                set_feedback(f"Producto duplicado correctamente: {nuevo_sku.strip()}. Ya quedó cargado en Crear / Editar.", "success")
                                st.rerun()
                            except Exception as e:
                                st.error(f"No se pudo duplicar el producto: {e}")


def mi_perfil():
    st.title("👤 Mi perfil")
    user_actual = get_user(st.session_state.user["username"])
    if not user_actual:
        st.error("No se pudo cargar tu perfil. Cierra sesión e inicia nuevamente.")
        return

    st.caption("Actualiza tus datos de contacto y entrega. El usuario, rol y condiciones de crédito solo puede cambiarlos el administrador.")

    with st.form("form_mi_perfil"):
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre / razón social", value=user_actual["nombre"] or "")
        email = c2.text_input("Correo", value=(user_actual["email"] if "email" in user_actual.keys() and user_actual["email"] else ""))

        c3, c4, c5 = st.columns(3)
        telefono = c3.text_input("Teléfono", value=user_actual["telefono"] or "")
        rif = c4.text_input("RIF / CI", value=user_actual["rif"] or "")
        ciudad = c5.text_input("Ciudad", value=user_actual["ciudad"] or "")

        direccion = st.text_area("Dirección fiscal / entrega", value=user_actual["direccion"] or "")
        password = st.text_input("Cambiar contraseña", type="password", help="Déjalo vacío si no deseas cambiarla.")

        st.info(
            f"Usuario de acceso: {user_actual['username']}\n\n"
            f"Rol: {user_actual['rol']}\n\n"
            f"Condición especial: {'Activa' if int(user_actual['cliente_especial'] if 'cliente_especial' in user_actual.keys() and user_actual['cliente_especial'] is not None else 0) == 1 else 'No activa'}\n\n"
            f"Crédito normal: {'Activo' if int(user_actual['credito_habilitado'] or 0) == 1 else 'No activo'}\n\n"
            f"Crédito BCV: {'Activo' if int(user_actual['credito_bcv_habilitado'] if 'credito_bcv_habilitado' in user_actual.keys() and user_actual['credito_bcv_habilitado'] is not None else 0) == 1 else 'No activo'}\n\n"
            "Para cambiar usuario, rol, crédito, límite o días de crédito, contacta al administrador."
        )

        submit = st.form_submit_button("💾 Guardar mi perfil", type="primary")

    if submit:
        if not nombre.strip():
            st.error("El nombre / razón social no puede quedar vacío.")
            return
        if email and email_existe(email, excluir_username=user_actual["username"]):
            st.error("Ese correo ya está usado por otro usuario.")
            return

        if password:
            q("""UPDATE usuarios SET nombre=?, email=?, telefono=?, rif=?, ciudad=?, direccion=?, password_hash=? WHERE username=?""",
              (nombre, email, telefono, rif, ciudad, direccion, hash_password(password), user_actual["username"]))
        else:
            q("""UPDATE usuarios SET nombre=?, email=?, telefono=?, rif=?, ciudad=?, direccion=? WHERE username=?""",
              (nombre, email, telefono, rif, ciudad, direccion, user_actual["username"]))

        refreshed = get_user(user_actual["username"])
        if refreshed:
            st.session_state.user = dict(refreshed)
        set_feedback("Perfil actualizado correctamente.", "success")
        st.rerun()


def admin_usuarios():
    st.title("👥 Usuarios / Clientes")
    tab1, tab2 = st.tabs(["Listado / Cliente 360", "Crear / Editar"])

    with tab1:
        df = pd.read_sql_query(
            "SELECT id_usuario,username,email,nombre,rol,telefono,rif,ciudad,activo,cliente_especial,credito_habilitado,credito_bcv_habilitado,ml_envio,limite_credito_usd,dias_credito FROM usuarios ORDER BY rol,nombre",
            get_conn()
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.subheader("Examinar cliente")
        usuarios_exam = q("SELECT username,nombre FROM usuarios ORDER BY nombre", fetch=True)
        if usuarios_exam:
            opts_exam = {f"{u['nombre'] or u['username']} — {u['username']}": u["username"] for u in usuarios_exam}
            sel_exam = st.selectbox("Seleccionar cliente / usuario", list(opts_exam.keys()), key="exam_cliente_select")
            username_exam = opts_exam[sel_exam]
            ped = pd.read_sql_query("SELECT * FROM pedidos WHERE username=? ORDER BY id DESC", get_conn(), params=(username_exam,))
            cot = pd.read_sql_query("SELECT * FROM cotizaciones WHERE username=? ORDER BY id DESC", get_conn(), params=(username_exam,))
            cre = pd.read_sql_query("SELECT * FROM creditos WHERE username=? ORDER BY id DESC", get_conn(), params=(username_exam,))
            total_gastado = float(ped[ped["status"].astype(str).str.lower() != "cancelado"]["total_usd"].sum()) if not ped.empty else 0.0
            total_pagado_final = float(ped[ped["status"].astype(str).str.contains("Finalizado|Pagado|Procesado|Confirmado", case=False, na=False)]["total_usd"].sum()) if not ped.empty else 0.0
            saldo_credito = float(cre["saldo_usd"].sum()) if not cre.empty else 0.0

            ultima_compra = ped["fecha"].max() if not ped.empty else "Sin compras"
            promedio_compra = total_gastado / len(ped) if len(ped) else 0.0
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("Pedidos", len(ped))
            k2.metric("Total pedidos", money_usd(total_gastado))
            k3.metric("Compras finalizadas", money_usd(total_pagado_final))
            k4.metric("Saldo crédito", money_usd(saldo_credito))
            k5.metric("Promedio compra", money_usd(promedio_compra))
            st.caption(f"Última compra / pedido: {ultima_compra}")

            sub1, sub2, sub3, sub4 = st.tabs(["Pedidos", "Cotizaciones", "Créditos", "Productos frecuentes"])
            with sub1:
                if ped.empty:
                    st.info("Sin pedidos.")
                else:
                    st.dataframe(ped[["id","fecha","cliente_nombre","tipo_pago","total_usd","status"]], use_container_width=True, hide_index=True)
            with sub2:
                if cot.empty:
                    st.info("Sin cotizaciones.")
                else:
                    st.dataframe(cot[["id","fecha","cliente_nombre","total_usd","status"]], use_container_width=True, hide_index=True)
            with sub3:
                if cre.empty:
                    st.info("Sin créditos.")
                else:
                    st.dataframe(cre[["id","pedido_id","fecha_inicio","fecha_vencimiento","monto_usd","saldo_usd","status"]], use_container_width=True, hide_index=True)
            with sub4:
                frecuentes = productos_mas_comprados_por_usuario(username_exam)
                if not frecuentes:
                    st.info("Sin productos frecuentes todavía.")
                else:
                    st.dataframe(pd.DataFrame(frecuentes).head(20), use_container_width=True, hide_index=True,
                                 column_config={"Total USD": st.column_config.NumberColumn(format="$%.2f")})

        st.subheader("Acciones administrativas")
        usuarios = q("SELECT username,nombre FROM usuarios ORDER BY nombre", fetch=True)
        if usuarios:
            opts = {f"{u['nombre'] or u['username']} — {u['username']}": u["username"] for u in usuarios}
            sel = st.selectbox("Usuario", list(opts.keys()), key="user_delete_select")
            username_sel = opts[sel]
            c1, c2 = st.columns(2)
            confirmar = st.checkbox("Confirmar acción sobre este usuario")
            if c1.button("🚫 Desactivar usuario", disabled=not confirmar, use_container_width=True):
                q("UPDATE usuarios SET activo=0 WHERE username=?", (username_sel,))
                st.warning("Usuario desactivado.")
                st.rerun()
            if c2.button("🗑️ Eliminar usuario", disabled=not confirmar, use_container_width=True):
                relacionados = q("SELECT COUNT(*) AS n FROM pedidos WHERE username=?", (username_sel,), fetch=True)[0]["n"]
                if relacionados:
                    st.error("Este usuario tiene pedidos asociados. Desactívalo para conservar trazabilidad.")
                elif username_sel == st.session_state.user["username"]:
                    st.error("No puedes eliminar tu propio usuario activo.")
                else:
                    q("DELETE FROM usuarios WHERE username=?", (username_sel,))
                    q("DELETE FROM carritos WHERE username=?", (username_sel,))
                    st.success("Usuario eliminado.")
                    st.rerun()

    with tab2:
        st.caption("Usa botones separados para crear o actualizar. Esto evita duplicar usuarios al editar correo o username.")
        modo = st.radio("Acción", ["Crear usuario nuevo", "Actualizar usuario existente"], horizontal=True)

        usuarios = q("SELECT username,nombre FROM usuarios ORDER BY nombre", fetch=True)
        edit_row = None
        username_original = ""

        if modo == "Actualizar usuario existente":
            if not usuarios:
                st.info("No hay usuarios para editar.")
                return
            opciones = [f"{u['nombre'] or u['username']} — {u['username']}" for u in usuarios]
            mapa = {f"{u['nombre'] or u['username']} — {u['username']}": u["username"] for u in usuarios}
            sel_edit = st.selectbox("Seleccionar usuario para editar", opciones)
            username_original = mapa[sel_edit]
            edit_row = get_user(username_original)
            if edit_row:
                st.info(f"Editando usuario existente: {edit_row['nombre'] or edit_row['username']} · ID interno: {edit_row['id_usuario'] if 'id_usuario' in edit_row.keys() else 'N/A'}")
        else:
            st.info("Creando usuario nuevo. Si quieres cambiar datos de alguien existente, usa Actualizar usuario existente.")

        with st.form("crear_editar_usuario_v43"):
            c1, c2, c3 = st.columns(3)
            username = c1.text_input("Usuario / login", value=edit_row["username"] if edit_row else "", help="Solo admin puede cambiarlo. Si cambia, se actualizarán pedidos, créditos, cotizaciones y carrito asociados.")
            email = c2.text_input("Correo", value=(edit_row["email"] if edit_row and "email" in edit_row.keys() and edit_row["email"] else ""))
            nombre = c3.text_input("Nombre / razón social", value=edit_row["nombre"] if edit_row else "")

            rol_default = edit_row["rol"] if edit_row and edit_row["rol"] in ["comprador", "vendedor", "vendedor_mercadolibre", "admin"] else "comprador"
            c4, c5, c6 = st.columns(3)
            rol = c4.selectbox("Rol", ["comprador", "vendedor", "vendedor_mercadolibre", "admin"], index=["comprador","vendedor","vendedor_mercadolibre","admin"].index(rol_default))
            telefono = c5.text_input("Teléfono", value=edit_row["telefono"] if edit_row else "")
            rif = c6.text_input("RIF / CI", value=edit_row["rif"] if edit_row else "")

            ciudad = st.text_input("Ciudad", value=edit_row["ciudad"] if edit_row else "")
            direccion = st.text_area("Dirección", value=edit_row["direccion"] if edit_row else "")

            c7, c8, c9, c10, c11, c12 = st.columns(6)
            cliente_especial = c7.checkbox("Cliente especial", value=bool(edit_row["cliente_especial"]) if edit_row and "cliente_especial" in edit_row.keys() else False, help="Activa precios especiales en productos que los tengan configurados.")
            credito_hab = c8.checkbox("Crédito habilitado", value=bool(edit_row["credito_habilitado"]) if edit_row else False)
            credito_bcv_hab = c9.checkbox("Crédito BCV habilitado", value=bool(edit_row["credito_bcv_habilitado"]) if edit_row and "credito_bcv_habilitado" in edit_row.keys() else False, help="Permite que este cliente vea y use la modalidad Crédito BCV.")
            ml_envio = c10.checkbox("ML / ENVÍO", value=bool(edit_row["ml_envio"]) if edit_row else False, help="Activa cálculo sugerido de envío por peso para clientes MercadoLibre o fuera del estado.")
            limite = c11.number_input("Límite crédito USD", min_value=0.0, value=float(edit_row["limite_credito_usd"] if edit_row else 0), step=1.0)
            dias = c12.number_input("Días crédito", min_value=1, max_value=90, value=int(edit_row["dias_credito"] if edit_row else parse_float(get_config("dias_credito_default","10"), 10)))
            activo = st.checkbox("Activo", value=bool(edit_row["activo"]) if edit_row else True)
            password = st.text_input("Contraseña nueva / inicial", type="password", help="Déjala vacía para conservar la actual si estás editando. En usuarios nuevos, si la dejas vacía será 1234.")

            cbtn1, cbtn2 = st.columns(2)
            submit_create = cbtn1.form_submit_button("➕ Crear usuario nuevo", type="primary", disabled=(modo != "Crear usuario nuevo"))
            submit_update = cbtn2.form_submit_button("💾 Actualizar usuario existente", type="primary", disabled=(modo != "Actualizar usuario existente"))

        if submit_create:
            ok, msg = crear_usuario_admin(username, password, nombre, rol, telefono, rif, ciudad, direccion, email, cliente_especial, credito_hab, credito_bcv_hab, ml_envio, limite, dias, activo)
            if ok:
                set_feedback(msg, "success")
                st.rerun()
            else:
                st.error(msg)

        if submit_update:
            ok, msg = actualizar_usuario_admin(username_original, username, nombre, rol, telefono, rif, ciudad, direccion, email, cliente_especial, credito_hab, credito_bcv_hab, ml_envio, limite, dias, activo, password)
            if ok:
                set_feedback(msg, "success")
                st.rerun()
            else:
                st.error(msg)



def admin_cotizaciones():
    st.title("📄 Cotizaciones")
    st.caption("Busca por número, cliente, fecha, estado o monto.")

    bus = st.text_input("Buscar cotización", placeholder="Ejemplo: Papelería, 29/05/2026, Pendiente, #12")
    df = pd.read_sql_query("SELECT id,fecha,cliente_nombre,cliente_rif,subtotal_usd,envio_usd,total_usd,total_bs_proveedor,status,peso_total_kg FROM cotizaciones ORDER BY id DESC", get_conn())

    if bus and not df.empty:
        b = bus.strip().lower().replace("#", "")
        mask = (
            df["id"].astype(str).str.contains(b, case=False, na=False) |
            df["fecha"].astype(str).str.lower().str.contains(b, na=False) |
            df["cliente_nombre"].astype(str).str.lower().str.contains(b, na=False) |
            df["cliente_rif"].astype(str).str.lower().str.contains(b, na=False) |
            df["status"].astype(str).str.lower().str.contains(b, na=False) |
            df["total_usd"].astype(str).str.contains(b, case=False, na=False)
        )
        df = df[mask]

    st.dataframe(df, use_container_width=True, hide_index=True)
    if df.empty:
        st.info("No hay cotizaciones que coincidan con la búsqueda.")
        return

    cot_ids = df["id"].astype(int).tolist()
    cot_id = st.selectbox("Seleccionar cotización", cot_ids, format_func=lambda x: f"Cotización #{x}")
    c1, c2 = st.columns(2)
    if c1.button("📄 Generar PDF", use_container_width=True):
        pdf = generar_pdf_cotizacion(int(cot_id))
        if pdf:
            st.download_button("⬇️ Descargar cotización PDF", data=pdf, file_name=f"cotizacion_{int(cot_id):04d}.pdf", mime="application/pdf", use_container_width=True)
        else:
            st.error("Cotización no encontrada.")

    rows_status = q("SELECT status FROM cotizaciones WHERE id=?", (int(cot_id),), fetch=True)
    estado_actual_cot = rows_status[0]["status"] if rows_status else "Pendiente"
    estados_cot = ["Pendiente", "Enviada", "Aprobada", "Rechazada", "Convertida en pedido"]
    c_estado1, c_estado2 = st.columns([1.2, 1])
    nuevo_estado_cot = c_estado1.selectbox(
        "Estado de cotización",
        estados_cot,
        index=estados_cot.index(estado_actual_cot) if estado_actual_cot in estados_cot else 0,
        key=f"estado_cot_{cot_id}"
    )
    if c_estado2.button("💾 Guardar estado cotización", use_container_width=True):
        q("UPDATE cotizaciones SET status=? WHERE id=?", (nuevo_estado_cot, int(cot_id)))
        st.success("Estado de cotización actualizado.")
        st.rerun()

    rows_det = q("SELECT * FROM cotizaciones WHERE id=?", (int(cot_id),), fetch=True)
    if rows_det:
        cot_det = rows_det[0]
        with st.expander("Ver detalle de cotización", expanded=False):
            st.write(f"Cliente: **{cot_det['cliente_nombre']}** · Total: **{money_usd(cot_det['total_usd'])}**")
            items_cot = pd.DataFrame(pedido_items_rows(cot_det))
            if not items_cot.empty:
                st.dataframe(items_cot, use_container_width=True, hide_index=True,
                             column_config={"Subtotal USD": st.column_config.NumberColumn(format="$%.2f")})

    c3, c4 = st.columns(2)
    tipo_convertir = c3.radio("Convertir como", ["Contado", "Crédito"], horizontal=True, key=f"tipo_convertir_cot_{cot_id}")
    if c4.button("➡️ Convertir cotización en pedido", use_container_width=True):
        rows = q("SELECT * FROM cotizaciones WHERE id=?", (int(cot_id),), fetch=True)
        if rows:
            cot = rows[0]
            fake_user = get_user(cot["username"]) or get_user(st.session_state.user["username"])
            items = json.loads(cot["items"] or "{}")
            tipo_pago = "credito" if tipo_convertir == "Crédito" else "contado"
            pid, msg = crear_pedido_desde_carrito(fake_user, items, tipo_pago, "Por confirmar", cot["envio_usd"], f"Convertido desde cotización #{cot_id}")
            if pid:
                q("UPDATE cotizaciones SET status='Convertida en pedido' WHERE id=?", (int(cot_id),))
                st.success(f"Cotización convertida en pedido #{pid}.")
                st.rerun()

    st.markdown("#### Zona sensible")
    confirmar_del_cot = st.checkbox("Confirmar eliminación de cotización", key=f"confirm_del_cot_{cot_id}")
    if st.button("🗑️ Eliminar cotización", disabled=not confirmar_del_cot, use_container_width=True, key=f"del_cot_{cot_id}"):
        q("DELETE FROM cotizaciones WHERE id=?", (int(cot_id),))
        st.warning("Cotización eliminada.")
        st.rerun()


def dashboard_admin():
    st.title("📊 Dashboard Comercial")

    pedidos = pd.read_sql_query("SELECT * FROM pedidos", get_conn())
    creditos = pd.read_sql_query("SELECT * FROM creditos", get_conn())
    abonos = pd.read_sql_query("SELECT * FROM abonos", get_conn())
    productos = pd.read_sql_query("SELECT * FROM productos", get_conn())

    pedidos_activos = pedidos[~pedidos["status"].astype(str).str.lower().isin(["cancelado", "anulado"])] if not pedidos.empty else pedidos
    total_pedidos = float(pedidos_activos["total_usd"].sum()) if not pedidos_activos.empty else 0.0
    saldo = float(creditos["saldo_usd"].sum()) if not creditos.empty else 0.0
    pend = len(abonos[abonos["status"]=="Pendiente de validar"]) if not abonos.empty else 0
    cot_pend = pd.read_sql_query("SELECT COUNT(*) AS n FROM cotizaciones WHERE status IN ('Pendiente','Enviada','Aprobada')", get_conn()).iloc[0]["n"]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Pedidos activos", len(pedidos_activos))
    c2.metric("Ventas/Pedidos USD", money_usd(total_pedidos))
    c3.metric("Saldo créditos", money_usd(saldo))
    c4.metric("Pagos por validar", pend)
    c5.metric("Cotizaciones abiertas", int(cot_pend or 0))

    tab1, tab2, tab3, tab4 = st.tabs(["Últimos pedidos", "Mejores clientes", "Productos/Categorías", "Alertas comerciales"])

    with tab1:
        if pedidos.empty:
            st.info("Sin pedidos.")
        else:
            cols = ["id","fecha","cliente_nombre","tipo_pago","metodo_pago","total_usd","status","pos_procesado"]
            st.dataframe(pedidos[cols].sort_values("id", ascending=False).head(25), use_container_width=True, hide_index=True)

    with tab2:
        if pedidos_activos.empty:
            st.info("Sin ventas activas.")
        else:
            mejores = pedidos_activos.groupby(["username","cliente_nombre"], dropna=False).agg(
                pedidos=("id","count"),
                total_usd=("total_usd","sum"),
                ultima_compra=("fecha","max")
            ).reset_index().sort_values("total_usd", ascending=False)
            st.dataframe(mejores.head(30), use_container_width=True, hide_index=True,
                         column_config={"total_usd": st.column_config.NumberColumn(format="$%.2f")})

    with tab3:
        items = []
        if not pedidos_activos.empty:
            for _, p in pedidos_activos.iterrows():
                for it in pedido_items_rows(p):
                    items.append(it)
        if not items:
            st.info("Aún no hay productos vendidos para analizar.")
        else:
            df_items = pd.DataFrame(items)
            prod_top = df_items.groupby(["SKU","Producto"], dropna=False).agg(
                unidades=("Unidades","sum"),
                total_usd=("Subtotal USD","sum"),
                lineas=("SKU","count")
            ).reset_index().sort_values("total_usd", ascending=False)
            st.subheader("Productos más vendidos")
            st.dataframe(prod_top.head(30), use_container_width=True, hide_index=True,
                         column_config={"total_usd": st.column_config.NumberColumn(format="$%.2f")})

            if not productos.empty:
                cat_map = productos[["sku","categoria_id"]].copy()
                cats = pd.read_sql_query("SELECT id,nombre FROM categorias", get_conn())
                cat_map = cat_map.merge(cats, left_on="categoria_id", right_on="id", how="left")
                df_cat = df_items.merge(cat_map, left_on="SKU", right_on="sku", how="left")
                cat_top = df_cat.groupby("nombre", dropna=False).agg(
                    unidades=("Unidades","sum"),
                    total_usd=("Subtotal USD","sum"),
                    lineas=("SKU","count")
                ).reset_index().rename(columns={"nombre":"Categoría"}).sort_values("total_usd", ascending=False)
                st.subheader("Categorías más vendidas")
                st.dataframe(cat_top, use_container_width=True, hide_index=True,
                             column_config={"total_usd": st.column_config.NumberColumn(format="$%.2f")})

    with tab4:
        alertas = productos_alertas_margen()
        if not alertas:
            st.success("No hay alertas comerciales relevantes.")
        else:
            df_alertas = pd.DataFrame(alertas)
            a1, a2, a3 = st.columns(3)
            a1.metric("Productos con alerta", len(df_alertas))
            a2.metric("Sin costo proveedor", int(df_alertas["Alertas"].str.contains("Sin costo proveedor").sum()))
            a3.metric("Margen bajo", int(df_alertas["Alertas"].str.contains("Margen").sum()))
            st.dataframe(df_alertas, use_container_width=True, hide_index=True)


def pagos_rows_para_usuario(username):
    rows = q("""SELECT a.*, p.cliente_nombre, p.total_usd AS pedido_total_usd, p.status AS pedido_status
                FROM abonos a
                LEFT JOIN pedidos p ON p.id = a.pedido_id
                WHERE a.username=?
                ORDER BY a.id DESC""", (username,), fetch=True)
    data = []
    for a in rows:
        tipo = str(a["tipo_credito"] if "tipo_credito" in a.keys() and a["tipo_credito"] else "usd").lower()
        credito_id = int(a["credito_id"] or 0)
        origen = "Pago contado" if credito_id <= 0 or tipo == "contado" else f"Crédito #{credito_id}"
        monto_txt = f"{money_usd(a['monto_bcv'] or a['monto_usd'])} BCV" if tipo == "bcv" else money_usd(a["monto_usd"])
        tasa_txt = ""
        if tipo == "bcv":
            tasa_txt = f"BCV {float(a['tasa_bcv'] or 0):,.2f}"
        elif tipo in ["usd", "contado"]:
            tasa_txt = f"Proveedor {float(a['tasa_proveedor'] if 'tasa_proveedor' in a.keys() and a['tasa_proveedor'] else 0):,.2f}"
        data.append({
            "id": int(a["id"]),
            "fecha": a["fecha"],
            "pedido_id": int(a["pedido_id"] or 0),
            "origen": origen,
            "tipo": tipo.upper(),
            "monto": monto_txt,
            "Bs esperado": money_bs(a["monto_bs_esperado"] if "monto_bs_esperado" in a.keys() and a["monto_bs_esperado"] else a["monto_bs"] or 0),
            "tasa usada": tasa_txt,
            "método": a["metodo"] or "",
            "referencia": a["referencia"] or "",
            "status": a["status"],
            "notas": a["notas"] or "",
        })
    return data

def mostrar_historial_pagos_cliente(username, titulo="Mis pagos notificados"):
    st.subheader(titulo)
    data = pagos_rows_para_usuario(username)
    if not data:
        st.info("Todavía no tienes pagos o abonos notificados.")
        return

    df = pd.DataFrame(data)
    pendientes = df[df["status"].astype(str) == "Pendiente de validar"]
    validados = df[df["status"].astype(str) == "Validado"]
    rechazados = df[df["status"].astype(str) == "Rechazado"]

    c1, c2, c3 = st.columns(3)
    c1.metric("En verificación", len(pendientes))
    c2.metric("Validados", len(validados))
    c3.metric("Rechazados", len(rechazados))

    if not pendientes.empty:
        st.warning("Pagos en proceso de verificación")
        st.dataframe(pendientes.drop(columns=["notas"], errors="ignore"), use_container_width=True, hide_index=True)

    with st.expander("Ver histórico completo de pagos", expanded=False):
        st.dataframe(df, use_container_width=True, hide_index=True)

def estado_visual(texto, tipo="pedido"):
    t = str(texto or "").strip()
    low = t.lower()
    if any(x in low for x in ["finalizado", "pagado", "validado"]):
        return f"🟢 {t}"
    if any(x in low for x in ["verificar", "validar", "revisión", "revision", "pago por validar", "pendiente de validar"]):
        return f"🔵 {t}"
    if any(x in low for x in ["crédito en curso", "credito en curso", "en curso", "parcial"]):
        return f"🟡 {t}"
    if any(x in low for x in ["pendiente", "preparando", "confirmado", "listo"]):
        return f"🟠 {t}"
    if any(x in low for x in ["cancelado", "anulado", "rechazado", "vencido"]):
        return f"🔴 {t}"
    return f"⚪ {t}"

def pos_visual(valor):
    try:
        return "🟢 POS procesado" if int(valor or 0) == 1 else "🟠 POS pendiente"
    except Exception:
        return "🟠 POS pendiente"

def alertas_inteligentes_admin():
    alertas = []

    # Pagos por verificar
    try:
        n = q("SELECT COUNT(*) AS n FROM abonos WHERE status='Pendiente de validar'", fetch=True)[0]["n"]
        if int(n or 0) > 0:
            alertas.append({"Tipo": "Pagos", "Alerta": f"{int(n)} pago(s) por verificar", "Prioridad": "Alta", "Acción sugerida": "Ir a Centro admin > Pagos por verificar"})
    except Exception:
        pass

    # Pedidos pendientes de pago / atención
    try:
        n = q("""SELECT COUNT(*) AS n FROM pedidos
                 WHERE COALESCE(status,'') IN ('Pendiente','Pendiente de pago','Pago por validar','Confirmado','Preparando','Listo para entregar','Crédito en curso')""", fetch=True)[0]["n"]
        if int(n or 0) > 0:
            alertas.append({"Tipo": "Pedidos", "Alerta": f"{int(n)} pedido(s) requieren atención", "Prioridad": "Media", "Acción sugerida": "Revisar pedidos por atender"})
    except Exception:
        pass

    # POS pendiente
    try:
        n = q("""SELECT COUNT(*) AS n FROM pedidos
                 WHERE COALESCE(pos_procesado,0)=0
                 AND COALESCE(status,'') NOT IN ('Cancelado','Anulado')""", fetch=True)[0]["n"]
        if int(n or 0) > 0:
            alertas.append({"Tipo": "POS", "Alerta": f"{int(n)} pedido(s) pendientes por POS", "Prioridad": "Media", "Acción sugerida": "Ir a Control POS"})
    except Exception:
        pass

    # Créditos próximos/vencidos
    try:
        rows = q("""SELECT id,cliente_nombre,fecha_vencimiento,saldo_usd,saldo_bcv,tipo_credito,status
                    FROM creditos
                    WHERE status NOT IN ('Pagado','Anulado')
                    AND (COALESCE(saldo_usd,0)>0 OR COALESCE(saldo_bcv,0)>0)""", fetch=True)
        hoy = datetime.now().date()
        for cr in rows:
            fv = str(cr["fecha_vencimiento"] or "").strip()
            try:
                dt = datetime.strptime(fv, "%d/%m/%Y").date()
                dias = (dt - hoy).days
                if dias < 0:
                    alertas.append({"Tipo": "Crédito", "Alerta": f"Crédito #{cr['id']} vencido ({cr['cliente_nombre']})", "Prioridad": "Alta", "Acción sugerida": "Contactar cliente / revisar pago"})
                elif dias <= 3:
                    alertas.append({"Tipo": "Crédito", "Alerta": f"Crédito #{cr['id']} vence en {dias} día(s) ({cr['cliente_nombre']})", "Prioridad": "Media", "Acción sugerida": "Recordatorio preventivo"})
            except Exception:
                pass
    except Exception:
        pass

    # Productos sin costo / margen bajo
    try:
        problemas = productos_alertas_margen()
        for p in problemas[:20]:
            alertas.append({"Tipo": "Producto", "Alerta": f"{p.get('SKU','')} · {p.get('Descripción','')} · {p.get('Alertas','')}", "Prioridad": "Media", "Acción sugerida": "Revisar costo/margen del producto"})
    except Exception:
        pass

    # Stock bajo
    try:
        umbral = int(parse_float(get_config("stock_bajo_umbral", "5"), 5))
        rows = q("""SELECT sku,descripcion,wc_stock FROM productos
                    WHERE activo=1 AND COALESCE(wc_stock,0)>0 AND COALESCE(wc_stock,0)<=?
                    ORDER BY wc_stock ASC LIMIT 30""", (umbral,), fetch=True)
        for p in rows:
            alertas.append({"Tipo": "Stock", "Alerta": f"{p['sku']} · {p['descripcion']} · stock {p['wc_stock']}", "Prioridad": "Media", "Acción sugerida": "Reponer o revisar WooCommerce"})
    except Exception:
        pass

    return alertas

def pedido_contado_pendiente_de_pago(p):
    try:
        tipo = str(p["tipo_pago"] or "").lower()
        status = str(p["status"] or "")
        return tipo == "contado" and status in ["Pendiente de pago", "Pendiente", "Pago parcial POS"]
    except Exception:
        return False

def pedido_contado_en_verificacion(p):
    try:
        return str(p["tipo_pago"] or "").lower() == "contado" and str(p["status"] or "") in ["Pago por verificar", "Pago por validar"]
    except Exception:
        return False

def pedidos_contado_pendientes_usuario(username, limit=20):
    return q("""SELECT * FROM pedidos
                WHERE username=?
                AND tipo_pago='contado'
                AND COALESCE(status,'') IN ('Pendiente','Pendiente de pago','Pago parcial POS')
                ORDER BY id DESC
                LIMIT ?""", (username, int(limit)), fetch=True)

def pedidos_contado_verificacion_usuario(username, limit=20):
    return q("""SELECT * FROM pedidos
                WHERE username=?
                AND tipo_pago='contado'
                AND COALESCE(status,'') IN ('Pago por verificar','Pago por validar')
                ORDER BY id DESC
                LIMIT ?""", (username, int(limit)), fetch=True)

def formulario_cargar_pago_contado_pendiente(pedido, username, key_prefix="pago_contado_pendiente"):
    pedido_id = int(pedido["id"])
    total_usd = float(pedido["total_usd"] or 0)
    tasa = get_tasa_proveedor()
    total_bs = total_usd * tasa

    # Si ya tiene un pago pendiente de validar, no dejamos duplicar desde aquí.
    pendientes = q("""SELECT * FROM abonos
                      WHERE pedido_id=? AND tipo_credito='contado'
                      AND status='Pendiente de validar'
                      ORDER BY id DESC""", (pedido_id,), fetch=True)
    if pendientes:
        st.info(f"Ya existe un pago en verificación para el pedido #{pedido_id}. Espera la validación del admin.")
        return

    with st.expander(f"💳 Cargar pago del pedido #{pedido_id} · {money_usd(total_usd)}", expanded=True):
        st.info(
            f"Tu pedido hace un total de **{money_usd(total_usd)} divisas**.  \n"
            f"Tasa proveedor: **{tasa:,.2f}**.  \n"
            f"Total a cancelar en bolívares: **{money_bs(total_bs)}**."
        )

        metodos = metodos_pago_activos()
        mp_sel = None
        metodo_nombre = ""
        metodo_id = 0
        tipo_metodo = ""

        if metodos:
            opts = {f"{m['nombre']} · {m['tipo']}": m for m in metodos}
            sel = st.selectbox("Método de pago", list(opts.keys()), key=f"{key_prefix}_mp_{pedido_id}")
            mp_sel = opts[sel]
            metodo_id = int(mp_sel["id"])
            metodo_nombre = f"{mp_sel['nombre']} · {mp_sel['tipo']}"
            tipo_metodo = str(mp_sel["tipo"] or "")
            render_metodo_pago_card(mp_sel)
            render_instruccion_comprobante(mp_sel)
        else:
            st.warning("No hay métodos de pago activos configurados. Puedes escribir el método manualmente.")
            metodo_nombre = st.text_input("Método de pago", value="Pago pendiente", key=f"{key_prefix}_metodo_manual_{pedido_id}")
            tipo_metodo = "Otro"

        metodo_local_bs = tipo_metodo in ["Pago móvil", "Cuenta bancaria Venezuela"]

        if metodo_local_bs:
            st.success(f"Pago móvil / transferencia en bolívares · Monto sugerido: {money_bs(total_bs)}")
            st.caption("Los campos arrancan en 0. Coloca el monto real pagado en Bs y, si aplica, una parte adicional en divisas.")

            c1, c2 = st.columns(2)
            monto_bs = c1.number_input(
                "Pago principal en Bs",
                min_value=0.0,
                value=0.0,
                step=100.0,
                key=f"{key_prefix}_bs_principal_{pedido_id}",
                help=f"Monto sugerido a pagar: {money_bs(total_bs)}"
            )
            monto_usd = c2.number_input(
                "Parte pagada en divisas USD (opcional)",
                min_value=0.0,
                value=0.0,
                step=1.0,
                key=f"{key_prefix}_usd_extra_{pedido_id}",
                help="Solo úsalo si el cliente canceló una parte en divisas aparte del pago móvil/transferencia."
            )

        else:
            forma_pago = st.radio(
                "¿Cómo vas a pagar este pedido?",
                ["Divisas / USD", "Bolívares a tasa proveedor", "Pago mixto"],
                horizontal=True,
                key=f"{key_prefix}_forma_{pedido_id}",
                help="Elige la forma de pago y coloca el monto real pagado. Los campos arrancan en 0."
            )

            if forma_pago == "Divisas / USD":
                st.success(f"Monto sugerido a pagar en divisas: {money_usd(total_usd)}")
                c1, c2 = st.columns(2)
                monto_usd = c1.number_input(
                    "Monto pagado USD",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    key=f"{key_prefix}_usd_usd_{pedido_id}",
                    help=f"Monto sugerido: {money_usd(total_usd)}"
                )
                monto_bs = c2.number_input(
                    "Monto pagado Bs",
                    min_value=0.0,
                    value=0.0,
                    step=100.0,
                    key=f"{key_prefix}_bs_usd_{pedido_id}",
                    disabled=True,
                    help="Para pago en divisas, este campo queda en 0 para evitar doble conteo."
                )
            elif forma_pago == "Bolívares a tasa proveedor":
                st.success(f"Monto sugerido a pagar en bolívares: {money_bs(total_bs)}")
                c1, c2 = st.columns(2)
                monto_usd = c1.number_input(
                    "Monto pagado USD",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    key=f"{key_prefix}_usd_bs_{pedido_id}",
                    disabled=True,
                    help="Para pago en bolívares, este campo queda en 0 para evitar doble conteo."
                )
                monto_bs = c2.number_input(
                    "Monto pagado Bs",
                    min_value=0.0,
                    value=0.0,
                    step=100.0,
                    key=f"{key_prefix}_bs_bs_{pedido_id}",
                    help=f"Monto sugerido: {money_bs(total_bs)}"
                )
            else:
                st.warning("Pago mixto: usa esta opción solo si realmente pagaste una parte en USD y otra parte en Bs.")
                c1, c2 = st.columns(2)
                monto_usd = c1.number_input(
                    "Monto pagado USD",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    key=f"{key_prefix}_usd_mix_{pedido_id}",
                    help="Parte pagada en divisas."
                )
                monto_bs = c2.number_input(
                    "Monto pagado Bs",
                    min_value=0.0,
                    value=0.0,
                    step=100.0,
                    key=f"{key_prefix}_bs_mix_{pedido_id}",
                    help="Parte pagada en bolívares."
                )

        equiv_usd = float(monto_usd or 0) + (float(monto_bs or 0) / tasa if tasa > 0 else 0)
        faltante = total_usd - equiv_usd
        resumen = f"Equivalente total pagado: {money_usd(equiv_usd)}"
        if float(monto_bs or 0) > 0:
            resumen += f" · Pago en Bs: {money_bs(monto_bs)}"
        if float(monto_usd or 0) > 0:
            resumen += f" · Parte divisas: {money_usd(monto_usd)}"

        if faltante > 0.01:
            st.warning(f"{resumen} · Falta: {money_usd(faltante)}")
        elif abs(faltante) <= 0.01 and equiv_usd > 0:
            st.success(f"{resumen} · Pago completo.")
        elif equiv_usd <= 0:
            st.warning(f"{resumen} · Falta: {money_usd(total_usd)}")
        else:
            st.info(f"{resumen} · Diferencia a favor: {money_usd(abs(faltante))}")

        referencia = st.text_input("Referencia / número de operación", key=f"{key_prefix}_ref_{pedido_id}")
        comp = st.file_uploader("Comprobante / capture", type=["png","jpg","jpeg","webp","pdf"], key=f"{key_prefix}_comp_{pedido_id}")
        notas = st.text_area("Notas del pago", key=f"{key_prefix}_notas_{pedido_id}")

        enviar = st.button("✅ Enviar pago para verificar", type="primary", use_container_width=True, key=f"{key_prefix}_enviar_{pedido_id}")
        if enviar:
            if float(monto_usd or 0) <= 0 and float(monto_bs or 0) <= 0:
                st.error("Debes indicar el monto pagado en USD o en Bs.")
                return
            if not referencia.strip() and comp is None:
                st.error("Coloca una referencia o carga un comprobante para respaldar el pago.")
                return
            ok = registrar_pago_contado_pendiente(
                pedido_id,
                username,
                float(monto_usd or 0),
                float(monto_bs or 0),
                metodo_nombre,
                referencia=referencia.strip(),
                comprobante=comp,
                notas=notas.strip(),
                metodo_pago_id=metodo_id
            )
            if ok:
                st.success("Pago enviado correctamente. Queda en proceso de verificación por el admin.")
                st.rerun()
            else:
                st.error("No se pudo registrar el pago.")


def seccion_pedidos_pendientes_pago(username, titulo="Pedidos pendientes por pagar", limit=10, expanded=False):
    pendientes = pedidos_contado_pendientes_usuario(username, limit=limit)
    verificacion = pedidos_contado_verificacion_usuario(username, limit=limit)

    if not pendientes and not verificacion:
        return

    st.markdown("---")
    st.subheader(titulo)

    if verificacion:
        st.info(f"Tienes {len(verificacion)} pago(s) contado en proceso de verificación.")
        data_v = [{
            "Pedido": int(p["id"]),
            "Fecha": p["fecha"],
            "Total": money_usd(p["total_usd"]),
            "Estado": estado_visual(p["status"]),
        } for p in verificacion]
        st.dataframe(pd.DataFrame(data_v), use_container_width=True, hide_index=True)

    if pendientes:
        st.warning(f"Tienes {len(pendientes)} pedido(s) contado pendiente(s) de pago.")
        data = [{
            "Pedido": int(p["id"]),
            "Fecha": p["fecha"],
            "Total": money_usd(p["total_usd"]),
            "Estado": estado_visual(p["status"]),
        } for p in pendientes]
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
        if expanded:
            for p in pendientes[:3]:
                formulario_cargar_pago_contado_pendiente(p, username, key_prefix="home_pago_pendiente")
        else:
            st.caption("Entra en Mis pagos o Mis pedidos para cargar el comprobante/referencia del pedido.")


def mi_cuenta_home():
    st.title("👤 Mi cuenta")
    user = get_user(st.session_state.user["username"])
    username = user["username"]

    pedidos = pd.read_sql_query("SELECT * FROM pedidos WHERE username=? ORDER BY id DESC LIMIT 10", get_conn(), params=(username,))
    creditos = pd.read_sql_query("""SELECT * FROM creditos
                                    WHERE username=?
                                    AND status NOT IN ('Pagado','Anulado')
                                    AND (COALESCE(saldo_usd,0)>0 OR COALESCE(saldo_bcv,0)>0)
                                    ORDER BY id DESC""", get_conn(), params=(username,))
    pagos = pd.read_sql_query("SELECT * FROM abonos WHERE username=? ORDER BY id DESC LIMIT 20", get_conn(), params=(username,))

    saldo_credito = 0.0
    saldo_bcv = 0.0
    if not creditos.empty:
        saldo_credito = float(creditos["saldo_usd"].fillna(0).sum())
        if "saldo_bcv" in creditos.columns:
            saldo_bcv = float(creditos["saldo_bcv"].fillna(0).sum())

    pagos_verif = int((pagos["status"].astype(str) == "Pendiente de validar").sum()) if not pagos.empty else 0
    pedidos_activos = len(pedidos[~pedidos["status"].astype(str).str.lower().isin(["finalizado / pagado","cancelado","anulado"])]) if not pedidos.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pedidos activos", pedidos_activos)
    c2.metric("Pagos en verificación", pagos_verif)
    c3.metric("Créditos en curso", len(creditos))
    c4.metric("Saldo crédito", money_usd(saldo_credito))

    if pagos_verif:
        st.info("Tienes pagos en proceso de verificación. El admin debe validarlos antes de actualizar saldos.")
    if not creditos.empty:
        st.warning("Tienes crédito en curso. Puedes notificar abonos desde Mis créditos.")

    seccion_pedidos_pendientes_pago(username, titulo="Pedidos contado pendientes", limit=5, expanded=True)

    st.markdown("### Accesos rápidos")
    b1, b2, b3, b4 = st.columns(4)
    if b1.button("🛍️ Ir a tienda", use_container_width=True):
        st.session_state.menu = "Tienda"
        st.rerun()
    if b2.button("🧾 Mis pedidos", use_container_width=True):
        st.session_state.menu = "Mis pedidos"
        st.rerun()
    if b3.button("💳 Mis créditos", use_container_width=True):
        st.session_state.menu = "Mis créditos"
        st.rerun()
    if b4.button("💵 Mis pagos", use_container_width=True):
        st.session_state.menu = "Mis pagos"
        st.rerun()

    st.markdown("---")
    st.subheader("Pedidos recientes")
    if pedidos.empty:
        st.info("Todavía no tienes pedidos.")
    else:
        vista = pedidos[["id","fecha","cliente_nombre","tipo_pago","total_usd","status"]].copy()
        vista["estado"] = vista["status"].apply(estado_visual)
        vista = vista.drop(columns=["status"])
        st.dataframe(vista, use_container_width=True, hide_index=True,
                     column_config={"total_usd": st.column_config.NumberColumn(format="$%.2f")})

    st.subheader("Pagos recientes")
    if pagos.empty:
        st.info("Todavía no tienes pagos notificados.")
    else:
        pview = pagos[["id","fecha","pedido_id","monto_usd","monto_bs","metodo","referencia","status"]].copy()
        pview["estado"] = pview["status"].apply(estado_visual)
        pview = pview.drop(columns=["status"])
        st.dataframe(pview, use_container_width=True, hide_index=True,
                     column_config={"monto_usd": st.column_config.NumberColumn(format="$%.2f")})


def mis_pagos():
    st.title("💵 Mis pagos")
    user = get_user(st.session_state.user["username"])
    seccion_pedidos_pendientes_pago(user["username"], titulo="Pedidos pendientes por pagar", limit=20, expanded=True)
    mostrar_historial_pagos_cliente(user["username"], titulo="Historial de pagos y abonos")


def mis_pedidos():
    st.title("🧾 Pedidos / Gestor de órdenes")
    user = get_user(st.session_state.user["username"])
    visibles = usuarios_visibles_para(user)
    placeholders = ",".join(["?"]*len(visibles))
    df = pd.read_sql_query(f"SELECT * FROM pedidos WHERE username IN ({placeholders}) ORDER BY id DESC", get_conn(), params=visibles)
    if df.empty:
        st.info("Sin pedidos.")
        return

    bus = st.text_input("Buscar pedido", placeholder="Cliente, número, fecha, estado, monto...")
    estados_filtro = ["Todos"] + sorted([x for x in df["status"].dropna().astype(str).unique().tolist()])
    colf1, colf2, colf3 = st.columns([2, 1.3, 1.3])
    with colf1:
        filtro_estado = st.selectbox("Estado", estados_filtro)
    with colf2:
        solo_credito = st.checkbox("Solo créditos")
    with colf3:
        solo_pos_pendiente = st.checkbox("Pendiente POS")

    df_view = df.copy()
    if bus:
        b = bus.lower().replace("#", "")
        mask = (
            df_view["id"].astype(str).str.contains(b, na=False) |
            df_view["fecha"].astype(str).str.lower().str.contains(b, na=False) |
            df_view["cliente_nombre"].astype(str).str.lower().str.contains(b, na=False) |
            df_view["status"].astype(str).str.lower().str.contains(b, na=False) |
            df_view["total_usd"].astype(str).str.contains(b, na=False)
        )
        df_view = df_view[mask]
    if filtro_estado != "Todos":
        df_view = df_view[df_view["status"].astype(str) == filtro_estado]
    if solo_credito:
        df_view = df_view[df_view["tipo_pago"].astype(str).str.lower() == "credito"]
    if solo_pos_pendiente and "pos_procesado" in df_view.columns:
        df_view = df_view[df_view["pos_procesado"].fillna(0).astype(int) == 0]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Pedidos filtrados", len(df_view))
    k2.metric("Total filtrado", money_usd(df_view["total_usd"].sum() if not df_view.empty else 0))
    k3.metric("Créditos", int((df_view["tipo_pago"].astype(str).str.lower()=="credito").sum()) if not df_view.empty else 0)
    k4.metric("Pendiente POS", int((df_view["pos_procesado"].fillna(0).astype(int)==0).sum()) if "pos_procesado" in df_view.columns and not df_view.empty else 0)

    df_view = df_view.copy()
    df_view["estado_visual"] = df_view["status"].apply(estado_visual)
    if "pos_procesado" in df_view.columns:
        df_view["pos_visual"] = df_view["pos_procesado"].apply(pos_visual)
    resumen_cols = ["id","fecha","cliente_nombre","tipo_pago","total_usd","estado_visual"]
    if "pos_visual" in df_view.columns:
        resumen_cols.append("pos_visual")
    st.dataframe(df_view[resumen_cols], use_container_width=True, hide_index=True,
                 column_config={"total_usd": st.column_config.NumberColumn(format="$%.2f")})

    st.markdown("---")
    if df_view.empty:
        st.info("No hay pedidos que coincidan con los filtros.")
        return

    pid = st.selectbox("Examinar pedido", df_view["id"].astype(int).tolist(), format_func=lambda x: f"Pedido #{x}")
    rows = q("SELECT * FROM pedidos WHERE id=?", (int(pid),), fetch=True)
    if not rows:
        st.error("Pedido no encontrado.")
        return
    p = rows[0]

    ctop1, ctop2, ctop3, ctop4 = st.columns(4)
    ctop1.metric("Total", money_usd(p["total_usd"]))
    ctop2.metric("Tipo", str(p["tipo_pago"]).upper())
    ctop3.metric("Estado", estado_visual(p["status"]))
    ctop4.metric("POS", pos_visual(p["pos_procesado"]))

    st.write(f"Cliente: **{p['cliente_nombre']}** · Fecha: **{p['fecha']}** · Método: **{p['metodo_pago'] or 'N/A'}**")
    if p["notas"]:
        st.info(p["notas"])

    items_df = pd.DataFrame(pedido_items_rows(p))
    if not items_df.empty:
        st.subheader("Items del pedido")
        st.dataframe(items_df, use_container_width=True, hide_index=True,
                     column_config={"Subtotal USD": st.column_config.NumberColumn(format="$%.2f")})

    pagos_pedido = q("SELECT * FROM abonos WHERE pedido_id=? ORDER BY id DESC", (int(pid),), fetch=True)
    st.subheader("Pagos / abonos del pedido")
    if pagos_pedido:
        data_pagos_pedido = []
        for abp in pagos_pedido:
            tipo_abp = str(abp["tipo_credito"] if "tipo_credito" in abp.keys() and abp["tipo_credito"] else "usd").lower()
            monto_txt = f"{money_usd(abp['monto_bcv'] or abp['monto_usd'])} BCV" if tipo_abp == "bcv" else money_usd(abp["monto_usd"])
            data_pagos_pedido.append({
                "id": int(abp["id"]),
                "fecha": abp["fecha"],
                "tipo": tipo_abp.upper(),
                "monto": monto_txt,
                "Bs esperado": money_bs(abp["monto_bs_esperado"] if "monto_bs_esperado" in abp.keys() and abp["monto_bs_esperado"] else abp["monto_bs"] or 0),
                "método": abp["metodo"] or "",
                "referencia": abp["referencia"] or "",
                "status": abp["status"],
            })
        st.dataframe(pd.DataFrame(data_pagos_pedido), use_container_width=True, hide_index=True)
    else:
        st.info("Este pedido todavía no tiene pagos o abonos notificados.")

    if user["rol"] != "admin":
        if pedido_contado_pendiente_de_pago(p):
            st.markdown("---")
            formulario_cargar_pago_contado_pendiente(p, user["username"], key_prefix="mis_pedidos_pago_pendiente")
        elif pedido_contado_en_verificacion(p):
            st.info("Este pedido ya tiene un pago en proceso de verificación. El admin debe validarlo.")

    estados = ["Pendiente", "Pendiente de pago", "Pago por verificar", "Pago por validar", "Confirmado", "Preparando", "Listo para entregar",
               "Entregado", "Crédito en curso", "Finalizado / Pagado", "Cancelado", "Anulado"]

    c1, c2, c3 = st.columns(3)
    with c1:
        pdf = generar_pdf_pedido(int(pid))
        packing_pdf = generar_pdf_packing_list_pedido(int(pid))
        st.download_button("📄 Descargar PDF", data=pdf, file_name=f"pedido_{int(pid):04d}.pdf", mime="application/pdf", use_container_width=True)
        st.download_button("📦 Descargar Packing List", data=packing_pdf, file_name=f"packing_list_{int(pid):04d}.pdf", mime="application/pdf", use_container_width=True)

    if user["rol"] == "admin":
        with c2:
            idx = estados.index(p["status"]) if p["status"] in estados else 0
            nuevo = st.selectbox("Cambiar estado", estados, index=idx, key=f"estado_pedido_manager_{pid}")
            if st.button("Guardar estado", use_container_width=True, key=f"save_estado_ped_{pid}"):
                if nuevo in ["Cancelado", "Anulado"]:
                    ok, msg = anular_credito_de_pedido(int(pid), f"Pedido cambiado a {nuevo} por admin")
                    if ok:
                        q("UPDATE pedidos SET status=? WHERE id=?", (nuevo, int(pid)))
                    st.success(msg) if ok else st.error(msg)
                elif nuevo == "Finalizado / Pagado" and p["credito_id"]:
                    ok, msg = marcar_credito_pagado(int(p["credito_id"]), st.session_state.user["username"])
                    st.success(msg) if ok else st.error(msg)
                else:
                    q("UPDATE pedidos SET status=? WHERE id=?", (nuevo, int(pid)))
                    st.success("Estado actualizado.")
                st.rerun()

        with c3:
            confirmar = st.checkbox("Confirmar eliminación", key=f"confirm_del_pedido_{pid}")
            if st.button("🗑️ Eliminar pedido", key=f"del_pedido_{pid}", disabled=not confirmar, use_container_width=True):
                ok, msg = eliminar_pedido_seguro(int(pid))
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        st.markdown("---")
        st.subheader("Asignar / transferir pedido")
        usuarios_dest = q("SELECT username,nombre FROM usuarios WHERE activo=1 ORDER BY nombre,username", fetch=True)
        if usuarios_dest:
            opts_dest = {f"{u['nombre'] or u['username']} — {u['username']}": u["username"] for u in usuarios_dest}
            sel_dest = st.selectbox("Cliente destino", list(opts_dest.keys()), key=f"transfer_cliente_{pid}")
            confirmar_transfer = st.checkbox("Confirmar transferencia de este pedido", key=f"confirm_transfer_{pid}")
            if st.button("🔁 Transferir pedido a cliente", disabled=not confirmar_transfer, use_container_width=True, key=f"btn_transfer_pedido_{pid}"):
                ok, msg = transferir_pedido_a_cliente(int(pid), opts_dest[sel_dest])
                st.success(msg) if ok else st.error(msg)
                if ok:
                    st.rerun()

        st.markdown("---")
        st.subheader("Editar pedido")
        if not pedido_permite_edicion(p):
            st.warning("Este pedido no puede editarse por su estado actual. Para editarlo, primero cámbialo a un estado pendiente si corresponde.")
        else:
            abonos_validados = q("SELECT COUNT(*) AS n FROM abonos WHERE pedido_id=? AND status='Validado'", (int(pid),), fetch=True)[0]["n"]
            if abonos_validados:
                st.warning("Este pedido tiene abonos validados. El sistema no permitirá que el nuevo total quede por debajo de lo abonado.")

            items = json.loads(p["items"] or "{}")
            items_edit = {}
            with st.form(f"form_editar_pedido_{pid}"):
                st.caption("Puedes quitar líneas o ajustar cantidades. Al guardar se recalculan totales y crédito asociado si aplica.")
                for k, item in items.items():
                    st.markdown(f"**{item.get('desc','Item')}**")
                    c_qty, c_keep = st.columns([1, 1])
                    qty = c_qty.number_input(
                        f"Cantidad ({presentacion_display_item(item)})",
                        min_value=0,
                        max_value=9999,
                        value=int(item.get("cantidad_presentacion", 1)),
                        step=1,
                        key=f"edit_qty_{pid}_{k}"
                    )
                    keep = c_keep.checkbox("Mantener item", value=True, key=f"edit_keep_{pid}_{k}")
                    nuevo_item = dict(item)
                    nuevo_item["cantidad_presentacion"] = int(qty)
                    if keep and int(qty) > 0:
                        items_edit[k] = nuevo_item

                cenv, cmet = st.columns(2)
                tasa_envio_edit = float(p["tasa_proveedor"] or get_tasa_proveedor() or 0)
                envio_bs_actual = float(p["envio_usd"] or 0) * tasa_envio_edit
                envio_bs_edit = cenv.number_input(
                    "Envío Bs",
                    min_value=0.0,
                    value=float(envio_bs_actual or 0),
                    step=100.0,
                    help="Editable. Se convierte internamente a USD equivalente para recalcular el pedido."
                )
                envio_edit = (float(envio_bs_edit or 0) / tasa_envio_edit) if tasa_envio_edit > 0 else 0.0
                cenv.caption(f"Equiv. interno: {money_usd(envio_edit)} · Tasa pedido: {tasa_envio_edit:,.2f}")
                metodo_edit = cmet.selectbox(
                    "Método de pago",
                    ["Por confirmar", "Divisas", "Transferencia", "Pago móvil", "Zelle", "Zinli", "Binance", "Otro"],
                    index=(["Por confirmar", "Divisas", "Transferencia", "Pago móvil", "Zelle", "Zinli", "Binance", "Otro"].index(p["metodo_pago"]) if p["metodo_pago"] in ["Por confirmar", "Divisas", "Transferencia", "Pago móvil", "Zelle", "Zinli", "Binance", "Otro"] else 0)
                )
                notas_edit = st.text_area("Notas", value=p["notas"] or "")
                submit_edit = st.form_submit_button("💾 Guardar cambios y recalcular", type="primary")

            if submit_edit:
                ok, msg = recalcular_pedido_y_credito(int(pid), items_edit, envio_edit, metodo_pago=metodo_edit, notas=notas_edit)
                st.success(msg) if ok else st.error(msg)
                if ok:
                    st.rerun()


def metodo_pago_label(mp):
    if not mp:
        return "Sin método"
    return f"{mp['nombre']} ({mp['tipo']})"

def metodo_pago_detalle_texto(mp):
    if not mp:
        return ""
    tipo = str(mp["tipo"] or "")
    partes = [f"Método: {mp['nombre']}"]
    if tipo:
        partes.append(f"Tipo: {tipo}")

    if tipo == "Pago móvil":
        for campo, etiqueta in [
            ("banco", "Banco"),
            ("cedula_rif", "Cédula/RIF"),
            ("telefono", "Teléfono"),
            ("titular", "Nombre titular"),
        ]:
            val = mp[campo] if campo in mp.keys() else None
            if val:
                partes.append(f"{etiqueta}: {val}")
    else:
        for campo, etiqueta in [
            ("banco", "Banco"),
            ("titular", "Titular"),
            ("cuenta", "Cuenta"),
            ("cedula_rif", "Cédula/RIF"),
            ("tipo_cuenta", "Tipo de cuenta"),
            ("telefono", "Teléfono"),
            ("correo", "Correo"),
            ("apodo", "Apodo"),
        ]:
            try:
                val = mp[campo]
            except Exception:
                val = None
            if val:
                partes.append(f"{etiqueta}: {val}")

    if mp["notas"]:
        partes.append(f"Notas: {mp['notas']}")
    return "\n".join(partes)


def metodos_pago_activos():
    return q("SELECT * FROM metodos_pago WHERE activo=1 ORDER BY tipo,nombre", fetch=True)

def render_metodo_pago_card(mp):
    if not mp:
        st.info("No hay método de pago seleccionado.")
        return
    st.markdown("#### Datos de pago")
    st.code(metodo_pago_detalle_texto(mp), language="text")

def render_instruccion_comprobante(mp):
    if not mp:
        return
    tipo = str(mp["tipo"] or "")
    if tipo in ["Pago móvil", "Cuenta bancaria Venezuela"]:
        st.caption("Para Pago Móvil / transferencia: coloca la referencia. Si el cliente desea enviar captura, puede mandarla por WhatsApp al 04126901346 y esperar validación del admin.")
    elif tipo in ["Zelle", "Binance", "Banesco Panamá"]:
        st.caption("Para Zelle, Binance o Banesco Panamá es recomendable cargar la captura/comprobante en la web para respaldar mejor la validación.")
    else:
        st.caption("Coloca la referencia o nota del pago para que el admin pueda validarlo.")


def admin_metodos_pago():
    st.title("🏦 Métodos de pago")
    st.caption("Carga aquí los datos bancarios y métodos que verán los clientes al notificar pagos o abonos.")

    tipos = ["Cuenta bancaria Venezuela", "Pago móvil", "Binance", "Banesco Panamá", "Zelle", "Efectivo", "Otro"]

    def valor_mp(mp, campo, default=""):
        try:
            v = mp[campo] if mp and campo in mp.keys() and mp[campo] is not None else default
            return v
        except Exception:
            return default

    def campos_metodo_pago(tipo, prefix, mp=None):
        banco = titular = cuenta = cedula_rif = tipo_cuenta = telefono = correo = apodo = ""

        if tipo == "Cuenta bancaria Venezuela":
            c1, c2 = st.columns(2)
            banco = c1.text_input("Banco", value=valor_mp(mp, "banco"), key=f"{prefix}_banco")
            titular = c2.text_input("Nombre titular", value=valor_mp(mp, "titular"), key=f"{prefix}_titular")
            c3, c4, c5 = st.columns(3)
            cuenta = c3.text_input("Número de cuenta", value=valor_mp(mp, "cuenta"), key=f"{prefix}_cuenta")
            cedula_rif = c4.text_input("Cédula/RIF titular", value=valor_mp(mp, "cedula_rif"), key=f"{prefix}_cedula")
            tipo_cuenta = c5.text_input("Tipo de cuenta", value=valor_mp(mp, "tipo_cuenta", "Corriente"), key=f"{prefix}_tipo_cuenta")

        elif tipo == "Pago móvil":
            st.info("Pago móvil usa Banco, Cédula/RIF, Teléfono y Nombre titular. No usa número de cuenta.")
            c1, c2 = st.columns(2)
            banco = c1.text_input("Banco", value=valor_mp(mp, "banco"), key=f"{prefix}_banco")
            titular = c2.text_input("Nombre titular", value=valor_mp(mp, "titular"), key=f"{prefix}_titular")
            c3, c4 = st.columns(2)
            cedula_rif = c3.text_input("Cédula/RIF", value=valor_mp(mp, "cedula_rif"), key=f"{prefix}_cedula")
            telefono = c4.text_input("Teléfono", value=valor_mp(mp, "telefono"), key=f"{prefix}_telefono")

        elif tipo == "Binance":
            c1, c2, c3 = st.columns(3)
            correo = c1.text_input("Correo Binance", value=valor_mp(mp, "correo"), key=f"{prefix}_correo")
            apodo = c2.text_input("Apodo / Pay ID", value=valor_mp(mp, "apodo"), key=f"{prefix}_apodo")
            titular = c3.text_input("Nombre titular", value=valor_mp(mp, "titular"), key=f"{prefix}_titular")

        elif tipo == "Banesco Panamá":
            c1, c2, c3 = st.columns(3)
            titular = c1.text_input("Titular", value=valor_mp(mp, "titular"), key=f"{prefix}_titular")
            cuenta = c2.text_input("Número de cuenta", value=valor_mp(mp, "cuenta"), key=f"{prefix}_cuenta")
            tipo_cuenta = c3.text_input("Tipo de cuenta", value=valor_mp(mp, "tipo_cuenta"), key=f"{prefix}_tipo_cuenta")

        elif tipo == "Zelle":
            c1, c2 = st.columns(2)
            titular = c1.text_input("Nombre titular", value=valor_mp(mp, "titular"), key=f"{prefix}_titular")
            correo = c2.text_input("Correo Zelle", value=valor_mp(mp, "correo"), key=f"{prefix}_correo")

        elif tipo == "Efectivo":
            titular = st.text_input("Responsable / titular", value=valor_mp(mp, "titular"), key=f"{prefix}_titular")

        else:
            c1, c2 = st.columns(2)
            titular = c1.text_input("Titular / responsable", value=valor_mp(mp, "titular"), key=f"{prefix}_titular")
            correo = c2.text_input("Correo / referencia", value=valor_mp(mp, "correo"), key=f"{prefix}_correo")

        return {
            "banco": banco,
            "titular": titular,
            "cuenta": cuenta,
            "cedula_rif": cedula_rif,
            "tipo_cuenta": tipo_cuenta,
            "telefono": telefono,
            "correo": correo,
            "apodo": apodo,
        }

    tab_list, tab_create, tab_edit = st.tabs(["Listado", "Crear nuevo", "Editar / eliminar"])

    with tab_list:
        df = pd.read_sql_query("SELECT id,nombre,tipo,banco,titular,cuenta,cedula_rif,tipo_cuenta,telefono,correo,apodo,activo,notas FROM metodos_pago ORDER BY activo DESC,tipo,nombre", get_conn())
        if df.empty:
            st.info("Aún no tienes métodos de pago cargados.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab_create:
        st.subheader("Agregar método nuevo")
        st.caption("Esta pantalla siempre crea un método nuevo. No sobrescribe métodos existentes.")

        tipo_nuevo = st.selectbox("Tipo de método", tipos, key="mp_create_tipo")
        nombre_nuevo = st.text_input("Nombre visible", placeholder="Ej: BNC Jurídica COLOR INSUMOS", key="mp_create_nombre")
        campos = campos_metodo_pago(tipo_nuevo, "mp_create")
        notas_nuevo = st.text_area("Notas internas / instrucciones", key="mp_create_notas")
        activo_nuevo = st.checkbox("Método activo", value=True, key="mp_create_activo")

        if st.button("➕ Crear método de pago", type="primary", use_container_width=True, key="mp_create_btn"):
            if not nombre_nuevo.strip():
                st.error("El nombre visible es obligatorio.")
            else:
                q("""INSERT INTO metodos_pago
                     (nombre,tipo,banco,titular,cuenta,cedula_rif,tipo_cuenta,telefono,correo,apodo,activo,notas,creado_en,actualizado_en)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (nombre_nuevo.strip(), tipo_nuevo, campos["banco"], campos["titular"], campos["cuenta"],
                   campos["cedula_rif"], campos["tipo_cuenta"], campos["telefono"], campos["correo"], campos["apodo"],
                   1 if activo_nuevo else 0, notas_nuevo, now(), now()))
                st.success("Método creado correctamente.")
                st.rerun()

    with tab_edit:
        st.subheader("Editar método existente")
        metodos = q("SELECT * FROM metodos_pago ORDER BY activo DESC,tipo,nombre", fetch=True)
        if not metodos:
            st.info("No hay métodos para editar.")
        else:
            opts = {f"#{m['id']} · {m['nombre']} ({m['tipo']})": m for m in metodos}
            sel = st.selectbox("Selecciona método a editar", list(opts.keys()), key="mp_edit_select")
            edit = opts[sel]
            edit_id = int(edit["id"])

            tipo_edit_actual = edit["tipo"] if edit["tipo"] in tipos else tipos[0]
            tipo_edit = st.selectbox("Tipo de método", tipos, index=tipos.index(tipo_edit_actual), key=f"mp_edit_tipo_{edit_id}")
            nombre_edit = st.text_input("Nombre visible", value=edit["nombre"] or "", key=f"mp_edit_nombre_{edit_id}")
            campos_edit = campos_metodo_pago(tipo_edit, f"mp_edit_{edit_id}", edit)
            notas_edit = st.text_area("Notas internas / instrucciones", value=edit["notas"] or "", key=f"mp_edit_notas_{edit_id}")
            activo_edit = st.checkbox("Método activo", value=bool(edit["activo"]), key=f"mp_edit_activo_{edit_id}")

            c1, c2 = st.columns(2)
            if c1.button("💾 Guardar cambios", type="primary", use_container_width=True, key=f"mp_edit_save_{edit_id}"):
                if not nombre_edit.strip():
                    st.error("El nombre visible es obligatorio.")
                else:
                    q("""UPDATE metodos_pago
                         SET nombre=?,tipo=?,banco=?,titular=?,cuenta=?,cedula_rif=?,tipo_cuenta=?,telefono=?,correo=?,apodo=?,activo=?,notas=?,actualizado_en=?
                         WHERE id=?""",
                      (nombre_edit.strip(), tipo_edit, campos_edit["banco"], campos_edit["titular"], campos_edit["cuenta"],
                       campos_edit["cedula_rif"], campos_edit["tipo_cuenta"], campos_edit["telefono"], campos_edit["correo"],
                       campos_edit["apodo"], 1 if activo_edit else 0, notas_edit, now(), edit_id))
                    st.success("Método actualizado correctamente.")
                    st.rerun()

            confirmar = st.checkbox("Confirmar eliminación definitiva", key=f"mp_edit_confirm_delete_{edit_id}")
            if c2.button("🗑️ Eliminar método", disabled=not confirmar, use_container_width=True, key=f"mp_edit_delete_{edit_id}"):
                q("DELETE FROM metodos_pago WHERE id=?", (edit_id,))
                st.warning("Método eliminado.")
                st.rerun()




def monto_input_seguro(valor, minimo=0.01):
    try:
        valor = float(valor or 0)
    except Exception:
        valor = 0.0
    if valor < minimo:
        return None
    return round(valor, 2)

def mis_creditos():
    st.title("💳 Mis créditos")
    user = get_user(st.session_state.user["username"])
    visibles = usuarios_visibles_para(user)
    placeholders = ",".join(["?"]*len(visibles))
    df = pd.read_sql_query(f"SELECT * FROM creditos WHERE username IN ({placeholders}) ORDER BY id DESC", get_conn(), params=visibles)
    tasa_bcv = get_tasa_bcv()
    tasa_prov = get_tasa_proveedor()

    if df.empty:
        st.info("Sin créditos registrados.")
    else:
        filas = []
        for _, cr in df.iterrows():
            tipo = str(cr.get("tipo_credito") or "usd").lower()
            saldo = float(cr.get("saldo_bcv") or cr.get("saldo_usd") or 0) if tipo == "bcv" else float(cr.get("saldo_usd") or 0)
            monto = float(cr.get("monto_bcv") or cr.get("monto_usd") or 0) if tipo == "bcv" else float(cr.get("monto_usd") or 0)
            bs_hoy = saldo * (tasa_bcv if tipo == "bcv" else tasa_prov)
            filas.append({
                "id": int(cr["id"]),
                "pedido_id": int(cr["pedido_id"]),
                "cliente_nombre": cr["cliente_nombre"],
                "tipo": "BCV" if tipo == "bcv" else "Divisas",
                "monto": f"{money_usd(monto)} BCV" if tipo == "bcv" else money_usd(monto),
                "saldo": f"{money_usd(saldo)} BCV" if tipo == "bcv" else money_usd(saldo),
                "Bs a pagar hoy": money_bs(bs_hoy),
                "status": cr["status"]
            })
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

    if user["rol"] != "admin":
        creditos_pend = q("SELECT * FROM creditos WHERE username=? AND COALESCE(saldo_usd,0)>0 ORDER BY id DESC", (user["username"],), fetch=True)
    else:
        creditos_pend = q("SELECT * FROM creditos WHERE COALESCE(saldo_usd,0)>0 ORDER BY id DESC", fetch=True)

    if creditos_pend:
        st.subheader("Cargar pago / abono")
        st.caption("El cálculo se actualiza al cambiar/confirmar el monto. El abono solo se registra al presionar el botón final.")

        def opt_label(c):
            tipo = str(c["tipo_credito"] if "tipo_credito" in c.keys() and c["tipo_credito"] else "usd").lower()
            saldo_txt = f"{money_usd(c['saldo_bcv'] or c['saldo_usd'])} BCV" if tipo == "bcv" else money_usd(c["saldo_usd"])
            return f"Crédito #{c['id']} - {c['cliente_nombre']} - saldo {saldo_txt}"

        opts = {opt_label(c): c for c in creditos_pend}
        sel = st.selectbox("Crédito", list(opts.keys()), key="mis_creditos_credito_sel")
        cr = opts[sel]
        tipo = str(cr["tipo_credito"] if "tipo_credito" in cr.keys() and cr["tipo_credito"] else "usd").lower()

        metodos = metodos_pago_activos()
        metodo_opts = {metodo_pago_label(m): m for m in metodos}
        if not metodo_opts:
            st.warning("No hay métodos de pago activos. El admin debe cargarlos en Métodos de pago. Puedes notificar igualmente usando 'Por confirmar'.")
            metodo_opts = {"Por confirmar": None}

        metodo_key = f"metodo_pago_credito_{tipo}_{cr['id']}"
        metodo_sel = st.selectbox("Método de pago", list(metodo_opts.keys()), key=metodo_key)
        mp = metodo_opts[metodo_sel]
        if mp:
            render_metodo_pago_card(mp)
            render_instruccion_comprobante(mp)

        if tipo == "bcv":
            saldo_bcv = float(cr["saldo_bcv"] or cr["saldo_usd"] or 0)
            monto_bcv_default = monto_input_seguro(saldo_bcv, 0.01)

            if monto_bcv_default is None:
                st.warning(
                    f"Este crédito tiene un saldo residual muy bajo en $ BCV: {saldo_bcv:.6f}. "
                    "Como es menor a 0,01, no se puede cargar desde este campo."
                )
                monto_bcv = 0.0
                ref = st.text_input("Referencia", key=f"ref_abono_bcv_{cr['id']}", disabled=True)
                comp = st.file_uploader("Comprobante", type=["jpg","jpeg","png","webp","pdf"], key=f"comp_abono_bcv_{cr['id']}", disabled=True)
                notas = st.text_area("Notas", key=f"notas_abono_bcv_{cr['id']}", disabled=True)
                submit = False
            else:
                monto_bcv = st.number_input(
                    "Monto a pagar en $ BCV",
                    min_value=0.01,
                    max_value=max(0.01, round(float(saldo_bcv or 0), 2)),
                    value=min(10.0, monto_bcv_default),
                    step=0.01,
                    key=f"monto_abono_bcv_{cr['id']}"
                )
                tasa_actual = get_tasa_bcv()
                monto_bs = float(monto_bcv or 0) * tasa_actual
                st.info(
                    f"Tasa BCV del momento: {tasa_actual:,.2f}\n\n"
                    f"Debes transferir: {money_bs(monto_bs)}\n\n"
                    "Esta tasa quedará guardada en la notificación del pago."
                )
                ref = st.text_input("Referencia", key=f"ref_abono_bcv_{cr['id']}")
                comp = st.file_uploader("Comprobante", type=["jpg","jpeg","png","webp","pdf"], key=f"comp_abono_bcv_{cr['id']}")
                notas = st.text_area("Notas", key=f"notas_abono_bcv_{cr['id']}")
                submit = st.button("Enviar pago BCV para validar", type="primary", use_container_width=True, key=f"btn_abono_bcv_{cr['id']}")
        else:
            saldo_usd = float(cr["saldo_usd"] or 0)
            monto = st.number_input(
                "Monto USD que deseas abonar",
                min_value=0.01,
                max_value=max(0.01, round(float(saldo_usd or 0), 2)),
                value=min(10.0, max(0.01, round(float(saldo_usd or 0), 2))),
                step=0.01,
                key=f"monto_abono_usd_{cr['id']}"
            )
            tasa_actual = get_tasa_proveedor()
            monto_bs = float(monto or 0) * tasa_actual
            st.info(
                f"Crédito en divisas.\n\n"
                f"Monto a abonar: {money_usd(monto)}\n\n"
                f"Tasa proveedor del momento: {tasa_actual:,.2f}\n\n"
                f"Monto a transferir: {money_bs(monto_bs)}\n\n"
                "Esta tasa quedará guardada en la notificación del pago."
            )
            ref = st.text_input("Referencia", key=f"ref_abono_usd_{cr['id']}")
            comp = st.file_uploader("Comprobante", type=["jpg","jpeg","png","webp","pdf"], key=f"comp_abono_usd_{cr['id']}")
            notas = st.text_area("Notas", key=f"notas_abono_usd_{cr['id']}")
            submit = st.button("Enviar pago para validar", type="primary", use_container_width=True, key=f"btn_abono_usd_{cr['id']}")

        if submit:
            path = save_uploaded_file(comp, PAGOS_DIR, prefix=f"abono_credito_{cr['id']}")
            metodo_nombre = metodo_pago_label(mp) if mp else metodo_sel
            metodo_id = int(mp["id"]) if mp else 0
            if tipo == "bcv":
                tasa_actual = get_tasa_bcv()
                monto_bcv = float(monto_bcv)
                monto_bs = monto_bcv * tasa_actual
                q("""INSERT INTO abonos
                     (credito_id,pedido_id,username,fecha,monto_usd,monto_bs,metodo,referencia,comprobante_path,status,notas,
                      tipo_credito,monto_bcv,tasa_bcv,tasa_proveedor,monto_bs_esperado,metodo_pago_id)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (cr["id"], cr["pedido_id"], cr["username"], now(), monto_bcv, monto_bs, metodo_nombre, ref, path, "Pendiente de validar", notas,
                   "bcv", monto_bcv, tasa_actual, 0, monto_bs, metodo_id))
            else:
                tasa_actual = get_tasa_proveedor()
                monto = float(monto)
                monto_bs = monto * tasa_actual
                q("""INSERT INTO abonos
                     (credito_id,pedido_id,username,fecha,monto_usd,monto_bs,metodo,referencia,comprobante_path,status,notas,
                      tipo_credito,monto_bcv,tasa_bcv,tasa_proveedor,monto_bs_esperado,metodo_pago_id)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (cr["id"], cr["pedido_id"], cr["username"], now(), monto, monto_bs, metodo_nombre, ref, path, "Pendiente de validar", notas,
                   "usd", 0, get_tasa_bcv(), tasa_actual, monto_bs, metodo_id))
            st.session_state["_pago_credito_feedback_msg"] = "Pago notificado correctamente. Queda en proceso de verificación por el admin."
            st.rerun()

    st.markdown("---")
    mostrar_historial_pagos_cliente(user["username"], titulo="Histórico de abonos y pagos")

    msg_pago_local = st.session_state.pop("_pago_credito_feedback_msg", None)
    if msg_pago_local:
        st.markdown("---")
        st.success(msg_pago_local)
        st.info("Tu pago ya fue enviado para revisión. El admin debe verificarlo antes de actualizar el saldo.")
        try:
            st.toast(msg_pago_local, icon="✅")
        except Exception:
            pass

    if st.button("📄 Descargar estado de cuenta", use_container_width=True):
        pdf = generar_pdf_estado_cuenta(user["username"])
        st.download_button("⬇️ Estado de cuenta PDF", data=pdf, file_name=f"estado_cuenta_{user['username']}.pdf", mime="application/pdf", use_container_width=True)



def admin_tareas_counts():
    try:
        pagos = q("SELECT COUNT(*) AS n FROM abonos WHERE status='Pendiente de validar'", fetch=True)[0]["n"]
    except Exception:
        pagos = 0
    try:
        pedidos = q("""SELECT COUNT(*) AS n FROM pedidos
                       WHERE COALESCE(status,'') IN ('Pendiente','Pendiente de pago','Pendiente de pago/entrega','Pago por verificar','Pago por validar','Confirmado','Preparando','Listo para entregar','Crédito en curso')""", fetch=True)[0]["n"]
    except Exception:
        pedidos = 0
    try:
        pos = q("""SELECT COUNT(*) AS n FROM pedidos
                   WHERE COALESCE(pos_procesado,0)=0
                   AND COALESCE(status,'') NOT IN ('Cancelado','Anulado')""", fetch=True)[0]["n"]
    except Exception:
        pos = 0
    try:
        creditos = q("""SELECT COUNT(*) AS n FROM creditos
                        WHERE status NOT IN ('Pagado','Anulado')
                        AND (COALESCE(saldo_usd,0)>0 OR COALESCE(saldo_bcv,0)>0)""", fetch=True)[0]["n"]
    except Exception:
        creditos = 0
    return {"pagos": int(pagos or 0), "pedidos": int(pedidos or 0), "pos": int(pos or 0), "creditos": int(creditos or 0)}


def abono_resumen_label(ab):
    tipo = str(ab["tipo_credito"] if "tipo_credito" in ab.keys() and ab["tipo_credito"] else "usd").lower()
    monto_txt = f"{money_usd(ab['monto_bcv'] or ab['monto_usd'])} BCV" if tipo == "bcv" else money_usd(ab["monto_usd"])
    credito_id = int(ab["credito_id"] or 0)
    origen = f"Crédito #{credito_id}" if credito_id > 0 else f"Pago contado pedido #{int(ab['pedido_id'] or 0)}"
    return f"#{ab['id']} · {origen} · {ab['username']} · {monto_txt} · {ab['status']}"

def admin_gestionar_abono(abono_id, key_prefix="abono_admin"):
    rows = q("SELECT * FROM abonos WHERE id=?", (int(abono_id),), fetch=True)
    if not rows:
        st.error("Abono no encontrado.")
        return
    ab = rows[0]
    tipo_ab = str(ab["tipo_credito"] if "tipo_credito" in ab.keys() and ab["tipo_credito"] else "usd").lower()

    st.markdown(f"### Abono #{ab['id']}")
    cinfo1, cinfo2, cinfo3 = st.columns(3)
    credito_id_info = int(ab["credito_id"] or 0)
    if credito_id_info > 0:
        cinfo1.write(f"**Crédito:** #{credito_id_info}")
    else:
        cinfo1.write("**Origen:** Pago contado")
    cinfo2.write(f"**Pedido:** #{ab['pedido_id']}")
    cinfo3.write(f"**Estado:** {ab['status']}")
    st.caption(f"Cliente/usuario: {ab['username']} · Fecha: {ab['fecha']}")
    st.caption(f"Método: {ab['metodo'] or 'N/A'} · Referencia: {ab['referencia'] or 'N/A'}")

    if ab["comprobante_path"]:
        st.caption(f"Comprobante: {ab['comprobante_path']}")

    with st.expander("✏️ Editar datos del abono", expanded=False):
        if ab["status"] == "Validado":
            st.warning("Este abono ya fue validado. Para proteger la cuenta del cliente, no se editan abonos validados desde aquí.")
        else:
            if tipo_ab == "bcv":
                monto_bcv_edit = st.number_input("Monto $ BCV", min_value=0.0, value=float(ab["monto_bcv"] or ab["monto_usd"] or 0), step=0.01, key=f"{key_prefix}_monto_bcv_{abono_id}")
                tasa_bcv_edit = st.number_input("Tasa BCV usada", min_value=0.0, value=float(ab["tasa_bcv"] or get_tasa_bcv()), step=0.01, key=f"{key_prefix}_tasa_bcv_{abono_id}")
                monto_bs_calc = monto_bcv_edit * tasa_bcv_edit
                st.info(f"Bs esperado recalculado: {money_bs(monto_bs_calc)}")
                monto_usd_edit = monto_bcv_edit
                tasa_prov_edit = 0.0
                monto_bcv_final = monto_bcv_edit
            else:
                monto_usd_edit = st.number_input("Monto USD abonado", min_value=0.0, value=float(ab["monto_usd"] or 0), step=0.01, key=f"{key_prefix}_monto_usd_{abono_id}")
                tasa_prov_edit = st.number_input("Tasa proveedor usada", min_value=0.0, value=float(ab["tasa_proveedor"] if "tasa_proveedor" in ab.keys() and ab["tasa_proveedor"] else get_tasa_proveedor()), step=0.01, key=f"{key_prefix}_tasa_prov_{abono_id}")
                monto_bs_calc = monto_usd_edit * tasa_prov_edit
                st.info(f"Bs esperado recalculado: {money_bs(monto_bs_calc)}")
                tasa_bcv_edit = float(ab["tasa_bcv"] or get_tasa_bcv())
                monto_bcv_final = 0.0

            metodo_edit = st.text_input("Método", value=ab["metodo"] or "", key=f"{key_prefix}_metodo_{abono_id}")
            referencia_edit = st.text_input("Referencia", value=ab["referencia"] or "", key=f"{key_prefix}_referencia_{abono_id}")
            notas_edit = st.text_area("Notas", value=ab["notas"] or "", key=f"{key_prefix}_notas_{abono_id}")

            if st.button("💾 Guardar cambios del abono", type="primary", use_container_width=True, key=f"{key_prefix}_save_{abono_id}"):
                q("""UPDATE abonos
                     SET monto_usd=?, monto_bcv=?, tasa_bcv=?, tasa_proveedor=?, monto_bs=?, monto_bs_esperado=?,
                         metodo=?, referencia=?, notas=?
                     WHERE id=?""",
                  (float(monto_usd_edit), float(monto_bcv_final), float(tasa_bcv_edit), float(tasa_prov_edit),
                   float(monto_bs_calc), float(monto_bs_calc), metodo_edit, referencia_edit, notas_edit, int(abono_id)))
                st.success("Abono actualizado.")
                st.rerun()

    c1, c2, c3 = st.columns(3)
    if c1.button("✅ Validar / aprobar", type="primary", use_container_width=True, key=f"{key_prefix}_validar_{abono_id}"):
        ok, msg = aplicar_abono_validado(int(abono_id), st.session_state.user["username"])
        st.success(msg) if ok else st.warning(msg)
        st.rerun()

    if c2.button("❌ Rechazar", use_container_width=True, key=f"{key_prefix}_rechazar_{abono_id}"):
        if ab["status"] == "Validado":
            st.warning("No se puede rechazar un abono ya validado desde aquí.")
        else:
            q("UPDATE abonos SET status='Rechazado', validado_por=?, fecha_validacion=? WHERE id=?",
              (st.session_state.user["username"], now(), int(abono_id)))
            try:
                if int(ab["credito_id"] or 0) <= 0 and int(ab["pedido_id"] or 0) > 0:
                    otros = q("""SELECT COUNT(*) AS n FROM abonos
                                  WHERE pedido_id=? AND id<>?
                                  AND status IN ('Pendiente de validar','Validado')""",
                               (int(ab["pedido_id"]), int(abono_id)), fetch=True)[0]["n"]
                    if int(otros or 0) == 0:
                        q("UPDATE pedidos SET status='Pendiente de pago' WHERE id=? AND status IN ('Pago por verificar','Pago por validar')", (int(ab["pedido_id"]),))
            except Exception:
                pass
            st.warning("Abono rechazado.")
            st.rerun()

    confirmar_del = st.checkbox("Confirmar eliminación de este abono", key=f"{key_prefix}_confirm_delete_{abono_id}")
    if c3.button("🗑️ Eliminar", disabled=not confirmar_del, use_container_width=True, key=f"{key_prefix}_delete_{abono_id}"):
        if ab["status"] == "Validado":
            st.error("Por seguridad, no se elimina un abono validado desde aquí porque ya afectó el saldo del crédito.")
        else:
            pedido_id_del = int(ab["pedido_id"] or 0)
            credito_id_del = int(ab["credito_id"] or 0)
            q("DELETE FROM abonos WHERE id=?", (int(abono_id),))
            try:
                if credito_id_del <= 0 and pedido_id_del > 0:
                    otros = q("""SELECT COUNT(*) AS n FROM abonos
                                  WHERE pedido_id=?
                                  AND status IN ('Pendiente de validar','Validado')""",
                               (pedido_id_del,), fetch=True)[0]["n"]
                    if int(otros or 0) == 0:
                        q("UPDATE pedidos SET status='Pendiente de pago' WHERE id=? AND status IN ('Pago por verificar','Pago por validar')", (pedido_id_del,))
            except Exception:
                pass
            st.success("Abono eliminado.")
            st.rerun()

def admin_panel_pedido(pedido_id, key_prefix="pedido_admin"):
    rows = q("SELECT * FROM pedidos WHERE id=?", (int(pedido_id),), fetch=True)
    if not rows:
        st.error("Pedido no encontrado.")
        return
    p = rows[0]

    st.markdown(f"### Pedido #{p['id']}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", money_usd(p["total_usd"]))
    c2.metric("Cliente", str(p["cliente_nombre"])[:25])
    c3.metric("Estado", p["status"])
    c4.metric("POS", "Procesado" if int(p["pos_procesado"] or 0) else "Pendiente")

    st.caption(f"Fecha: {p['fecha']} · Usuario: {p['username']} · Pago: {p['tipo_pago']} · Método: {p['metodo_pago'] or 'N/A'}")
    if p["notas"]:
        st.info(p["notas"])

    items_df = pd.DataFrame(pedido_items_rows(p))
    if not items_df.empty:
        st.dataframe(items_df, use_container_width=True, hide_index=True,
                     column_config={"Subtotal USD": st.column_config.NumberColumn(format="$%.2f")})

    pdf = generar_pdf_pedido(int(pedido_id))
    packing_pdf = generar_pdf_packing_list_pedido(int(pedido_id))
    dp1, dp2 = st.columns(2)
    dp1.download_button("📄 Descargar PDF del pedido", data=pdf, file_name=f"pedido_{int(pedido_id):04d}.pdf",
                       mime="application/pdf", use_container_width=True, key=f"{key_prefix}_pdf_{pedido_id}")
    dp2.download_button("📦 Descargar Packing List", data=packing_pdf, file_name=f"packing_list_{int(pedido_id):04d}.pdf",
                       mime="application/pdf", use_container_width=True, key=f"{key_prefix}_packing_{pedido_id}")

    estados = ["Pendiente", "Pendiente de pago", "Pago por verificar", "Pago por validar", "Confirmado", "Preparando", "Listo para entregar",
               "Entregado", "Crédito en curso", "Finalizado / Pagado", "Cancelado", "Anulado"]

    st.markdown("#### Acciones del pedido")
    a1, a2 = st.columns(2)
    with a1:
        idx_estado = estados.index(p["status"]) if p["status"] in estados else 0
        nuevo_estado = st.selectbox("Cambiar estado", estados, index=idx_estado, key=f"{key_prefix}_estado_{pedido_id}")
        if st.button("💾 Guardar estado", use_container_width=True, key=f"{key_prefix}_guardar_estado_{pedido_id}"):
            if nuevo_estado in ["Cancelado", "Anulado"]:
                ok, msg = anular_credito_de_pedido(int(pedido_id), f"Pedido cambiado a {nuevo_estado} desde Centro admin")
                if ok:
                    q("UPDATE pedidos SET status=? WHERE id=?", (nuevo_estado, int(pedido_id)))
                st.success(msg) if ok else st.error(msg)
            elif nuevo_estado == "Finalizado / Pagado" and p["credito_id"]:
                ok, msg = marcar_credito_pagado(int(p["credito_id"]), st.session_state.user["username"])
                st.success(msg) if ok else st.error(msg)
            else:
                q("UPDATE pedidos SET status=? WHERE id=?", (nuevo_estado, int(pedido_id)))
                st.success("Estado actualizado.")
            st.rerun()

    with a2:
        if int(p["pos_procesado"] or 0) == 0:
            notas_pos = st.text_area("Notas POS", key=f"{key_prefix}_notas_pos_{pedido_id}")
            confirmar_pos = st.checkbox("Confirmar procesado en POS", key=f"{key_prefix}_confirm_pos_{pedido_id}")
            if st.button("✅ Marcar procesado en POS", disabled=not confirmar_pos, use_container_width=True, key=f"{key_prefix}_pos_{pedido_id}"):
                q("""UPDATE pedidos SET pos_procesado=1, pos_fecha=?, pos_usuario=?, pos_notas=? WHERE id=?""",
                  (now(), st.session_state.user["username"], notas_pos, int(pedido_id)))
                st.success("Pedido marcado como procesado en POS.")
                st.rerun()
        else:
            confirmar_reverso = st.checkbox("Confirmar reverso POS", key=f"{key_prefix}_confirm_reverso_pos_{pedido_id}")
            if st.button("↩️ Volver a pendiente POS", disabled=not confirmar_reverso, use_container_width=True, key=f"{key_prefix}_reverso_pos_{pedido_id}"):
                q("UPDATE pedidos SET pos_procesado=0, pos_fecha=NULL, pos_usuario=NULL, pos_notas=NULL WHERE id=?", (int(pedido_id),))
                st.warning("Pedido devuelto a pendiente POS.")
                st.rerun()

    st.markdown("#### Zona sensible")
    b1, b2 = st.columns(2)
    with b1:
        confirmar_cancelar = st.checkbox("Confirmar cancelación/anulación", key=f"{key_prefix}_confirm_cancel_{pedido_id}")
        estado_cancel = st.selectbox("Tipo de anulación", ["Cancelado", "Anulado"], key=f"{key_prefix}_cancel_tipo_{pedido_id}")
        if st.button("🚫 Cancelar / Anular pedido", disabled=not confirmar_cancelar, use_container_width=True, key=f"{key_prefix}_cancel_{pedido_id}"):
            ok, msg = anular_credito_de_pedido(int(pedido_id), f"Pedido {estado_cancel} desde Centro admin")
            if ok:
                q("UPDATE pedidos SET status=? WHERE id=?", (estado_cancel, int(pedido_id)))
            st.success(msg) if ok else st.error(msg)
            if ok:
                st.rerun()

    with b2:
        confirmar_eliminar = st.checkbox("Confirmar eliminación definitiva", key=f"{key_prefix}_confirm_del_{pedido_id}")
        if st.button("🗑️ Eliminar pedido", disabled=not confirmar_eliminar, use_container_width=True, key=f"{key_prefix}_del_{pedido_id}"):
            ok, msg = eliminar_pedido_seguro(int(pedido_id))
            st.success(msg) if ok else st.error(msg)
            if ok:
                st.rerun()


def admin_centro_tareas():
    st.title("🔔 Centro admin")
    st.caption("Resumen de eventos y tareas pendientes del sistema. POS es solo control interno y no cambia el estado comercial del pedido.")

    counts = admin_tareas_counts()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pagos por verificar", counts["pagos"])
    c2.metric("Pedidos por atender", counts["pedidos"])
    c3.metric("POS pendiente", counts["pos"])
    c4.metric("Créditos en curso", counts["creditos"])

    tab_alertas, tab1, tab2, tab_pos, tab3 = st.tabs(["Alertas inteligentes", "Pagos por verificar", "Pedidos por atender", "POS pendiente", "Créditos en curso"])

    with tab_alertas:
        alertas = alertas_inteligentes_admin()
        if not alertas:
            st.success("Sin alertas importantes por ahora.")
        else:
            st.warning(f"{len(alertas)} alerta(s) detectada(s).")
            st.dataframe(pd.DataFrame(alertas), use_container_width=True, hide_index=True)

    with tab1:
        abonos = q("SELECT * FROM abonos WHERE status='Pendiente de validar' ORDER BY id DESC", fetch=True)
        if not abonos:
            st.success("No hay pagos por verificar.")
        else:
            st.warning(f"Tienes {len(abonos)} pago(s) por verificar.")
            df = pd.DataFrame([dict(a) for a in abonos])
            cols = ["id","credito_id","pedido_id","username","fecha","tipo_credito","monto_usd","monto_bcv","tasa_proveedor","tasa_bcv","monto_bs_esperado","metodo","referencia","status"]
            st.dataframe(df[[c for c in cols if c in df.columns]], use_container_width=True, hide_index=True)
            opts = {abono_resumen_label(a): int(a["id"]) for a in abonos}
            sel = st.selectbox("Gestionar pago", list(opts.keys()), key="centro_admin_abono_sel")
            admin_gestionar_abono(opts[sel], key_prefix="centro_admin")

    with tab2:
        pedidos = pd.read_sql_query("""SELECT id,fecha,username,cliente_nombre,tipo_pago,metodo_pago,total_usd,status,pos_procesado
                                       FROM pedidos
                                       WHERE COALESCE(status,'') IN ('Pendiente','Pendiente de pago','Pendiente de pago/entrega','Pago por verificar','Pago por validar','Confirmado','Preparando','Listo para entregar','Crédito en curso')
                                       ORDER BY id DESC LIMIT 80""", get_conn())
        if pedidos.empty:
            st.success("No hay pedidos por atender.")
        else:
            pedidos = pedidos.copy()
            pedidos["estado_visual"] = pedidos["status"].apply(estado_visual)
            pedidos["pos_visual"] = pedidos["pos_procesado"].apply(pos_visual)
            st.dataframe(pedidos, use_container_width=True, hide_index=True,
                         column_config={"total_usd": st.column_config.NumberColumn(format="$%.2f")})
            opts_ped = {
                f"#{int(r['id'])} · {r['cliente_nombre']} · {money_usd(r['total_usd'])} · {r['status']}": int(r["id"])
                for _, r in pedidos.iterrows()
            }
            sel_ped = st.selectbox("Gestionar pedido", list(opts_ped.keys()), key="centro_admin_pedido_sel")
            admin_panel_pedido(opts_ped[sel_ped], key_prefix="centro_admin_pedido")

    with tab_pos:
        pedidos_pos = pd.read_sql_query("""SELECT id,fecha,username,cliente_nombre,tipo_pago,metodo_pago,total_usd,status,pos_procesado
                                           FROM pedidos
                                           WHERE COALESCE(pos_procesado,0)=0
                                           AND COALESCE(status,'') NOT IN ('Cancelado','Anulado')
                                           ORDER BY id DESC LIMIT 80""", get_conn())
        if pedidos_pos.empty:
            st.success("No hay pedidos pendientes por POS.")
        else:
            st.caption("Marcar POS no cambia el estado del pedido ni del crédito. Solo sirve como indicativo interno de Color Insumos.")
            pedidos_pos = pedidos_pos.copy()
            pedidos_pos["estado_visual"] = pedidos_pos["status"].apply(estado_visual)
            pedidos_pos["pos_visual"] = pedidos_pos["pos_procesado"].apply(pos_visual)
            st.dataframe(pedidos_pos, use_container_width=True, hide_index=True,
                         column_config={"total_usd": st.column_config.NumberColumn(format="$%.2f")})
            opts_pos = {
                f"#{int(r['id'])} · {r['cliente_nombre']} · {money_usd(r['total_usd'])} · Estado: {r['status']}": int(r["id"])
                for _, r in pedidos_pos.iterrows()
            }
            sel_pos = st.selectbox("Gestionar POS del pedido", list(opts_pos.keys()), key="centro_admin_pos_sel")
            admin_panel_pedido(opts_pos[sel_pos], key_prefix="centro_admin_pos")

    with tab3:
        creditos = pd.read_sql_query("""SELECT id,pedido_id,username,cliente_nombre,fecha_inicio,fecha_vencimiento,
                                               monto_usd,saldo_usd,tipo_credito,monto_bcv,saldo_bcv,status
                                        FROM creditos
                                        WHERE status NOT IN ('Pagado','Anulado')
                                        AND (COALESCE(saldo_usd,0)>0 OR COALESCE(saldo_bcv,0)>0)
                                        ORDER BY id DESC LIMIT 80""", get_conn())
        if creditos.empty:
            st.success("No hay créditos en curso.")
        else:
            st.dataframe(creditos, use_container_width=True, hide_index=True)



def validar_creditos():
    st.title("✅ Validar créditos / pagos")
    tab1, tab2 = st.tabs(["Créditos", "Abonos por validar"])

    with tab1:
        creditos = pd.read_sql_query("SELECT * FROM creditos ORDER BY id DESC", get_conn())
        if creditos.empty:
            st.info("No hay créditos.")
        else:
            for _, cr in creditos.iterrows():
                cid = int(cr["id"])
                tipo_cr_txt = "BCV" if str(cr.get("tipo_credito") or "usd").lower() == "bcv" else "Divisas"
                saldo_cr_txt = f"{money_usd(cr.get('saldo_bcv') or cr.get('saldo_usd') or 0)} BCV" if tipo_cr_txt == "BCV" else money_usd(cr["saldo_usd"])
                with st.expander(f"Crédito #{cid} | {cr['cliente_nombre']} | {tipo_cr_txt} | Saldo {saldo_cr_txt} | {cr['status']}"):
                    c1, c2, c3 = st.columns(3)
                    c1.write(f"Pedido: #{cr['pedido_id']}")
                    c2.write(f"Monto: {money_usd(cr.get('monto_bcv') or cr.get('monto_usd') or 0)} BCV" if tipo_cr_txt == "BCV" else f"Monto: {money_usd(cr['monto_usd'])}")
                    c3.write(f"Vence: {cr['fecha_vencimiento']}")
                    estados = ["En curso", "Parcial", "Pagado", "Vencido", "Anulado"]
                    idx = estados.index(cr["status"]) if cr["status"] in estados else 0
                    nuevo = st.selectbox("Estado crédito", estados, index=idx, key=f"estado_credito_{cid}")
                    if nuevo != cr["status"]:
                        if nuevo == "Pagado":
                            ok, msg = marcar_credito_pagado(cid, st.session_state.user["username"])
                            st.success(msg) if ok else st.error(msg)
                        elif nuevo == "Anulado":
                            q("UPDATE creditos SET saldo_usd=0,status='Anulado' WHERE id=?", (cid,))
                            q("UPDATE pedidos SET status='Cancelado' WHERE id=?", (int(cr["pedido_id"]),))
                            st.warning("Crédito anulado y pedido marcado como Cancelado.")
                        else:
                            q("UPDATE creditos SET status=? WHERE id=?", (nuevo, cid))
                            st.success("Estado del crédito actualizado.")
                        st.rerun()

                    ab = pd.read_sql_query("SELECT * FROM abonos WHERE credito_id=? ORDER BY id DESC", get_conn(), params=(cid,))
                    if not ab.empty:
                        cols_credito_ab = ["id","fecha","tipo_credito","monto_usd","monto_bcv","tasa_bcv","tasa_proveedor","monto_bs_esperado","monto_bs","metodo","referencia","status"]
                        cols_credito_ab = [c for c in cols_credito_ab if c in ab.columns]
                        st.dataframe(ab[cols_credito_ab], use_container_width=True, hide_index=True)
                        abonos_credito = q("SELECT * FROM abonos WHERE credito_id=? ORDER BY id DESC", (cid,), fetch=True)
                        opts_ab_credito = {abono_resumen_label(a): int(a["id"]) for a in abonos_credito}
                        sel_ab_credito = st.selectbox("Gestionar abono de este crédito", list(opts_ab_credito.keys()), key=f"gest_ab_credito_{cid}")
                        admin_gestionar_abono(opts_ab_credito[sel_ab_credito], key_prefix=f"credito_{cid}")
                    else:
                        st.info("Este crédito todavía no tiene abonos registrados.")

                    confirmar = st.checkbox("Confirmar eliminación de este crédito y sus abonos", key=f"confirm_del_credito_{cid}")
                    if st.button("🗑️ Eliminar crédito", key=f"del_credito_{cid}", disabled=not confirmar, use_container_width=True):
                        ok, msg = eliminar_credito_y_abonos(cid)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

    with tab2:
        df = pd.read_sql_query("SELECT * FROM abonos WHERE status='Pendiente de validar' ORDER BY id DESC", get_conn())
        if df.empty:
            st.success("No hay abonos pendientes.")
        else:
            cols_abonos = ["id","credito_id","pedido_id","username","fecha","tipo_credito","monto_usd","monto_bcv","tasa_bcv","tasa_proveedor","monto_bs_esperado","monto_bs","metodo","referencia","status"]
            cols_abonos = [c for c in cols_abonos if c in df.columns]
            st.dataframe(df[cols_abonos], use_container_width=True, hide_index=True)

            rows = q("SELECT * FROM abonos WHERE status='Pendiente de validar' ORDER BY id DESC", fetch=True)
            opts = {abono_resumen_label(a): int(a["id"]) for a in rows}
            sel = st.selectbox("Selecciona abono para gestionar", list(opts.keys()), key="validar_creditos_abono_sel")
            admin_gestionar_abono(opts[sel], key_prefix="validar_creditos")


def nomina_trabajadores_activos(incluir_inactivos=False):
    if incluir_inactivos:
        return q("SELECT * FROM nomina_trabajadores ORDER BY activo DESC, nombre", fetch=True)
    return q("SELECT * FROM nomina_trabajadores WHERE activo=1 ORDER BY nombre", fetch=True)

def nomina_trabajador_label(t):
    estado = "" if int(t["activo"] or 0) == 1 else " (inactivo)"
    return f"{t['nombre']} — {t['cargo'] or 'Sin cargo'} — {money_usd(t['salario_mensual_usd'])}{estado}"

def nomina_pago_movil_label(t):
    banco = ""
    titular = ""
    cedula = ""
    telefono_pm = ""
    try:
        banco = t["banco"] if "banco" in t.keys() and t["banco"] else ""
        titular = t["titular_pago"] if "titular_pago" in t.keys() and t["titular_pago"] else ""
        cedula = t["cedula_rif_pago"] if "cedula_rif_pago" in t.keys() and t["cedula_rif_pago"] else ""
        telefono_pm = t["telefono_pago_movil"] if "telefono_pago_movil" in t.keys() and t["telefono_pago_movil"] else ""
    except Exception:
        pass
    partes = []
    if banco:
        partes.append(f"Banco: {banco}")
    if titular:
        partes.append(f"Titular: {titular}")
    if cedula:
        partes.append(f"CI/RIF: {cedula}")
    if telefono_pm:
        partes.append(f"Tel: {telefono_pm}")
    return "Pago móvil" + (f" · {' · '.join(partes)}" if partes else "")

def render_nomina_pago_movil_card(t):
    st.markdown("##### Datos de pago móvil del trabajador")
    c1, c2 = st.columns(2)
    banco = t["banco"] if "banco" in t.keys() and t["banco"] else "No definido"
    titular = t["titular_pago"] if "titular_pago" in t.keys() and t["titular_pago"] else (t["nombre"] or "No definido")
    cedula = t["cedula_rif_pago"] if "cedula_rif_pago" in t.keys() and t["cedula_rif_pago"] else (t["cedula"] or "No definida")
    telpm = t["telefono_pago_movil"] if "telefono_pago_movil" in t.keys() and t["telefono_pago_movil"] else "No definido"
    c1.info(f"Banco: **{banco}**\n\nTitular: **{titular}**")
    c2.info(f"Cédula/RIF: **{cedula}**\n\nTeléfono pago móvil: **{telpm}**")

def nomina_anio_de_fecha(fecha_txt):
    try:
        return datetime.strptime(str(fecha_txt)[:10], "%d/%m/%Y").year
    except Exception:
        return datetime.now().year

def nomina_utilidades_pagadas(trabajador_id, anio=None):
    anio = int(anio or datetime.now().year)
    rows = q("SELECT fecha, utilidad_usd FROM nomina_pagos WHERE trabajador_id=?", (int(trabajador_id),), fetch=True)
    total = 0.0
    for r in rows:
        if nomina_anio_de_fecha(r["fecha"]) == anio:
            total += float(r["utilidad_usd"] or 0)
    return total

def nomina_adelantos_pendientes(trabajador_id):
    row = q("SELECT COALESCE(SUM(saldo_usd),0) AS s FROM nomina_adelantos WHERE trabajador_id=? AND estado='Pendiente'", (int(trabajador_id),), fetch=True)
    return float(row[0]["s"] or 0) if row else 0.0

def nomina_aplicar_descuento_adelantos(trabajador_id, monto_usd, pago_id):
    restante = float(monto_usd or 0)
    if restante <= 0:
        return 0.0
    rows = q("""SELECT * FROM nomina_adelantos
                WHERE trabajador_id=? AND estado='Pendiente' AND COALESCE(saldo_usd,0)>0
                ORDER BY id ASC""", (int(trabajador_id),), fetch=True)
    aplicado = 0.0
    for ad in rows:
        if restante <= 0:
            break
        saldo = float(ad["saldo_usd"] or 0)
        desc = min(saldo, restante)
        nuevo_saldo = round(saldo - desc, 4)
        nuevo_estado = "Descontado" if nuevo_saldo <= 0.0001 else "Pendiente"
        q("UPDATE nomina_adelantos SET saldo_usd=?, estado=?, pago_id=? WHERE id=?",
          (max(0.0, nuevo_saldo), nuevo_estado, int(pago_id), int(ad["id"])))
        aplicado += desc
        restante -= desc
    return aplicado

def generar_pdf_nomina_pago(pago_id):
    rows = q("""SELECT p.*, t.nombre, t.cedula, t.cargo, t.salario_mensual_usd,
                       t.banco, t.titular_pago, t.cedula_rif_pago, t.telefono_pago_movil
                FROM nomina_pagos p
                LEFT JOIN nomina_trabajadores t ON t.id=p.trabajador_id
                WHERE p.id=?""", (int(pago_id),), fetch=True)
    if not rows:
        return b""
    p = rows[0]
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 8, pdf_clean(get_config("nombre_empresa", "Sistema de Insumos al Mayor")), ln=1, align="C")
    pdf.set_font("Arial", "", 9)
    pdf.cell(190, 5, pdf_clean("RECIBO DE PAGO DE NOMINA / CONTROL INTERNO"), ln=1, align="C")
    pdf.ln(4)

    pdf.set_font("Arial", "B", 13)
    pdf.cell(190, 8, pdf_clean(f"RECIBO NOMINA #{int(p['id'])}"), ln=1)
    pdf.set_font("Arial", "", 9)
    pdf.cell(95, 6, pdf_clean(f"Fecha: {p['fecha']}"), ln=0)
    pdf.cell(95, 6, pdf_clean(f"Periodo: {p['periodo']}"), ln=1)
    pdf.cell(95, 6, pdf_clean(f"Trabajador: {p['nombre'] or ''}"), ln=0)
    pdf.cell(95, 6, pdf_clean(f"CI: {p['cedula'] or 'N/A'}"), ln=1)
    pdf.cell(95, 6, pdf_clean(f"Cargo: {p['cargo'] or 'N/A'}"), ln=0)
    pdf.cell(95, 6, pdf_clean(f"Salario mensual ref.: {money_usd(p['salario_mensual_usd'] or 0)}"), ln=1)
    pdf.ln(4)

    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(130, 7, pdf_clean("Concepto"), 1, 0, "C", True)
    pdf.cell(60, 7, pdf_clean("Monto USD"), 1, 1, "C", True)
    pdf.set_font("Arial", "", 9)
    conceptos = [
        ("Sueldo base del periodo", p["base_usd"]),
        ("Bono", p["bono_usd"]),
        ("Adelanto de utilidades", p["utilidad_usd"]),
        ("Descuento de adelantos", -float(p["descuento_adelanto_usd"] or 0)),
    ]
    for label, val in conceptos:
        pdf.cell(130, 7, pdf_clean(label), 1, 0, "L")
        pdf.cell(60, 7, money_usd(val), 1, 1, "R")

    pdf.set_font("Arial", "B", 10)
    pdf.cell(130, 8, pdf_clean("TOTAL NETO PAGADO"), 1, 0, "R")
    pdf.cell(60, 8, money_usd(p["total_usd"]), 1, 1, "R")

    pdf.set_font("Arial", "", 9)
    pdf.ln(3)
    pdf.cell(190, 6, pdf_clean(f"Tasa proveedor usada: {float(p['tasa_proveedor'] or 0):,.2f}"), ln=1)
    pdf.cell(190, 6, pdf_clean(f"Total pagado en Bs: {money_bs(p['total_bs'])}"), ln=1)
    pdf.cell(190, 6, pdf_clean(f"Metodo: {p['metodo_pago'] or 'N/A'} | Referencia: {p['referencia'] or 'N/A'}"), ln=1)
    if p["banco"] or p["titular_pago"] or p["cedula_rif_pago"] or p["telefono_pago_movil"]:
        pdf.multi_cell(190, 5, pdf_clean(
            f"Pago movil trabajador: Banco {p['banco'] or 'N/A'} | Titular {p['titular_pago'] or 'N/A'} | CI/RIF {p['cedula_rif_pago'] or 'N/A'} | Telefono {p['telefono_pago_movil'] or 'N/A'}"
        ))
    if p["notas"]:
        pdf.multi_cell(190, 5, pdf_clean(f"Notas: {p['notas']}"))

    pdf.ln(12)
    pdf.cell(90, 7, "____________________________", ln=0, align="C")
    pdf.cell(10, 7, "", ln=0)
    pdf.cell(90, 7, "____________________________", ln=1, align="C")
    pdf.cell(90, 6, pdf_clean("Firma trabajador"), ln=0, align="C")
    pdf.cell(10, 6, "", ln=0)
    pdf.cell(90, 6, pdf_clean("Firma admin"), ln=1, align="C")

    pdf.set_font("Arial", "I", 8)
    pdf.ln(4)
    pdf.multi_cell(190, 4, pdf_clean("Nota: recibo de control interno. Validar criterios laborales/fiscales definitivos con contador o asesor laboral."))
    pdf_force_latin1(pdf)
    out = pdf.output(dest="S")
    if isinstance(out, str):
        return out.encode("latin-1", "replace")
    return bytes(out)

# -----------------------------
# POS EXPERIMENTAL
# -----------------------------
def pos_cart_key():
    return "_pos_experimental_cart"

def pos_get_cart():
    return st.session_state.setdefault(pos_cart_key(), {})

def pos_set_cart(cart):
    st.session_state[pos_cart_key()] = cart

def pos_clear_cart():
    st.session_state[pos_cart_key()] = {}

def pos_cliente_selector():
    st.markdown("#### Cliente")
    modo = st.radio("Tipo de cliente", ["Mostrador", "Cliente registrado"], horizontal=True, key="pos_cliente_modo")
    if modo == "Mostrador":
        c1, c2, c3 = st.columns(3)
        nombre = c1.text_input("Nombre mostrador", value="Cliente mostrador", key="pos_mostrador_nombre")
        telefono = c2.text_input("Teléfono", key="pos_mostrador_tel")
        rif = c3.text_input("RIF/CI", key="pos_mostrador_rif")
        return {
            "username": "pos_mostrador",
            "nombre": nombre.strip() or "Cliente mostrador",
            "rif": rif.strip(),
            "telefono": telefono.strip(),
            "direccion": "",
            "cliente_especial": 0,
            "ml_envio": 0,
        }

    usuarios = q("SELECT * FROM usuarios WHERE activo=1 ORDER BY nombre, username", fetch=True)
    if not usuarios:
        st.warning("No hay clientes registrados activos. Se usará Cliente mostrador.")
        return {"username": "pos_mostrador", "nombre": "Cliente mostrador", "rif": "", "telefono": "", "direccion": "", "cliente_especial": 0, "ml_envio": 0}
    opts = {f"{u['nombre'] or u['username']} — {u['username']}": u for u in usuarios}
    sel = st.selectbox("Buscar/seleccionar cliente", list(opts.keys()), key="pos_cliente_reg")
    u = opts[sel]
    return {
        "username": u["username"],
        "nombre": u["nombre"] or u["username"],
        "rif": u["rif"] or "",
        "telefono": u["telefono"] or "",
        "direccion": u["direccion"] or "",
        "cliente_especial": u["cliente_especial"] if "cliente_especial" in u.keys() else 0,
        "ml_envio": u["ml_envio"] if "ml_envio" in u.keys() else 0,
    }

def pos_item_from_producto(prod, cliente, cantidad=1, presentacion="unidad"):
    prod_precio = producto_con_precio_para_usuario(prod, cliente)
    calc = calcular_precio_inteligente(prod_precio, presentacion, int(cantidad))
    return {
        "sku": prod["sku"],
        "desc": prod["descripcion"],
        "presentacion": presentacion,
        "escala_aplicada": calc["escala_aplicada"],
        "detalle_precio": calc.get("detalle_precio", calc["escala_aplicada"]),
        "presentacion_nombre": calc.get("presentacion_nombre", "Unidad"),
        "presentacion_label": calc.get("presentacion_label", "Unidad"),
        "cantidad_presentacion": int(cantidad),
        "equivalencia": int(calc["equivalencia"]),
        "unidades_base_total": int(calc["unidades_base_total"]),
        "precio_presentacion": float(calc["precio_presentacion"]),
        "precio_total": float(calc["precio_total"]),
        "peso_total_kg": float(prod["peso_unidad_kg"] or 0) * int(calc["unidades_base_total"]),
        "imagen_url": prod["wc_imagen_url"],
        "cliente_precio_username": cliente.get("username", "pos_mostrador"),
        "cliente_precio_nombre": cliente.get("nombre", "Cliente mostrador"),
        "precio_especial_aplicado": bool(prod_precio.get("_precio_especial_aplicado", False)),
    }

def pos_recalcular_cart(cliente):
    cart = pos_get_cart()
    nuevo = {}
    for k, item in cart.items():
        prod = get_producto_row(item.get("sku"))
        if not prod:
            continue
        pres = item.get("presentacion", "unidad")
        cant = int(item.get("cantidad_presentacion", 1) or 1)
        nuevo[k] = pos_item_from_producto(prod, cliente, cant, pres)
    pos_set_cart(nuevo)
    return nuevo

def pos_total_cart(cart):
    subtotal = sum(float(i.get("precio_total", 0) or 0) for i in cart.values())
    unidades = sum(int(i.get("unidades_base_total", 0) or 0) for i in cart.values())
    peso = sum(float(i.get("peso_total_kg", 0) or 0) for i in cart.values())
    return {"subtotal": subtotal, "total": subtotal, "unidades": unidades, "peso": peso, "total_bs": subtotal * get_tasa_proveedor()}

def pos_registrar_venta(cliente, cart, metodo_pago, pago_usd, pago_bs, notas):
    if not cart:
        return None, "Carrito POS vacío."

    # Validación local de stock para que sea rápido. Este POS es experimental.
    faltantes = []
    requeridos = {}
    for item in cart.values():
        sku = item.get("sku")
        requeridos[sku] = requeridos.get(sku, 0) + int(item.get("unidades_base_total", 0) or 0)
    for sku, req in requeridos.items():
        prod = get_producto_row(sku)
        if prod and int(prod["wc_stock"] or 0) < req:
            faltantes.append(f"{sku}: requiere {req}, stock local {int(prod['wc_stock'] or 0)}")
    if faltantes:
        return None, "Stock insuficiente:\n" + "\n".join(faltantes)

    t = pos_total_cart(cart)
    tasa = get_tasa_proveedor()
    tasa_bcv = get_tasa_bcv()
    token = f"POS-{datetime.now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}"
    total_bs = float(t["total"] or 0) * tasa
    pago_total_equiv_usd = float(pago_usd or 0) + (float(pago_bs or 0) / tasa if tasa > 0 else 0)
    estado = "Finalizado / Pagado" if pago_total_equiv_usd + 0.0001 >= float(t["total"] or 0) else "Pago parcial POS"

    notas_full = (
        f"POS Experimental. Pago USD: {money_usd(pago_usd)}. Pago Bs: {money_bs(pago_bs)}. "
        f"Equiv. pagado USD: {money_usd(pago_total_equiv_usd)}. "
        f"{notas or ''}"
    )

    q("""INSERT INTO pedidos
         (fecha, username, cliente_nombre, cliente_rif, cliente_telefono, cliente_direccion, items,
          tipo_pago, metodo_pago, subtotal_usd, envio_usd, total_usd, tasa_proveedor, tasa_bcv,
          total_bs_proveedor, peso_total_kg, status, notas, credito_tipo, total_bcv_credito, pedido_token,
          pos_procesado, pos_fecha, pos_usuario, pos_notas)
         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (now(), cliente.get("username","pos_mostrador"), cliente.get("nombre","Cliente mostrador"), cliente.get("rif",""), cliente.get("telefono",""), cliente.get("direccion",""),
       json.dumps(cart, ensure_ascii=False), "contado", metodo_pago, float(t["subtotal"] or 0), 0.0, float(t["total"] or 0), tasa, tasa_bcv,
       total_bs, float(t["peso"] or 0), estado, notas_full, "usd", 0, token,
       1, now(), st.session_state.user["username"], "Venta creada desde POS Experimental"))

    pedido_id = q("SELECT last_insert_rowid() AS id", fetch=True)[0]["id"]

    # Registrar pago contado pendiente/validado como trazabilidad simple si hubo monto.
    if float(pago_usd or 0) > 0 or float(pago_bs or 0) > 0:
        q("""INSERT INTO abonos
             (credito_id,pedido_id,username,fecha,monto_usd,monto_bs,metodo,referencia,comprobante_path,status,notas,
              tipo_credito,monto_bcv,tasa_bcv,tasa_proveedor,monto_bs_esperado,metodo_pago_id)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (0, int(pedido_id), cliente.get("username","pos_mostrador"), now(), float(pago_usd or 0), float(pago_bs or 0), metodo_pago,
           token, "", "Validado", "Pago registrado automáticamente desde POS Experimental.",
           "contado", 0, tasa_bcv, tasa, total_bs, 0))

    pos_clear_cart()
    return int(pedido_id), "Venta POS registrada."

def pos_experimental():
    st.title("🧪 POS Experimental")
    st.caption("Prueba tipo Open POS: venta directa rápida, carrito POS separado y pago multimoneda. No reemplaza el flujo normal.")

    user = get_user(st.session_state.user["username"])
    if user["rol"] != "admin":
        st.error("Este módulo experimental solo está disponible para admin.")
        return

    cliente = pos_cliente_selector()
    cart = pos_recalcular_cart(cliente)
    tasa = get_tasa_proveedor()

    left, right = st.columns([2.1, 1.1], vertical_alignment="top")

    with left:
        st.markdown("### Productos")
        cats = categorias_activas()
        cat_names = ["Todas"] + [c["nombre"] for c in cats]
        cat_ids = {"Todas": None}
        cat_ids.update({c["nombre"]: c["id"] for c in cats})

        f1, f2, f3 = st.columns([2, 1.2, 1])
        bus = f1.text_input("Buscar", placeholder="SKU o nombre...", key="pos_bus_producto")
        cat_sel = f2.selectbox("Categoría", cat_names, key="pos_cat")
        limite = f3.number_input("Mostrar", min_value=8, max_value=80, value=24, step=8)

        sql = """SELECT p.*, c.nombre AS categoria
                 FROM productos p LEFT JOIN categorias c ON p.categoria_id=c.id
                 WHERE p.activo=1 AND COALESCE(p.wc_stock,0)>0"""
        params = []
        if cat_ids[cat_sel]:
            sql += " AND p.categoria_id=?"
            params.append(cat_ids[cat_sel])
        if bus:
            sql += " AND (p.sku LIKE ? OR p.descripcion LIKE ? OR COALESCE(p.atributo_medida,'') LIKE ? OR COALESCE(p.atributo_color,'') LIKE ?)"
            params.extend([f"%{bus}%", f"%{bus}%", f"%{bus}%", f"%{bus}%"])
        sql += " ORDER BY c.orden, p.descripcion LIMIT ?"
        params.append(int(limite))
        rows = q(sql, params, fetch=True)

        if not rows:
            st.info("No hay productos con stock para mostrar.")
        else:
            cols = st.columns(4)
            for i, prod in enumerate(rows):
                prodp = producto_con_precio_para_usuario(prod, cliente)
                with cols[i % 4]:
                    st.markdown("<div style='border:1px solid #e5e7eb;border-radius:12px;padding:8px;margin-bottom:8px;background:white;'>", unsafe_allow_html=True)
                    if prod["wc_imagen_url"]:
                        st.image(prod["wc_imagen_url"], width=95)
                    st.markdown(f"**{str(prod['descripcion'])[:42]}**")
                    st.caption(f"{prod['sku']} · Stock {int(prod['wc_stock'] or 0)}")
                    st.write(f"**{money_usd(prodp['precio_unidad'])}**")
                    if st.button("➕ Agregar", key=f"pos_add_{prod['sku']}", use_container_width=True):
                        cart = pos_get_cart()
                        key = f"{prod['sku']}::unidad"
                        cant = int(cart.get(key, {}).get("cantidad_presentacion", 0) or 0) + 1
                        cart[key] = pos_item_from_producto(prod, cliente, cant, "unidad")
                        pos_set_cart(cart)
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("### Carrito POS")
        cart = pos_get_cart()
        total = pos_total_cart(cart)

        if not cart:
            st.info("Agrega productos para iniciar una venta.")
        else:
            for key, item in list(cart.items()):
                st.markdown(f"**{item['desc']}**")
                st.caption(f"SKU {item['sku']} · {money_usd(item['precio_presentacion'])} c/u")
                c1, c2, c3 = st.columns([1, 1, 1])
                if c1.button("➖", key=f"pos_minus_{key}", use_container_width=True):
                    cant = int(item.get("cantidad_presentacion", 1) or 1) - 1
                    if cant <= 0:
                        cart.pop(key, None)
                    else:
                        prod = get_producto_row(item["sku"])
                        cart[key] = pos_item_from_producto(prod, cliente, cant, item.get("presentacion","unidad"))
                    pos_set_cart(cart)
                    st.rerun()
                c2.write(f"x {int(item.get('cantidad_presentacion',1))}")
                if c3.button("➕", key=f"pos_plus_{key}", use_container_width=True):
                    cant = int(item.get("cantidad_presentacion", 1) or 1) + 1
                    prod = get_producto_row(item["sku"])
                    cart[key] = pos_item_from_producto(prod, cliente, cant, item.get("presentacion","unidad"))
                    pos_set_cart(cart)
                    st.rerun()
                st.write(f"Subtotal: **{money_usd(item['precio_total'])}**")
                st.markdown("---")

            st.metric("Total USD", money_usd(total["total"]))
            st.metric("Total Bs", money_bs(total["total_bs"]))
            st.caption(f"Tasa proveedor: {tasa:,.2f}")

            st.markdown("### Pago multimoneda")
            p1, p2 = st.columns(2)
            pago_usd = p1.number_input("Pago USD", min_value=0.0, value=float(total["total"]), step=1.0, key="pos_pago_usd")
            pago_bs = p2.number_input("Pago Bs", min_value=0.0, value=0.0, step=100.0, key="pos_pago_bs")
            equiv = float(pago_usd or 0) + (float(pago_bs or 0) / tasa if tasa > 0 else 0)
            diferencia = equiv - float(total["total"] or 0)
            if diferencia >= 0:
                st.success(f"Pagado equivalente: {money_usd(equiv)} · Vuelto: {money_usd(diferencia)}")
            else:
                st.warning(f"Pagado equivalente: {money_usd(equiv)} · Falta: {money_usd(abs(diferencia))}")

            metodo = st.selectbox("Método", ["Efectivo USD", "Pago móvil", "Transferencia", "Zelle", "Mixto", "Otro"], key="pos_metodo")
            notas = st.text_area("Notas POS", key="pos_notas")

            cfin1, cfin2 = st.columns(2)
            if cfin1.button("✅ Finalizar venta POS", type="primary", use_container_width=True):
                pedido_id, msg = pos_registrar_venta(cliente, cart, metodo, pago_usd, pago_bs, notas)
                if pedido_id:
                    set_feedback(f"{msg} Pedido #{pedido_id}.", "success")
                    st.session_state["pos_ultimo_pedido"] = int(pedido_id)
                    st.rerun()
                else:
                    st.error(msg)
            if cfin2.button("🧹 Vaciar POS", use_container_width=True):
                pos_clear_cart()
                st.rerun()

    ultimo = st.session_state.get("pos_ultimo_pedido")
    if ultimo:
        st.markdown("---")
        st.success(f"Última venta POS registrada: Pedido #{ultimo}")
        pdf = generar_pdf_pedido(int(ultimo))
        st.download_button("📄 Descargar nota POS", data=pdf, file_name=f"pos_pedido_{int(ultimo):04d}.pdf", mime="application/pdf", use_container_width=True)



def nomina_admin():
    st.title("👥 Nómina")
    st.caption("Control interno de pagos, adelantos, bonos y utilidades adelantadas. No sustituye asesoría contable/laboral.")

    tab_resumen, tab_trab, tab_pago, tab_adel, tab_util, tab_hist = st.tabs([
        "Resumen", "Trabajadores", "Generar pago", "Adelantos", "Utilidades", "Histórico"
    ])

    with tab_resumen:
        trabajadores = nomina_trabajadores_activos()
        pagos_mes = pd.read_sql_query("SELECT * FROM nomina_pagos ORDER BY id DESC", get_conn())
        adelantos = pd.read_sql_query("SELECT * FROM nomina_adelantos ORDER BY id DESC", get_conn())

        mes_actual = datetime.now().month
        anio_actual = datetime.now().year
        total_mes = 0.0
        bonos_mes = 0.0
        util_mes = 0.0
        if not pagos_mes.empty:
            temp = pagos_mes.copy()
            temp["_anio"] = temp["fecha"].apply(nomina_anio_de_fecha)
            temp["_mes"] = temp["fecha"].astype(str).str.slice(3,5).apply(lambda x: int(x) if str(x).isdigit() else 0)
            temp_mes = temp[(temp["_anio"] == anio_actual) & (temp["_mes"] == mes_actual)]
            total_mes = float(temp_mes["total_usd"].fillna(0).sum()) if not temp_mes.empty else 0.0
            bonos_mes = float(temp_mes["bono_usd"].fillna(0).sum()) if not temp_mes.empty else 0.0
            util_mes = float(temp_mes["utilidad_usd"].fillna(0).sum()) if not temp_mes.empty else 0.0

        adel_pend = float(adelantos[adelantos["estado"]=="Pendiente"]["saldo_usd"].sum()) if not adelantos.empty else 0.0
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Trabajadores activos", len(trabajadores))
        c2.metric("Pagado este mes", money_usd(total_mes))
        c3.metric("Bonos este mes", money_usd(bonos_mes))
        c4.metric("Adelantos pendientes", money_usd(adel_pend))

        st.markdown("#### Resumen de utilidades del año")
        data_util = []
        dias_util = parse_float(get_config("nomina_dias_utilidades", "30"), 30)
        for t in trabajadores:
            estimado = float(t["salario_mensual_usd"] or 0) / 30 * dias_util
            pagado = nomina_utilidades_pagadas(t["id"], anio_actual)
            data_util.append({
                "Trabajador": t["nombre"],
                "Salario mensual": money_usd(t["salario_mensual_usd"]),
                "Utilidades estimadas": money_usd(estimado),
                "Adelantado": money_usd(pagado),
                "Pendiente": money_usd(max(0, estimado - pagado)),
            })
        if data_util:
            st.dataframe(pd.DataFrame(data_util), use_container_width=True, hide_index=True)
        else:
            st.info("Crea trabajadores para ver el resumen.")

    with tab_trab:
        st.subheader("Trabajadores")
        rows = nomina_trabajadores_activos(incluir_inactivos=True)
        if rows:
            df = pd.DataFrame([dict(r) for r in rows])
            st.dataframe(df[["id","nombre","cedula","cargo","fecha_ingreso","salario_mensual_usd","activo","telefono","banco","titular_pago","cedula_rif_pago","telefono_pago_movil"]], use_container_width=True, hide_index=True,
                         column_config={"salario_mensual_usd": st.column_config.NumberColumn(format="$%.2f")})
        else:
            st.info("Todavía no hay trabajadores.")

        st.markdown("#### Crear / editar trabajador")
        opts = {"Crear nuevo": 0}
        for t in rows:
            opts[nomina_trabajador_label(t)] = int(t["id"])
        sel = st.selectbox("Seleccionar", list(opts.keys()), key="nomina_trab_sel")
        tid = opts[sel]
        trow = q("SELECT * FROM nomina_trabajadores WHERE id=?", (tid,), fetch=True)[0] if tid else None

        with st.form("form_nomina_trabajador"):
            c1, c2, c3 = st.columns(3)
            nombre = c1.text_input("Nombre", value=trow["nombre"] if trow else "")
            cedula = c2.text_input("Cédula", value=trow["cedula"] if trow else "")
            cargo = c3.text_input("Cargo", value=trow["cargo"] if trow else "")

            c4, c5, c6 = st.columns(3)
            fecha_ingreso = c4.text_input("Fecha ingreso", value=trow["fecha_ingreso"] if trow else datetime.now().strftime("%d/%m/%Y"))
            salario = c5.number_input("Salario mensual USD", min_value=0.0, value=float(trow["salario_mensual_usd"] if trow else 250), step=5.0)
            activo = c6.checkbox("Activo", value=bool(trow["activo"]) if trow else True)

            st.markdown("#### Datos de pago móvil")
            c7, c8, c9 = st.columns(3)
            telefono = c7.text_input("Teléfono contacto", value=trow["telefono"] if trow and "telefono" in trow.keys() and trow["telefono"] else "")
            banco = c8.text_input("Banco", value=trow["banco"] if trow and "banco" in trow.keys() and trow["banco"] else "")
            titular_pago = c9.text_input("Titular", value=trow["titular_pago"] if trow and "titular_pago" in trow.keys() and trow["titular_pago"] else (trow["nombre"] if trow else ""))

            c10, c11, c12 = st.columns(3)
            cedula_rif_pago = c10.text_input("Cédula/RIF pago móvil", value=trow["cedula_rif_pago"] if trow and "cedula_rif_pago" in trow.keys() and trow["cedula_rif_pago"] else (trow["cedula"] if trow else ""))
            telefono_pago_movil = c11.text_input("Teléfono pago móvil", value=trow["telefono_pago_movil"] if trow and "telefono_pago_movil" in trow.keys() and trow["telefono_pago_movil"] else "")
            tipo_cuenta_pago = c12.text_input("Tipo cuenta / nota", value=trow["tipo_cuenta_pago"] if trow and "tipo_cuenta_pago" in trow.keys() and trow["tipo_cuenta_pago"] else "")

            metodo_pago = nomina_pago_movil_label({
                "banco": banco,
                "titular_pago": titular_pago,
                "cedula_rif_pago": cedula_rif_pago,
                "telefono_pago_movil": telefono_pago_movil,
                "nombre": nombre,
                "cedula": cedula,
            })
            st.caption(f"Método generado: {metodo_pago}")
            notas = st.text_area("Notas", value=trow["notas"] if trow and "notas" in trow.keys() and trow["notas"] else "")

            guardar = st.form_submit_button("💾 Guardar trabajador", type="primary")
        if guardar:
            if not nombre.strip():
                st.error("El nombre es obligatorio.")
            elif tid:
                q("""UPDATE nomina_trabajadores
                     SET nombre=?,cedula=?,cargo=?,fecha_ingreso=?,salario_mensual_usd=?,activo=?,telefono=?,metodo_pago=?,
                         banco=?,titular_pago=?,cedula_rif_pago=?,telefono_pago_movil=?,tipo_cuenta_pago=?,notas=?,actualizado_en=?
                     WHERE id=?""",
                  (nombre.strip(), cedula.strip(), cargo.strip(), fecha_ingreso.strip(), salario, 1 if activo else 0, telefono.strip(), metodo_pago.strip(),
                   banco.strip(), titular_pago.strip(), cedula_rif_pago.strip(), telefono_pago_movil.strip(), tipo_cuenta_pago.strip(), notas.strip(), now(), tid))
                st.success("Trabajador actualizado.")
                st.rerun()
            else:
                q("""INSERT INTO nomina_trabajadores
                     (nombre,cedula,cargo,fecha_ingreso,salario_mensual_usd,activo,telefono,metodo_pago,
                      banco,titular_pago,cedula_rif_pago,telefono_pago_movil,tipo_cuenta_pago,notas,creado_en,actualizado_en)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (nombre.strip(), cedula.strip(), cargo.strip(), fecha_ingreso.strip(), salario, 1 if activo else 0, telefono.strip(), metodo_pago.strip(),
                   banco.strip(), titular_pago.strip(), cedula_rif_pago.strip(), telefono_pago_movil.strip(), tipo_cuenta_pago.strip(), notas.strip(), now(), now()))
                st.success("Trabajador creado.")
                st.rerun()

    with tab_pago:
        st.subheader("Generar pago de nómina")
        trabajadores = nomina_trabajadores_activos()
        if not trabajadores:
            st.info("Primero crea al menos un trabajador.")
        else:
            opts = {nomina_trabajador_label(t): t for t in trabajadores}
            sel = st.selectbox("Trabajador", list(opts.keys()), key="nomina_pago_trab")
            t = opts[sel]

            c1, c2, c3 = st.columns(3)
            periodo_tipo = c1.selectbox("Período", ["1era quincena", "2da quincena", "Mensual", "Personalizado"], key="nomina_periodo")
            fecha_pago = c2.text_input("Fecha pago", value=now(), key="nomina_fecha_pago")
            tasa = c3.number_input("Tasa proveedor", min_value=0.0, value=get_tasa_proveedor(), step=0.01, key="nomina_tasa")

            salario_mensual = float(t["salario_mensual_usd"] or 0)
            if periodo_tipo in ["1era quincena", "2da quincena"]:
                base_default = salario_mensual / 2
            elif periodo_tipo == "Mensual":
                base_default = salario_mensual
            else:
                base_default = 0.0

            c4, c5, c6, c7 = st.columns(4)
            base_usd = c4.number_input("Base del período USD", min_value=0.0, value=float(base_default), step=5.0)
            bono_usd = c5.number_input("Bono USD", min_value=0.0, value=0.0, step=5.0, help="Bono simple de control interno. No afecta utilidades automáticamente.")
            utilidad_usd = c6.number_input("Adelanto utilidades USD", min_value=0.0, value=0.0, step=5.0)
            adelanto_pend = nomina_adelantos_pendientes(t["id"])
            descuento_usd = c7.number_input("Descontar adelantos USD", min_value=0.0, max_value=float(adelanto_pend), value=0.0, step=5.0, help=f"Pendiente actual: {money_usd(adelanto_pend)}")

            total_usd = float(base_usd or 0) + float(bono_usd or 0) + float(utilidad_usd or 0) - float(descuento_usd or 0)
            total_bs = total_usd * float(tasa or 0)

            st.markdown("#### Resumen antes de registrar")
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Base", money_usd(base_usd))
            r2.metric("Bono", money_usd(bono_usd))
            r3.metric("Utilidades adelantadas", money_usd(utilidad_usd))
            r4.metric("Total neto", money_usd(total_usd))
            st.info(f"Total en Bs a tasa proveedor {float(tasa or 0):,.2f}: {money_bs(total_bs)}")
            if descuento_usd > 0:
                st.warning(f"Se descontarán {money_usd(descuento_usd)} de adelantos pendientes.")

            render_nomina_pago_movil_card(t)
            metodo_default = nomina_pago_movil_label(t)
            c8, c9 = st.columns(2)
            metodo_pago = c8.text_input("Método de pago", value=metodo_default)
            referencia = c9.text_input("Referencia")
            notas = st.text_area("Notas del pago")

            if st.button("✅ Registrar pago de nómina", type="primary", use_container_width=True):
                if total_usd < 0:
                    st.error("El total no puede ser negativo.")
                else:
                    q("""INSERT INTO nomina_pagos
                         (trabajador_id,fecha,periodo,base_usd,bono_usd,utilidad_usd,descuento_adelanto_usd,total_usd,tasa_proveedor,total_bs,metodo_pago,referencia,notas,creado_por,creado_en)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (int(t["id"]), fecha_pago.strip(), periodo_tipo, base_usd, bono_usd, utilidad_usd, descuento_usd, total_usd, tasa, total_bs, metodo_pago.strip(), referencia.strip(), notas.strip(), st.session_state.user["username"], now()))
                    pago_id = q("SELECT last_insert_rowid() AS id", fetch=True)[0]["id"]
                    aplicado = nomina_aplicar_descuento_adelantos(t["id"], descuento_usd, pago_id)
                    st.success(f"Pago de nómina registrado. Adelantos descontados: {money_usd(aplicado)}")
                    pdf = generar_pdf_nomina_pago(pago_id)
                    st.download_button("📄 Descargar recibo PDF", data=pdf, file_name=f"recibo_nomina_{int(pago_id):04d}.pdf", mime="application/pdf", use_container_width=True)

    with tab_adel:
        st.subheader("Adelantos de sueldo")
        trabajadores = nomina_trabajadores_activos()
        if not trabajadores:
            st.info("Primero crea trabajadores.")
        else:
            opts = {nomina_trabajador_label(t): t for t in trabajadores}
            sel = st.selectbox("Trabajador", list(opts.keys()), key="nomina_adel_trab")
            t = opts[sel]
            c1, c2, c3 = st.columns(3)
            fecha = c1.text_input("Fecha", value=now(), key="nomina_adel_fecha")
            monto = c2.number_input("Monto adelanto USD", min_value=0.0, value=0.0, step=5.0)
            tasa = c3.number_input("Tasa proveedor", min_value=0.0, value=get_tasa_proveedor(), step=0.01, key="nomina_adel_tasa")
            motivo = st.text_area("Motivo / notas del adelanto")
            st.info(f"Monto en Bs: {money_bs(monto * tasa)}")
            if st.button("➕ Registrar adelanto", type="primary", use_container_width=True):
                if monto <= 0:
                    st.error("El monto debe ser mayor a 0.")
                else:
                    q("""INSERT INTO nomina_adelantos
                         (trabajador_id,fecha,monto_usd,tasa_proveedor,monto_bs,saldo_usd,estado,motivo,creado_en)
                         VALUES (?,?,?,?,?,?,?,?,?)""",
                      (int(t["id"]), fecha.strip(), monto, tasa, monto*tasa, monto, "Pendiente", motivo.strip(), now()))
                    st.success("Adelanto registrado.")
                    st.rerun()

        df_ad = pd.read_sql_query("""SELECT a.id,t.nombre,a.fecha,a.monto_usd,a.saldo_usd,a.estado,a.motivo
                                     FROM nomina_adelantos a
                                     LEFT JOIN nomina_trabajadores t ON t.id=a.trabajador_id
                                     ORDER BY a.id DESC""", get_conn())
        if not df_ad.empty:
            st.markdown("#### Histórico de adelantos")
            st.dataframe(df_ad, use_container_width=True, hide_index=True,
                         column_config={"monto_usd": st.column_config.NumberColumn(format="$%.2f"), "saldo_usd": st.column_config.NumberColumn(format="$%.2f")})

    with tab_util:
        st.subheader("Utilidades / adelantos de fin de año")
        dias_util = st.number_input("Días de utilidades estimadas", min_value=1, max_value=120, value=int(parse_float(get_config("nomina_dias_utilidades", "30"), 30)), step=1)
        if st.button("💾 Guardar días de utilidades", use_container_width=True):
            set_config("nomina_dias_utilidades", dias_util)
            st.success("Configuración guardada.")
            st.rerun()

        anio = st.number_input("Año", min_value=2020, max_value=2100, value=datetime.now().year, step=1)
        trabajadores = nomina_trabajadores_activos(incluir_inactivos=True)
        data = []
        for t in trabajadores:
            estimado = float(t["salario_mensual_usd"] or 0) / 30 * float(dias_util or 30)
            pagado = nomina_utilidades_pagadas(t["id"], int(anio))
            data.append({
                "Trabajador": t["nombre"],
                "Salario mensual": float(t["salario_mensual_usd"] or 0),
                "Utilidades estimadas": estimado,
                "Adelantado": pagado,
                "Saldo pendiente": max(0.0, estimado - pagado),
                "Activo": int(t["activo"] or 0),
            })
        if data:
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True,
                         column_config={
                             "Salario mensual": st.column_config.NumberColumn(format="$%.2f"),
                             "Utilidades estimadas": st.column_config.NumberColumn(format="$%.2f"),
                             "Adelantado": st.column_config.NumberColumn(format="$%.2f"),
                             "Saldo pendiente": st.column_config.NumberColumn(format="$%.2f"),
                         })
        else:
            st.info("No hay trabajadores registrados.")

    with tab_hist:
        st.subheader("Histórico de pagos")
        bus = st.text_input("Buscar histórico", placeholder="Trabajador, período, referencia...")
        sql = """SELECT p.id,p.fecha,t.nombre,p.periodo,p.base_usd,p.bono_usd,p.utilidad_usd,p.descuento_adelanto_usd,p.total_usd,p.tasa_proveedor,p.total_bs,p.metodo_pago,p.referencia,p.creado_por
                 FROM nomina_pagos p
                 LEFT JOIN nomina_trabajadores t ON t.id=p.trabajador_id
                 WHERE 1=1"""
        params = []
        if bus:
            sql += " AND (t.nombre LIKE ? OR p.periodo LIKE ? OR p.referencia LIKE ?)"
            params.extend([f"%{bus}%", f"%{bus}%", f"%{bus}%"])
        sql += " ORDER BY p.id DESC"
        df = pd.read_sql_query(sql, get_conn(), params=params)
        if df.empty:
            st.info("Sin pagos registrados.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True,
                         column_config={
                             "base_usd": st.column_config.NumberColumn(format="$%.2f"),
                             "bono_usd": st.column_config.NumberColumn(format="$%.2f"),
                             "utilidad_usd": st.column_config.NumberColumn(format="$%.2f"),
                             "descuento_adelanto_usd": st.column_config.NumberColumn(format="$%.2f"),
                             "total_usd": st.column_config.NumberColumn(format="$%.2f"),
                             "total_bs": st.column_config.NumberColumn(format="%.2f"),
                         })
            pagos = q("SELECT id FROM nomina_pagos ORDER BY id DESC LIMIT 100", fetch=True)
            if pagos:
                ids = [int(p["id"]) for p in pagos]
                pid = st.selectbox("Descargar recibo", ids, format_func=lambda x: f"Recibo nómina #{x}")
                pdf = generar_pdf_nomina_pago(int(pid))
                st.download_button("📄 Descargar recibo PDF", data=pdf, file_name=f"recibo_nomina_{int(pid):04d}.pdf", mime="application/pdf", use_container_width=True)



def reportes():
    st.title("📈 Reportes")

    tab1, tab2, tab3, tab4 = st.tabs(["Resumen general", "Valor de inventario", "Alertas comerciales", "Exportar Excel"])

    pedidos = pd.read_sql_query("SELECT * FROM pedidos ORDER BY id DESC", get_conn())
    creditos = pd.read_sql_query("SELECT * FROM creditos ORDER BY id DESC", get_conn())
    abonos = pd.read_sql_query("SELECT * FROM abonos ORDER BY id DESC", get_conn())
    productos = pd.read_sql_query("SELECT * FROM productos ORDER BY descripcion", get_conn())

    with tab1:
        c1, c2, c3 = st.columns(3)
        c1.metric("Pedidos USD", money_usd(pedidos["total_usd"].sum() if not pedidos.empty else 0))
        c2.metric("Créditos saldo", money_usd(creditos["saldo_usd"].sum() if not creditos.empty else 0))
        c3.metric("Abonos validados", money_usd(abonos[abonos["status"]=="Validado"]["monto_usd"].sum() if not abonos.empty else 0))
        st.subheader("Últimos pedidos")
        if pedidos.empty:
            st.info("Sin pedidos.")
        else:
            st.dataframe(pedidos[["id","fecha","cliente_nombre","tipo_pago","total_usd","status"]].head(20), use_container_width=True, hide_index=True)

        st.subheader("Mejores clientes")
        if pedidos.empty:
            st.info("Sin datos de clientes.")
        else:
            p_ok = pedidos[~pedidos["status"].astype(str).str.lower().isin(["cancelado", "anulado"])]
            if p_ok.empty:
                st.info("Sin ventas activas.")
            else:
                mejores = p_ok.groupby(["username","cliente_nombre"], dropna=False).agg(
                    pedidos=("id","count"),
                    total_usd=("total_usd","sum")
                ).reset_index().sort_values("total_usd", ascending=False)
                st.dataframe(mejores.head(20), use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("📦 Valor total de inventario")
        st.caption("Calculado con stock de WooCommerce + costos internos cargados en cada producto.")

        ctop1, ctop2, ctop3 = st.columns([1.3, 1.2, 1.2])
        solo_activos = ctop1.checkbox("Solo productos activos", value=True)
        solo_stock = ctop2.checkbox("Solo con stock", value=True)
        if ctop3.button("🔄 Sincronizar stock", type="primary", use_container_width=True):
            with st.spinner("Sincronizando WooCommerce..."):
                ok, no, errors = sync_todos_productos()
            st.success(f"Sincronizados: {ok}. No sincronizados: {no}.")
            if errors:
                st.warning("Algunos errores:")
                st.code("\\n".join(errors))
            st.rerun()

        rows = q("""SELECT p.*, c.nombre AS categoria
                    FROM productos p LEFT JOIN categorias c ON p.categoria_id=c.id
                    ORDER BY c.nombre, p.descripcion""", fetch=True)

        data = []
        for p in rows:
            if solo_activos and int(p["activo"] or 0) != 1:
                continue
            val = calcular_valor_inventario_producto(p)
            if solo_stock and val["stock"] <= 0:
                continue
            data.append({
                "Categoría": p["categoria"] or "Sin categoría",
                "SKU": p["sku"],
                "Descripción": p["descripcion"],
                "Stock": val["stock"],
                "Bultos": val["bultos_disp"],
                "Resto": val["resto"],
                "Costo real c/u": val["costo_real_unitario"],
                "Valor costo": val["valor_costo"],
                "Valor venta unidad": val["valor_venta_unidad"],
                "Ganancia unidad": val["gan_unidad"],
                "Valor venta docena c/u": val["valor_venta_docena"],
                "Ganancia docena": val["gan_docena"],
                "Valor venta bulto c/u": val["valor_venta_bulto"],
                "Ganancia bulto": val["gan_bulto"],
            })

        df_inv = pd.DataFrame(data)
        if df_inv.empty:
            st.info("No hay inventario para valorar según los filtros.")
            return

        total_costo = float(df_inv["Valor costo"].sum())
        total_venta_unidad = float(df_inv["Valor venta unidad"].sum())
        total_venta_docena = float(df_inv["Valor venta docena c/u"].sum())
        total_venta_bulto = float(df_inv["Valor venta bulto c/u"].sum())
        total_gan_unidad = float(df_inv["Ganancia unidad"].sum())
        total_gan_docena = float(df_inv["Ganancia docena"].sum())
        total_gan_bulto = float(df_inv["Ganancia bulto"].sum())

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Valor inventario costo", money_usd(total_costo))
        k2.metric("Venta potencial unidad", money_usd(total_venta_unidad), delta=money_usd(total_gan_unidad))
        k3.metric("Venta potencial docena", money_usd(total_venta_docena), delta=money_usd(total_gan_docena))
        k4.metric("Venta potencial bulto", money_usd(total_venta_bulto), delta=money_usd(total_gan_bulto))

        st.markdown("### Lectura rápida")
        st.write(f"Ganancia estimada vendiendo todo a **unidad**: **{money_usd(total_gan_unidad)}**.")
        st.write(f"Ganancia estimada vendiendo todo a **docena c/u**: **{money_usd(total_gan_docena)}**.")
        st.write(f"Ganancia estimada vendiendo todo a **bulto c/u**: **{money_usd(total_gan_bulto)}**.")

        bus = st.text_input("Buscar dentro del inventario", placeholder="SKU, descripción o categoría")
        df_show = df_inv
        if bus:
            b = bus.lower()
            df_show = df_inv[
                df_inv["SKU"].astype(str).str.lower().str.contains(b) |
                df_inv["Descripción"].astype(str).str.lower().str.contains(b) |
                df_inv["Categoría"].astype(str).str.lower().str.contains(b)
            ]

        st.dataframe(
            df_show,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Costo real c/u": st.column_config.NumberColumn(format="$%.2f"),
                "Valor costo": st.column_config.NumberColumn(format="$%.2f"),
                "Valor venta unidad": st.column_config.NumberColumn(format="$%.2f"),
                "Ganancia unidad": st.column_config.NumberColumn(format="$%.2f"),
                "Valor venta docena c/u": st.column_config.NumberColumn(format="$%.2f"),
                "Ganancia docena": st.column_config.NumberColumn(format="$%.2f"),
                "Valor venta bulto c/u": st.column_config.NumberColumn(format="$%.2f"),
                "Ganancia bulto": st.column_config.NumberColumn(format="$%.2f"),
            }
        )

        st.download_button(
            "⬇️ Descargar inventario valorado CSV",
            data=df_inv.to_csv(index=False).encode("utf-8-sig"),
            file_name="valor_inventario.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with tab3:
        st.subheader("Alertas comerciales de productos")
        alertas = productos_alertas_margen()
        if not alertas:
            st.success("No hay alertas comerciales relevantes.")
        else:
            df_alertas = pd.DataFrame(alertas)
            c1, c2, c3 = st.columns(3)
            c1.metric("Productos con alerta", len(df_alertas))
            c2.metric("Sin costo proveedor", int(df_alertas["Alertas"].str.contains("Sin costo proveedor").sum()))
            c3.metric("Margen bajo", int(df_alertas["Alertas"].str.contains("Margen").sum()))
            filtro_alerta = st.text_input("Buscar alerta", placeholder="SKU, producto, categoría o tipo de alerta")
            df_show = df_alertas
            if filtro_alerta:
                b = filtro_alerta.lower()
                df_show = df_alertas[
                    df_alertas["SKU"].astype(str).str.lower().str.contains(b) |
                    df_alertas["Producto"].astype(str).str.lower().str.contains(b) |
                    df_alertas["Categoría"].astype(str).str.lower().str.contains(b) |
                    df_alertas["Alertas"].astype(str).str.lower().str.contains(b)
                ]
            st.dataframe(df_show, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Descargar alertas CSV",
                data=df_alertas.to_csv(index=False).encode("utf-8-sig"),
                file_name="alertas_comerciales_productos.csv",
                mime="text/csv",
                use_container_width=True,
            )

    with tab4:
        st.subheader("Exportar reporte completo")
        rows = q("""SELECT p.*, c.nombre AS categoria
                    FROM productos p LEFT JOIN categorias c ON p.categoria_id=c.id
                    ORDER BY c.nombre, p.descripcion""", fetch=True)
        inv_rows = []
        for p in rows:
            val = calcular_valor_inventario_producto(p)
            inv_rows.append({
                "Categoria": p["categoria"] or "Sin categoría",
                "SKU": p["sku"],
                "Descripcion": p["descripcion"],
                "Stock": val["stock"],
                "Bultos": val["bultos_disp"],
                "Resto": val["resto"],
                "Costo real c/u": val["costo_real_unitario"],
                "Valor costo": val["valor_costo"],
                "Valor venta unidad": val["valor_venta_unidad"],
                "Ganancia unidad": val["gan_unidad"],
                "Valor venta docena c/u": val["valor_venta_docena"],
                "Ganancia docena": val["gan_docena"],
                "Valor venta bulto c/u": val["valor_venta_bulto"],
                "Ganancia bulto": val["gan_bulto"],
            })
        inventario_valorado = pd.DataFrame(inv_rows)

        with BytesIO() as output:
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                pedidos.to_excel(writer, sheet_name="Pedidos", index=False)
                creditos.to_excel(writer, sheet_name="Creditos", index=False)
                abonos.to_excel(writer, sheet_name="Abonos", index=False)
                productos.to_excel(writer, sheet_name="Productos", index=False)
                inventario_valorado.to_excel(writer, sheet_name="Inventario valorado", index=False)
            st.download_button(
                "⬇️ Descargar reporte Excel",
                data=output.getvalue(),
                file_name="reporte_insumos_mayor.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )


def respaldo():
    st.title("💾 Respaldo")
    st.info("Para respaldar en Google Drive, usa una carpeta local sincronizada con Google Drive para escritorio. Ejemplo: C:\\Users\\Rene\\Google Drive\\Backups\\InsumosMayor")

    tab1, tab2, tab_zip, tab_clean, tab3 = st.tabs(["Configuración", "Exportar JSON / DB", "Backup ZIP completo", "Limpieza", "Importar respaldo"])

    with tab1:
        folder = st.text_input("Carpeta destino de respaldo automático/manual", value=get_config("backup_folder", str(BACKUP_DIR)))
        auto = st.checkbox("Hacer respaldo automático diario al abrir/usar el sistema", value=get_config("backup_auto_diario", "1") == "1")
        if st.button("💾 Guardar configuración de respaldo"):
            set_config("backup_folder", folder)
            set_config("backup_auto_diario", "1" if auto else "0")
            st.success("Configuración guardada.")
        st.caption(f"Último respaldo automático: {get_config('backup_ultima_fecha','Nunca')}")

    with tab2:
        st.subheader("Exportar JSON / DB")
        st.write("Genera un respaldo JSON y una copia de la base de datos `.db`.")
        st.caption("El JSON incluye usuarios, categorías, productos, cotizaciones, pedidos, créditos, abonos, métodos de pago, carritos, asignaciones de vendedores y configuración.")
        folder_manual = st.text_input("Carpeta destino", value=get_config("backup_folder", str(BACKUP_DIR)), key="folder_manual_backup")
        c1, c2 = st.columns(2)

        if c1.button("📦 Crear respaldo JSON + DB en carpeta", type="primary", use_container_width=True):
            try:
                json_path, db_path = crear_respaldo(folder_manual)
                st.success("Respaldo creado.")
                st.write(json_path)
                if db_path:
                    st.write(db_path)
            except Exception as e:
                st.error(f"No se pudo respaldar: {e}")

        if c2.button("⬇️ Preparar JSON para descargar", use_container_width=True):
            try:
                content, filename = exportar_json_actual()
                st.download_button("Descargar respaldo JSON", data=content, file_name=filename, mime="application/json", use_container_width=True)
            except Exception as e:
                st.error(f"No se pudo exportar: {e}")

    with tab_zip:
        st.subheader("Backup ZIP completo")
        st.write("Este respaldo es el más completo cuando aceptas comprobantes por la web.")
        st.caption("Incluye JSON, DB y opcionalmente archivos físicos como comprobantes en static/pagos y PDFs generados.")
        folder_zip = st.text_input("Carpeta destino ZIP", value=get_config("backup_folder", str(BACKUP_DIR)), key="folder_zip_backup")
        incluir_pagos = st.checkbox("Incluir comprobantes / pagos físicos", value=True, key="zip_incluir_pagos")
        incluir_pdfs = st.checkbox("Incluir PDFs de cotizaciones/pedidos generados", value=True, key="zip_incluir_pdfs")

        cz1, cz2 = st.columns(2)
        if cz1.button("🗜️ Crear ZIP completo en carpeta", type="primary", use_container_width=True):
            try:
                zip_path = crear_respaldo_zip(folder_zip, incluir_pagos=incluir_pagos, incluir_pdfs=incluir_pdfs)
                st.success("ZIP completo creado.")
                st.write(zip_path)
            except Exception as e:
                st.error(f"No se pudo crear ZIP: {e}")

        if cz2.button("⬇️ Preparar ZIP para descargar", use_container_width=True):
            try:
                content, filename = exportar_zip_actual(incluir_pagos=incluir_pagos, incluir_pdfs=incluir_pdfs)
                st.download_button("Descargar ZIP completo", data=content, file_name=filename, mime="application/zip", use_container_width=True)
            except Exception as e:
                st.error(f"No se pudo preparar ZIP: {e}")

    with tab_clean:
        st.subheader("Limpieza de comprobantes viejos")
        st.warning("Esta limpieza solo borra archivos físicos en la carpeta static/pagos. No borra abonos ni créditos de la base de datos.")
        dias = st.number_input("Buscar archivos con más de X días", min_value=1, max_value=3650, value=90, step=1)
        solo_no_ref = st.checkbox("Borrar solo archivos no referenciados en abonos", value=True, help="Recomendado. Evita borrar comprobantes que todavía estén asociados a pagos.")
        archivos, total_mb = listar_archivos_limpieza_pagos(dias=dias, solo_no_referenciados=solo_no_ref)
        st.metric("Archivos candidatos", len(archivos))
        st.metric("Espacio estimado", f"{total_mb} MB")
        if archivos:
            st.dataframe(pd.DataFrame(archivos), use_container_width=True, hide_index=True)
        else:
            st.success("No hay archivos candidatos para limpieza con esos filtros.")

        confirmar_limpieza = st.checkbox("Confirmo que deseo borrar estos archivos físicos", key="confirmar_limpieza_pagos")
        if st.button("🧹 Borrar archivos candidatos", disabled=not confirmar_limpieza or not archivos, use_container_width=True):
            borrados, mb, errores = borrar_archivos_limpieza_pagos(dias=dias, solo_no_referenciados=solo_no_ref)
            st.success(f"Archivos borrados: {borrados}. Espacio estimado liberado: {mb} MB.")
            if errores:
                st.warning("Algunos archivos no se pudieron borrar:")
                st.code("\\n".join(errores[:20]))
            st.rerun()

    with tab3:
        st.subheader("Importar respaldo")
        st.warning("Antes de importar, crea un respaldo actual. La importación puede modificar productos, categorías, usuarios, pedidos, créditos, abonos, métodos de pago, carritos y asignaciones de vendedores.")
        uploaded = st.file_uploader("Seleccionar respaldo .json", type=["json"])
        modo = st.radio(
            "Modo de importación",
            ["fusionar", "reemplazar"],
            horizontal=True,
            help="Fusionar actualiza/agrega registros. Reemplazar limpia tablas comerciales antes de importar."
        )
        confirmar = st.checkbox("Confirmo que deseo importar este respaldo")
        if st.button("📥 Importar respaldo JSON", type="primary", use_container_width=True):
            if not confirmar:
                st.error("Marca la confirmación antes de importar.")
            elif uploaded is None:
                st.error("Selecciona un archivo JSON.")
            else:
                try:
                    ok, msg = importar_respaldo_json(uploaded, modo=modo)
                    if ok:
                        st.success(msg)
                        st.info("Recarga la aplicación para ver todos los cambios reflejados.")
                    else:
                        st.error(msg)
                except Exception as e:
                    st.error(f"No se pudo importar: {e}")



def control_pos():
    st.title("🧾 Control POS")
    st.caption("Control interno para marcar qué pedidos ya fueron sacados/procesados en el sistema POS.")

    tab1, tab2 = st.tabs(["Pendientes por procesar en POS", "Procesados en POS"])

    with tab1:
        df = pd.read_sql_query("""SELECT id,fecha,cliente_nombre,tipo_pago,metodo_pago,total_usd,status,pos_procesado
                                  FROM pedidos
                                  WHERE COALESCE(pos_procesado,0)=0
                                  AND status NOT IN ('Cancelado','Anulado')
                                  ORDER BY id DESC""", get_conn())
        st.dataframe(df, use_container_width=True, hide_index=True)
        if not df.empty:
            pid = st.selectbox("Seleccionar pedido pendiente", df["id"].astype(int).tolist(), format_func=lambda x: f"Pedido #{x}")
            rows = q("SELECT * FROM pedidos WHERE id=?", (int(pid),), fetch=True)
            if rows:
                ped = rows[0]
                st.write(f"Cliente: **{ped['cliente_nombre']}**")
                st.write(f"Total: **{money_usd(ped['total_usd'])}**")
                confirmar = st.checkbox("Confirmo que este pedido ya fue sacado/procesado en el POS")
                notas = st.text_area("Notas POS", key=f"notas_pos_{pid}")
                if st.button("✅ Marcar como procesado en POS", type="primary", disabled=not confirmar, use_container_width=True):
                    q("""UPDATE pedidos SET pos_procesado=1, pos_fecha=?, pos_usuario=?, pos_notas=? WHERE id=?""",
                      (now(), st.session_state.user["username"], notas, int(pid)))
                    st.success("Pedido marcado como procesado en POS.")
                    st.rerun()

    with tab2:
        df2 = pd.read_sql_query("""SELECT id,fecha,cliente_nombre,total_usd,status,pos_fecha,pos_usuario,pos_notas
                                   FROM pedidos
                                   WHERE COALESCE(pos_procesado,0)=1
                                   ORDER BY pos_fecha DESC""", get_conn())
        st.dataframe(df2, use_container_width=True, hide_index=True)
        if not df2.empty:
            pid2 = st.selectbox("Seleccionar procesado", df2["id"].astype(int).tolist(), format_func=lambda x: f"Pedido #{x}", key="pos_proc")
            confirmar2 = st.checkbox("Confirmar reverso POS")
            if st.button("↩️ Marcar como pendiente en POS", disabled=not confirmar2, use_container_width=True):
                q("UPDATE pedidos SET pos_procesado=0, pos_fecha=NULL, pos_usuario=NULL, pos_notas=NULL WHERE id=?", (int(pid2),))
                st.warning("Pedido devuelto a pendiente POS.")
                st.rerun()



def rentabilidad_productos():
    st.title("💰 Rentabilidad de Productos")
    st.caption("La rentabilidad real se calcula automáticamente según precio de venta y costo real. El % funciona como margen objetivo para sugerir precios.")

    productos = q("""SELECT p.*, c.nombre AS categoria FROM productos p
                     LEFT JOIN categorias c ON p.categoria_id=c.id
                     ORDER BY p.descripcion""", fetch=True)
    if not productos:
        st.info("No hay productos creados.")
        return

    cat_names = ["Todas"] + sorted(list({str(p["categoria"] or "Sin categoría") for p in productos}))
    col_cat, col_bus = st.columns([1.4, 2.4])

    with col_cat:
        cat_sel = st.selectbox("Filtrar por categoría", cat_names)

    with col_bus:
        bus = st.text_input("Buscar producto", placeholder="Nombre o SKU. Ejemplo: fotografico, sticker, 180")

    filtrados = []
    for p in productos:
        categoria = str(p["categoria"] or "Sin categoría")
        if cat_sel != "Todas" and categoria != cat_sel:
            continue
        if bus:
            b = bus.lower()
            if (
                b not in str(p["sku"]).lower()
                and b not in str(p["descripcion"]).lower()
                and b not in categoria.lower()
            ):
                continue
        filtrados.append(p)

    filtrados = sorted(filtrados, key=lambda p: str(p["descripcion"]).lower())

    st.caption(f"{len(filtrados)} producto(s) disponibles en esta selección.")
    if not filtrados:
        st.info("No hay productos para esa categoría o búsqueda.")
        return

    opts = {
        f"{p['descripcion']}  |  SKU: {p['sku']}  |  Stock: {p['wc_stock'] or 0}": p
        for p in filtrados
    }

    seleccion = st.selectbox(
        "Producto",
        list(opts.keys()),
        index=0,
        help="Primero filtra por categoría y luego selecciona el producto de la lista."
    )
    prod = opts[seleccion]

    col_img, col_base = st.columns([1.1, 3])
    with col_img:
        if prod["wc_imagen_url"]:
            st.image(prod["wc_imagen_url"], use_container_width=True)
        else:
            st.markdown("<div style='height:220px;border-radius:14px;background:#f3f4f6;display:flex;align-items:center;justify-content:center;font-size:44px'>📦</div>", unsafe_allow_html=True)

    with col_base:
        st.markdown(f"### {prod['descripcion']}")
        st.caption(f"SKU: {prod['sku']} · Categoría: {prod['categoria'] or 'Sin categoría'}")
        sim1, sim2, sim3, sim4 = st.columns(4)
        costo_unit = sim1.number_input("Costo proveedor unitario", min_value=0.0, value=float(prod["costo_proveedor_unitario"] or 0), step=0.01)
        envio_bulto = sim2.number_input("Envío por bulto", min_value=0.0, value=float(prod["envio_costo_bulto"] or 0), step=0.01)
        otros_bulto = sim3.number_input("Otros costos por bulto", min_value=0.0, value=float(prod["otros_costos_bulto"] or 0), step=0.01)
        margen_obj = sim4.number_input("Margen objetivo %", min_value=0.0, max_value=90.0, value=float(prod["margen_minimo_pct"] or 25), step=1.0)

        pv1, pv2, pv3 = st.columns(3)
        precio_unidad = pv1.number_input("Venta unidad", min_value=0.0, value=float(prod["precio_unidad"] or 0), step=0.01)
        precio_docena = pv2.number_input("Venta docena c/u", min_value=0.0, value=float(prod["precio_docena"] or 0), step=0.01)
        precio_bulto = pv3.number_input("Venta bulto c/u", min_value=0.0, value=float(prod["precio_bulto"] or 0), step=0.01)

    sim = dict(prod)
    sim.update({
        "costo_proveedor_unitario": costo_unit,
        "envio_costo_bulto": envio_bulto,
        "otros_costos_bulto": otros_bulto,
        "margen_minimo_pct": margen_obj,
        "precio_unidad": precio_unidad,
        "precio_docena": precio_docena,
        "precio_bulto": precio_bulto,
    })
    m = calc_costos_margen(sim)
    sugerido = precio_sugerido_por_margen(m["costo_real_unitario"], margen_obj)

    st.markdown("---")
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Costo proveedor c/u", money_usd(m["costo_proveedor_unitario"]))
    a2.metric("Costo logístico c/u", money_usd(m["costo_logistico_unitario"]))
    a3.metric("Costo real c/u", money_usd(m["costo_real_unitario"]))
    a4.metric("Precio sugerido objetivo", money_usd(sugerido))

    st.markdown("### Margen real según tus precios actuales")
    c1, c2, c3 = st.columns(3)
    for col, title, data in [(c1, "Unidad", m["unidad"]), (c2, "Docena c/u", m["docena"]), (c3, "Bulto c/u", m["bulto"])]:
        with col:
            estado = etiqueta_margen(data["margen_pct"], margen_obj)
            falta = max(0, sugerido - float(data["precio"] or 0))
            st.markdown(f"""
            <div class="card">
                <div style="font-weight:900;font-size:1.15rem;">{title}</div>
                <div class="muted">Precio venta actual</div>
                <div style="font-weight:900;font-size:1.4rem;">{money_usd(data['precio'])}</div>
                <div class="muted">Costo real c/u: {money_usd(m['costo_real_unitario'])}</div>
                <div style="font-weight:800;color:#047857;">Ganancia c/u: {money_usd(data['ganancia'])}</div>
                <div style="font-weight:900;">Margen real: {data['margen_pct']:.1f}%</div>
                <div>{estado}</div>
                <div class="muted" style="margin-top:6px;">Para margen {margen_obj:.0f}%: {money_usd(sugerido)}</div>
                <div class="muted">Diferencia: {money_usd(falta)}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("### Bulto completo")
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Ingreso bulto", money_usd(m["ingreso_bulto"]))
    b2.metric("Costo total bulto", money_usd(m["costo_bulto"]))
    b3.metric("Ganancia bulto", money_usd(m["ganancia_bulto_total"]))
    b4.metric("Margen bulto", f"{m['margen_bulto_total']:.1f}%")

    st.markdown("### Sugerido MercadoLibre")
    st.caption("Fórmula: Precio en divisas x Tasa proveedor + % comisión MercadoLibre configurable.")
    com_ml = get_comision_ml_pct()
    ml1, ml2, ml3 = st.columns(3)
    for col, titulo, precio in [
        (ml1, "Unidad", precio_unidad),
        (ml2, "Docena c/u", precio_docena),
        (ml3, "Bulto c/u", precio_bulto),
    ]:
        bs_ml, bcv_equiv = precio_ml_resumen(precio)
        with col:
            st.markdown(f"""
            <div class="card">
                <div style="font-weight:900;font-size:1.1rem;">{titulo}</div>
                <div class="muted">Precio divisas base: {money_usd(precio)}</div>
                <div class="muted">Comisión ML: {com_ml:.1f}%</div>
                <div style="font-weight:900;font-size:1.35rem;color:#1d4ed8;">{money_bs(bs_ml)}</div>
                <div class="muted">Equivalente BCV: ${bcv_equiv:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("### Aplicar sugerencia")
    st.caption("El margen objetivo no cambia el margen real por sí solo; sirve para calcular precio sugerido. Puedes aplicarlo a una o varias escalas.")
    ap1, ap2, ap3 = st.columns(3)
    aplicar_unidad = ap1.checkbox("Aplicar sugerido a unidad")
    aplicar_docena = ap2.checkbox("Aplicar sugerido a docena c/u")
    aplicar_bulto = ap3.checkbox("Aplicar sugerido a bulto c/u")

    if st.button("💾 Guardar costos/precios", type="primary", use_container_width=True):
        new_unidad = sugerido if aplicar_unidad else precio_unidad
        new_docena = sugerido if aplicar_docena else precio_docena
        new_bulto = sugerido if aplicar_bulto else precio_bulto
        q("""UPDATE productos SET costo_proveedor_unitario=?, envio_costo_bulto=?, otros_costos_bulto=?,
             margen_minimo_pct=?, precio_unidad=?, precio_docena=?, precio_bulto=?, actualizado_en=? WHERE sku=?""",
          (costo_unit, envio_bulto, otros_bulto, margen_obj, new_unidad, new_docena, new_bulto, now(), prod["sku"]))
        st.success("Producto actualizado.")
        st.rerun()


def publicaciones():
    st.title("📢 Publicaciones")
    df = pd.read_sql_query("""SELECT sku,descripcion,wc_stock,activo,pub_web,pub_instagram,pub_mercadolibre,pub_marketplace,pub_whatsapp,
                              link_instagram,link_mercadolibre,link_marketplace,notas_publicacion
                              FROM productos ORDER BY descripcion""", get_conn())
    if df.empty:
        st.info("No hay productos.")
        return
    f1, f2 = st.columns([2, 1])
    bus = f1.text_input("Buscar producto", placeholder="SKU o descripción")
    filtro = f2.selectbox("Filtro", ["Todos", "Pendientes Instagram", "Pendientes MercadoLibre", "Pendientes Marketplace", "Pendientes WhatsApp", "Publicados en todos", "Con stock"])

    df_f = df.copy()
    if bus:
        b = bus.lower()
        df_f = df_f[df_f["sku"].astype(str).str.lower().str.contains(b) | df_f["descripcion"].astype(str).str.lower().str.contains(b)]
    if filtro == "Pendientes Instagram":
        df_f = df_f[df_f["pub_instagram"] == 0]
    elif filtro == "Pendientes MercadoLibre":
        df_f = df_f[df_f["pub_mercadolibre"] == 0]
    elif filtro == "Pendientes Marketplace":
        df_f = df_f[df_f["pub_marketplace"] == 0]
    elif filtro == "Pendientes WhatsApp":
        df_f = df_f[df_f["pub_whatsapp"] == 0]
    elif filtro == "Publicados en todos":
        df_f = df_f[(df_f["pub_instagram"]==1)&(df_f["pub_mercadolibre"]==1)&(df_f["pub_marketplace"]==1)&(df_f["pub_whatsapp"]==1)&(df_f["pub_web"]==1)]
    elif filtro == "Con stock":
        df_f = df_f[df_f["wc_stock"] > 0]

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total filtrado", len(df_f))
    c2.metric("Pend. IG", int((df["pub_instagram"]==0).sum()))
    c3.metric("Pend. ML", int((df["pub_mercadolibre"]==0).sum()))
    c4.metric("Pend. Market", int((df["pub_marketplace"]==0).sum()))
    c5.metric("Pend. WA", int((df["pub_whatsapp"]==0).sum()))

    for _, r in df_f.iterrows():
        with st.expander(f"{r['descripcion']} — {r['sku']}"):
            st.caption(f"Stock web: {int(r['wc_stock'] or 0)}")
            p1, p2, p3, p4, p5 = st.columns(5)
            web = p1.checkbox("Web", value=bool(r["pub_web"]), key=f"pub_web_{r['sku']}")
            ig = p2.checkbox("Instagram", value=bool(r["pub_instagram"]), key=f"pub_ig_{r['sku']}")
            ml = p3.checkbox("MercadoLibre", value=bool(r["pub_mercadolibre"]), key=f"pub_ml_{r['sku']}")
            mk = p4.checkbox("Marketplace", value=bool(r["pub_marketplace"]), key=f"pub_mk_{r['sku']}")
            wa = p5.checkbox("WhatsApp", value=bool(r["pub_whatsapp"]), key=f"pub_wa_{r['sku']}")
            l1, l2, l3 = st.columns(3)
            link_ig = l1.text_input("Link IG", value=r["link_instagram"] or "", key=f"link_ig_{r['sku']}")
            link_ml = l2.text_input("Link ML", value=r["link_mercadolibre"] or "", key=f"link_ml_{r['sku']}")
            link_mk = l3.text_input("Link Marketplace", value=r["link_marketplace"] or "", key=f"link_mk_{r['sku']}")
            notas = st.text_area("Notas", value=r["notas_publicacion"] or "", key=f"notas_pub_{r['sku']}")
            if st.button("💾 Guardar publicación", key=f"save_pub_{r['sku']}"):
                q("""UPDATE productos SET pub_web=?,pub_instagram=?,pub_mercadolibre=?,pub_marketplace=?,pub_whatsapp=?,
                     link_instagram=?,link_mercadolibre=?,link_marketplace=?,notas_publicacion=?,actualizado_en=? WHERE sku=?""",
                  (1 if web else 0, 1 if ig else 0, 1 if ml else 0, 1 if mk else 0, 1 if wa else 0,
                   link_ig, link_ml, link_mk, notas, now(), r["sku"]))
                st.success("Actualizado.")
                st.rerun()


def vendedores_asignaciones():
    st.title("👤 Vendedores / Asignaciones")
    st.caption("Panel comercial para asignar productos, revisar pendientes y copiar una lista para WhatsApp.")

    vendedores = q("SELECT username,nombre FROM usuarios WHERE rol IN ('vendedor','comprador','admin') AND activo=1 ORDER BY nombre", fetch=True)
    if not vendedores:
        st.info("No hay usuarios activos.")
        return

    opts = {f"{v['nombre'] or v['username']} — {v['username']}": v for v in vendedores}
    vend = opts[st.selectbox("Vendedor / responsable", list(opts.keys()))]

    asign = q("""SELECT p.*, c.nombre AS categoria, pv.fecha_asignacion
                 FROM productos_vendedores pv
                 JOIN productos p ON p.sku=pv.sku
                 LEFT JOIN categorias c ON p.categoria_id=c.id
                 WHERE pv.vendedor_username=? AND p.activo=1
                 ORDER BY p.descripcion""", (vend["username"],), fetch=True)

    total_asig = len(asign)
    con_stock = sum(1 for p in asign if int(p["wc_stock"] or 0) > 0)
    pend_ig = sum(1 for p in asign if not int(p["pub_instagram"] or 0))
    pend_ml = sum(1 for p in asign if not int(p["pub_mercadolibre"] or 0))

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Asignados", total_asig)
    k2.metric("Con stock", con_stock)
    k3.metric("Pend. Instagram", pend_ig)
    k4.metric("Pend. MercadoLibre", pend_ml)

    tab1, tab2, tab3 = st.tabs(["Panel del vendedor", "Asignar productos", "Texto para WhatsApp"])

    with tab1:
        f1, f2, f3 = st.columns([2, 1.2, 1.2])
        bus = f1.text_input("Buscar asignados", placeholder="SKU o descripción")
        filtro = f2.selectbox("Filtro", ["Todos", "Con stock", "Sin stock", "Pendientes publicación", "Pendientes Instagram", "Pendientes MercadoLibre"])
        ordenar = f3.selectbox("Ordenar", ["Descripción", "Stock mayor", "Stock menor", "Categoría"])

        lista = list(asign)
        if bus:
            b = bus.lower()
            lista = [p for p in lista if b in str(p["sku"]).lower() or b in str(p["descripcion"]).lower()]
        if filtro == "Con stock":
            lista = [p for p in lista if int(p["wc_stock"] or 0) > 0]
        elif filtro == "Sin stock":
            lista = [p for p in lista if int(p["wc_stock"] or 0) <= 0]
        elif filtro == "Pendientes publicación":
            lista = [p for p in lista if pendientes_publicacion(p)]
        elif filtro == "Pendientes Instagram":
            lista = [p for p in lista if not int(p["pub_instagram"] or 0)]
        elif filtro == "Pendientes MercadoLibre":
            lista = [p for p in lista if not int(p["pub_mercadolibre"] or 0)]

        if ordenar == "Stock mayor":
            lista = sorted(lista, key=lambda x: int(x["wc_stock"] or 0), reverse=True)
        elif ordenar == "Stock menor":
            lista = sorted(lista, key=lambda x: int(x["wc_stock"] or 0))
        elif ordenar == "Categoría":
            lista = sorted(lista, key=lambda x: str(x["categoria"] or ""))

        if not lista:
            st.info("No hay productos asignados que coincidan.")
        for p in lista:
            disp = disponibilidad(p)
            pend = pendientes_publicacion(p)
            pend_txt = ", ".join(pend) if pend else "Completo"
            with st.container():
                col_img, col_info, col_acc = st.columns([0.8, 3.2, 1.2])
                with col_img:
                    if p["wc_imagen_url"]:
                        st.image(p["wc_imagen_url"], width=95)
                    else:
                        st.markdown("<div style='height:90px;border-radius:10px;background:#f3f4f6;display:flex;align-items:center;justify-content:center;font-size:26px'>📦</div>", unsafe_allow_html=True)
                with col_info:
                    st.markdown(f"**{p['descripcion']}**")
                    st.caption(f"{p['sku']} · {p['categoria'] or 'Sin categoría'} · {resumen_publicacion_icons(p)}")
                    st.write(f"Stock: **{p['wc_stock'] or 0} und** · Bultos: **{disp['bultos']}** · Pendiente: **{pend_txt}**")
                    st.caption(f"Unidad: {money_usd(p['precio_unidad'])} · Docena c/u: {money_usd(p['precio_docena'])} · Bulto c/u: {money_usd(p['precio_bulto'])}")
                with col_acc:
                    if st.button("Quitar", key=f"quita_asig_{vend['username']}_{p['sku']}", use_container_width=True):
                        q("DELETE FROM productos_vendedores WHERE sku=? AND vendedor_username=?", (p["sku"], vend["username"]))
                        st.warning("Producto quitado.")
                        st.rerun()
                st.markdown("---")

    with tab2:
        productos = q("""SELECT p.*, c.nombre AS categoria FROM productos p
                         LEFT JOIN categorias c ON p.categoria_id=c.id
                         WHERE p.activo=1 ORDER BY p.descripcion""", fetch=True)
        asignados = {r["sku"] for r in q("SELECT sku FROM productos_vendedores WHERE vendedor_username=?", (vend["username"],), fetch=True)}

        a1, a2, a3 = st.columns([2.5, 1.3, 1.3])
        bus2 = a1.text_input("Buscar producto para asignar", placeholder="SKU o descripción")
        solo_stock = a2.checkbox("Solo con stock")
        solo_no_asignados = a3.checkbox("Solo no asignados")

        filtrados = []
        for p in productos:
            if bus2 and bus2.lower() not in p["sku"].lower() and bus2.lower() not in p["descripcion"].lower():
                continue
            if solo_stock and int(p["wc_stock"] or 0) <= 0:
                continue
            if solo_no_asignados and p["sku"] in asignados:
                continue
            filtrados.append(p)

        st.caption(f"{len(filtrados)} productos disponibles para revisar.")
        for p in filtrados:
            checked = p["sku"] in asignados
            nuevo = st.checkbox(f"{p['descripcion']} — {p['sku']} | Stock {p['wc_stock'] or 0}", value=checked, key=f"asig_{vend['username']}_{p['sku']}")
            if nuevo != checked:
                if nuevo:
                    q("""INSERT OR IGNORE INTO productos_vendedores (sku,vendedor_username,fecha_asignacion,notas)
                         VALUES (?,?,?,?)""", (p["sku"], vend["username"], now(), ""))
                else:
                    q("DELETE FROM productos_vendedores WHERE sku=? AND vendedor_username=?", (p["sku"], vend["username"]))
                st.rerun()

    with tab3:
        modo = st.selectbox("Tipo de lista", ["Todos asignados", "Solo con stock", "Pendientes Instagram", "Pendientes MercadoLibre", "Pendientes publicación"])
        lista = list(asign)
        if modo == "Solo con stock":
            lista = [p for p in lista if int(p["wc_stock"] or 0) > 0]
        elif modo == "Pendientes Instagram":
            lista = [p for p in lista if not int(p["pub_instagram"] or 0)]
        elif modo == "Pendientes MercadoLibre":
            lista = [p for p in lista if not int(p["pub_mercadolibre"] or 0)]
        elif modo == "Pendientes publicación":
            lista = [p for p in lista if pendientes_publicacion(p)]

        lineas = [f"Hola {vend['nombre'] or vend['username']} 👋", "", f"Lista asignada ({modo}):", ""]
        for i, p in enumerate(lista, start=1):
            disp = disponibilidad(p)
            pend = pendientes_publicacion(p)
            pend_txt = ", ".join(pend) if pend else "Completo"
            lineas += [
                f"{i}. {p['sku']}",
                f"{p['descripcion']}",
                f"Stock: {p['wc_stock'] or 0} unidades / {disp['bultos']} bultos",
                f"Unidad: {money_usd(p['precio_unidad'])} | Docena c/u: {money_usd(p['precio_docena'])} | Bulto c/u: {money_usd(p['precio_bulto'])}",
                f"Pendiente: {pend_txt}",
                ""
            ]
        texto = "\\n".join(lineas).strip()
        st.text_area("Texto para copiar a WhatsApp", value=texto, height=380)
        st.download_button("⬇️ Descargar lista TXT", data=texto.encode("utf-8"), file_name=f"lista_{vend['username']}.txt", mime="text/plain", use_container_width=True)


# -----------------------------
# TIENDA
# -----------------------------
@st.dialog("Imagen del producto")
def dialog_imagen(nombre, sku, url):
    st.markdown(f"### {nombre}")
    st.caption(f"SKU: {sku}")
    if url:
        st.image(url, width=500)
    else:
        st.info("Este producto no tiene imagen sincronizada.")

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
            price_lines.append(f"{producto_intermedia_label(prod)}{etiqueta}: <b>{money_usd(prod['precio_docena'])}</b> c/u · {money_bs(float(prod['precio_docena'] or 0) * tasa)} c/u")
        if int(prod["maneja_bulto"] or 0):
            bulto_contiene = int(prod["bulto_contiene"] or 1)
            precio_bulto_unitario = float(prod["precio_bulto"] or 0)
            total_bulto_usd = precio_bulto_unitario * bulto_contiene
            total_bulto_bs = total_bulto_usd * tasa
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


def producto_es_variante_agrupada(prod):
    try:
        return int(prod["es_variante"] or 0) == 1 and str(prod["grupo_variantes"] or "").strip() != ""
    except Exception:
        return False

def producto_visible_tienda(prod):
    try:
        return int(prod["visible_tienda"] if "visible_tienda" in prod.keys() and prod["visible_tienda"] is not None else 1) == 1
    except Exception:
        return True

def render_card_producto_grupo_variantes(grupo, variantes, user, cliente_precio=None):
    if not variantes:
        return

    # Ordenar por orden/medida/color para que la selección sea estable.
    def sort_key(v):
        try:
            orden = int(v["orden_variante"] or 0)
        except Exception:
            orden = 0
        return (orden, str(v["atributo_medida"] or ""), str(v["atributo_color"] or ""), str(v["descripcion"] or ""))

    variantes = sorted(variantes, key=sort_key)
    primero = variantes[0]
    nombre_grupo = str(primero["nombre_visible_grupo"] if "nombre_visible_grupo" in primero.keys() and primero["nombre_visible_grupo"] else "").strip()
    if not nombre_grupo:
        nombre_grupo = str(grupo).strip() or str(primero["descripcion"] or "Producto agrupado")

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"### {nombre_grupo}")
    st.caption(f"Producto agrupado · {len(variantes)} variante(s) disponibles. Cada color/medida conserva su SKU real.")

    medidas = []
    for v in variantes:
        med = str(v["atributo_medida"] if "atributo_medida" in v.keys() and v["atributo_medida"] else "Sin medida").strip() or "Sin medida"
        if med not in medidas:
            medidas.append(med)

    c1, c2 = st.columns(2)
    medida_sel = c1.selectbox("Medida", medidas, key=f"grupo_med_{grupo}")

    variantes_medida = [
        v for v in variantes
        if (str(v["atributo_medida"] if "atributo_medida" in v.keys() and v["atributo_medida"] else "Sin medida").strip() or "Sin medida") == medida_sel
    ]

    colores = []
    for v in variantes_medida:
        col = str(v["atributo_color"] if "atributo_color" in v.keys() and v["atributo_color"] else "Sin color").strip() or "Sin color"
        if col not in colores:
            colores.append(col)

    color_sel = c2.selectbox("Color", colores, key=f"grupo_col_{grupo}_{medida_sel}")

    seleccion = None
    for v in variantes_medida:
        col = str(v["atributo_color"] if "atributo_color" in v.keys() and v["atributo_color"] else "Sin color").strip() or "Sin color"
        if col == color_sel:
            seleccion = v
            break

    if not seleccion:
        st.warning("No hay una variante disponible para esa combinación.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    data = dict(seleccion)
    med_txt = str(data.get("atributo_medida") or "").strip()
    col_txt = str(data.get("atributo_color") or "").strip()
    sufijo = " · ".join([x for x in [med_txt, col_txt] if x])
    data["descripcion"] = f"{nombre_grupo}" + (f" ({sufijo})" if sufijo else "")
    st.info(f"Seleccionado: **{data['descripcion']}** · SKU real: **{data['sku']}**")
    st.markdown("</div>", unsafe_allow_html=True)

    render_card_producto(data, user, cliente_precio=cliente_precio)


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
             WHERE p.activo=1
             AND (
                COALESCE(p.visible_tienda,1)=1
                OR (COALESCE(p.es_variante,0)=1 AND COALESCE(p.grupo_variantes,'')<>'')
             )"""
    params = []
    if cat_ids[cat_sel]:
        sql += " AND p.categoria_id=?"
        params.append(cat_ids[cat_sel])
    if bus:
        sql += " AND (p.descripcion LIKE ? OR p.sku LIKE ? OR COALESCE(p.grupo_variantes,'') LIKE ? OR COALESCE(p.nombre_visible_grupo,'') LIKE ? OR COALESCE(p.atributo_medida,'') LIKE ? OR COALESCE(p.atributo_color,'') LIKE ?)"
        params.extend([f"%{bus}%", f"%{bus}%", f"%{bus}%", f"%{bus}%", f"%{bus}%", f"%{bus}%"])
    sql += " ORDER BY c.orden, COALESCE(p.grupo_variantes,''), p.orden_variante, p.descripcion"
    rows = q(sql, params, fetch=True)

    grupos = {}
    standalone = []
    for prod in rows:
        if producto_es_variante_agrupada(prod):
            g = str(prod["grupo_variantes"] or "").strip()
            grupos.setdefault(g, []).append(prod)
        else:
            if producto_visible_tienda(prod):
                standalone.append(prod)

    total_visible = len(grupos) + len(standalone)

    rinfo1, rinfo2 = st.columns([3, 1])
    rinfo1.caption(f"{total_visible} publicación(es) visibles · {len(rows)} SKU activo(s) cargado(s)")
    if rinfo2.button("🔄 Actualizar stock", use_container_width=True):
        with st.spinner("Sincronizando WooCommerce..."):
            ok, no, errors = sync_todos_productos()
        st.success(f"Sincronizados: {ok}. No sincronizados: {no}.")
        if errors:
            st.warning("Algunos errores:")
            st.code("\n".join(errors))
        st.rerun()

    if not rows or total_visible == 0:
        st.info("No hay productos para mostrar.")
        return

    # Primero productos agrupados por variantes, luego productos normales.
    for grupo, variantes in grupos.items():
        render_card_producto_grupo_variantes(grupo, variantes, user, cliente_precio=cliente_precio)

    for prod in standalone:
        render_card_producto(prod, user, cliente_precio=cliente_precio)



def pedido_permite_edicion(pedido):
    status = str(pedido["status"] or "").lower()
    bloqueados = ["finalizado", "pagado", "cancelado", "anulado"]
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

def pedido_carrito_signature(username, carrito, tipo_operacion, metodo_pago, envio_usd, cliente_username):
    try:
        data = {
            "username": username,
            "cliente_username": cliente_username,
            "carrito": carrito,
            "tipo_operacion": tipo_operacion,
            "metodo_pago": metodo_pago,
            "envio_usd": float(envio_usd or 0),
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    except Exception:
        return secrets.token_hex(16)

def obtener_token_pedido_seguro(signature, key_token="_pedido_token_actual", key_sig="_pedido_signature_actual"):
    if st.session_state.get(key_sig) != signature or not st.session_state.get(key_token):
        st.session_state[key_sig] = signature
        st.session_state[key_token] = secrets.token_hex(24)
    return st.session_state[key_token]

def reset_token_pedido_seguro(key_token="_pedido_token_actual", key_sig="_pedido_signature_actual"):
    st.session_state.pop(key_token, None)
    st.session_state.pop(key_sig, None)


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
    envio_sugerido_usuario = t["envio"] if cliente_usa_ml_envio(cliente_precio_carrito) else 0.0
    if user["rol"] == "admin":
        st.markdown('<div class="admin-only">', unsafe_allow_html=True)
        st.markdown("**Vista interna admin**")
        st.write(f"Peso total estimado: **{t['peso_total_kg']:.2f} kg**")
        if cliente_usa_ml_envio(cliente_precio_carrito):
            st.write(f"Rango envío ML / ENVÍO: **{t.get('envio_rango','N/A')}**")
            st.write(f"Envío sugerido: **{money_bs(t.get('envio_bs',0))}** ({money_usd(envio_sugerido_usuario)} equiv.)")
            st.write(f"Total con envío sugerido: **{money_usd(t['subtotal'] + envio_sugerido_usuario)}**")
        else:
            st.write("Envío sugerido: **No aplica**")
            st.caption("Este cliente no tiene activa la casilla ML / ENVÍO.")
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

    pago_contado_mp = None
    pago_contado_metodo_id = 0
    pago_contado_notificacion = "Solo crear pedido"
    pago_contado_ref = ""
    pago_contado_comp = None
    pago_contado_notas = ""

    if tipo_operacion == "Contado":
        st.markdown("#### Método de pago para contado")
        metodos_contado = metodos_pago_activos()
        if metodos_contado:
            opts_metodos_contado = {"Selecciona método de pago": None}
            for mp_tmp in metodos_contado:
                opts_metodos_contado[metodo_pago_label(mp_tmp)] = mp_tmp
            metodo_sel_contado = st.selectbox("Método de pago", list(opts_metodos_contado.keys()), key="metodo_pago_pedido_contado")
            pago_contado_mp = opts_metodos_contado[metodo_sel_contado]
            metodo_pago = metodo_pago_label(pago_contado_mp) if pago_contado_mp else "Por confirmar"
            pago_contado_metodo_id = int(pago_contado_mp["id"]) if pago_contado_mp else 0
            if pago_contado_mp:
                render_metodo_pago_card(pago_contado_mp)
                render_instruccion_comprobante(pago_contado_mp)
        else:
            st.warning("No hay métodos de pago activos cargados por el admin.")
            metodo_pago = st.selectbox(
                "Método de pago",
                ["Por confirmar", "Divisas", "Transferencia", "Pago móvil", "Zelle", "Zinli", "Binance", "Otro"],
                key="metodo_pago_pedido"
            )

        if metodo_pago != "Por confirmar":
            pago_contado_notificacion = st.radio(
                "Notificación del pago",
                ["Solo crear pedido", "Cargar referencia/comprobante ahora", "Enviar captura por WhatsApp"],
                horizontal=False,
                key="pago_contado_notificacion"
            )
            if pago_contado_notificacion == "Cargar referencia/comprobante ahora":
                pago_contado_ref = st.text_input("Referencia del pago", key="pago_contado_ref")
                pago_contado_comp = st.file_uploader("Comprobante", type=["jpg","jpeg","png","webp","pdf"], key="pago_contado_comp")
                pago_contado_notas = st.text_area("Notas del pago", key="pago_contado_notas")
            elif pago_contado_notificacion == "Enviar captura por WhatsApp":
                st.info("El sistema creará una tarea pendiente para el admin. Envía la captura por WhatsApp al 04126901346 e indica el número de pedido.")
                pago_contado_ref = "WhatsApp"
                pago_contado_notas = "Cliente indicó que enviará captura por WhatsApp al 04126901346."
    else:
        metodo_pago = st.selectbox(
            "Método de pago",
            ["Por confirmar", "Divisas", "Transferencia", "Pago móvil", "Zelle", "Zinli", "Binance", "Otro"],
            key="metodo_pago_pedido"
        )

    if cliente_usa_ml_envio(cliente_pedido):
        envio_detalle_pedido = sugerir_envio_detalle(t["peso_total_kg"])
        st.markdown("#### Envío ML / ENVÍO")
        st.caption(
            f"Peso estimado: {t['peso_total_kg']:.2f} kg · "
            f"Rango aplicado: {envio_detalle_pedido['rango']} · "
            f"Sugerido: {money_bs(envio_detalle_pedido['envio_bs'])}"
        )
        envio_bs_pedido = st.number_input(
            "Envío a cobrar Bs",
            min_value=0.0,
            value=float(envio_detalle_pedido["envio_bs"] or 0),
            step=100.0,
            key="envio_bs_pedido_procesar",
            help="Puedes editar este monto antes de crear el pedido si el envío real cambia."
        )
        tasa_envio_pedido = get_tasa_proveedor()
        envio_pedido = (float(envio_bs_pedido or 0) / tasa_envio_pedido) if tasa_envio_pedido > 0 else 0.0
        st.caption(f"Equivalente interno: {money_usd(envio_pedido)} a tasa proveedor {tasa_envio_pedido:,.2f}")
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
        st.info(
            f"Pago contado seleccionado.\n\n"
            f"Cliente: {cliente_pedido['nombre'] or cliente_pedido['username']}\n\n"
            f"Método: {metodo_pago}\n\n"
            f"Total del pedido: {money_usd(total_preview_usd)}\n\n"
            f"Equivalente Bs a tasa proveedor actual ({tasa_prov_preview:,.2f}): {money_bs(total_preview_bs)}"
        )
        if pago_contado_notificacion == "Cargar referencia/comprobante ahora":
            st.success("Al crear el pedido se cargará una notificación de pago pendiente para validación del admin.")
        elif pago_contado_notificacion == "Enviar captura por WhatsApp":
            st.warning("Al crear el pedido se notificará al admin que el cliente enviará captura por WhatsApp.")
        else:
            st.caption("Puedes crear el pedido sin notificar pago todavía.")

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

    pedido_sig_actual = pedido_carrito_signature(
        user["username"],
        carrito_preview,
        tipo_operacion,
        metodo_pago,
        envio_pedido,
        cliente_pedido["username"]
    )
    pedido_token_actual = obtener_token_pedido_seguro(pedido_sig_actual)
    pedido_creando = bool(st.session_state.get("_pedido_creando", False))
    if pedido_creando:
        st.info("⏳ Creando tu pedido, por favor espera y no cierres la página.")

    col_accion1, col_accion2 = st.columns(2)
    calcular_bcv = col_accion1.button(
        "🧮 Calcular crédito BCV",
        type="secondary",
        disabled=not puede_calcular_bcv or pedido_creando,
        use_container_width=True,
        key="btn_calcular_credito_bcv"
    )
    crear_pedido_normal = col_accion2.button(
        "✅ Crear pedido",
        type="primary",
        disabled=not puede_crear_normal or pedido_creando,
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
            "pedido_token": pedido_token_actual,
            "pedido_signature": pedido_sig_actual,
        }
        st.success("Crédito BCV calculado. Revisa el resumen y luego confirma el pedido.")

    if crear_pedido_normal:
        if st.session_state.get("_pedido_creando", False):
            st.warning("Ya se está creando un pedido. Espera unos segundos.")
        else:
            st.session_state["_pedido_creando"] = True
            tipo_pago = "credito" if tipo_operacion == "Crédito en divisas" else "contado"
            try:
                with st.spinner("Creando tu pedido... por favor espera."):
                    pid, msg = crear_pedido_desde_carrito(
                        user,
                        carrito,
                        tipo_pago,
                        metodo_pago,
                        envio_pedido,
                        notas_pedido,
                        tipo_credito="usd",
                        cliente_target_username=cliente_pedido["username"],
                        pedido_token=pedido_token_actual
                    )
                if pid:
                    reset_token_pedido_seguro()
                    st.session_state["_ultimo_pedido_creado_id"] = int(pid)

                    if tipo_operacion == "Contado" and pago_contado_notificacion in ["Cargar referencia/comprobante ahora", "Enviar captura por WhatsApp"]:
                        registrar_pago_contado_pendiente(
                            pid,
                            cliente_pedido["username"],
                            total_preview_usd,
                            total_preview_bs,
                            metodo_pago,
                            referencia=pago_contado_ref,
                            comprobante=pago_contado_comp if pago_contado_notificacion == "Cargar referencia/comprobante ahora" else None,
                            notas=pago_contado_notas,
                            metodo_pago_id=pago_contado_metodo_id
                        )
                        st.info("Pago contado notificado correctamente. Queda en proceso de verificación por el admin.")

                    st.success(f"{msg} Pedido #{pid}.")
                    pdf = generar_pdf_pedido(pid)
                    packing_pdf = generar_pdf_packing_list_pedido(pid)
                    d1, d2 = st.columns(2)
                    d1.download_button("⬇️ Descargar PDF pedido", data=pdf, file_name=f"pedido_{pid:04d}.pdf", mime="application/pdf", use_container_width=True)
                    d2.download_button("📦 Descargar Packing List", data=packing_pdf, file_name=f"packing_list_{pid:04d}.pdf", mime="application/pdf", use_container_width=True)
                else:
                    st.error(msg)
            finally:
                st.session_state["_pedido_creando"] = False

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
            confirmar_pedido_bcv = cc1.button(
                "✅ Crear pedido confirmado con Crédito BCV",
                type="primary",
                use_container_width=True,
                key="btn_confirmar_pedido_bcv",
                disabled=bool(st.session_state.get("_pedido_creando", False))
            )
            if confirmar_pedido_bcv:
                if st.session_state.get("_pedido_creando", False):
                    st.warning("Ya se está creando un pedido. Espera unos segundos.")
                else:
                    st.session_state["_pedido_creando"] = True
                    try:
                        with st.spinner("Creando pedido con Crédito BCV... por favor espera."):
                            pid, msg = crear_pedido_desde_carrito(
                                user,
                                carrito,
                                "credito",
                                calc["metodo_pago"],
                                calc["envio_usd"],
                                calc["notas"],
                                tipo_credito="bcv",
                                cliente_target_username=calc.get("cliente_target_username"),
                                pedido_token=calc.get("pedido_token") or pedido_token_actual
                            )
                        if pid:
                            st.session_state["_credito_bcv_calc"] = None
                            reset_token_pedido_seguro()
                            st.session_state["_ultimo_pedido_creado_id"] = int(pid)
                            st.success(f"{msg} Pedido #{pid} creado con Crédito BCV.")
                            pdf = generar_pdf_pedido(pid)
                            packing_pdf = generar_pdf_packing_list_pedido(pid)
                            d1, d2 = st.columns(2)
                            d1.download_button("⬇️ Descargar PDF pedido", data=pdf, file_name=f"pedido_{pid:04d}.pdf", mime="application/pdf", use_container_width=True)
                            d2.download_button("📦 Descargar Packing List", data=packing_pdf, file_name=f"packing_list_{pid:04d}.pdf", mime="application/pdf", use_container_width=True)
                        else:
                            st.error(msg)
                    finally:
                        st.session_state["_pedido_creando"] = False

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
# Stock manual: no se sincroniza automáticamente al iniciar sesión.
# Usa el botón "Actualizar stock ahora" en el sidebar cuando quieras sincronizar WooCommerce.

with st.sidebar:
    st.title("📦 Insumos Mayor")
    st.write(f"**{user['nombre']}**")
    st.caption(f"{user['rol']} · {user['username']}")
    if user["rol"] == "admin":
        try:
            _tareas = admin_tareas_counts()
            _total_tareas = _tareas["pagos"] + _tareas["pedidos"] + _tareas.get("pos", 0)
            if _total_tareas > 0:
                st.warning(f"🔔 Tareas admin: {_total_tareas} · Pagos: {_tareas['pagos']} · Pedidos: {_tareas['pedidos']} · POS: {_tareas.get('pos',0)}")
            else:
                st.success("🔔 Sin tareas críticas.")
        except Exception:
            pass
    ultima_stock_sidebar = get_config("stock_auto_sync_ultima", "")
    if ultima_stock_sidebar:
        st.caption(f"📦 Última actualización manual stock: {ultima_stock_sidebar}")
    else:
        st.caption("📦 Stock no sincronizado todavía. Usa Actualizar stock ahora.")
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

    opciones = ["Mi cuenta", "Tienda", "Carrito", "Mis pedidos", "Mis créditos", "Mis pagos", "Mi perfil"]
    if user["rol"] == "admin":
        opciones += ["Centro admin", "Dashboard", "Control POS", "POS Experimental", "Rentabilidad", "Nómina", "Publicaciones", "Vendedores", "Productos", "Categorías", "Cotizaciones", "Usuarios", "Métodos de pago", "Validar créditos", "Reportes", "Configuración", "Respaldo"]
    elif user["rol"] == "vendedor":
        opciones += ["Publicaciones", "Vendedores"]
    elif user["rol"] == "vendedor_mercadolibre":
        opciones += ["Publicaciones"]

    current = st.session_state.get("menu", "Mi cuenta")
    if current not in opciones:
        current = "Mi cuenta"

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

if menu == "Mi cuenta":
    mi_cuenta_home()
elif menu == "Tienda":
    tienda()
elif menu == "Carrito":
    carrito_view()
elif menu == "Mis pedidos":
    mis_pedidos()
elif menu == "Mis créditos":
    mis_creditos()
elif menu == "Mis pagos":
    mis_pagos()
elif menu == "Mi perfil":
    mi_perfil()
elif menu == "Centro admin":
    admin_centro_tareas()
elif menu == "Dashboard":
    dashboard_admin()
elif menu == "Control POS":
    control_pos()
elif menu == "POS Experimental":
    pos_experimental()
elif menu == "Rentabilidad":
    rentabilidad_productos()
elif menu == "Nómina":
    nomina_admin()
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
elif menu == "Métodos de pago":
    admin_metodos_pago()
elif menu == "Validar créditos":
    validar_creditos()
elif menu == "Reportes":
    reportes()
elif menu == "Configuración":
    admin_config()
elif menu == "Respaldo":
    respaldo()
