import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import requests
from io import BytesIO

# ─── CONFIGURACIÓN DE PÁGINA ───────────────────────────────────────────────
st.set_page_config(
    page_title="Control de Proceso — Vienesas",
    page_icon="🌭",
    layout="wide"
)

st.title("🌭 Control de Proceso — Vienesas")
st.markdown("---")

# ─── LINK DE ONEDRIVE ──────────────────────────────────────────────────────
ONEDRIVE_URL = "https://alumnosutalca-my.sharepoint.com/:x:/g/personal/ycordova21_alumnos_utalca_cl/IQCLYCe918veTJb2uRXKuyzYAeiSB22E4dE5dTLQ89UsMrQ?e=3b0TNv"
# Convertir link compartido a link de descarga directa
DOWNLOAD_URL = ONEDRIVE_URL.replace("/:x:/g/", "/:x:/r/").split("?")[0] + "?download=1"

# ─── CARGA DE DATOS ────────────────────────────────────────────────────────
@st.cache_data(ttl=300)  # cache 5 minutos
def cargar_datos():
    try:
        response = requests.get(DOWNLOAD_URL, timeout=30)
        response.raise_for_status()
        excel_data = BytesIO(response.content)

        muestreo = pd.read_excel(excel_data, sheet_name="Muestreo")
        excel_data.seek(0)
        sticks = pd.read_excel(excel_data, sheet_name="StickRotos")

        # Limpiar y convertir tipos
        muestreo["Fecha"] = pd.to_datetime(muestreo["Fecha"], errors="coerce")
        muestreo["PromedioLargo"] = pd.to_numeric(muestreo["PromedioLargo"], errors="coerce").fillna(0)
        muestreo["PromedioTorsiones"] = pd.to_numeric(muestreo["PromedioTorsiones"], errors="coerce").fillna(0)
        muestreo["Defectuosas"] = pd.to_numeric(muestreo["Defectuosas"], errors="coerce").fillna(0)
        muestreo["p"] = muestreo["Defectuosas"] / 10

        for j in range(1, 11):
            col = f"Largo_{j}"
            if col in muestreo.columns:
                muestreo[col] = pd.to_numeric(muestreo[col], errors="coerce").fillna(0)

        sticks["Fecha"] = pd.to_datetime(sticks["Fecha"], errors="coerce")
        sticks["TotalRotos"] = pd.to_numeric(sticks["TotalRotos"], errors="coerce").fillna(0)

        # Convertir columnas de texto
        for col in ["Turno", "Maquina", "TipoMasa", "Tripa"]:
            if col in muestreo.columns:
                muestreo[col] = muestreo[col].astype(str)

        return muestreo, sticks, None

    except Exception as e:
        return None, None, str(e)


# ─── HELPERS PARA CARTAS ───────────────────────────────────────────────────
COLORES_TURNO = {"14": "#534AB7", "34": "#1d9e75", "38": "#D85A30"}

def agregar_linea(fig, valor, nombre, color, dash="dash"):
    fig.add_hline(
        y=valor, line_color=color, line_dash=dash, line_width=1.5,
        annotation_text=f"  {nombre}: {valor:.3f}",
        annotation_font_color=color, annotation_position="right"
    )

def estilo_base(fig, titulo, ylabel):
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=15)),
        xaxis_title="Fecha",
        yaxis_title=ylabel,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=80, t=60, b=10),
        height=340,
        hovermode="x unified"
    )
    return fig


# ─── CARTA X̄ ──────────────────────────────────────────────────────────────
def carta_xbarra(df, maquina, campo="PromedioLargo", titulo_extra="Largo (cm)"):
    df_m = df[df["Maquina"] == maquina].copy().sort_values("Fecha")
    if df_m.empty:
        return None

    xbar  = df_m[campo].mean()
    sigma = df_m[campo].std()
    UCL   = xbar + 3 * sigma
    LCL   = xbar - 3 * sigma

    fig = go.Figure()
    for turno, color in COLORES_TURNO.items():
        d = df_m[df_m["Turno"] == str(turno)].sort_values("Fecha")
        if d.empty: continue
        fig.add_trace(go.Scatter(
            x=d["Fecha"], y=d[campo],
            mode="lines+markers", name=f"Turno {turno}",
            line=dict(color=color, width=2),
            marker=dict(size=6)
        ))

    agregar_linea(fig, UCL,  "UCL",      "#e24b4a", "dash")
    agregar_linea(fig, LCL,  "LCL",      "#e24b4a", "dash")
    agregar_linea(fig, xbar, "X̄",        "#185fa5", "dot")
    if campo == "PromedioLargo":
        agregar_linea(fig, 14.5, "Estándar", "#f39c12", "longdash")
        agregar_linea(fig, 14.7, "LSE",      "#8e44ad", "dashdot")
        agregar_linea(fig, 14.0, "LIE",      "#8e44ad", "dashdot")

    return estilo_base(fig, f"Carta X̄ — {titulo_extra} | {maquina}", titulo_extra)


