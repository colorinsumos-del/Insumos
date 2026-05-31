
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

APP_NAME = "Sistema de Insumos al Mayor V2 Fix19 CSS Limpio"
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
    add_col("productos", "costo_proveedor_unitario", "REAL DEFAULT 0")
    add_col("productos", "envio_costo_bulto", "REAL DEFAULT 0")
    add_col("productos", "otros_costos_bulto", "REAL DEFAULT 0")
    add_col("productos", "margen_minimo_pct", "REAL DEFAULT 25")
    add_col("productos", "pub_instagram", "INTEGER DEFAULT 0")
    add_col("productos", "pub_mercadolibre", "INTEGER DEFAULT 0")
    add_col("productos", "pub_marketplace", "INTEGER DEFAULT 0")
    add_col("productos", "pub_whatsapp", "INTEGER DEFAULT 0")
    add_col("productos", "pub_web", "INTEGER DEFAULT 0")
    add_col("productos", "link_instagram", "TEXT")
    add_col("productos", "link_mercadolibre", "TEXT")
    add_col("productos", "link_marketplace", "TEXT")
    add_col("productos", "link_whatsapp", "TEXT")
    add_col("productos", "notas_publicacion", "TEXT")
    add_col("pedidos", "pos_procesado", "INTEGER DEFAULT 0")
    add_col("pedidos", "pos_fecha", "TEXT")
    add_col("pedidos", "pos_usuario", "TEXT")
    add_col("pedidos", "pos_notas", "TEXT")

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

def sync_todos_productos():
    rows = q("SELECT sku FROM productos WHERE activo=1", fetch=True)
    ok = 0
    no = 0
    errors = []
    for r in rows:
        try:
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

