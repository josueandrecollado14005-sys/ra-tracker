import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, date, time
import io

# ─── CONFIG ───────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RA Productivity Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

COLORES = {
    "Estimación (Regresiones/Gráficos)":         "#185FA5",
    "Debugging (solución de errores)":            "#3B6D11",
    "Data Wrangling (Limpieza/Merges)":           "#854F0B",
    "Curva de Aprendizaje (Lectura/Sintaxis)":    "#3C3489",
    "Reuniones y Preparación":                    "#A32D2D",
    "Reportes/ actualizaciones":                  "#0F6E56",
    "Otros":                                      "#888780",
}

PROYECTOS = {"Fintech": "#185FA5", "MFI": "#3B6D11", "LRC": "#854F0B", "Otros": "#888780"}

META_SEMANAL = 40.0

st.markdown("""
<style>
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 16px 20px;
        border: 1px solid #e9ecef;
    }
    .metric-val { font-size: 28px; font-weight: 600; color: #1a1a2e; }
    .metric-lbl { font-size: 12px; color: #6c757d; margin-top: 2px; }
    .metric-delta-pos { font-size: 12px; color: #3B6D11; font-weight: 500; }
    .metric-delta-neg { font-size: 12px; color: #A32D2D; font-weight: 500; }
    .section-header {
        font-size: 15px; font-weight: 600; color: #1a1a2e;
        border-left: 3px solid #185FA5;
        padding-left: 10px; margin: 24px 0 12px;
    }
    .stTabs [data-baseweb="tab"] { font-size: 14px; }
    div[data-testid="stSidebar"] { background: #1a1a2e; }
    div[data-testid="stSidebar"] * { color: #f0f0f0 !important; }
    div[data-testid="stSidebar"] .stSelectbox label,
    div[data-testid="stSidebar"] .stMultiSelect label,
    div[data-testid="stSidebar"] .stNumberInput label { color: #adb5bd !important; }
</style>
""", unsafe_allow_html=True)


# ─── FUNCIONES ────────────────────────────────────────────────────────────────

def parse_horas(val):
    try:
        return float(str(val).replace(",", "."))
    except:
        return 0.0

def load_data(file=None):
    if file is not None:
        df = pd.read_csv(file)
    else:
        return pd.DataFrame(columns=["Fecha","Proyecto","Tipo de tarea",
                                      "task description","Minutos netos",
                                      "Horas Reales","Estado","Semana",
                                      "Hora inicio","Hora fin"])
    df.columns = df.columns.str.strip()
    df["Proyecto"] = df["Proyecto"].str.strip()
    df["Tipo de tarea"] = df["Tipo de tarea"].str.strip()
    df["Estado"] = df["Estado"].str.strip()
    df["Horas Reales"] = df["Horas Reales"].apply(parse_horas)
    df["Minutos netos"] = pd.to_numeric(df["Minutos netos"], errors="coerce").fillna(0)
    if "Hora inicio" not in df.columns:
        df["Hora inicio"] = None
    if "Hora fin" not in df.columns:
        df["Hora fin"] = None
    df = df.dropna(subset=["Semana","Tipo de tarea"])
    df["Semana"] = df["Semana"].astype(int)
    return df

def save_df_to_csv(df):
    return df.to_csv(index=False).encode("utf-8")

def bloque_horario(hora_str):
    try:
        h = int(str(hora_str).split(":")[0])
        if 5 <= h < 9:   return "Madrugada (5–9)"
        if 9 <= h < 13:  return "Mañana (9–13)"
        if 13 <= h < 17: return "Tarde (13–17)"
        if 17 <= h < 21: return "Noche temprana (17–21)"
        return "Noche (21+)"
    except:
        return "Sin horario"

def eficiencia(minutos_netos, minutos_totales):
    if minutos_totales == 0:
        return 0
    return round((minutos_netos / minutos_totales) * 100, 1)

