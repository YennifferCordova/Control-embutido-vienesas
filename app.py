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
DOWNLOAD_URL = "https://alumnosutalca-my.sharepoint.com/:x:/g/personal/ycordova21_alumnos_utalca_cl/IQCLYCe918veTJb2uRXKuyzYAeiSB22E4dE5dTLQ89UsMrQ?download=1&e=e3ClKv"

# ─── CARGA DE DATOS ────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def cargar_datos():
    try:
        response = requests.get(DOWNLOAD_URL, timeout=30)
        response.raise_for_status()
        excel_data = BytesIO(response.content)

        muestreo = pd.read_excel(excel_data, sheet_name="Muestreo")
        excel_data.seek(0)
        sticks = pd.read_excel(excel_data, sheet_name="StickRotos")

        muestreo["Fecha"] = pd.to_datetime(muestreo["Fecha"], errors="coerce")
        for col in ["PromedioLargo", "PromedioTorsiones", "Defectuosas", "Punta", "Cola"]:
            if col in muestreo.columns:
                muestreo[col] = pd.to_numeric(muestreo[col], errors="coerce").fillna(0)

        for j in range(1, 11):
            for prefix in ["Largo_", "Torsion_"]:
                col = f"{prefix}{j}"
                if col in muestreo.columns:
                    muestreo[col] = pd.to_numeric(muestreo[col], errors="coerce").fillna(0)

        muestreo["p"] = muestreo["Defectuosas"] / 10
        muestreo["np"] = muestreo["Defectuosas"]

        # Calcular Rango para Largo y Torsiones
        largos = [f"Largo_{j}" for j in range(1, 11) if f"Largo_{j}" in muestreo.columns]
        torsiones = [f"Torsion_{j}" for j in range(1, 11) if f"Torsion_{j}" in muestreo.columns]
        if largos:
            muestreo["RangoLargo"] = muestreo[largos].max(axis=1) - muestreo[largos].min(axis=1)
        if torsiones:
            muestreo["RangoTorsiones"] = muestreo[torsiones].max(axis=1) - muestreo[torsiones].min(axis=1)

        for col in ["Turno", "Maquina", "TipoMasa", "Tripa"]:
            if col in muestreo.columns:
                muestreo[col] = muestreo[col].astype(str)

        sticks["Fecha"] = pd.to_datetime(sticks["Fecha"], errors="coerce")
        sticks["TotalRotos"] = pd.to_numeric(sticks["TotalRotos"], errors="coerce").fillna(0)
        for col in ["Tripa23180_40", "Tripa23180_50", "Tripa21170_40", "Tripa21170_50"]:
            if col in sticks.columns:
                sticks[col] = pd.to_numeric(sticks[col], errors="coerce").fillna(0)
        if "Turno" in sticks.columns:
            sticks["Turno"] = sticks["Turno"].astype(str)
        if "Maquina" in sticks.columns:
            sticks["Maquina"] = sticks["Maquina"].astype(str)

        # Calcular U (defectos por unidad) para sticks
        if "CantidadTotal" in sticks.columns:
            sticks["U"] = sticks["TotalRotos"] / sticks["CantidadTotal"].replace(0, np.nan)
        else:
            sticks["U"] = sticks["TotalRotos"]

        return muestreo, sticks, None
    except Exception as e:
        return None, None, str(e)


# ─── HELPERS ───────────────────────────────────────────────────────────────
COLORES_TURNO = {"14": "#534AB7", "34": "#1d9e75", "38": "#D85A30"}
# Constante d2 para n=10
D2 = 3.078
# Constantes para carta R con n=10
D3 = 0.223
D4 = 1.777

def agregar_linea(fig, valor, nombre, color, dash="dash"):
    fig.add_hline(
        y=valor, line_color=color, line_dash=dash, line_width=1.5,
        annotation_text=f"  {nombre}: {valor:.3f}",
        annotation_font_color=color, annotation_position="right"
    )

def estilo_base(fig, titulo, ylabel, height=320):
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=14)),
        xaxis_title="Fecha",
        yaxis_title=ylabel,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=90, t=60, b=10),
        height=height,
        hovermode="x unified"
    )
    return fig