# ─── CARTA p ───────────────────────────────────────────────────────────────
def carta_p(df, maquina, n=10):
    df_m = df[df["Maquina"] == maquina].copy().sort_values("Fecha")
    if df_m.empty: return None

    pb  = df_m["p"].mean()
    UCL = min(1.0, pb + 3 * np.sqrt(pb * (1 - pb) / n))
    LCL = max(0.0, pb - 3 * np.sqrt(pb * (1 - pb) / n))

    fig = go.Figure()
    for turno, color in COLORES_TURNO.items():
        d = df_m[df_m["Turno"] == str(turno)].sort_values("Fecha")
        if d.empty: continue
        fig.add_trace(go.Scatter(
            x=d["Fecha"], y=d["p"],
            mode="lines+markers", name=f"Turno {turno}",
            line=dict(color=color, width=2),
            marker=dict(size=6,
                symbol=["circle" if v <= UCL else "x" for v in d["p"]])
        ))

    agregar_linea(fig, UCL, "UCL", "#e24b4a", "dash")
    agregar_linea(fig, LCL, "LCL", "#e24b4a", "dash")
    agregar_linea(fig, pb,  "p̄",   "#185fa5", "dot")

    fig.update_yaxes(tickformat=".1%")
    return estilo_base(fig, f"Carta p — % Vienesas fuera de rango | {maquina}", "Proporción defectuosa")


# ─── CARTA C ───────────────────────────────────────────────────────────────
def carta_c(df_stick, maquina=None):
    df = df_stick.copy()
    if maquina:
        df = df[df["Maquina"] == maquina]
    df = df.sort_values("Fecha")
    if df.empty: return None

    cb  = df["TotalRotos"].mean()
    UCL = cb + 3 * np.sqrt(cb)
    LCL = max(0.0, cb - 3 * np.sqrt(cb))

    fig = go.Figure()
    for turno, color in COLORES_TURNO.items():
        d = df[df["Turno"] == str(turno)].sort_values("Fecha")
        if d.empty: continue
        fig.add_trace(go.Scatter(
            x=d["Fecha"], y=d["TotalRotos"],
            mode="lines+markers", name=f"Turno {turno}",
            line=dict(color=color, width=2), marker=dict(size=6)
        ))

    agregar_linea(fig, UCL, "UCL", "#e24b4a", "dash")
    agregar_linea(fig, LCL, "LCL", "#e24b4a", "dash")
    agregar_linea(fig, cb,  "c̄",   "#185fa5", "dot")

    label = maquina if maquina else "Ambas máquinas"
    return estilo_base(fig, f"Carta C — Stick rotos | {label}", "Cantidad stick rotos")


# ─── GRÁFICO BARRAS APILADAS STICK ─────────────────────────────────────────
def grafico_sticks_apilado(df_stick, maquina=None):
    df = df_stick.copy()
    if maquina:
        df = df[df["Maquina"] == maquina]
    df = df.sort_values("Fecha")
    if df.empty: return None

    etiquetas = df["Fecha"].dt.strftime("%d/%m %H:%M").tolist()
    fig = go.Figure()
    for campo, nombre, color in [
        ("Tripa23180_40", "23-180 / 40cm", "#534AB7"),
        ("Tripa23180_50", "23-180 / 50cm", "#AFA9EC"),
        ("Tripa21170_40", "21-170 / 40cm", "#D85A30"),
        ("Tripa21170_50", "21-170 / 50cm", "#F0997B"),
    ]:
        if campo in df.columns:
            fig.add_trace(go.Bar(x=etiquetas, y=df[campo], name=nombre, marker_color=color))
    fig.update_layout(barmode="stack", height=300,
                      title="Comparativo stick rotos por tipo de tripa",
                      margin=dict(l=10,r=10,t=50,b=10),
                      legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1))
    return fig


# ═══════════════════════════════════════════════════════════════════════════
#  CARGA DE DATOS
# ═══════════════════════════════════════════════════════════════════════════
with st.spinner("Cargando datos desde OneDrive..."):
    muestreo, sticks, error = cargar_datos()

if error:
    st.error(f"❌ Error al cargar datos: {error}")
    st.stop()

if muestreo is None or muestreo.empty:
    st.warning("⚠️ No se encontraron datos en el archivo Excel.")
    st.stop()

st.success(f"✅ Datos cargados: {len(muestreo)} registros de muestreo | {len(sticks) if sticks is not None else 0} registros de stick rotos")

if st.button("🔄 Actualizar datos"):
    st.cache_data.clear()
    st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
#  FILTROS GLOBALES
# ═══════════════════════════════════════════════════════════════════════════
col1, col2, col3 = st.columns(3)
with col1:
    turnos_disp = sorted(muestreo["Turno"].dropna().unique().tolist())
    turnos_sel  = st.multiselect("Turnos", turnos_disp, default=turnos_disp)