# ─── SESSION STATE ─────────────────────────────────────────────────────────────
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(columns=["Fecha","Proyecto","Tipo de tarea",
                                                  "task description","Minutos netos",
                                                  "Horas Reales","Estado","Semana",
                                                  "Hora inicio","Hora fin"])
if "semana_actual" not in st.session_state:
    st.session_state.semana_actual = datetime.now().isocalendar()[1]

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 RA Tracker")
    st.markdown("---")

    uploaded = st.file_uploader("Cargar CSV existente", type=["csv"])
    if uploaded:
        st.session_state.df = load_data(uploaded)
        st.success(f"{len(st.session_state.df)} registros cargados")

    st.markdown("---")
    st.markdown("**Meta semanal**")
    meta = st.number_input("Horas / semana", value=META_SEMANAL, step=0.5, min_value=1.0)

    st.markdown("---")
    st.markdown("**Exportar datos**")
    if len(st.session_state.df) > 0:
        csv_bytes = save_df_to_csv(st.session_state.df)
        st.download_button("⬇ Descargar CSV", csv_bytes,
                           file_name="tracker_ra.csv", mime="text/csv")

# ─── HEADER ───────────────────────────────────────────────────────────────────
st.markdown("# RA Productivity Tracker")
st.markdown("Registro y análisis de horas de investigación · Prof. Burga")