# ─── CARTA X̄ ────────────────────────────────────────────────────────────
def carta_xbarra(df, maquina, campo, titulo_extra, meta=None):
    df_m = df[df["Maquina"] == maquina].copy().sort_values("Fecha")
    if df_m.empty or campo not in df_m.columns:
        return None

    xbar  = df_m[campo].mean()
    sigma = df_m[campo].std()
    UCL   = xbar + 3 * sigma
    LCL   = xbar - 3 * sigma

    fig = go.Figure()
    for turno, color in COLORES_TURNO.items():
        d = df_m[df_m["Turno"] == turno].sort_values("Fecha")
        if d.empty: continue
        fig.add_trace(go.Scatter(x=d["Fecha"], y=d[campo],
            mode="lines+markers", name=f"Turno {turno}",
            line=dict(color=color, width=2), marker=dict(size=6)))

    agregar_linea(fig, UCL,  "UCL", "#e24b4a", "dash")
    agregar_linea(fig, LCL,  "LCL", "#e24b4a", "dash")
    agregar_linea(fig, xbar, "X̄",  "#185fa5", "dot")
    if meta: agregar_linea(fig, meta, "Meta", "#f39c12", "longdash")

    return estilo_base(fig, f"Carta X̄ — {titulo_extra} | {maquina}", titulo_extra)


# ─── CARTA R ────────────────────────────────────────────────────────────
def carta_r(df, maquina, campo_rango, titulo_extra):
    df_m = df[df["Maquina"] == maquina].copy().sort_values("Fecha")
    if df_m.empty or campo_rango not in df_m.columns:
        return None

    Rbar = df_m[campo_rango].mean()
    UCL  = D4 * Rbar
    LCL  = D3 * Rbar

    fig = go.Figure()
    for turno, color in COLORES_TURNO.items():
        d = df_m[df_m["Turno"] == turno].sort_values("Fecha")
        if d.empty: continue
        fig.add_trace(go.Scatter(x=d["Fecha"], y=d[campo_rango],
            mode="lines+markers", name=f"Turno {turno}",
            line=dict(color=color, width=2), marker=dict(size=6)))

    agregar_linea(fig, UCL,  "UCL", "#e24b4a", "dash")
    agregar_linea(fig, LCL,  "LCL", "#e24b4a", "dash")
    agregar_linea(fig, Rbar, "R̄",   "#185fa5", "dot")

    return estilo_base(fig, f"Carta R — {titulo_extra} | {maquina}", "Rango")


# ─── CARTA p ────────────────────────────────────────────────────────────
def carta_p(df, maquina, n=10):
    df_m = df[df["Maquina"] == maquina].copy().sort_values("Fecha")
    if df_m.empty: return None

    pb  = df_m["p"].mean()
    UCL = min(1.0, pb + 3 * np.sqrt(pb * (1 - pb) / n))
    LCL = max(0.0, pb - 3 * np.sqrt(pb * (1 - pb) / n))

    fig = go.Figure()
    for turno, color in COLORES_TURNO.items():
        d = df_m[df_m["Turno"] == turno].sort_values("Fecha")
        if d.empty: continue
        fig.add_trace(go.Scatter(x=d["Fecha"], y=d["p"],
            mode="lines+markers", name=f"Turno {turno}",
            line=dict(color=color, width=2),
            marker=dict(size=6, symbol=["x" if v > UCL else "circle" for v in d["p"]])))

    agregar_linea(fig, UCL, "UCL", "#e24b4a", "dash")
    agregar_linea(fig, LCL, "LCL", "#e24b4a", "dash")
    agregar_linea(fig, pb,  "p̄",   "#185fa5", "dot")
    fig.update_yaxes(tickformat=".1%")
    return estilo_base(fig, f"Carta p — % Rechazo | {maquina}", "Proporción defectuosa")


