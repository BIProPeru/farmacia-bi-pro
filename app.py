"""
Dashboard BI para Farmacias - MVP comercial
Framework: Streamlit

Instalación:
    pip install streamlit pandas numpy plotly openpyxl

Ejecución:
    streamlit run dashboard_farmacia_bi.py

Columnas esperadas en Excel/CSV:
    fecha
    sku
    producto
    categoria
    laboratorio
    proveedor
    unidades_vendidas
    precio_venta
    costo_unitario
    stock_actual
    stock_minimo
    dias_reposicion

Columnas opcionales recomendadas:
    fecha_vencimiento
    lote
    requiere_receta

Objetivo del dashboard:
- Detectar productos críticos y riesgo de quiebre
- Detectar medicamentos próximos a vencer
- Calcular capital inmovilizado
- Predecir demanda futura
- Recomendar compras/reposición
- Detectar productos muertos y sobrestock
- Analizar rentabilidad por categoría, laboratorio y producto
- Exportar recomendaciones para gerencia/compras
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import hashlib
from io import BytesIO

st.set_page_config(
    page_title="Farmacia BI Pro",
    page_icon="💊",
    layout="wide"
)

# =====================================================
# CONTROL DE ACCESO
# =====================================================

USUARIOS = {
    "admin": {
        "nombre": "Administrador",
        "empresa": "Farmacia BI Pro",
        "password_hash": "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9",  # admin123
        "expira": "2030-12-31",
    },
    "cliente_demo": {
        "nombre": "Cliente Demo",
        "empresa": "Farmacia Demo SAC",
        "password_hash": "d3ad9315b7be5dd53b31a273b3b3aba5defe700808305aa16a3062b76658a791",  # demo123
        "expira": "2026-12-31",
    },
}


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def login():
    st.title("🔐 Acceso privado")
    st.markdown("Ingrese sus credenciales para acceder al dashboard.")

    with st.form("login_form"):
        usuario = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        ingresar = st.form_submit_button("Ingresar")

    if ingresar:
        user_data = USUARIOS.get(usuario)
        if user_data is None or hash_password(password) != user_data["password_hash"]:
            st.error("Usuario o contraseña incorrectos.")
            st.stop()

        fecha_expiracion = datetime.strptime(user_data["expira"], "%Y-%m-%d").date()
        if datetime.now().date() > fecha_expiracion:
            st.error("Tu acceso ha expirado. Comunícate con el administrador.")
            st.stop()

        st.session_state["autenticado"] = True
        st.session_state["usuario"] = usuario
        st.session_state["nombre"] = user_data["nombre"]
        st.session_state["empresa"] = user_data["empresa"]
        st.session_state["expira"] = user_data["expira"]
        st.rerun()


def cerrar_sesion():
    for key in ["autenticado", "usuario", "nombre", "empresa", "expira"]:
        st.session_state.pop(key, None)
    st.rerun()


if "autenticado" not in st.session_state:
    login()
    st.stop()

with st.sidebar:
    st.success(f"Acceso: {st.session_state['empresa']}")
    st.caption(f"Usuario: {st.session_state['nombre']}")
    st.caption(f"Válido hasta: {st.session_state['expira']}")
    if st.button("Cerrar sesión"):
        cerrar_sesion()

# =====================================================
# DATOS DEMO FARMACIA
# =====================================================

@st.cache_data
def generar_datos_demo(n_productos=180, dias=240):
    np.random.seed(42)

    categorias = [
        "Analgésicos", "Antibióticos", "Antigripales", "Dermatología",
        "Gastrointestinal", "Vitaminas", "Cuidado personal", "Bebés", "Material médico"
    ]
    laboratorios = ["Pfizer", "Bayer", "Abbott", "Roche", "Genfar", "Medifarma", "Bagó", "Portugal"]
    proveedores = ["Distribuidora Lima", "Droguería Andina", "Proveedor Norte", "Mayorista Salud", "Laboratorio Directo"]

    productos = []
    for i in range(1, n_productos + 1):
        categoria = np.random.choice(categorias)
        laboratorio = np.random.choice(laboratorios)
        proveedor = np.random.choice(proveedores)
        costo = np.random.uniform(2.5, 95)
        margen = np.random.uniform(0.18, 0.55)
        precio = costo * (1 + margen)
        stock_actual = np.random.randint(0, 450)
        stock_minimo = np.random.randint(5, 70)
        dias_reposicion = np.random.randint(2, 21)
        fecha_vencimiento = datetime.today().date() + timedelta(days=int(np.random.choice([20, 45, 75, 120, 180, 365, 540])))
        requiere_receta = "Sí" if categoria == "Antibióticos" or np.random.rand() < 0.18 else "No"

        productos.append({
            "sku": f"MED-{i:04d}",
            "producto": f"Producto farmacéutico {i}",
            "categoria": categoria,
            "laboratorio": laboratorio,
            "proveedor": proveedor,
            "precio_venta": round(precio, 2),
            "costo_unitario": round(costo, 2),
            "stock_actual": stock_actual,
            "stock_minimo": stock_minimo,
            "dias_reposicion": dias_reposicion,
            "fecha_vencimiento": fecha_vencimiento,
            "lote": f"L-{np.random.randint(1000, 9999)}",
            "requiere_receta": requiere_receta,
        })

    productos_df = pd.DataFrame(productos)
    fechas = pd.date_range(datetime.today() - timedelta(days=dias), periods=dias, freq="D")

    ventas = []
    for _, row in productos_df.iterrows():
        demanda_base = np.random.gamma(shape=2.0, scale=3.8)
        estacionalidad = np.random.uniform(0.75, 1.50)

        for fecha in fechas:
            factor = 1.0
            if fecha.weekday() in [4, 5]:
                factor *= 1.12
            if row["categoria"] in ["Antigripales", "Vitaminas"] and fecha.month in [5, 6, 7, 8]:
                factor *= 1.35

            unidades = np.random.poisson(demanda_base * estacionalidad * factor) if np.random.rand() < 0.70 else 0

            ventas.append({
                "fecha": fecha,
                "sku": row["sku"],
                "producto": row["producto"],
                "categoria": row["categoria"],
                "laboratorio": row["laboratorio"],
                "proveedor": row["proveedor"],
                "unidades_vendidas": unidades,
                "precio_venta": row["precio_venta"],
                "costo_unitario": row["costo_unitario"],
                "stock_actual": row["stock_actual"],
                "stock_minimo": row["stock_minimo"],
                "dias_reposicion": row["dias_reposicion"],
                "fecha_vencimiento": row["fecha_vencimiento"],
                "lote": row["lote"],
                "requiere_receta": row["requiere_receta"],
            })

    return pd.DataFrame(ventas)

# =====================================================
# PROCESAMIENTO
# =====================================================

def normalizar_columnas(df):
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns]
    return df


def preparar_datos(df):
    df = normalizar_columnas(df)

    # Compatibilidad con tu dashboard original de importadoras
    if "dias_entrega" in df.columns and "dias_reposicion" not in df.columns:
        df["dias_reposicion"] = df["dias_entrega"]
    if "laboratorio" not in df.columns:
        df["laboratorio"] = "Sin laboratorio"
    if "fecha_vencimiento" not in df.columns:
        df["fecha_vencimiento"] = pd.NaT
    if "lote" not in df.columns:
        df["lote"] = "Sin lote"
    if "requiere_receta" not in df.columns:
        df["requiere_receta"] = "No"

    columnas_necesarias = [
        "fecha", "sku", "producto", "categoria", "proveedor",
        "unidades_vendidas", "precio_venta", "costo_unitario",
        "stock_actual", "stock_minimo", "dias_reposicion"
    ]

    faltantes = [c for c in columnas_necesarias if c not in df.columns]
    if faltantes:
        st.error(f"Faltan columnas necesarias: {', '.join(faltantes)}")
        st.stop()

    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["fecha_vencimiento"] = pd.to_datetime(df["fecha_vencimiento"], errors="coerce")

    numericas = ["unidades_vendidas", "precio_venta", "costo_unitario", "stock_actual", "stock_minimo", "dias_reposicion"]
    for col in numericas:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df = df.dropna(subset=["fecha"])

    df["venta_soles"] = df["unidades_vendidas"] * df["precio_venta"]
    df["costo_soles"] = df["unidades_vendidas"] * df["costo_unitario"]
    df["margen_soles"] = df["venta_soles"] - df["costo_soles"]
    df["margen_pct"] = np.where(df["venta_soles"] > 0, df["margen_soles"] / df["venta_soles"], 0)

    hoy = pd.Timestamp(datetime.today().date())
    df["dias_para_vencer"] = (df["fecha_vencimiento"] - hoy).dt.days

    return df


def calcular_resumen_producto(df, dias_prediccion=30, dias_alerta_vencimiento=90):
    max_fecha = df["fecha"].max()
    ultimos_30 = df[df["fecha"] >= max_fecha - pd.Timedelta(days=30)]
    ultimos_90 = df[df["fecha"] >= max_fecha - pd.Timedelta(days=90)]
    ultimos_180 = df[df["fecha"] >= max_fecha - pd.Timedelta(days=180)]

    resumen = df.groupby(["sku", "producto", "categoria", "laboratorio", "proveedor"], as_index=False).agg(
        unidades_total=("unidades_vendidas", "sum"),
        ventas_total=("venta_soles", "sum"),
        margen_total=("margen_soles", "sum"),
        precio_promedio=("precio_venta", "mean"),
        costo_promedio=("costo_unitario", "mean"),
    )

    ultimo_stock = (
        df.sort_values(["sku", "fecha"])
        .groupby("sku", as_index=False)
        .tail(1)[["sku", "stock_actual", "stock_minimo", "dias_reposicion", "fecha", "fecha_vencimiento", "dias_para_vencer", "lote", "requiere_receta"]]
        .rename(columns={"fecha": "fecha_ultimo_stock"})
    )
    resumen = resumen.merge(ultimo_stock, on="sku", how="left")

    for dias, data in [(30, ultimos_30), (90, ultimos_90), (180, ultimos_180)]:
        demanda = data.groupby("sku", as_index=False).agg(**{f"demanda_{dias}d": ("unidades_vendidas", "sum")})
        resumen = resumen.merge(demanda, on="sku", how="left")

    resumen[["demanda_30d", "demanda_90d", "demanda_180d"]] = resumen[["demanda_30d", "demanda_90d", "demanda_180d"]].fillna(0)
    resumen["demanda_diaria_predicha"] = resumen["demanda_30d"] / 30 * 0.55 + resumen["demanda_90d"] / 90 * 0.30 + resumen["demanda_180d"] / 180 * 0.15
    resumen["demanda_predicha"] = np.ceil(resumen["demanda_diaria_predicha"] * dias_prediccion)

    resumen["dias_cobertura"] = np.where(resumen["demanda_diaria_predicha"] > 0, resumen["stock_actual"] / resumen["demanda_diaria_predicha"], 999).round(1)
    resumen["dias_para_quiebre"] = resumen["dias_cobertura"]
    resumen["margen_pct"] = np.where(resumen["ventas_total"] > 0, resumen["margen_total"] / resumen["ventas_total"], 0)
    resumen["capital_inmovilizado"] = resumen["stock_actual"] * resumen["costo_promedio"]

    resumen["punto_reorden"] = np.ceil(resumen["demanda_diaria_predicha"] * resumen["dias_reposicion"] + resumen["stock_minimo"])
    resumen["cantidad_sugerida_compra"] = np.maximum(resumen["punto_reorden"] - resumen["stock_actual"], 0)
    resumen["inversion_sugerida_compra"] = resumen["cantidad_sugerida_compra"] * resumen["costo_promedio"]

    condiciones_estado = [
        resumen["dias_para_vencer"].notna() & (resumen["dias_para_vencer"] < 0),
        resumen["dias_para_vencer"].notna() & (resumen["dias_para_vencer"] <= dias_alerta_vencimiento),
        (resumen["stock_actual"] <= resumen["stock_minimo"]) | (resumen["dias_para_quiebre"] <= 7),
        resumen["stock_actual"] < resumen["punto_reorden"],
        resumen["dias_cobertura"] > 180,
        resumen["dias_cobertura"] > 90,
        resumen["demanda_90d"] == 0,
    ]
    estados = [
        "Vencido",
        "Próximo a vencer",
        "Riesgo de quiebre",
        "Reponer pronto",
        "Sobrestock crítico",
        "Sobrestock moderado",
        "Producto muerto",
    ]
    resumen["estado_inventario"] = np.select(condiciones_estado, estados, default="Saludable")

    resumen["accion_recomendada"] = "Mantener"
    resumen.loc[resumen["estado_inventario"].isin(["Riesgo de quiebre", "Reponer pronto"]), "accion_recomendada"] = "Comprar / reponer"
    resumen.loc[resumen["estado_inventario"].isin(["Próximo a vencer", "Sobrestock crítico", "Sobrestock moderado"]), "accion_recomendada"] = "Promocionar / rotar"
    resumen.loc[resumen["estado_inventario"].isin(["Producto muerto"]), "accion_recomendada"] = "Evaluar liquidación"
    resumen.loc[resumen["estado_inventario"] == "Vencido", "accion_recomendada"] = "Retirar / revisar lote"

    resumen["score_prioridad_compra"] = (
        resumen["margen_total"].rank(pct=True) * 0.25 +
        resumen["demanda_30d"].rank(pct=True) * 0.35 +
        resumen["ventas_total"].rank(pct=True) * 0.20 +
        (1 / resumen["dias_cobertura"].replace(0, np.nan)).rank(pct=True).fillna(0) * 0.20
    )

    return resumen.sort_values("score_prioridad_compra", ascending=False)


def exportar_excel(resumen):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        resumen.to_excel(writer, sheet_name="Resumen_SKU", index=False)
        resumen[resumen["accion_recomendada"] == "Comprar / reponer"].to_excel(writer, sheet_name="Comprar_Reponer", index=False)
        resumen[resumen["estado_inventario"].isin(["Próximo a vencer", "Vencido"])].to_excel(writer, sheet_name="Vencimientos", index=False)
        resumen[resumen["accion_recomendada"].isin(["Promocionar / rotar", "Evaluar liquidación"])].to_excel(writer, sheet_name="Promocionar_Liquidar", index=False)
    output.seek(0)
    return output

# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.title("💊 Farmacia BI Pro")
st.sidebar.caption("Ventas, inventario, vencimientos, rotación, forecast y compras")

archivo = st.sidebar.file_uploader("Sube Excel o CSV", type=["xlsx", "csv"])
dias_prediccion = st.sidebar.slider("Días para predecir demanda", 15, 90, 30, step=15)
dias_alerta_vencimiento = st.sidebar.slider("Alerta de vencimiento en días", 30, 180, 90, step=15)

if archivo is not None:
    data = pd.read_csv(archivo) if archivo.name.endswith(".csv") else pd.read_excel(archivo)
else:
    data = generar_datos_demo()

ventas = preparar_datos(data)

fecha_min = ventas["fecha"].min().date()
fecha_max = ventas["fecha"].max().date()

rango = st.sidebar.date_input("Rango de fechas", value=(fecha_min, fecha_max), min_value=fecha_min, max_value=fecha_max)

categorias = sorted(ventas["categoria"].dropna().unique())
laboratorios = sorted(ventas["laboratorio"].dropna().unique())
proveedores = sorted(ventas["proveedor"].dropna().unique())

cat_sel = st.sidebar.multiselect("Categorías", categorias, default=categorias)
lab_sel = st.sidebar.multiselect("Laboratorios", laboratorios, default=laboratorios)
prov_sel = st.sidebar.multiselect("Proveedores", proveedores, default=proveedores)

if isinstance(rango, tuple) and len(rango) == 2:
    inicio, fin = pd.to_datetime(rango[0]), pd.to_datetime(rango[1])
else:
    inicio, fin = ventas["fecha"].min(), ventas["fecha"].max()

ventas_filtradas = ventas[
    (ventas["fecha"] >= inicio) &
    (ventas["fecha"] <= fin) &
    (ventas["categoria"].isin(cat_sel)) &
    (ventas["laboratorio"].isin(lab_sel)) &
    (ventas["proveedor"].isin(prov_sel))
]

if ventas_filtradas.empty:
    st.warning("No hay datos con los filtros seleccionados.")
    st.stop()

resumen = calcular_resumen_producto(ventas_filtradas, dias_prediccion, dias_alerta_vencimiento)

# =====================================================
# HEADER Y KPIS
# =====================================================

st.title("💊 Dashboard BI para Farmacias")
st.markdown("Sistema para controlar ventas, stock, vencimientos, rotación, rentabilidad y reposición.")

ventas_total = ventas_filtradas["venta_soles"].sum()
margen_total = ventas_filtradas["margen_soles"].sum()
unidades_total = ventas_filtradas["unidades_vendidas"].sum()
margen_pct = margen_total / ventas_total if ventas_total > 0 else 0
capital_inmovilizado = resumen["capital_inmovilizado"].sum()
inversion_recomendada = resumen["inversion_sugerida_compra"].sum()

quiebre = (resumen["estado_inventario"] == "Riesgo de quiebre").sum()
reponer = (resumen["estado_inventario"] == "Reponer pronto").sum()
proximos_vencer = (resumen["estado_inventario"] == "Próximo a vencer").sum()
vencidos = (resumen["estado_inventario"] == "Vencido").sum()
sobrestock = resumen["estado_inventario"].isin(["Sobrestock crítico", "Sobrestock moderado"]).sum()
muertos = (resumen["estado_inventario"] == "Producto muerto").sum()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Ventas", f"S/ {ventas_total:,.0f}")
col2.metric("Margen", f"S/ {margen_total:,.0f}")
col3.metric("Margen %", f"{margen_pct:.1%}")
col4.metric("Capital en inventario", f"S/ {capital_inmovilizado:,.0f}")

col5, col6, col7, col8 = st.columns(4)
col5.metric("Riesgo de quiebre", int(quiebre))
col6.metric("Por reponer", int(reponer))
col7.metric("Próximos a vencer", int(proximos_vencer))
col8.metric("Vencidos", int(vencidos))

st.divider()

# =====================================================
# ALERTAS
# =====================================================

st.subheader("🚨 Alertas gerenciales")
alertas = []
if vencidos > 0:
    alertas.append(f"Hay {vencidos} productos vencidos. Revisar lotes y retirar de venta.")
if proximos_vencer > 0:
    alertas.append(f"Hay {proximos_vencer} productos próximos a vencer en {dias_alerta_vencimiento} días o menos.")
if quiebre > 0:
    alertas.append(f"Hay {quiebre} productos con riesgo de quiebre de stock.")
if sobrestock > 0:
    alertas.append(f"Hay {sobrestock} productos con sobrestock que podrían requerir promoción o rotación.")
if muertos > 0:
    alertas.append(f"Hay {muertos} productos sin ventas recientes.")
if inversion_recomendada > 0:
    alertas.append(f"La inversión sugerida de compra es aproximadamente S/ {inversion_recomendada:,.0f}.")

if alertas:
    for alerta in alertas:
        st.warning(alerta)
else:
    st.success("No se detectan alertas críticas con los filtros actuales.")

# =====================================================
# TABS
# =====================================================

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Resumen ejecutivo", "Ventas", "Inventario", "Vencimientos", "Forecast y compras", "Rentabilidad", "Exportar"
])

with tab1:
    st.subheader("Resumen ejecutivo por categoría")
    resumen_cat = resumen.groupby("categoria", as_index=False).agg(
        skus=("sku", "count"), ventas=("ventas_total", "sum"), margen=("margen_total", "sum"),
        capital_inventario=("capital_inmovilizado", "sum"), compra_sugerida=("inversion_sugerida_compra", "sum")
    )
    resumen_cat["margen_pct"] = np.where(resumen_cat["ventas"] > 0, resumen_cat["margen"] / resumen_cat["ventas"], 0)
    st.dataframe(resumen_cat, use_container_width=True)

    col_a, col_b = st.columns(2)
    col_a.plotly_chart(px.bar(resumen_cat, x="categoria", y="ventas", title="Ventas por categoría"), use_container_width=True)
    col_b.plotly_chart(px.bar(resumen_cat, x="categoria", y="capital_inventario", title="Capital inmovilizado por categoría"), use_container_width=True)

with tab2:
    st.subheader("Evolución de ventas")
    ventas_diarias = ventas_filtradas.groupby("fecha", as_index=False).agg(venta_soles=("venta_soles", "sum"), unidades=("unidades_vendidas", "sum"))
    st.plotly_chart(px.line(ventas_diarias, x="fecha", y="venta_soles", title="Ventas por fecha"), use_container_width=True)

    top_productos = resumen.sort_values("ventas_total", ascending=False).head(20)
    st.plotly_chart(px.bar(top_productos, x="ventas_total", y="producto", orientation="h", title="Top 20 productos por ventas"), use_container_width=True)

with tab3:
    st.subheader("Estado de inventario")
    estado = resumen.groupby("estado_inventario", as_index=False).agg(skus=("sku", "count"))
    st.plotly_chart(px.bar(estado, x="estado_inventario", y="skus", title="SKU por estado de inventario"), use_container_width=True)

    st.markdown("### Productos críticos")
    criticos = resumen[resumen["estado_inventario"] != "Saludable"].copy()
    st.dataframe(criticos[[
        "sku", "producto", "categoria", "laboratorio", "proveedor", "stock_actual", "stock_minimo",
        "demanda_30d", "demanda_predicha", "dias_cobertura", "capital_inmovilizado",
        "estado_inventario", "accion_recomendada"
    ]], use_container_width=True)

with tab4:
    st.subheader("Control de vencimientos")
    vencimientos = resumen[resumen["estado_inventario"].isin(["Próximo a vencer", "Vencido"])].copy()
    vencimientos = vencimientos.sort_values("dias_para_vencer")
    st.dataframe(vencimientos[[
        "sku", "producto", "categoria", "laboratorio", "lote", "stock_actual", "fecha_vencimiento",
        "dias_para_vencer", "capital_inmovilizado", "estado_inventario", "accion_recomendada"
    ]], use_container_width=True)

    if not vencimientos.empty:
        st.plotly_chart(px.bar(vencimientos.head(30), x="dias_para_vencer", y="producto", orientation="h", title="Productos más próximos a vencer"), use_container_width=True)

with tab5:
    st.subheader("Forecast de demanda y recomendación de compra")
    comprar = resumen[resumen["accion_recomendada"] == "Comprar / reponer"].sort_values("score_prioridad_compra", ascending=False)
    st.metric("Inversión sugerida total", f"S/ {comprar['inversion_sugerida_compra'].sum():,.0f}")
    st.dataframe(comprar[[
        "sku", "producto", "categoria", "laboratorio", "proveedor", "stock_actual", "stock_minimo",
        "dias_para_quiebre", "dias_reposicion", "demanda_30d", "demanda_predicha", "punto_reorden",
        "cantidad_sugerida_compra", "inversion_sugerida_compra", "score_prioridad_compra"
    ]], use_container_width=True)

    top_forecast = resumen.sort_values("demanda_predicha", ascending=False).head(20)
    st.plotly_chart(px.bar(top_forecast, x="demanda_predicha", y="producto", orientation="h", title=f"Top 20 productos con mayor demanda predicha a {dias_prediccion} días"), use_container_width=True)

with tab6:
    st.subheader("Rentabilidad")
    col_a, col_b = st.columns(2)
    top_margen = resumen.sort_values("margen_total", ascending=False).head(20)
    col_a.plotly_chart(px.bar(top_margen, x="margen_total", y="producto", orientation="h", title="Top productos por margen"), use_container_width=True)

    col_b.plotly_chart(px.scatter(
        resumen, x="demanda_30d", y="margen_pct", size="ventas_total", color="estado_inventario",
        hover_data=["sku", "producto", "categoria", "laboratorio", "stock_actual", "capital_inmovilizado"],
        title="Matriz: demanda vs margen"
    ), use_container_width=True)

    st.markdown("### Alto capital inmovilizado")
    alto_capital = resumen.sort_values("capital_inmovilizado", ascending=False).head(30)
    st.dataframe(alto_capital[[
        "sku", "producto", "categoria", "laboratorio", "stock_actual", "costo_promedio",
        "capital_inmovilizado", "demanda_90d", "dias_cobertura", "estado_inventario", "accion_recomendada"
    ]], use_container_width=True)

with tab7:
    st.subheader("Exportar información para gerencia y compras")
    st.markdown("Descarga un Excel con hojas de resumen, compras, vencimientos y productos para promocionar/liquidar.")
    archivo_excel = exportar_excel(resumen)
    st.download_button(
        "📥 Descargar reporte ejecutivo en Excel",
        data=archivo_excel,
        file_name="reporte_farmacia_bi.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.markdown("### Base completa procesada")
    st.dataframe(resumen, use_container_width=True)

st.caption("Farmacia BI Pro - MVP comercial para farmacias y boticas.")