df = st.session_state.df
tab_reg, tab_dash, tab_analisis = st.tabs(["📝  Registro", "📊  Dashboard", "🔬  Análisis profundo"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — REGISTRO
# ══════════════════════════════════════════════════════════════════════════════
with tab_reg:
    st.markdown('<div class="section-header">Registrar nueva sesión de trabajo</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        fecha = st.date_input("Fecha", value=date.today())
        proyecto = st.selectbox("Proyecto", ["Fintech", "MFI", "LRC", "Otros"])
    with col2:
        tipo = st.selectbox("Tipo de tarea", list(COLORES.keys()))
        estado = st.selectbox("Estado", ["Terminado", "En Proceso", "Bloqueado"])
    with col3:
        hora_ini = st.time_input("Hora inicio", value=time(7, 0))
        hora_fin = st.time_input("Hora fin", value=time(9, 0))

    descripcion = st.text_area("Descripción de la tarea", height=80,
                                placeholder="¿Qué hiciste exactamente? Ej: Debugging del merge ubigeo en panel MFI 2002-2012")

    # calcular minutos automáticamente
    dt_ini = datetime.combine(date.today(), hora_ini)
    dt_fin = datetime.combine(date.today(), hora_fin)
    minutos_calc = max(int((dt_fin - dt_ini).total_seconds() / 60), 0)
    horas_calc = round(minutos_calc / 60, 3)

    col_a, col_b, col_c = st.columns([1,1,2])
    with col_a:
        st.metric("Minutos calculados", minutos_calc)
    with col_b:
        st.metric("Horas calculadas", f"{horas_calc:.2f}h")
    with col_c:
        semana_num = fecha.isocalendar()[1]
        st.metric("Semana ISO", semana_num)

    if st.button("➕ Agregar registro", type="primary", use_container_width=True):
        if descripcion.strip() == "":
            st.warning("Agrega una descripción antes de guardar.")
        elif minutos_calc <= 0:
            st.warning("La hora de fin debe ser posterior a la de inicio.")
        else:
            nuevo = {
                "Fecha": fecha.strftime("%d/%m"),
                "Proyecto": proyecto,
                "Tipo de tarea": tipo,
                "task description": descripcion,
                "Minutos netos": minutos_calc,
                "Horas Reales": horas_calc,
                "Estado": estado,
                "Semana": semana_num,
                "Hora inicio": str(hora_ini),
                "Hora fin": str(hora_fin),
            }
            st.session_state.df = pd.concat(
                [st.session_state.df, pd.DataFrame([nuevo])], ignore_index=True
            )
            st.success(f"✅ Registrado: {horas_calc:.2f}h de {tipo} en {proyecto}")

    # Tabla de registros recientes
    if len(df) > 0:
        st.markdown('<div class="section-header">Registros recientes</div>', unsafe_allow_html=True)
        semanas_disp = sorted(df["Semana"].unique(), reverse=True)
        sem_sel = st.selectbox("Filtrar por semana", ["Todas"] + [f"Semana {s}" for s in semanas_disp])

        df_view = df.copy()
        if sem_sel != "Todas":
            s = int(sem_sel.split(" ")[1])
            df_view = df_view[df_view["Semana"] == s]

        df_show = df_view[["Fecha","Semana","Proyecto","Tipo de tarea",
                            "task description","Minutos netos","Horas Reales","Estado"]].copy()
        df_show["Horas Reales"] = df_show["Horas Reales"].apply(lambda x: f"{x:.2f}h")
        df_show["Minutos netos"] = df_show["Minutos netos"].apply(lambda x: f"{int(x)} min")

        st.dataframe(df_show, use_container_width=True, height=320,
                     column_config={
                         "task description": st.column_config.TextColumn("Descripción", width="large"),
                         "Tipo de tarea": st.column_config.TextColumn("Tipo", width="medium"),
                     })


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with tab_dash:
    if len(df) == 0:
        st.info("Carga un CSV o agrega registros en la pestaña Registro.")
    else:
        semanas = sorted(df["Semana"].unique())
        sem_dash = st.selectbox("Semana a analizar", semanas, index=len(semanas)-1, key="sem_dash")
        df_sem = df[df["Semana"] == sem_dash]
        df_prev = df[df["Semana"] == sem_dash - 1] if (sem_dash - 1) in df["Semana"].values else pd.DataFrame()

        h_sem = df_sem["Horas Reales"].sum()
        h_prev = df_prev["Horas Reales"].sum() if len(df_prev) > 0 else 0
        cumplimiento = round((h_sem / meta) * 100, 1)
        sesiones = len(df_sem)
        avg_sesion = round(df_sem["Minutos netos"].mean(), 0) if sesiones > 0 else 0
        h_faltantes = max(meta - h_sem, 0)
        delta_prev = round(h_sem - h_prev, 2)

        # KPI row
        st.markdown('<div class="section-header">KPIs de la semana</div>', unsafe_allow_html=True)
        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            st.metric("Horas trabajadas", f"{h_sem:.1f}h",
                      delta=f"{delta_prev:+.1f}h vs sem anterior")
        with k2:
            st.metric("Cumplimiento meta", f"{cumplimiento}%",
                      delta=f"Meta: {meta}h")
        with k3:
            st.metric("Sesiones", sesiones)
        with k4:
            st.metric("Duración media sesión", f"{int(avg_sesion)} min")
        with k5:
            st.metric("Horas restantes", f"{h_faltantes:.1f}h")

        # Progress bar
        prog = min(h_sem / meta, 1.0)
        color = "#3B6D11" if prog >= 1 else "#185FA5" if prog >= 0.7 else "#A32D2D"
        st.markdown(f"""
        <div style="margin: 8px 0 20px;">
            <div style="font-size:12px;color:#666;margin-bottom:4px;">
                Progreso semanal: {h_sem:.1f}h / {meta}h
            </div>
            <div style="background:#e9ecef;border-radius:8px;height:14px;overflow:hidden;">
                <div style="background:{color};width:{prog*100:.1f}%;height:100%;border-radius:8px;
                            transition:width 0.5s;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_l, col_r = st.columns(2)

        with col_l:
            st.markdown('<div class="section-header">Horas por tipo de tarea</div>', unsafe_allow_html=True)
            tipo_data = df_sem.groupby("Tipo de tarea")["Horas Reales"].sum().reset_index()
            tipo_data = tipo_data.sort_values("Horas Reales", ascending=True)
            fig_tipo = px.bar(tipo_data, x="Horas Reales", y="Tipo de tarea",
                              orientation="h",
                              color="Tipo de tarea",
                              color_discrete_map=COLORES,
                              text="Horas Reales")
            fig_tipo.update_traces(texttemplate="%{text:.2f}h", textposition="outside")
            fig_tipo.update_layout(showlegend=False, margin=dict(l=0,r=20,t=10,b=0),
                                   height=280, xaxis_title="Horas",
                                   plot_bgcolor="white", paper_bgcolor="white",
                                   yaxis_title="")
            st.plotly_chart(fig_tipo, use_container_width=True)

        with col_r:
            st.markdown('<div class="section-header">Horas por proyecto</div>', unsafe_allow_html=True)
            proy_data = df_sem.groupby("Proyecto")["Horas Reales"].sum().reset_index()
            fig_proy = px.pie(proy_data, values="Horas Reales", names="Proyecto",
                              color="Proyecto", color_discrete_map=PROYECTOS,
                              hole=0.45)
            fig_proy.update_traces(textinfo="label+percent+value",
                                   texttemplate="%{label}<br>%{value:.1f}h (%{percent})")
            fig_proy.update_layout(showlegend=False, margin=dict(l=0,r=0,t=10,b=0),
                                   height=280, plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig_proy, use_container_width=True)

        # Evolución semanal
        st.markdown('<div class="section-header">Evolución semanal de horas</div>', unsafe_allow_html=True)
        evo = df.groupby("Semana")["Horas Reales"].sum().reset_index()
        evo["Meta"] = meta
        fig_evo = go.Figure()
        fig_evo.add_trace(go.Bar(x=evo["Semana"], y=evo["Horas Reales"],
                                  name="Horas trabajadas",
                                  marker_color="#185FA5",
                                  text=evo["Horas Reales"].apply(lambda x: f"{x:.1f}h"),
                                  textposition="outside"))
        fig_evo.add_trace(go.Scatter(x=evo["Semana"], y=evo["Meta"],
                                      mode="lines", name=f"Meta ({meta}h)",
                                      line=dict(color="#A32D2D", dash="dash", width=2)))
        fig_evo.update_layout(height=280, margin=dict(l=0,r=0,t=10,b=0),
                               xaxis_title="Semana", yaxis_title="Horas",
                               plot_bgcolor="white", paper_bgcolor="white",
                               legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig_evo, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — ANÁLISIS PROFUNDO
# ══════════════════════════════════════════════════════════════════════════════
with tab_analisis:
    if len(df) == 0:
        st.info("Carga un CSV o agrega registros en la pestaña Registro.")
    else:
        st.markdown('<div class="section-header">Distribución por bloque horario</div>', unsafe_allow_html=True)

        df_h = df.dropna(subset=["Hora inicio"]).copy()
        if len(df_h) > 0:
            df_h["Bloque"] = df_h["Hora inicio"].apply(bloque_horario)
            bloque_data = df_h.groupby("Bloque")["Horas Reales"].sum().reset_index()
            orden_bloques = ["Madrugada (5–9)", "Mañana (9–13)",
                             "Tarde (13–17)", "Noche temprana (17–21)", "Noche (21+)"]
            bloque_data["Bloque"] = pd.Categorical(bloque_data["Bloque"],
                                                    categories=orden_bloques, ordered=True)
            bloque_data = bloque_data.sort_values("Bloque")
            fig_bloque = px.bar(bloque_data, x="Bloque", y="Horas Reales",
                                color_discrete_sequence=["#3C3489"],
                                text="Horas Reales")
            fig_bloque.update_traces(texttemplate="%{text:.1f}h", textposition="outside")
            fig_bloque.update_layout(height=260, margin=dict(l=0,r=0,t=10,b=0),
                                     plot_bgcolor="white", paper_bgcolor="white",
                                     xaxis_title="", yaxis_title="Horas")
            st.plotly_chart(fig_bloque, use_container_width=True)
        else:
            st.info("Agrega hora de inicio en nuevos registros para ver análisis por bloque horario.")

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown('<div class="section-header">Duración media de sesión por tipo</div>', unsafe_allow_html=True)
            avg_tipo = df.groupby("Tipo de tarea")["Minutos netos"].mean().reset_index()
            avg_tipo.columns = ["Tipo de tarea", "Minutos promedio"]
            avg_tipo = avg_tipo.sort_values("Minutos promedio", ascending=True)
            fig_avg = px.bar(avg_tipo, x="Minutos promedio", y="Tipo de tarea",
                             orientation="h", color="Tipo de tarea",
                             color_discrete_map=COLORES, text="Minutos promedio")
            fig_avg.update_traces(texttemplate="%{text:.0f} min", textposition="outside")
            fig_avg.update_layout(showlegend=False, height=280,
                                   margin=dict(l=0,r=20,t=10,b=0),
                                   plot_bgcolor="white", paper_bgcolor="white",
                                   xaxis_title="Minutos", yaxis_title="")
            st.plotly_chart(fig_avg, use_container_width=True)

        with col_b:
            st.markdown('<div class="section-header">Estado de tareas</div>', unsafe_allow_html=True)
            estado_data = df.groupby("Estado").agg(
                Sesiones=("Estado","count"),
                Horas=("Horas Reales","sum")
            ).reset_index()
            fig_est = px.bar(estado_data, x="Estado", y="Horas",
                             color="Estado",
                             color_discrete_map={
                                 "Terminado": "#3B6D11",
                                 "En Proceso": "#185FA5",
                                 "Bloqueado": "#A32D2D"
                             },
                             text="Horas")
            fig_est.update_traces(texttemplate="%{text:.1f}h", textposition="outside")
            fig_est.update_layout(showlegend=False, height=280,
                                   margin=dict(l=0,r=0,t=10,b=0),
                                   plot_bgcolor="white", paper_bgcolor="white",
                                   xaxis_title="", yaxis_title="Horas")
            st.plotly_chart(fig_est, use_container_width=True)

        # Heatmap semana x tipo
        st.markdown('<div class="section-header">Heatmap: horas por semana y tipo de tarea</div>', unsafe_allow_html=True)
        pivot = df.pivot_table(index="Tipo de tarea", columns="Semana",
                                values="Horas Reales", aggfunc="sum", fill_value=0)
        fig_heat = px.imshow(pivot, color_continuous_scale="Blues",
                              labels=dict(x="Semana", y="Tipo de tarea", color="Horas"),
                              aspect="auto", text_auto=".1f")
        fig_heat.update_layout(height=300, margin=dict(l=0,r=0,t=10,b=0),
                                plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_heat, use_container_width=True)

        # Tabla resumen por semana
        st.markdown('<div class="section-header">Resumen por semana</div>', unsafe_allow_html=True)
        resumen = df.groupby("Semana").agg(
            Horas_totales=("Horas Reales","sum"),
            Sesiones=("Horas Reales","count"),
            Avg_sesion_min=("Minutos netos","mean"),
            Proyectos=("Proyecto", lambda x: ", ".join(sorted(x.dropna().unique())))
        ).reset_index()
        resumen["Cumplimiento"] = (resumen["Horas_totales"] / meta * 100).round(1).astype(str) + "%"
        resumen["Horas_totales"] = resumen["Horas_totales"].apply(lambda x: f"{x:.1f}h")
        resumen["Avg_sesion_min"] = resumen["Avg_sesion_min"].apply(lambda x: f"{x:.0f} min")
        resumen.columns = ["Semana","Horas totales","Sesiones","Avg. sesión","Proyectos","Cumplimiento"]
        st.dataframe(resumen, use_container_width=True, hide_index=True)