# ─── CARTA np ────────────────────────────────────────────────────────────
def carta_np(df, maquina, n=10):
    df_m = df[df["Maquina"] == maquina].copy().sort_values("Fecha")
    if df_m.empty: return None

    pb   = df_m["p"].mean()
    npb  = pb * n
    UCL  = npb + 3 * np.sqrt(npb * (1 - pb))
    LCL  = max(0.0, npb - 3 * np.sqrt(npb * (1 - pb)))

    fig = go.Figure()
    for turno, color in COLORES_TURNO.items():
        d = df_m[df_m["Turno"] == turno].sort_values("Fecha")
        if d.empty: continue
        fig.add_trace(go.Scatter(x=d["Fecha"], y=d["np"],
            mode="lines+markers", name=f"Turno {turno}",
            line=dict(color=color, width=2), marker=dict(size=6)))

    agregar_linea(fig, UCL, "UCL", "#e24b4a", "dash")
    agregar_linea(fig, LCL, "LCL", "#e24b4a", "dash")
    agregar_linea(fig, npb, "n̄p",  "#185fa5", "dot")
    return estilo_base(fig, f"Carta np — N° defectuosos | {maquina}", "N° defectuosos")


# ─── CARTA I (Individuales) ──────────────────────────────────────────────
def carta_i(df, maquina, campo, titulo_extra):
    df_m = df[df["Maquina"] == maquina].copy().sort_values("Fecha")
    if df_m.empty or campo not in df_m.columns:
        return None

    valores = df_m[campo].values
    xbar    = np.mean(valores)
    MR      = np.abs(np.diff(valores))
    MR_bar  = np.mean(MR) if len(MR) > 0 else 0
    UCL     = xbar + 3 * MR_bar / 1.128
    LCL     = xbar - 3 * MR_bar / 1.128

    fig = go.Figure()
    for turno, color in COLORES_TURNO.items():
        d = df_m[df_m["Turno"] == turno].sort_values("Fecha")
        if d.empty: continue
        fig.add_trace(go.Scatter(x=d["Fecha"], y=d[campo],
            mode="lines+markers", name=f"Turno {turno}",
            line=dict(color=color, width=2), marker=dict(size=6)))

    agregar_linea(fig, UCL,  "UCL", "#e24b4a", "dash")
    agregar_linea(fig, LCL,  "LCL", "#e24b4a", "dash")
    agregar_linea(fig, xbar, "X̄",   "#185fa5", "dot")
    return estilo_base(fig, f"Carta I — {titulo_extra} | {maquina}", titulo_extra)


# ─── CARTA MR ────────────────────────────────────────────────────────────
def carta_mr(df, maquina, campo, titulo_extra):
    df_m = df[df["Maquina"] == maquina].copy().sort_values("Fecha")
    if df_m.empty or campo not in df_m.columns:
        return None

    valores = df_m[campo].values
    MR      = np.concatenate([[np.nan], np.abs(np.diff(valores))])
    MR_bar  = np.nanmean(MR)
    UCL     = 3.267 * MR_bar
    LCL     = 0.0

    df_m = df_m.copy()
    df_m["MR"] = MR

    fig = go.Figure()
    for turno, color in COLORES_TURNO.items():
        d = df_m[df_m["Turno"] == turno].sort_values("Fecha")
        if d.empty: continue
        fig.add_trace(go.Scatter(x=d["Fecha"], y=d["MR"],
            mode="lines+markers", name=f"Turno {turno}",
            line=dict(color=color, width=2), marker=dict(size=6)))

    agregar_linea(fig, UCL,    "UCL", "#e24b4a", "dash")
    agregar_linea(fig, LCL,    "LCL", "#e24b4a", "dash")
    agregar_linea(fig, MR_bar, "M̄R",  "#185fa5", "dot")
    return estilo_base(fig, f"Carta MR — {titulo_extra} | {maquina}", "Rango móvil")


# ─── CARTA C ─────────────────────────────────────────────────────────────
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
        d = df[df["Turno"] == turno].sort_values("Fecha")
        if d.empty: continue
        fig.add_trace(go.Scatter(x=d["Fecha"], y=d["TotalRotos"],
            mode="lines+markers", name=f"Turno {turno}",
            line=dict(color=color, width=2), marker=dict(size=6)))

    agregar_linea(fig, UCL, "UCL", "#e24b4a", "dash")
    agregar_linea(fig, LCL, "LCL", "#e24b4a", "dash")
    agregar_linea(fig, cb,  "c̄",   "#185fa5", "dot")
    label = maquina if maquina else "Ambas máquinas"
    return estilo_base(fig, f"Carta C — Stick rotos | {label}", "Cantidad stick rotos")