def crear_pedido_desde_carrito(user, carrito, tipo_pago, metodo_pago, envio_usd, notas, cliente_extra=None):
    if not carrito:
        return None, "Carrito vacío."

    ok_stock, stock_msgs = validar_stock_carrito_woocommerce(carrito)
    if not ok_stock:
        return None, "No se puede crear pedido por stock insuficiente:\n" + "\n".join(stock_msgs)

    t = calcular_carrito(carrito)
    subtotal = float(t["subtotal"])
    total = subtotal + float(envio_usd or 0)
    tasa = get_tasa_proveedor()
    cliente_extra = cliente_extra or {}

    username = user["username"]
    cliente_nombre = cliente_extra.get("cliente_nombre") or user["nombre"] or username
    cliente_rif = cliente_extra.get("cliente_rif") or user["rif"] or ""
    cliente_tel = cliente_extra.get("cliente_telefono") or user["telefono"] or ""
    cliente_dir = cliente_extra.get("cliente_direccion") or user["direccion"] or ""

    q("""INSERT INTO pedidos
         (fecha, username, cliente_nombre, cliente_rif, cliente_telefono, cliente_direccion, items,
          tipo_pago, metodo_pago, subtotal_usd, envio_usd, total_usd, tasa_proveedor,
          total_bs_proveedor, peso_total_kg, status, notas)
         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
      (now(), username, cliente_nombre, cliente_rif, cliente_tel, cliente_dir, json.dumps(carrito, ensure_ascii=False),
       tipo_pago, metodo_pago, subtotal, float(envio_usd or 0), total, tasa, total*tasa, t["peso_total_kg"],
       "Crédito / Pendiente de pago" if tipo_pago == "credito" else "Pendiente de pago", notas))
    pedido_id = q("SELECT last_insert_rowid() AS id", fetch=True)[0]["id"]

    credito_id = None
    if tipo_pago == "credito":
        dias = int(user["dias_credito"] or parse_float(get_config("dias_credito_default", "10"), 10))
        venc = (datetime.now() + timedelta(days=dias)).strftime("%d/%m/%Y")
        q("""INSERT INTO creditos
             (pedido_id, username, cliente_nombre, fecha_inicio, fecha_vencimiento, monto_usd, saldo_usd, tasa_proveedor, status, notas)
             VALUES (?,?,?,?,?,?,?,?,?,?)""",
          (pedido_id, username, cliente_nombre, now(), venc, total, total, tasa, "Pendiente", "Crédito creado desde pedido."))
        credito_id = q("SELECT last_insert_rowid() AS id", fetch=True)[0]["id"]
        q("UPDATE pedidos SET credito_id=?, status='Crédito / Pendiente de pago' WHERE id=?", (credito_id, pedido_id))
    else:
        q("UPDATE pedidos SET status='Pendiente de pago' WHERE id=?", (pedido_id,))

    limpiar_carrito(username)
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
        return float(prod["precio_docena"] or 0), 12
    if presentacion == "bulto":
        # precio_bulto se maneja como precio unitario dentro del bulto.
        # Total de 1 bulto = precio_bulto * bulto_contiene.
        bulto_contiene = int(prod["bulto_contiene"] or 1)
        return float(prod["precio_bulto"] or 0) * bulto_contiene, bulto_contiene
    return float(prod["precio_unidad"] or 0), 1

def calcular_precio_inteligente(prod, presentacion, cantidad_presentacion):
    """
    Calcula el precio final de forma inteligente.

    Caso clave:
    - Si el usuario elige unidad y coloca 12, aplica precio docena.
    - Si el usuario elige unidad y coloca la cantidad del bulto, aplica precio bulto.
    - Si coloca cantidades mayores, combina bultos + docenas + unidades.

    Ejemplo:
    bulto=50, cantidad unidades=62
    => 1 bulto + 1 docena = precio_bulto + precio_docena

    Si el usuario elige docena o bulto explícitamente, respeta esa presentación.
    """
    cantidad_presentacion = int(cantidad_presentacion or 1)
    precio_unidad = float(prod["precio_unidad"] or 0)
    precio_docena = float(prod["precio_docena"] or 0)
    precio_bulto = float(prod["precio_bulto"] or 0)
    maneja_docena = bool(int(prod["maneja_docena"] or 0))
    maneja_bulto = bool(int(prod["maneja_bulto"] or 0))
    bulto_contiene = max(1, int(prod["bulto_contiene"] or 1))

    precio_pres, equivalencia = producto_precio_presentacion(prod, presentacion)
    unidades_base_total = cantidad_presentacion * int(equivalencia)

    # Si el usuario eligió docena o bulto, se respeta esa selección.
    if presentacion != "unidad":
        return {
            "precio_total": precio_pres * cantidad_presentacion,
            "unidades_base_total": unidades_base_total,
            "precio_presentacion": precio_pres,
            "equivalencia": equivalencia,
            "escala_aplicada": presentacion,
            "detalle_precio": f"{cantidad_presentacion} {presentacion}(s)",
        }

    # Precio inteligente solo cuando el usuario compra en unidades.
    restante = unidades_base_total
    total = 0.0
    partes = []

    if maneja_bulto and precio_bulto > 0 and restante >= bulto_contiene:
        n_bultos = restante // bulto_contiene
        total += n_bultos * precio_bulto * bulto_contiene
        restante -= n_bultos * bulto_contiene
        partes.append(f"{n_bultos} bulto(s)")

    if maneja_docena and precio_docena > 0 and restante >= 12:
        n_docenas = restante // 12
        total += n_docenas * precio_docena
        restante -= n_docenas * 12
        partes.append(f"{n_docenas} docena(s)")

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
    }

def disponibilidad(prod):
    stock = int(prod["wc_stock"] or 0)
    bulto_contiene = int(prod["bulto_contiene"] or 1)
    return {
        "unidades": stock,
        "docenas": stock // 12,
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

def get_producto_row(sku):
    rows = q("SELECT * FROM productos WHERE sku=?", (sku,), fetch=True)
    return rows[0] if rows else None

def recalcular_item_carrito(item, nueva_cantidad=None):
    """
    Recalcula un item del carrito usando los precios actuales del producto.
    Evita errores visuales como 12 x precio promedio.
    """
    sku = item.get("sku")
    prod = get_producto_row(sku)
    if not prod:
        return item

    cantidad = int(nueva_cantidad if nueva_cantidad is not None else item.get("cantidad_presentacion", 1))
    cantidad = max(1, cantidad)
    presentacion = item.get("presentacion", "unidad")

    precio_calc = calcular_precio_inteligente(prod, presentacion, cantidad)
    item["cantidad_presentacion"] = cantidad
    item["equivalencia"] = int(precio_calc["equivalencia"])
    item["unidades_base_total"] = int(precio_calc["unidades_base_total"])
    item["precio_presentacion"] = float(precio_calc["precio_presentacion"])
    item["precio_total"] = float(precio_calc["precio_total"])
    item["escala_aplicada"] = precio_calc["escala_aplicada"]
    item["detalle_precio"] = precio_calc.get("detalle_precio", precio_calc["escala_aplicada"])
    item["peso_total_kg"] = float(prod["peso_unidad_kg"] or 0) * int(precio_calc["unidades_base_total"])
    item["imagen_url"] = prod["wc_imagen_url"]
    item["desc"] = prod["descripcion"]
    return item

def texto_linea_carrito(item):
    """
    Texto comercial correcto para el carrito.
    - Unidad con cantidad 12 muestra: 12 unidades · Precio aplicado: 1 docena.
    - Docena muestra: 1 docena = 12 unidades · Precio docena.
    - Bulto muestra: 1 bulto = X unidades · Precio bulto.
    """
    presentacion = item.get("presentacion", "unidad")
    cantidad = int(item.get("cantidad_presentacion", 1))
    unidades = int(item.get("unidades_base_total", cantidad))
    escala = item.get("escala_aplicada", presentacion)
    precio_total = float(item.get("precio_total", 0) or 0)

    if presentacion == "unidad":
        return f"{unidades} unidad(es) · Precio aplicado: {escala}"

    # En presentaciones cerradas, la cantidad representa cantidad de docenas/bultos.
    if cantidad == 1:
        return f"1 {presentacion} = {unidades} unidad(es) · Precio {presentacion}: {money_usd(precio_total)}"

    precio_pres = float(item.get("precio_total", 0) or 0) / cantidad if cantidad else 0
    return f"{cantidad} {presentacion}(s) = {unidades} unidad(es) · {money_usd(precio_pres)} c/{presentacion}"


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
    """
    Devuelve (cant, pres) para PDF sin contaminar SKU:
    - 1 a 11 unidades => cant = número, pres = und
    - 12 exactas por escala docena => DOC
    - 24 exactas => DOC x2
    - bulto exacto => BULTO / BULTO x2
    - cantidades mixtas como 15 unidades quedan como 15, porque no son docena cerrada.
    """
    presentacion = str(item.get("presentacion", "unidad")).lower()
    escala = str(item.get("escala_aplicada", "")).lower()
    unidades = int(item.get("unidades_base_total", item.get("cantidad_presentacion", 1)) or 1)
    cantidad_pres = int(item.get("cantidad_presentacion", 1) or 1)

    if presentacion == "bulto":
        cant = "BULTO" if cantidad_pres == 1 else f"BULTO x{cantidad_pres}"
        return cant, f"{unidades} und"

    if presentacion == "docena":
        cant = "DOC" if cantidad_pres == 1 else f"DOC x{cantidad_pres}"
        return cant, f"{unidades} und"

    # Para unidad con precio inteligente: solo mostrar DOC/BULTO si la escala es cerrada y exacta.
    if "bulto" in escala and "+" not in escala:
        n = unidades  # fallback
        m = re.search(r"(\\d+)\\s*bulto", escala)
        if m:
            n = int(m.group(1))
        return ("BULTO" if n == 1 else f"BULTO x{n}"), f"{unidades} und"

    if "docena" in escala and "+" not in escala and unidades % 12 == 0:
        n = unidades // 12
        return ("DOC" if n == 1 else f"DOC x{n}"), f"{unidades} und"

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
    saldo = float(cr["saldo_usd"] or 0)
    if saldo > 0.009:
        tasa = get_tasa_proveedor()
        q("""INSERT INTO abonos
             (credito_id,pedido_id,username,fecha,monto_usd,monto_bs,metodo,referencia,comprobante_path,status,validado_por,fecha_validacion,notas)
             VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (cr["id"], cr["pedido_id"], cr["username"], now(), saldo, saldo*tasa, "Cierre administrativo", "CREDITO-PAGADO", None, "Validado", actor, now(), "Cierre manual de crédito como pagado."))
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
    text = str(text or "")
    repl = {
        "á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n",
        "Á":"A","É":"E","Í":"I","Ó":"O","Ú":"U","Ñ":"N",
        "–":"-","—":"-","“":"\"","”":"\"","’":"'",
        "📦":"","💵":"","🧱":"","✅":"","❌":"","🔎":"","🛒":""
    }
    for a,b in repl.items():
        text = text.replace(a,b)
    return text

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
    if ped["notas"]:
        pdf.ln(3)
        pdf.multi_cell(190, 5, pdf_clean(f"Notas: {ped['notas']}"))
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
        envio = st.number_input("Envío sugerido MercadoLibre >10kg hasta 40kg", min_value=0.0, value=parse_float(get_config("envio_ml_10_40_usd", "10"), 10), step=0.5)
        comision_ml = st.number_input("% comisión MercadoLibre", min_value=0.0, max_value=80.0, value=get_comision_ml_pct(), step=0.5)
        if st.button("💾 Guardar configuración", type="primary", key="save_empresa"):
            set_config("nombre_empresa", nombre)
            set_config("telefono_empresa", tel)
            set_config("instagram_empresa", ig)
            set_config("validez_cotizacion_dias", validez)
            set_config("envio_ml_10_40_usd", envio)
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
            st.code("\n".join(errors))

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
                st.success("Categoría creada.")
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
    tab_list, tab_form = st.tabs(["Listado", "Crear / Editar"])

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
        st.dataframe(df[["sku","descripcion","categoria","precio_unidad","precio_docena","precio_bulto","bulto_contiene","wc_stock","activo","ultima_sync"]], use_container_width=True, hide_index=True)

    with tab_form:
        st.subheader("Crear o editar producto")
        sku_e = st.text_input("SKU")
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
            precio_docena = c2.number_input("Precio docena USD", min_value=0.0, value=float(prod["precio_docena"] if prod else 0), step=0.01)
            precio_bulto = c3.number_input("Precio bulto USD", min_value=0.0, value=float(prod["precio_bulto"] if prod else 0), step=0.01)

            c4, c5, c6 = st.columns(3)
            maneja_docena = c4.checkbox("Maneja docena", value=bool(prod["maneja_docena"]) if prod else True)
            maneja_bulto = c5.checkbox("Maneja bulto", value=bool(prod["maneja_bulto"]) if prod else True)
            bulto_contiene = c6.number_input("Bulto contiene unidades base", min_value=1, max_value=9999, value=int(prod["bulto_contiene"] if prod and prod["bulto_contiene"] else 1), step=1)

            c7, c8 = st.columns(2)
            peso = c7.number_input("Peso por unidad base KG (interno admin)", min_value=0.0, value=float(prod["peso_unidad_kg"] if prod else 0), step=0.01)
            activo = c8.checkbox("Producto activo", value=bool(prod["activo"]) if prod else True)

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
                      bulto_contiene, maneja_docena, maneja_bulto, peso_unidad_kg, activo,
                      costo_proveedor_unitario, envio_costo_bulto, otros_costos_bulto, margen_minimo_pct,
                      pub_web, pub_instagram, pub_mercadolibre, pub_marketplace, pub_whatsapp,
                      link_instagram, link_mercadolibre, link_marketplace, notas_publicacion,
                      creado_en, actualizado_en)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                   int(bulto_contiene), 1 if maneja_docena else 0, 1 if maneja_bulto else 0,
                   peso, 1 if activo else 0,
                   costo_proveedor_unitario, envio_costo_bulto, otros_costos_bulto, margen_minimo_pct,
                   1 if pub_web else 0, 1 if pub_instagram else 0, 1 if pub_mercadolibre else 0, 1 if pub_marketplace else 0, 1 if pub_whatsapp else 0,
                   link_instagram, link_mercadolibre, link_marketplace, notas_publicacion,
                   now(), now()))
                st.success("Producto guardado.")
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