with col2:
    masas_disp = sorted(muestreo["TipoMasa"].dropna().unique().tolist())
    masa_sel   = st.multiselect("Tipo de masa", masas_disp, default=masas_disp)
with col3:
    fecha_min = muestreo["Fecha"].min().date()
    fecha_max = muestreo["Fecha"].max().date()
    rango = st.date_input("Rango de fechas", [fecha_min, fecha_max])

df_filtrado = muestreo[
    muestreo["Turno"].isin([str(t) for t in turnos_sel]) &
    muestreo["TipoMasa"].isin(masa_sel) &
    (muestreo["Fecha"].dt.date >= rango[0]) &
    (muestreo["Fecha"].dt.date <= rango[1])
]

# ═══════════════════════════════════════════════════════════════════════════
#  KPIs RESUMEN
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("### 📊 Resumen del período")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Registros",         len(df_filtrado))
k2.metric("Prom. largo",       f"{df_filtrado['PromedioLargo'].mean():.2f} cm" if not df_filtrado.empty else "—")
k3.metric("Prom. torsiones",   f"{df_filtrado['PromedioTorsiones'].mean():.1f}"  if not df_filtrado.empty else "—")
k4.metric("% rechazo prom.",   f"{df_filtrado['p'].mean()*100:.1f}%"             if not df_filtrado.empty else "—")
k5.metric("Total stick rotos", int(sticks["TotalRotos"].sum()) if sticks is not None and not sticks.empty else "—")

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════
#  PESTAÑAS DE CARTAS
# ═══════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📏 Carta X̄ — Largo",
    "🔄 Carta X̄ — Torsiones",
    "📉 Carta p — Rechazo",
    "🔩 Carta C — Stick rotos",
    "📋 Historial"
])

with tab1:
    st.markdown("**Promedio de largo por muestreo — comparación por turno y máquina**")
    c1, c2 = st.columns(2)
    with c1:
        fig = carta_xbarra(df_filtrado, "VEMAG 1", "PromedioLargo", "Largo (cm)")
        if fig: st.plotly_chart(fig, use_container_width=True)
        else:   st.info("Sin datos para VEMAG 1")
    with c2:
        fig = carta_xbarra(df_filtrado, "VEMAG 2", "PromedioLargo", "Largo (cm)")
        if fig: st.plotly_chart(fig, use_container_width=True)
        else:   st.info("Sin datos para VEMAG 2")

with tab2:
    st.markdown("**Promedio de torsiones por muestreo — comparación por turno y máquina**")
    c1, c2 = st.columns(2)
    with c1:
        fig = carta_xbarra(df_filtrado, "VEMAG 1", "PromedioTorsiones", "Torsiones")
        if fig: st.plotly_chart(fig, use_container_width=True)
        else:   st.info("Sin datos para VEMAG 1")
    with c2:
        fig = carta_xbarra(df_filtrado, "VEMAG 2", "PromedioTorsiones", "Torsiones")
        if fig: st.plotly_chart(fig, use_container_width=True)
        else:   st.info("Sin datos para VEMAG 2")

with tab3:
    st.markdown("**Proporción de vienesas fuera de rango (largo < 14.0 cm o > 14.7 cm)**")
    c1, c2 = st.columns(2)
    with c1:
        fig = carta_p(df_filtrado, "VEMAG 1")
        if fig: st.plotly_chart(fig, use_container_width=True)
        else:   st.info("Sin datos para VEMAG 1")
    with c2:
        fig = carta_p(df_filtrado, "VEMAG 2")
        if fig: st.plotly_chart(fig, use_container_width=True)
        else:   st.info("Sin datos para VEMAG 2")

with tab4:
    if sticks is None or sticks.empty:
        st.info("Sin datos de stick rotos aún.")
    else:
        df_stick_f = sticks.copy()
        if turnos_sel:
            df_stick_f = df_stick_f[df_stick_f["Turno"].isin([str(t) for t in turnos_sel])]
        c1, c2 = st.columns(2)
        with c1:
            fig = carta_c(df_stick_f, "VEMAG 1")
            if fig: st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig = carta_c(df_stick_f, "VEMAG 2")
            if fig: st.plotly_chart(fig, use_container_width=True)
        fig_bar = grafico_sticks_apilado(df_stick_f)
        if fig_bar: st.plotly_chart(fig_bar, use_container_width=True)

with tab5:
    st.markdown("**Registros de muestreo**")
    cols_mostrar = ["Fecha","Turno","Maquina","TipoMasa","Tripa",
                    "CantidadTotal","PromedioLargo","PromedioTorsiones",
                    "Defectuosas","p"]
    cols_ok = [c for c in cols_mostrar if c in df_filtrado.columns]
    st.dataframe(
        df_filtrado[cols_ok].sort_values("Fecha", ascending=False),
        use_container_width=True, hide_index=True
    )
    csv = df_filtrado[cols_ok].to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Descargar CSV", csv, "muestreo.csv", "text/csv")