# ─── CARTA U ─────────────────────────────────────────────────────────────
def carta_u(df_stick, maquina=None):
    df = df_stick.copy()
    if maquina:
        df = df[df["Maquina"] == maquina]
    df = df.sort_values("Fecha")
    if df.empty or "U" not in df.columns: return None

    ub  = df["U"].mean()
    n   = df["TotalRotos"].mean() if df["TotalRotos"].mean() > 0 else 1
    UCL = ub + 3 * np.sqrt(ub / n)
    LCL = max(0.0, ub - 3 * np.sqrt(ub / n))

    fig = go.Figure()
    for turno, color in COLORES_TURNO.items():
        d = df[df["Turno"] == turno].sort_values("Fecha")
        if d.empty: continue
        fig.add_trace(go.Scatter(x=d["Fecha"], y=d["U"],
            mode="lines+markers", name=f"Turno {turno}",
            line=dict(color=color, width=2), marker=dict(size=6)))

    agregar_linea(fig, UCL, "UCL", "#e24b4a", "dash")
    agregar_linea(fig, LCL, "LCL", "#e24b4a", "dash")
    agregar_linea(fig, ub,  "ū",   "#185fa5", "dot")
    label = maquina if maquina else "Ambas máquinas"
    return estilo_base(fig, f"Carta U — Stick rotos por unidad | {label}", "Rotos por unidad")


# ─── GRÁFICO LÍNEAS POR TURNO ──────────────────────────────────────────────
def grafico_lineas_turno(df_stick, columnas_tripa):
    df = df_stick.copy().sort_values("Fecha")
    if df.empty: return None

    df["TotalFiltrado"] = df[columnas_tripa].sum(axis=1) if columnas_tripa else df["TotalRotos"]

    fig = go.Figure()
    for turno, color in COLORES_TURNO.items():
        d = df[df["Turno"] == turno]
        if d.empty: continue
        fig.add_trace(go.Scatter(
            x=d["Fecha"], y=d["TotalFiltrado"], name=f"Turno {turno}",
            mode="lines+markers", line=dict(color=color, width=2),
            marker=dict(size=6)
        ))
    fig.update_layout(height=320,
                      title="Stick rotos por turno en el tiempo",
                      xaxis_title="Fecha", yaxis_title="Cantidad",
                      margin=dict(l=10,r=10,t=50,b=10),
                      hovermode="x unified",
                      legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1))
    return fig


# ─── GRÁFICO TOTAL ROTOS POR TURNO ─────────────────────────────────────────
def grafico_total_por_turno(df_stick, columnas_tripa):
    df = df_stick.copy()
    if df.empty: return None

    df["TotalFiltrado"] = df[columnas_tripa].sum(axis=1) if columnas_tripa else df["TotalRotos"]
    resumen = df.groupby("Turno")["TotalFiltrado"].sum().reset_index()
    resumen = resumen.sort_values("Turno")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=resumen["Turno"], y=resumen["TotalFiltrado"],
        marker_color=[COLORES_TURNO.get(t, "#888") for t in resumen["Turno"]],
        text=resumen["TotalFiltrado"], textposition="outside"
    ))
    fig.update_layout(height=320,
                      title="Total stick rotos por turno",
                      xaxis_title="Turno", yaxis_title="Cantidad total",
                      margin=dict(l=10,r=10,t=50,b=10))
    return fig
def grafico_sticks_apilado(df_stick, maquina=None):
    df = df_stick.copy()
    if maquina:
        df = df[df["Maquina"] == maquina]
    df = df.sort_values("Fecha")
    if df.empty: return None

    fig = go.Figure()
    for campo, nombre, color in [
        ("Tripa23180_40", "23-180 / 40cm", "#534AB7"),
        ("Tripa23180_50", "23-180 / 50cm", "#AFA9EC"),
        ("Tripa21170_40", "21-170 / 40cm", "#D85A30"),
        ("Tripa21170_50", "21-170 / 50cm", "#F0997B"),
    ]:
        if campo in df.columns:
            fig.add_trace(go.Scatter(
                x=df["Fecha"], y=df[campo], name=nombre,
                mode="lines+markers", line=dict(color=color, width=2),
                marker=dict(size=6)
            ))
    fig.update_layout(height=320,
                      title="Comparativo stick rotos por tipo de tripa",
                      xaxis_title="Fecha", yaxis_title="Cantidad",
                      margin=dict(l=10,r=10,t=50,b=10),
                      hovermode="x unified",
                      legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1))
    return fig