def admin_usuarios():
    st.title("👥 Usuarios / Clientes")
    tab1, tab2 = st.tabs(["Listado", "Crear / Editar"])

    with tab1:
        df = pd.read_sql_query("SELECT username,nombre,rol,telefono,rif,ciudad,activo,credito_habilitado,ml_envio,limite_credito_usd,dias_credito FROM usuarios ORDER BY rol,nombre", get_conn())
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

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Pedidos", len(ped))
            k2.metric("Total pedidos", money_usd(total_gastado))
            k3.metric("Compras finalizadas", money_usd(total_pagado_final))
            k4.metric("Saldo crédito", money_usd(saldo_credito))

            sub1, sub2, sub3 = st.tabs(["Pedidos", "Cotizaciones", "Créditos"])
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
                    st.success("Usuario eliminado.")
                    st.rerun()

    with tab2:
        usuarios = q("SELECT username,nombre FROM usuarios ORDER BY nombre", fetch=True)
        opciones = ["Crear nuevo"] + [f"{u['nombre'] or u['username']} — {u['username']}" for u in usuarios]
        mapa = {f"{u['nombre'] or u['username']} — {u['username']}": u["username"] for u in usuarios}
        sel_edit = st.selectbox("Seleccionar usuario para editar", opciones)
        edit_row = None
        if sel_edit != "Crear nuevo":
            edit_row = get_user(mapa[sel_edit])

        with st.form("crear_editar_usuario"):
            c1, c2, c3 = st.columns(3)
            username = c1.text_input("Correo / usuario", value=edit_row["username"] if edit_row else "")
            nombre = c2.text_input("Nombre", value=edit_row["nombre"] if edit_row else "")
            rol_default = edit_row["rol"] if edit_row and edit_row["rol"] in ["comprador", "vendedor", "vendedor_mercadolibre", "admin"] else "comprador"
            rol = c3.selectbox("Rol", ["comprador", "vendedor", "vendedor_mercadolibre", "admin"], index=["comprador","vendedor","vendedor_mercadolibre","admin"].index(rol_default))
            c4, c5, c6 = st.columns(3)
            telefono = c4.text_input("Teléfono", value=edit_row["telefono"] if edit_row else "")
            rif = c5.text_input("RIF / CI", value=edit_row["rif"] if edit_row else "")
            ciudad = c6.text_input("Ciudad", value=edit_row["ciudad"] if edit_row else "")
            direccion = st.text_area("Dirección", value=edit_row["direccion"] if edit_row else "")
            c7, c8, c9, c10 = st.columns(4)
            credito_hab = c7.checkbox("Crédito habilitado", value=bool(edit_row["credito_habilitado"]) if edit_row else False)
            ml_envio = c8.checkbox("ML / ENVÍO", value=bool(edit_row["ml_envio"]) if edit_row else False, help="Activa cálculo sugerido de envío por peso para clientes MercadoLibre o fuera del estado.")
            limite = c9.number_input("Límite crédito USD", min_value=0.0, value=float(edit_row["limite_credito_usd"] if edit_row else 0), step=1.0)
            dias = c10.number_input("Días crédito", min_value=1, max_value=90, value=int(edit_row["dias_credito"] if edit_row else parse_float(get_config("dias_credito_default","10"), 10)))
            activo = st.checkbox("Activo", value=bool(edit_row["activo"]) if edit_row else True)
            password = st.text_input("Contraseña nueva / inicial", type="password", help="Déjala vacía para conservar la actual si estás editando.")
            submit = st.form_submit_button("💾 Guardar usuario", type="primary")

        if submit:
            if not username.strip() or not nombre.strip():
                st.error("Usuario y nombre son obligatorios.")
            else:
                existing = get_user(username.strip())
                if existing and not password:
                    q("""UPDATE usuarios SET nombre=?, rol=?, telefono=?, rif=?, ciudad=?, direccion=?,
                         credito_habilitado=?, ml_envio=?, limite_credito_usd=?, dias_credito=?, activo=? WHERE username=?""",
                      (nombre, rol, telefono, rif, ciudad, direccion, 1 if credito_hab else 0, 1 if ml_envio else 0, limite, int(dias), 1 if activo else 0, username.strip()))
                else:
                    q("""INSERT INTO usuarios
                         (username,password_hash,nombre,rol,telefono,rif,ciudad,direccion,activo,tipo_precio,credito_habilitado,ml_envio,limite_credito_usd,dias_credito,creado_en)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                         ON CONFLICT(username) DO UPDATE SET nombre=excluded.nombre, rol=excluded.rol,
                         password_hash=excluded.password_hash, telefono=excluded.telefono, rif=excluded.rif,
                         ciudad=excluded.ciudad, direccion=excluded.direccion, activo=excluded.activo,
                         credito_habilitado=excluded.credito_habilitado, ml_envio=excluded.ml_envio,
                         limite_credito_usd=excluded.limite_credito_usd, dias_credito=excluded.dias_credito""",
                      (username.strip(), hash_password(password or "1234"), nombre, rol, telefono, rif, ciudad, direccion, 1 if activo else 0, "proveedor", 1 if credito_hab else 0, 1 if ml_envio else 0, limite, int(dias), now()))
                st.success("Usuario guardado.")
                st.rerun()


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
            else:
                st.error(msg)
    confirmar = st.checkbox("Confirmar eliminación de cotización")
    if c2.button("🗑️ Eliminar cotización", disabled=not confirmar, use_container_width=True):
        eliminar_cotizacion(int(cot_id))
        st.success("Cotización eliminada.")
        st.rerun()