# ═══════════════════════════════════════════════════════════════════════════
#  CARGA
# ═══════════════════════════════════════════════════════════════════════════
with st.spinner("Cargando datos desde OneDrive..."):
    muestreo, sticks, error = cargar_datos()

if error:
    st.error(f"❌ Error al cargar datos: {error}")
    st.stop()

if muestreo is None or muestreo.empty:
    st.warning("⚠️ No se encontraron datos.")
    st.stop()

st.success(f"✅ {len(muestreo)} registros de muestreo | {len(sticks) if sticks is not None else 0} registros de stick rotos")

if st.button("🔄 Actualizar datos"):
    st.cache_data.clear()
    st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
#  FILTROS
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
#  KPIs
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("### 📊 Resumen del período")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Registros",         len(df_filtrado))
k2.metric("Prom. largo",       f"{df_filtrado['PromedioLargo'].mean():.2f} cm" if not df_filtrado.empty else "—")
k3.metric("Prom. torsiones",   f"{df_filtrado['PromedioTorsiones'].mean():.1f}" if not df_filtrado.empty else "—")
k4.metric("% rechazo prom.",   f"{df_filtrado['p'].mean()*100:.1f}%" if not df_filtrado.empty else "—")
k5.metric("Total stick rotos", int(sticks["TotalRotos"].sum()) if sticks is not None and not sticks.empty else "—")
st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════
#  PESTAÑAS
# ═══════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📏 X̄-R Largo",
    "🔄 X̄-R Torsiones",
    "📉 p-np Rechazo",
    "📐 I-MR Punta y Cola",
    "🔩 C-U Stick rotos"
])

# ── TAB 1: X̄-R Largo ──────────────────────────────────────────────────────
with tab1:
    st.markdown("**Carta X̄-R — Largo de vienesa (cm)**")
    for maq in ["VEMAG 1", "VEMAG 2"]:
        st.markdown(f"##### {maq}")
        c1, c2 = st.columns(2)
        with c1:
            fig = carta_xbarra(df_filtrado, maq, "PromedioLargo", "Largo (cm)", meta=14.5)
            if fig: st.plotly_chart(fig, use_container_width=True)
            else:   st.info(f"Sin datos para {maq}")
        with c2:
            fig = carta_r(df_filtrado, maq, "RangoLargo", "Largo (cm)")
            if fig: st.plotly_chart(fig, use_container_width=True)
            else:   st.info(f"Sin datos para {maq}")

# ── TAB 2: X̄-R Torsiones ──────────────────────────────────────────────────
with tab2:
    st.markdown("**Carta X̄-R — Torsiones**")
    for maq in ["VEMAG 1", "VEMAG 2"]:
        st.markdown(f"##### {maq}")
        c1, c2 = st.columns(2)
        with c1:
            fig = carta_xbarra(df_filtrado, maq, "PromedioTorsiones", "Torsiones", meta=2.0)
            if fig: st.plotly_chart(fig, use_container_width=True)
            else:   st.info(f"Sin datos para {maq}")
        with c2:
            fig = carta_r(df_filtrado, maq, "RangoTorsiones", "Torsiones")
            if fig: st.plotly_chart(fig, use_container_width=True)
            else:   st.info(f"Sin datos para {maq}")

# ── TAB 3: p-np ────────────────────────────────────────────────────────────
with tab3:
    st.markdown("**Carta p-np — Proporción y número de vienesas rechazadas**")
    for maq in ["VEMAG 1", "VEMAG 2"]:
        st.markdown(f"##### {maq}")
        c1, c2 = st.columns(2)
        with c1:
            fig = carta_p(df_filtrado, maq)
            if fig: st.plotly_chart(fig, use_container_width=True)
            else:   st.info(f"Sin datos para {maq}")
        with c2:
            fig = carta_np(df_filtrado, maq)
            if fig: st.plotly_chart(fig, use_container_width=True)
            else:   st.info(f"Sin datos para {maq}")