def dashboard_admin():
    st.title("📊 Dashboard")
    pedidos = pd.read_sql_query("SELECT * FROM pedidos", get_conn())
    creditos = pd.read_sql_query("SELECT * FROM creditos", get_conn())
    abonos = pd.read_sql_query("SELECT * FROM abonos", get_conn())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pedidos", len(pedidos))
    c2.metric("Ventas/Pedidos USD", money_usd(pedidos["total_usd"].sum() if not pedidos.empty else 0))
    saldo = creditos["saldo_usd"].sum() if not creditos.empty else 0
    c3.metric("Saldo créditos", money_usd(saldo))
    pend = len(abonos[abonos["status"]=="Pendiente de validar"]) if not abonos.empty else 0
    c4.metric("Pagos por validar", pend)
    st.subheader("Últimos pedidos")
    if pedidos.empty:
        st.info("Sin pedidos.")
    else:
        st.dataframe(pedidos[["id","fecha","cliente_nombre","tipo_pago","total_usd","status"]].sort_values("id", ascending=False).head(12), use_container_width=True, hide_index=True)

def mis_pedidos():
    st.title("🧾 Mis pedidos")
    user = get_user(st.session_state.user["username"])
    visibles = usuarios_visibles_para(user)
    placeholders = ",".join(["?"]*len(visibles))
    df = pd.read_sql_query(f"SELECT * FROM pedidos WHERE username IN ({placeholders}) ORDER BY id DESC", get_conn(), params=visibles)
    if df.empty:
        st.info("Sin pedidos.")
        return

    estados = ["Pendiente", "Pendiente de pago/entrega", "Crédito pendiente", "Crédito parcial", "Pago por validar", "Confirmado", "Preparando", "Listo para entregar", "Entregado", "Finalizado", "Anulado"]

    for _, p in df.iterrows():
        pid = int(p["id"])
        with st.expander(f"Pedido #{pid} | {p['cliente_nombre']} | {p['fecha']} | {money_usd(p['total_usd'])} | {p['status']}"):
            ctop1, ctop2, ctop3 = st.columns(3)
            ctop1.write(f"Cliente: **{p['cliente_nombre']}**")
            ctop2.write(f"Tipo: **{p['tipo_pago']}**")
            ctop3.write(f"Método: **{p['metodo_pago'] or 'N/A'}**")
            st.write(f"Total: **{money_usd(p['total_usd'])}** · {money_bs(float(p['total_bs_proveedor'] or 0))}")

            if user["rol"] == "admin":
                idx = estados.index(p["status"]) if p["status"] in estados else 0
                nuevo = st.selectbox("Estado del pedido", estados, index=idx, key=f"estado_pedido_{pid}")
                if nuevo != p["status"]:
                    if nuevo == "Cancelado":
                        ok, msg = anular_credito_de_pedido(pid, "Pedido cambiado a Cancelado por admin")
                        st.success(msg) if ok else st.error(msg)
                    elif nuevo == "Finalizado / Pagado" and p["credito_id"]:
                        ok, msg = marcar_credito_pagado(int(p["credito_id"]), st.session_state.user["username"])
                        st.success(msg) if ok else st.error(msg)
                    else:
                        q("UPDATE pedidos SET status=? WHERE id=?", (nuevo, pid))
                        st.success("Estado actualizado.")
                    st.rerun()

            c1, c2 = st.columns(2)
            if c1.button("📄 Descargar PDF", key=f"pdf_pedido_{pid}", use_container_width=True):
                pdf = generar_pdf_pedido(pid)
                st.download_button("⬇️ Descargar", data=pdf, file_name=f"pedido_{pid:04d}.pdf", mime="application/pdf", use_container_width=True, key=f"down_pedido_{pid}")

            if user["rol"] == "admin":
                confirmar = st.checkbox("Confirmar eliminación de este pedido", key=f"confirm_del_pedido_{pid}")
                if c2.button("🗑️ Eliminar pedido", key=f"del_pedido_{pid}", disabled=not confirmar, use_container_width=True):
                    ok, msg = eliminar_pedido_seguro(pid)
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)


def mis_creditos():
    st.title("💳 Mis créditos")
    user = get_user(st.session_state.user["username"])
    visibles = usuarios_visibles_para(user)
    placeholders = ",".join(["?"]*len(visibles))
    df = pd.read_sql_query(f"SELECT * FROM creditos WHERE username IN ({placeholders}) ORDER BY id DESC", get_conn(), params=visibles)
    if df.empty:
        st.info("Sin créditos registrados.")
    else:
        st.dataframe(df[["id","pedido_id","cliente_nombre","fecha_vencimiento","monto_usd","saldo_usd","status"]], use_container_width=True, hide_index=True)

    if user["rol"] != "admin":
        creditos_pend = q("SELECT * FROM creditos WHERE username=? AND saldo_usd>0 ORDER BY id DESC", (user["username"],), fetch=True)
    else:
        creditos_pend = q("SELECT * FROM creditos WHERE saldo_usd>0 ORDER BY id DESC", fetch=True)

    if creditos_pend:
        st.subheader("Cargar pago / abono")
        opts = {f"Crédito #{c['id']} - {c['cliente_nombre']} - saldo {money_usd(c['saldo_usd'])}": c for c in creditos_pend}
        sel = st.selectbox("Crédito", list(opts.keys()))
        cr = opts[sel]
        with st.form("form_abono"):
            monto = st.number_input("Monto USD", min_value=0.01, max_value=float(cr["saldo_usd"] or 0), value=min(10.0, float(cr["saldo_usd"] or 0)), step=0.01)
            metodo = st.text_input("Método de pago", value="Pago móvil / transferencia / divisas")
            ref = st.text_input("Referencia")
            comp = st.file_uploader("Comprobante", type=["jpg","jpeg","png","webp","pdf"])
            notas = st.text_area("Notas")
            submit = st.form_submit_button("Enviar pago para validar", type="primary")
        if submit:
            path = save_uploaded_file(comp, PAGOS_DIR, prefix=f"abono_credito_{cr['id']}")
            tasa = get_tasa_proveedor()
            q("""INSERT INTO abonos
                 (credito_id,pedido_id,username,fecha,monto_usd,monto_bs,metodo,referencia,comprobante_path,status,notas)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
              (cr["id"], cr["pedido_id"], cr["username"], now(), monto, monto*tasa, metodo, ref, path, "Pendiente de validar", notas))
            st.success("Pago cargado. Queda pendiente de validación.")
            st.rerun()

    if st.button("📄 Descargar estado de cuenta", use_container_width=True):
        pdf = generar_pdf_estado_cuenta(user["username"])
        st.download_button("⬇️ Estado de cuenta PDF", data=pdf, file_name=f"estado_cuenta_{user['username']}.pdf", mime="application/pdf", use_container_width=True)

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
                with st.expander(f"Crédito #{cid} | {cr['cliente_nombre']} | Saldo {money_usd(cr['saldo_usd'])} | {cr['status']}"):
                    c1, c2, c3 = st.columns(3)
                    c1.write(f"Pedido: #{cr['pedido_id']}")
                    c2.write(f"Monto: {money_usd(cr['monto_usd'])}")
                    c3.write(f"Vence: {cr['fecha_vencimiento']}")
                    estados = ["Pendiente", "Parcial", "Pagado", "Vencido", "Anulado"]
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
                    st.dataframe(ab[["id","fecha","monto_usd","metodo","referencia","status"]] if not ab.empty else ab, use_container_width=True, hide_index=True)

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
            return
        st.dataframe(df[["id","credito_id","pedido_id","username","fecha","monto_usd","metodo","referencia","status"]], use_container_width=True, hide_index=True)
        abono_id = st.number_input("ID abono", min_value=1, value=int(df.iloc[0]["id"]))
        rows = q("SELECT * FROM abonos WHERE id=?", (int(abono_id),), fetch=True)
        if rows:
            ab = rows[0]
            if ab["comprobante_path"]:
                st.caption(f"Comprobante: {ab['comprobante_path']}")
            c1, c2, c3 = st.columns(3)
            if c1.button("✅ Validar abono", type="primary", use_container_width=True):
                ok, msg = aplicar_abono_validado(int(abono_id), st.session_state.user["username"])
                st.success(msg) if ok else st.warning(msg)
                st.rerun()
            if c2.button("❌ Rechazar abono", use_container_width=True):
                q("UPDATE abonos SET status='Rechazado', validado_por=?, fecha_validacion=? WHERE id=?",
                  (st.session_state.user["username"], now(), int(abono_id)))
                st.warning("Abono rechazado.")
                st.rerun()
            confirmar_ab = st.checkbox("Confirmar eliminación de abono", key=f"confirm_del_abono_{abono_id}")
            if c3.button("🗑️ Eliminar abono", disabled=not confirmar_ab, use_container_width=True):
                q("DELETE FROM abonos WHERE id=?", (int(abono_id),))
                st.success("Abono eliminado.")
                st.rerun()


def reportes():
    st.title("📈 Reportes")

    tab1, tab2, tab3 = st.tabs(["Resumen general", "Valor de inventario", "Exportar Excel"])

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

    tab1, tab2, tab3 = st.tabs(["Configuración", "Exportar manual", "Importar respaldo"])

    with tab1:
        folder = st.text_input("Carpeta destino de respaldo automático/manual", value=get_config("backup_folder", str(BACKUP_DIR)))
        auto = st.checkbox("Hacer respaldo automático diario al abrir/usar el sistema", value=get_config("backup_auto_diario", "1") == "1")
        if st.button("💾 Guardar configuración de respaldo"):
            set_config("backup_folder", folder)
            set_config("backup_auto_diario", "1" if auto else "0")
            st.success("Configuración guardada.")
        st.caption(f"Último respaldo automático: {get_config('backup_ultima_fecha','Nunca')}")

    with tab2:
        st.subheader("Exportar manual")
        st.write("Genera un respaldo completo en JSON y una copia de la base de datos `.db`.")
        folder_manual = st.text_input("Carpeta destino", value=get_config("backup_folder", str(BACKUP_DIR)), key="folder_manual_backup")
        c1, c2 = st.columns(2)

        if c1.button("📦 Crear respaldo en carpeta", type="primary", use_container_width=True):
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

    with tab3:
        st.subheader("Importar respaldo")
        st.warning("Antes de importar, crea un respaldo actual. La importación puede modificar productos, categorías, usuarios, pedidos, créditos y abonos.")
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
                    q("""UPDATE pedidos SET pos_procesado=1, pos_fecha=?, pos_usuario=?, pos_notas=?, status='Procesado en POS' WHERE id=?""",
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
                q("UPDATE pedidos SET pos_procesado=0, pos_fecha=NULL, pos_usuario=NULL, pos_notas=NULL, status='Confirmado' WHERE id=?", (int(pid2),))
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

def render_card_producto(prod, user):
    tasa = get_tasa_proveedor()
    stock = int(prod["wc_stock"] or 0)
    disp = disponibilidad(prod)
    img = prod["wc_imagen_url"]
    st.markdown('<div class="product-card">', unsafe_allow_html=True)
    img_col, zoom_col = st.columns([5, 1])
    with img_col:
        if img:
            st.image(img, width=250)
        else:
            st.markdown("<div style='height:250px;width:250px;max-width:100%;border-radius:14px;background:#f3f4f6;display:flex;align-items:center;justify-content:center;font-size:50px'>📦</div>", unsafe_allow_html=True)
    with zoom_col:
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        if st.button("🔍", key=f"zoom_{prod['sku']}", help="Ampliar imagen"):
            dialog_imagen(prod["descripcion"], prod["sku"], img)

    st.markdown(f'<div class="product-title">{prod["descripcion"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="muted">SKU: {prod["sku"]} · {categoria_nombre(prod["categoria_id"])}</div>', unsafe_allow_html=True)

    if stock > 0 and prod["wc_stock_status"] != "outofstock":
        st.markdown(f'<span class="badge badge-ok">Disponible: {stock} {prod["unidad_base"]}</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge badge-no">Sin stock</span>', unsafe_allow_html=True)

    st.caption(f"Docenas: {disp['docenas']} · Bultos: {disp['bultos']}")

    st.markdown(f"<div class='price-main'>Unidad: {money_usd(prod['precio_unidad'])}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='price-bs'>{money_bs(float(prod['precio_unidad'] or 0) * tasa)}</div>", unsafe_allow_html=True)

    if int(prod["maneja_docena"] or 0):
        st.markdown(f"<div class='muted'>Docena: <b>{money_usd(prod['precio_docena'])}</b> · {money_bs(float(prod['precio_docena'] or 0) * tasa)}</div>", unsafe_allow_html=True)
    if int(prod["maneja_bulto"] or 0):
        bulto_contiene = int(prod["bulto_contiene"] or 1)
        precio_bulto_unitario = float(prod["precio_bulto"] or 0)
        total_bulto_usd = precio_bulto_unitario * bulto_contiene
        total_bulto_bs = total_bulto_usd * tasa

        st.markdown(
            f"<div class='muted'>Bulto: <b>{money_usd(precio_bulto_unitario)}</b> c/u · {money_bs(precio_bulto_unitario * tasa)} c/u</div>",
            unsafe_allow_html=True
        )
        st.markdown(
            f"<div class='price-bs'>Bulto Total ({bulto_contiene} {prod['unidad_base']}): <b>{money_usd(total_bulto_usd)}</b> · <b>{money_bs(total_bulto_bs)}</b></div>",
            unsafe_allow_html=True
        )

    if user["rol"] in ["admin", "vendedor_mercadolibre"]:
        com_ml = get_comision_ml_pct()
        ml_u_bs, ml_u_bcv = precio_ml_resumen(prod["precio_unidad"])
        ml_d_bs, ml_d_bcv = precio_ml_resumen(prod["precio_docena"])
        ml_b_bs, ml_b_bcv = precio_ml_resumen(prod["precio_bulto"])
        st.markdown(
            f"""
            <div style="margin-top:6px;border:1px solid #dbeafe;background:#eff6ff;border-radius:12px;padding:8px;">
              <div style="font-weight:900;color:#1d4ed8;">Sugerido MercadoLibre (+{com_ml:.1f}%)</div>
              <div class="muted">Unidad: <b>{money_bs(ml_u_bs)}</b> · Eq. BCV ${ml_u_bcv:,.2f}</div>
              <div class="muted">Docena c/u: <b>{money_bs(ml_d_bs)}</b> · Eq. BCV ${ml_d_bcv:,.2f}</div>
              <div class="muted">Bulto c/u: <b>{money_bs(ml_b_bs)}</b> · Eq. BCV ${ml_b_bcv:,.2f}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    opciones = ["unidad"]
    if int(prod["maneja_docena"] or 0):
        opciones.append("docena")
    if int(prod["maneja_bulto"] or 0):
        opciones.append("bulto")

    c1, c2 = st.columns([1.2, 1])
    presentacion = c1.selectbox("Presentación", opciones, key=f"pres_{prod['sku']}", label_visibility="collapsed")

    # En tienda, docena y bulto son presentaciones cerradas.
    # Se bloquea el campo para que "docena" sea 1 docena = 12 unidades
    # y "bulto" sea 1 bulto = bulto_contiene unidades.
    if presentacion == "unidad":
        cantidad = c2.number_input("Cantidad", min_value=1, max_value=9999, value=1, step=1, key=f"cant_{prod['sku']}", label_visibility="collapsed")
    else:
        cantidad = 1
        c2.number_input("Cantidad", min_value=1, max_value=1, value=1, step=1, key=f"cant_locked_{prod['sku']}_{presentacion}", label_visibility="collapsed", disabled=True)
        st.caption(f"{presentacion.capitalize()} bloqueado: se agrega 1 {presentacion}. Puedes aumentar o bajar en el carrito con + / -.")

    st.markdown(
        f"<div class='muted'>{resumen_presentacion_catalogo(prod, presentacion, int(cantidad))}</div>",
        unsafe_allow_html=True
    )

    precio_calc = calcular_precio_inteligente(prod, presentacion, int(cantidad))
    precio_pres = float(precio_calc["precio_presentacion"])
    eq = int(precio_calc["equivalencia"])
    unidades_base_total = int(precio_calc["unidades_base_total"])
    precio_total_calc = float(precio_calc["precio_total"])
    escala_aplicada = precio_calc["escala_aplicada"]

    # Resumen de precio ya mostrado arriba.

    if unidades_base_total > stock:
        st.warning(f"No alcanza stock. Requiere {unidades_base_total}, disponible {stock}.")
        disabled = True
    else:
        disabled = False

    if st.button("🛒 Agregar", key=f"add_{prod['sku']}", type="primary", use_container_width=True, disabled=disabled):
        carrito = cargar_carrito(user["username"])
        key = f"{prod['sku']}::{presentacion}"
        carrito[key] = {
            "sku": prod["sku"],
            "desc": prod["descripcion"],
            "presentacion": presentacion,
            "escala_aplicada": escala_aplicada,
            "detalle_precio": precio_calc.get("detalle_precio", escala_aplicada),
            "cantidad_presentacion": int(cantidad),
            "equivalencia": int(eq),
            "unidades_base_total": int(unidades_base_total),
            "precio_presentacion": float(precio_pres),
            "precio_total": precio_total_calc,
            "peso_total_kg": float(prod["peso_unidad_kg"] or 0) * int(unidades_base_total),
            "imagen_url": prod["wc_imagen_url"],
        }
        guardar_carrito(user["username"], carrito)
        st.success("Agregado al carrito.")
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

def tienda():
    st.title("🛍️ Tienda / Catálogo")
    user = get_user(st.session_state.user["username"])
    tasa = get_tasa_proveedor()
    carrito = cargar_carrito(user["username"])
    t = calcular_carrito(carrito)

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
        st.markdown(
            f"""
            <div style="font-size:.78rem;color:#6b7280;">Carrito</div>
            <div style="font-size:1.05rem;font-weight:900;">{len(carrito)} item(s)</div>
            <div style="font-size:.82rem;color:#047857;font-weight:800;">{money_usd(t['subtotal'])}</div>
            """,
            unsafe_allow_html=True
        )

    with top4:
        if st.button("🛒 Ver carrito", use_container_width=True):
            st.session_state.menu = "Carrito"
            st.rerun()

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

    cols = st.columns(4)
    for i, prod in enumerate(rows):
        with cols[i % 4]:
            render_card_producto(prod, user)


def carrito_view():
    st.title("🛒 Carrito")
    user = get_user(st.session_state.user["username"])
    carrito = cargar_carrito(user["username"])
    tasa = get_tasa_proveedor()

    if not carrito:
        st.info("Tu carrito está vacío.")
        return

    for key, item in list(carrito.items()):
        # Recalcula silenciosamente para mantener precios actuales y corregir visual.
        item = recalcular_item_carrito(item)
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
                st.rerun()
            nueva_q = bqty.number_input("Cantidad", min_value=1, max_value=99999, value=int(item.get("cantidad_presentacion", 1)), key=f"qty_{key}", label_visibility="collapsed")
            if int(nueva_q) != int(item.get("cantidad_presentacion", 1)):
                carrito[key] = recalcular_item_carrito(item, int(nueva_q))
                guardar_carrito(user["username"], carrito)
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
        st.rerun()

    st.markdown("---")
    st.subheader("Finalizar pedido")
    st.info("Selecciona el tipo de operación antes de crear el pedido. Así evitamos hacer doble paso.")

    with st.form("form_procesar_pedido_directo"):
        tipo_label = st.radio(
            "Tipo de operación",
            ["Contado", "Crédito"],
            horizontal=True,
            help="Contado no crea saldo pendiente. Crédito crea una cuenta por cobrar."
        )

        if tipo_label == "Crédito" and user["rol"] != "admin" and int(user["credito_habilitado"] or 0) != 1:
            st.warning("Tu usuario no tiene crédito habilitado. El administrador debe activarlo.")

        metodo_pago = st.selectbox(
            "Método de pago",
            ["Por confirmar", "Divisas", "Transferencia", "Pago móvil", "Zelle", "Zinli", "Binance", "Otro"]
        )

        if cliente_usa_ml_envio(user):
            envio_pedido = st.number_input(
                "Envío a cobrar USD",
                min_value=0.0,
                value=float(t["envio"]),
                step=0.5
            )
        else:
            envio_pedido = 0.0
            st.caption("Este cliente no tiene activa la casilla ML / ENVÍO, por eso no se muestra cobro de envío.")

        notas_pedido = st.text_area("Notas del pedido")
        submit_pedido = st.form_submit_button("✅ Crear pedido", type="primary")

    if submit_pedido:
        if tipo_label == "Crédito" and user["rol"] != "admin" and int(user["credito_habilitado"] or 0) != 1:
            st.error("No puedes crear pedido a crédito porque tu usuario no tiene crédito habilitado.")
        else:
            tipo_pago = "credito" if tipo_label == "Crédito" else "contado"
            pid, msg = crear_pedido_desde_carrito(user, carrito, tipo_pago, metodo_pago, envio_pedido, notas_pedido)
            if pid:
                st.success(f"{msg} Pedido #{pid}.")
                pdf = generar_pdf_pedido(pid)
                st.download_button("⬇️ Descargar PDF pedido", data=pdf, file_name=f"pedido_{pid:04d}.pdf", mime="application/pdf", use_container_width=True)
            else:
                st.error(msg)

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

with st.sidebar:
    st.title("📦 Insumos Mayor")
    st.write(f"**{user['nombre']}**")
    st.caption(f"{user['rol']} · {user['username']}")
    st.markdown("---")

    opciones = ["Tienda", "Carrito", "Mis pedidos", "Mis créditos"]
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