# ── TAB 4: I-MR Punta y Cola ──────────────────────────────────────────────
with tab4:
    st.markdown("**Carta I-MR — Punta y Cola (mediciones individuales)**")
    for maq in ["VEMAG 1", "VEMAG 2"]:
        st.markdown(f"##### {maq}")
        for campo, label in [("Punta", "Punta"), ("Cola", "Cola")]:
            if campo in df_filtrado.columns:
                st.markdown(f"**{label}**")
                c1, c2 = st.columns(2)
                with c1:
                    fig = carta_i(df_filtrado, maq, campo, label)
                    if fig: st.plotly_chart(fig, use_container_width=True)
                    else:   st.info(f"Sin datos para {maq}")
                with c2:
                    fig = carta_mr(df_filtrado, maq, campo, label)
                    if fig: st.plotly_chart(fig, use_container_width=True)
                    else:   st.info(f"Sin datos para {maq}")

# ── TAB 5: C-U Sticks ─────────────────────────────────────────────────────
with tab5:
    if sticks is None or sticks.empty:
        st.info("Sin datos de stick rotos aún.")
    else:
        df_stick_f = sticks.copy()
        if turnos_sel:
            df_stick_f = df_stick_f[df_stick_f["Turno"].isin([str(t) for t in turnos_sel])]

        st.markdown("**Carta C-U — Stick rotos**")
        for maq in ["VEMAG 1", "VEMAG 2"]:
            st.markdown(f"##### {maq}")
            c1, c2 = st.columns(2)
            with c1:
                fig = carta_c(df_stick_f, maq)
                if fig: st.plotly_chart(fig, use_container_width=True)
            with c2:
                fig = carta_u(df_stick_f, maq)
                if fig: st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Comparativo stick rotos por tipo de tripa**")
        turno_bar_sel = st.multiselect("Filtrar gráfico por turno", turnos_disp, default=turnos_disp, key="turno_bar")
        df_stick_bar = df_stick_f[df_stick_f["Turno"].isin(turno_bar_sel)] if turno_bar_sel else df_stick_f
        fig_bar = grafico_sticks_apilado(df_stick_bar)
        if fig_bar: st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("---")
        st.markdown("**Stick rotos por turno en el tiempo**")
        tripas_disp2 = {
            "23-180 / 40cm": "Tripa23180_40",
            "23-180 / 50cm": "Tripa23180_50",
            "21-170 / 40cm": "Tripa21170_40",
            "21-170 / 50cm": "Tripa21170_50",
        }
        tripas_disp2_ok = {k: v for k, v in tripas_disp2.items() if v in df_stick_f.columns}
        tripa_sel2 = st.multiselect("Filtrar por tipo de tripa", list(tripas_disp2_ok.keys()),
                                     default=list(tripas_disp2_ok.keys()), key="tripa_lineas_turno")
        columnas_sel2 = [tripas_disp2_ok[t] for t in tripa_sel2]
        fig_lineas_turno = grafico_lineas_turno(df_stick_f, columnas_sel2)
        if fig_lineas_turno: st.plotly_chart(fig_lineas_turno, use_container_width=True)

        st.markdown("---")
        st.markdown("**Total stick rotos por turno**")
        tripas_disp = {
            "23-180 / 40cm": "Tripa23180_40",
            "23-180 / 50cm": "Tripa23180_50",
            "21-170 / 40cm": "Tripa21170_40",
            "21-170 / 50cm": "Tripa21170_50",
        }
        tripas_disp_ok = {k: v for k, v in tripas_disp.items() if v in df_stick_f.columns}
        tripa_sel = st.multiselect("Filtrar por tipo de tripa", list(tripas_disp_ok.keys()),
                                    default=list(tripas_disp_ok.keys()), key="tripa_turno")
        columnas_sel = [tripas_disp_ok[t] for t in tripa_sel]
        fig_turno = grafico_total_por_turno(df_stick_f, columnas_sel)
        if fig_turno: st.plotly_chart(fig_turno, use_container_width=True)
