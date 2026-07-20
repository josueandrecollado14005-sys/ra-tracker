"""
RA Productivity Tracker — v4.1 (Minutos dinámicos y Fix Plotly)
- Plan semanal personalizado por semana (modo horas rápidas o horario por bloques exactos)
- Rango de fechas legible por semana ISO (Semana del X al Y de <mes> de <año>)
- Horario visual (tabla dinámica HH:MM) + timeline tipo Gantt del plan
- Medidor/gauge de progreso semanal (real vs plan) corregido
- Comparación diaria plan vs real · Cierre dominical automático
- Proyectos y tipos de tarea configurables
- Persistencia en Supabase (funciona en todos los dispositivos)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, time, timedelta
import pytz
import json

st.set_page_config(page_title="RA Tracker", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")

# ─── SUPABASE ────────────────────────────────────────────────────────────────
# ─── SUPABASE ────────────────────────────────────────────────────────────────
@st.cache_resource
def get_supabase():
    try:
        from supabase import create_client
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"⚠️ Error detallado de Supabase: {e}")
        return None

sb = get_supabase()
USE_DB = sb is not None

# ─── CONSTANTES ───────────────────────────────────────────────────────────────
def get_now_peru():
    tz_peru = pytz.timezone('America/Lima')
    return datetime.now(tz_peru)

DIAS = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
MESES = ["enero","febrero","marzo","abril","mayo","junio",
         "julio","agosto","septiembre","octubre","noviembre","diciembre"]

DEFAULT_PROYECTOS   = ["Fintech","MFI","LRC","Otros"]
DEFAULT_TIPOS       = [
    "Estimación (Regresiones/Gráficos)",
    "Debugging (solución de errores)",
    "Data Wrangling (Limpieza/Merges)",
    "Curva de Aprendizaje (Lectura/Sintaxis)",
    "Reuniones y Preparación",
    "Reportes/ actualizaciones",
]

COLORES_BASE = ["#185FA5","#3B6D11","#854F0B","#3C3489",
                "#A32D2D","#0F6E56","#888780","#C47B00","#5E3A8C","#1A7A6E"]

CHART = dict(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
             font_color="#e0e0e0", margin=dict(l=0,r=20,t=10,b=0))
GRID  = dict(gridcolor="#2a2a3e")

st.markdown("""<style>
.section-header{font-size:15px;font-weight:600;border-left:3px solid #185FA5;
  padding-left:10px;margin:24px 0 12px}
.pill{background:#185FA540;color:#B5D4F4;font-size:11px;
  padding:2px 10px;border-radius:20px;display:inline-block;margin:2px}
.db-ok{color:#3B6D11;font-size:12px;font-weight:600}
.db-no{color:#A32D2D;font-size:12px;font-weight:600}
.week-banner{background:linear-gradient(90deg,#185FA530,#3C348920);
  border:1px solid #185FA540;border-radius:10px;padding:10px 16px;margin:6px 0 14px}
.week-banner b{color:#B5D4F4;font-size:16px}
</style>""", unsafe_allow_html=True)

# ─── HELPERS DB / SESSION STATE ───────────────────────────────────────────────

def _init_state():
    defaults = {
        "sessions":    [],    
        "planes":      {},    
        "proyectos":   list(DEFAULT_PROYECTOS),
        "tipos":       list(DEFAULT_TIPOS),
    }
    for k,v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ── Sesiones ──────────────────────────────────────────────────────────────────
def load_sessions():
    if USE_DB:
        try:
            r = sb.table("sessions").select("*").execute()
            return r.data or []
        except: pass
    return st.session_state.sessions

def save_session(row: dict):
    if USE_DB:
        try:
            sb.table("sessions").insert(row).execute()
            return
        except: pass
    st.session_state.sessions.append(row)

def delete_session(sid):
    if USE_DB:
        try:
            sb.table("sessions").delete().eq("id", sid).execute()
            return
        except: pass
    st.session_state.sessions = [s for s in st.session_state.sessions if s.get("id") != sid]

# ── Planes semanales ──────────────────────────────────────────────────────────
def load_planes():
    if USE_DB:
        try:
            r = sb.table("planes").select("*").execute()
            planes = {}
            for row in (r.data or []):
                planes[row["semana"]] = json.loads(row["datos"])
            return planes
        except: pass
    return st.session_state.planes

def save_plan(semana: int, datos: dict):
    if USE_DB:
        try:
            sb.table("planes").upsert(
                {"semana": semana, "datos": json.dumps(datos)},
                on_conflict="semana"
            ).execute()
            return
        except: pass
    st.session_state.planes[semana] = datos

# ── Normalización de planes ───────────────────────────────────────────────────
def _norm_plan(plan):
    if not plan:
        return {"horas": {}, "bloques": {}, "modo": "rapido"}
    if isinstance(plan, dict) and "horas" in plan and isinstance(plan.get("horas"), dict):
        # Transforma bloques legacy (enteros) al nuevo formato ("HH:MM")
        bloques_raw = plan.get("bloques", {}) or {}
        bloques_str = {}
        for d, segs in bloques_raw.items():
            bloques_str[d] = []
            for seg in segs:
                if len(seg) == 2:
                    ini = f"{int(seg[0]):02d}:00" if isinstance(seg[0], (int, float)) else seg[0]
                    fin = f"{int(seg[1]):02d}:00" if isinstance(seg[1], (int, float)) else seg[1]
                    bloques_str[d].append([ini, fin])

        return {"horas": plan.get("horas", {}) or {},
                "bloques": bloques_str,
                "modo": plan.get("modo", "rapido")}
    return {"horas": {k: float(v) for k, v in plan.items() if k in DIAS},
            "bloques": {}, "modo": "rapido"}

def plan_horas_dia(plan, dia):
    return float(_norm_plan(plan)["horas"].get(dia, 0.0))

def plan_total_h(plan):
    return float(sum(_norm_plan(plan)["horas"].values()))

# ── Rango de fechas de una semana ISO ─────────────────────────────────────────
def rango_semana(sem, year):
    try:
        lun = date.fromisocalendar(int(year), int(sem), 1)
        dom = date.fromisocalendar(int(year), int(sem), 7)
    except (ValueError, TypeError):
        return None, None, ""
    if lun.month == dom.month:
        txt = f"{lun.day} al {dom.day} de {MESES[lun.month-1]} de {lun.year}"
    elif lun.year == dom.year:
        txt = (f"{lun.day} de {MESES[lun.month-1]} al "
               f"{dom.day} de {MESES[dom.month-1]} de {lun.year}")
    else:
        txt = (f"{lun.day} de {MESES[lun.month-1]} {lun.year} al "
               f"{dom.day} de {MESES[dom.month-1]} {dom.year}")
    return lun, dom, txt

def parse_h(v):
    try: return float(str(v).replace(",","."))
    except: return 0.0

def bloque(h_str):
    try:
        h = int(str(h_str).split(":")[0])
        if h < 9:  return "Madrugada (<9h)"
        if h < 13: return "Mañana (9–13h)"
        if h < 17: return "Tarde (13–17h)"
        if h < 21: return "Noche (17–21h)"
        return "Noche tarde (21h+)"
    except: return "Sin horario"

def color_for(i): return COLORES_BASE[i % len(COLORES_BASE)]

def sessions_to_df(sessions):
    if not sessions: return pd.DataFrame()
    df = pd.DataFrame(sessions)
    df["Horas"] = df["Horas"].apply(parse_h)
    df["Minutos"] = pd.to_numeric(df.get("Minutos",0), errors="coerce").fillna(0)
    df["Semana"] = pd.to_numeric(df["Semana"], errors="coerce").fillna(0).astype(int)

    dias_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    def extraer_dia(fila):
        dia_actual = str(fila.get("Dia", "")).strip()
        if dia_actual and dia_actual.lower() not in ["nan", "none", ""]:
            d = dia_actual.capitalize()
            return d.replace("Miercoles", "Miércoles").replace("Sabado", "Sábado")
        fecha_str = str(fila.get("Fecha", "")).strip()
        if "/" in fecha_str:
            try:
                if fecha_str.count("/") == 1:
                    fecha_str += "/2026"
                dt = pd.to_datetime(fecha_str, format="%d/%m/%Y")
                return dias_es[dt.weekday()]
            except:
                pass
        return "Sin Día"

    df["Dia"] = df.apply(extraer_dia, axis=1)
    return df

def is_domingo():
    return get_now_peru().weekday() == 6

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 RA Tracker")
    if USE_DB:
        st.markdown('<span class="db-ok">● Conectado a Supabase</span>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<span class="db-no">● Sin BD — datos solo en esta sesión</span>',
                    unsafe_allow_html=True)
        st.caption("Configura Supabase en secrets.toml para sincronizar entre dispositivos.")

    st.markdown("---")
    up = st.file_uploader("Importar CSV antiguo", type=["csv"])
    if up:
        df_imp = pd.read_csv(up)
        df_imp.columns = df_imp.columns.str.strip()
        imported = 0
        for _, row in df_imp.iterrows():
            s = {
                "id": str(datetime.now().timestamp()) + str(imported),
                "Fecha": str(row.get("Fecha","")),
                "Semana": int(row.get("Semana",0)),
                "Dia": str(row.get("Día semana", row.get("Dia",""))),
                "Proyecto": str(row.get("Proyecto","")).strip(),
                "Tipo": str(row.get("Tipo de tarea","")).strip(),
                "Descripcion": str(row.get("task description","")),
                "Minutos": float(row.get("Minutos netos",0)),
                "Horas": parse_h(row.get("Horas Reales",0)),
                "Estado": str(row.get("Estado","Terminado")),
                "HoraInicio": str(row.get("Hora inicio","")),
                "HoraFin": str(row.get("Hora fin","")),
            }
            save_session(s)
            imported += 1
        st.success(f"{imported} registros importados")

    st.markdown("---")
    sessions_all = load_sessions()
    if sessions_all:
        df_exp = sessions_to_df(sessions_all)
        st.download_button("⬇ Exportar CSV",
                           df_exp.to_csv(index=False).encode("utf-8"),
                           "tracker_ra.csv","text/csv")


# ─── HEADER ───────────────────────────────────────────────────────────────────
st.markdown("# RA Productivity Tracker")

def load_config():
    if USE_DB:
        try:
            r = sb.table("config").select("*").execute()
            cfg = {}
            for row in (r.data or []):
                cfg[row["clave"]] = json.loads(row["valor"])
            return (cfg.get("proyectos", DEFAULT_PROYECTOS),
                    cfg.get("tipos",     DEFAULT_TIPOS))
        except: pass
    return st.session_state.proyectos, st.session_state.tipos

def save_config(proyectos, tipos):
    if USE_DB:
        try:
            sb.table("config").upsert(
                {"clave":"proyectos","valor":json.dumps(proyectos)},
                on_conflict="clave").execute()
            sb.table("config").upsert(
                {"clave":"tipos","valor":json.dumps(tipos)},
                on_conflict="clave").execute()
            return
        except: pass
    st.session_state.proyectos = proyectos
    st.session_state.tipos     = tipos

proyectos, tipos = load_config()
planes_all = load_planes()
sessions_all = load_sessions()
df_all = sessions_to_df(sessions_all)

t_reg, t_semana, t_dash, t_analisis, t_config = st.tabs([
    "📝 Registro", "📅 Mi semana", "📊 Dashboard", "🔬 Análisis", "⚙️ Configuración"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — REGISTRO
# ══════════════════════════════════════════════════════════════════════════════
with t_reg:
    st.markdown('<div class="section-header">Nueva sesión de trabajo</div>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    with c1:
      fecha    = st.date_input("Fecha", value=get_now_peru().date())
      proyecto = st.selectbox("Proyecto", proyectos)
      dia_sem  = st.selectbox("Día", DIAS, index=min(get_now_peru().weekday(), 6))
    with c2:
        tipo   = st.selectbox("Tipo de tarea", tipos)
        estado = st.selectbox("Estado", ["Terminado","En Proceso","Bloqueado"])
    with c3:
        h_ini = st.time_input("Hora inicio", value=time(7,0))
        h_fin = st.time_input("Hora fin",    value=time(9,0))

    desc = st.text_area("Descripción", height=80, placeholder="Ej: Debugging merge ubigeo MFI 2002-2012")

    dt_i = datetime.combine(fecha, h_ini)
    dt_f = datetime.combine(fecha, h_fin)
    mins = max(int((dt_f - dt_i).total_seconds() / 60), 0)
    horas = round(mins / 60, 3)
    sem = int(fecha.isocalendar()[1])

    plan_obj_hoy = planes_all.get(sem, {})
    plan_hoy = plan_horas_dia(plan_obj_hoy, dia_sem) if plan_obj_hoy else None
    real_hoy_antes = 0.0
    if len(df_all) > 0 and "Semana" in df_all.columns:
        real_hoy_antes = float(df_all[df_all["Semana"]==sem]["Horas"].sum()) if len(df_all)>0 else 0.0

    ka,kb,kc,kd = st.columns(4)
    ka.metric("Minutos", mins)
    kb.metric("Horas", f"{horas:.2f}h")
    kc.metric("Semana", sem)
    if plan_hoy is not None:
        kd.metric("Plan del día", f"{plan_hoy:g}h",
                  f"Real acum.: {real_hoy_antes:.1f}h")
    else:
        kd.metric("Plan del día", "Sin plan",
                  "Defínelo en 'Mi semana'")

    if st.button("➕ Registrar sesión", type="primary", use_container_width=True):
        if not desc.strip():
            st.warning("Agrega una descripción.")
        elif mins <= 0:
            st.warning("La hora de fin debe ser posterior a la de inicio.")
        else:
            nuevo = {
                "id":          f"{datetime.now().timestamp()}",
                "Fecha":       fecha.strftime("%d/%m"),
                "Semana":      sem,
                "Dia":         dia_sem,
                "Proyecto":    proyecto,
                "Tipo":        tipo,
                "Descripcion": desc,
                "Minutos":     mins,
                "Horas":       horas,
                "Estado":      estado,
                "HoraInicio":  str(h_ini)[:5],
                "HoraFin":     str(h_fin)[:5],
            }
            save_session(nuevo)
            st.success(f"✅ {horas:.2f}h · {tipo} · {proyecto}")
            st.rerun()

    sessions_all = load_sessions()
    df_all = sessions_to_df(sessions_all)
    if len(df_all) > 0:
        st.markdown('<div class="section-header">Registros recientes</div>', unsafe_allow_html=True)
        sems_disp = sorted(df_all["Semana"].unique(), reverse=True)
        sel = st.selectbox("Filtrar semana", ["Todas"] + [f"Sem {s}" for s in sems_disp])
        
        # 1. Hacemos una copia
        dv = df_all.copy() if sel=="Todas" else df_all[df_all["Semana"]==int(sel.split()[1])].copy()
        
        # 2. Creamos la nueva columna "Intervalo" quitando los segundos (solo los primeros 5 caracteres)
        if "HoraInicio" in dv.columns and "HoraFin" in dv.columns:
            dv["Intervalo"] = dv["HoraInicio"].fillna("").astype(str).str[:5] + " - " + dv["HoraFin"].fillna("").astype(str).str[:5]
        else:
            dv["Intervalo"] = "—"
            
        # 3. Quitamos "Estado" de la lista y ordenamos
        show_cols = [c for c in ["Fecha","Semana","Dia","Intervalo","Proyecto","Tipo",
                                  "Descripcion","Minutos","Horas"] if c in dv.columns]
                                  
        dv2 = dv[show_cols].copy()
        if "Horas"   in dv2.columns: dv2["Horas"]   = dv2["Horas"].apply(lambda x:f"{x:.2f}h")
        if "Minutos" in dv2.columns: dv2["Minutos"] = dv2["Minutos"].apply(lambda x:f"{int(x)} min")
        
        # 4. Ajustamos el ancho de la columna Intervalo y dibujamos la tabla
        st.dataframe(dv2, use_container_width=True, height=320,
                     column_config={
                         "Descripcion": st.column_config.TextColumn("Descripción", width="large"),
                         "Intervalo": st.column_config.TextColumn("Intervalo", width="medium")
                     })


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — MI SEMANA (plan + horario + seguimiento diario)
# ══════════════════════════════════════════════════════════════════════════════
with t_semana:
    st.markdown('<div class="section-header">Define tu plan semanal</div>', unsafe_allow_html=True)

    col_s, col_y = st.columns([2, 1])
    with col_s:
        sem_w = st.number_input("Semana ISO", min_value=1, max_value=53,
                                value=int(get_now_peru().isocalendar()[1]), key="sem_w")
    with col_y:
        año_w = st.number_input("Año", min_value=2020, max_value=2035,
                                value=int(get_now_peru().year), key="año_w")

    lun_w, dom_w, txt_rango = rango_semana(sem_w, año_w)
    if txt_rango:
        st.markdown(
            f'<div class="week-banner">📅 <b>Semana del {txt_rango}</b>'
            f'<br><span style="color:#999;font-size:12px">Semana ISO {sem_w} · {año_w}</span></div>',
            unsafe_allow_html=True)

    plan_prev = _norm_plan(planes_all.get(sem_w, {}))

    modo = st.radio(
        "¿Cómo quieres planificar?",
        ["🗓️ Horario por bloques", "⚡ Horas rápidas por día"],
        horizontal=True,
        index=0 if plan_prev.get("modo") == "horario" else 1,
        key="modo_plan")

    # ── MODO A: HORARIO POR BLOQUES (Dinámico HH:MM) ───────────────────────────
    if modo == "🗓️ Horario por bloques":
        st.caption("Añade tus bloques de horario con precisión de minutos (ej. 12:30 a 14:30). "
                   "Puedes agregar o eliminar filas dinámicamente.")

        filas_bloques = []
        for dia, segs in plan_prev.get("bloques", {}).items():
            for seg in segs:
                filas_bloques.append({"Día": dia, "Inicio": seg[0], "Fin": seg[1]})

        if not filas_bloques:
            filas_bloques.append({"Día": "Lunes", "Inicio": "09:00", "Fin": "11:30"})

        df_b = pd.DataFrame(filas_bloques)

        edited_b = st.data_editor(
            df_b,
            num_rows="dynamic",
            column_config={
                "Día": st.column_config.SelectboxColumn("Día", options=DIAS, required=True),
                "Inicio": st.column_config.TextColumn("Hora Inicio (24h)", required=True, validate="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"),
                "Fin": st.column_config.TextColumn("Hora Fin (24h)", required=True, validate="^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$"),
            },
            use_container_width=True,
            key=f"editor_bloques_{sem_w}_{año_w}"
        )

        bloques_new = {d: [] for d in DIAS}
        horas_new = {d: 0.0 for d in DIAS}

        for _, row in edited_b.iterrows():
            d = row.get("Día")
            ini_str = str(row.get("Inicio", "")).strip()
            fin_str = str(row.get("Fin", "")).strip()
            
            if d in DIAS and ini_str and fin_str:
                try:
                    h_i, m_i = map(int, ini_str.split(":"))
                    h_f, m_f = map(int, fin_str.split(":"))
                    dur = (h_f + m_f/60.0) - (h_i + m_i/60.0)
                    if dur > 0:
                        bloques_new[d].append([ini_str, fin_str])
                        horas_new[d] += dur
                except Exception:
                    pass

        total_plan = sum(horas_new.values())

        c_save, c_tot = st.columns([1, 2])
        with c_save:
            if st.button("💾 Guardar horario", type="primary"):
                save_plan(sem_w, {"horas": horas_new, "bloques": bloques_new, "modo": "horario"})
                st.success(f"Horario de la semana {sem_w} guardado.")
                st.rerun()
        with c_tot:
            resumen = " · ".join(f"{d[:3]} {horas_new[d]:.1f}h" for d in DIAS if horas_new[d] > 0) or "sin horas configuradas"
            st.markdown(f"<br>Total planificado: **{total_plan:.1f}h** \n"
                        f"<span style='color:#999;font-size:12px'>{resumen}</span>",
                        unsafe_allow_html=True)

        # Timeline tipo Gantt adaptado a minutos
        if total_plan > 0 and lun_w is not None:
            filas = []
            for i, dia in enumerate(DIAS):
                fecha_dia = lun_w + timedelta(days=i)
                base = datetime.combine(fecha_dia, time(0, 0))
                for seg in bloques_new.get(dia, []):
                    try:
                        hi, mi = map(int, seg[0].split(":"))
                        hf, mf = map(int, seg[1].split(":"))
                        filas.append(dict(
                            Día=dia,
                            Inicio=base + timedelta(hours=hi, minutes=mi),
                            Fin=base + timedelta(hours=hf, minutes=mf),
                            Bloque=f"{seg[0]}–{seg[1]}"))
                    except Exception:
                        pass

            if filas:
                st.markdown('<div class="section-header">Vista de horario semanal</div>', unsafe_allow_html=True)
                df_tl = pd.DataFrame(filas)
                fig_tl = px.timeline(df_tl, x_start="Inicio", x_end="Fin",
                                     y="Día", color="Día", text="Bloque",
                                     color_discrete_sequence=COLORES_BASE)
                fig_tl.update_yaxes(categoryorder="array", categoryarray=DIAS[::-1])
                fig_tl.update_traces(textposition="inside", insidetextanchor="middle")
                fig_tl.update_layout(**CHART, height=320, showlegend=False,
                                     xaxis={**GRID, "title": "Hora del día"},
                                     yaxis={**GRID, "title": ""})
                st.plotly_chart(fig_tl, use_container_width=True)

    # ── MODO B: HORAS RÁPIDAS POR DÍA ─────────────────────────────────────────
    else:
        st.caption("Pon cuántas horas planificas trabajar cada día.")
        st.markdown("**Horas planificadas por día:**")
        cols_d = st.columns(7)
        horas_new = {}
        for i, dia in enumerate(DIAS):
            with cols_d[i]:
                horas_new[dia] = st.number_input(
                    dia[:3], min_value=0.0, max_value=24.0,
                    value=float(plan_prev["horas"].get(dia, 0.0)), step=0.25,
                    key=f"plan_{sem_w}_{año_w}_{dia}")
        total_plan = sum(horas_new.values())
        
        c_save, c_tot = st.columns([1, 2])
        with c_save:
            if st.button("💾 Guardar plan", type="primary"):
                save_plan(sem_w, {"horas": horas_new,
                                  "bloques": plan_prev.get("bloques", {}),
                                  "modo": "rapido"})
                st.success(f"Plan de la semana {sem_w} guardado.")
                st.rerun()
        with c_tot:
            st.markdown(f"<br>Total planificado: **{total_plan:.1f}h**", unsafe_allow_html=True)

    # ── Seguimiento diario plan vs real + MEDIDOR ─────────────────────────────
    planes_all = load_planes()
    plan_sem_raw = planes_all.get(sem_w, {})
    if plan_total_h(plan_sem_raw) > 0 and len(df_all) > 0:
        st.markdown('<div class="section-header">Seguimiento diario — semana seleccionada</div>', unsafe_allow_html=True)

        df_sem = df_all[df_all["Semana"] == sem_w] if len(df_all) > 0 else pd.DataFrame()
        rows = []
        for dia in DIAS:
            p = plan_horas_dia(plan_sem_raw, dia)
            if len(df_sem) > 0 and "Dia" in df_sem.columns:
                r = df_sem[df_sem["Dia"] == dia]["Horas"].sum()
            else:
                r = 0.0
            ahorro = round(p - r, 2)
            registrado = (len(df_sem[df_sem["Dia"] == dia]) > 0
                          if len(df_sem) > 0 and "Dia" in df_sem.columns else False)
            rows.append({"Día": dia, "Plan": p, "Real": round(r, 2),
                         "Ahorro": ahorro, "Registrado": registrado})
        dfcomp = pd.DataFrame(rows)

        # FIX PLOTLY: Forzamos conversiones a flotantes de Python (no numpy types)
        tp = float(dfcomp["Plan"].sum())
        tr = float(dfcomp["Real"].sum())
        ta = round(tp - tr, 2)
        dias_con_registro = int(dfcomp["Registrado"].sum())

        col_g, col_k = st.columns([1, 1])
        with col_g:
            prog_pct = (tr / tp * 100) if tp > 0 else 0
            
            # Gauge condicional: protege contra anchos de barra cero y colores inválidos
            gauge_dict = {
                "axis": {"range": [0, float(max(tp, tr, 1))], "tickcolor": "#666"},
                "bar": {"color": "#185FA5"},
                "bgcolor": "rgba(0,0,0,0)",
                "borderwidth": 0
            }
            if tp > 0:
                gauge_dict["steps"] = [
                    {"range": [0, float(tp * 0.7)], "color": "#2a2a3e"},
                    # Reemplazamos el Hex de 8 caracteres por RGBA para evitar el ValueError
                    {"range": [float(tp * 0.7), float(tp)], "color": "rgba(60, 52, 137, 0.25)"}
                ]
                gauge_dict["threshold"] = {
                    "line": {"color": "#3B6D11", "width": 3},
                    "thickness": 0.85, "value": float(tp)
                }

            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=float(tr),
                number={"suffix": " h", "font": {"color": "#e0e0e0"}},
                delta={"reference": float(tp), "increasing": {"color": "#A32D2D"},
                       "decreasing": {"color": "#3B6D11"},
                       "position": "bottom"},
                title={"text": f"Progreso: {prog_pct:.0f}% del plan",
                       "font": {"size": 14, "color": "#aaa"}},
                gauge=gauge_dict
            ))
            fig_gauge.update_layout(**CHART, height=260)
            st.plotly_chart(fig_gauge, use_container_width=True)
        with col_k:
            st.markdown("<br>", unsafe_allow_html=True)
            k1, k2 = st.columns(2)
            k1.metric("Plan total", f"{tp:.1f}h")
            k2.metric("Real acum.", f"{tr:.1f}h")
            k3, k4 = st.columns(2)
            k3.metric("Ahorro", f"{ta:.1f}h",
                      "Menos ✓" if ta >= 0 else "Más",
                      delta_color="normal" if ta >= 0 else "inverse")
            k4.metric("Días registrados", f"{dias_con_registro}/7")

        fig_comp = go.Figure()
        fig_comp.add_trace(go.Bar(name="Plan", x=dfcomp["Día"], y=dfcomp["Plan"],
                                  marker_color="#3C3489", opacity=0.7,
                                  text=dfcomp["Plan"].apply(lambda x: f"{x:.1f}h"),
                                  textposition="outside"))
        fig_comp.add_trace(go.Bar(name="Real", x=dfcomp["Día"], y=dfcomp["Real"],
                                  marker_color="#185FA5",
                                  text=dfcomp["Real"].apply(lambda x: f"{x:.1f}h"),
                                  textposition="outside"))
        fig_comp.update_layout(**CHART, barmode="group", height=300,
                               xaxis={**GRID}, yaxis={**GRID, "title": "Horas"},
                               legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig_comp, use_container_width=True)

        dfcomp["Estado"] = dfcomp.apply(lambda r:
            f"🟢 -{abs(r['Ahorro']):.2f}h" if r["Ahorro"] > 0 else
            (f"🔴 +{abs(r['Ahorro']):.2f}h extra" if r["Ahorro"] < 0 else "⚪ Exacto"),
            axis=1)
        st.dataframe(dfcomp[["Día", "Plan", "Real", "Estado"]],
                     use_container_width=True, hide_index=True)

        if is_domingo() or st.checkbox("👀 Ver cierre de semana (resumen final)", key="cierre"):
            st.markdown('<div class="section-header">🏁 Cierre semanal</div>', unsafe_allow_html=True)
            st.markdown(f"""
| Métrica | Valor |
|---|---|
| Semana | **{txt_rango}** |
| Horas planificadas | **{tp:.1f}h** |
| Horas reales trabajadas | **{tr:.1f}h** |
| Horas ahorradas | **{ta:.1f}h** |
| Eficiencia (real/plan) | **{round(tr/tp*100,1) if tp>0 else 0}%** |
| Días completados (con registro) | **{dias_con_registro}/7** |
""")
            if ta >= 0:
                st.success(f"✅ Terminaste {ta:.1f}h antes de lo planificado esta semana.")
            else:
                st.warning(f"⚠️ Trabajaste {abs(ta):.1f}h más de lo que planificaste.")

    elif plan_total_h(plan_sem_raw) == 0:
        st.info("Define tu plan/horario arriba y guárdalo para ver el seguimiento y el medidor.")

    if len(planes_all) > 1:
        st.markdown('<div class="section-header">Histórico de semanas</div>', unsafe_allow_html=True)
        hist = []
        for s, plan in sorted(planes_all.items()):
            tp2 = plan_total_h(plan)
            tr2 = df_all[df_all["Semana"] == s]["Horas"].sum() if len(df_all) > 0 else 0.0
            _, _, txt_s = rango_semana(s, año_w)
            hist.append({"Semana": s, "Rango": txt_s, "Plan": tp2, "Real": round(tr2, 2),
                         "Ahorro": round(tp2 - tr2, 2),
                         "Efic.": f"{round(tr2/tp2*100,1) if tp2>0 else 0}%"})
        df_hist = pd.DataFrame(hist)
        fig_hist = go.Figure()
        fig_hist.add_trace(go.Bar(x=df_hist["Semana"], y=df_hist["Plan"],
                                  name="Plan", marker_color="#3C3489", opacity=0.7))
        fig_hist.add_trace(go.Bar(x=df_hist["Semana"], y=df_hist["Real"],
                                  name="Real", marker_color="#185FA5"))
        fig_hist.add_trace(go.Scatter(x=df_hist["Semana"], y=df_hist["Ahorro"],
                                      name="Ahorro", mode="lines+markers",
                                      line=dict(color="#3B6D11", width=2),
                                      marker=dict(size=7)))
        fig_hist.update_layout(**CHART, barmode="group", height=280,
                               xaxis={**GRID, "title": "Semana"},
                               yaxis={**GRID, "title": "Horas"},
                               legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig_hist, use_container_width=True)
        st.dataframe(df_hist, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with t_dash:
    if len(df_all) == 0:
        st.info("Carga datos o agrega registros.")
    else:
        sems  = sorted(df_all["Semana"].unique())
        sem_d = st.selectbox("Semana", sems, index=len(sems)-1, key="sd")
        _, _, txt_d = rango_semana(sem_d, int(get_now_peru().year))
        if txt_d:
            st.caption(f"📅 Semana del {txt_d}")
        dfs   = df_all[df_all["Semana"]==sem_d]
        dfp   = df_all[df_all["Semana"]==sem_d-1] if (sem_d-1) in df_all["Semana"].values else pd.DataFrame()

        h_sem  = dfs["Horas"].sum()
        h_prev = dfp["Horas"].sum() if len(dfp)>0 else 0
        delta  = round(h_sem - h_prev, 2)
        plan_s = plan_total_h(planes_all.get(sem_d, {}))

        k1,k2,k3,k4,k5 = st.columns(5)
        k1.metric("Horas trabajadas", f"{h_sem:.1f}h", f"{delta:+.1f}h vs sem ant.")
        k2.metric("Plan semana",      f"{plan_s:.1f}h" if plan_s>0 else "Sin plan")
        k3.metric("Ahorro",           f"{plan_s-h_sem:.1f}h" if plan_s>0 else "—")
        k4.metric("Sesiones",         len(dfs))
        k5.metric("Avg. sesión",      f"{dfs['Minutos'].mean():.0f} min" if len(dfs)>0 else "—")

        if plan_s > 0:
            prog  = min(h_sem/plan_s, 1.0)
            color = "#3B6D11" if prog>=1 else "#185FA5" if prog>=0.7 else "#A32D2D"
            st.markdown(f"""<div style="margin:8px 0 20px">
              <div style="font-size:12px;color:#888;margin-bottom:4px">
                Progreso: {h_sem:.1f}h / {plan_s:.1f}h</div>
              <div style="background:#2a2a3e;border-radius:8px;height:14px;overflow:hidden">
                <div style="background:{color};width:{prog*100:.1f}%;height:100%;
                            border-radius:8px"></div></div></div>""",
                        unsafe_allow_html=True)

        cl,cr = st.columns(2)
        with cl:
            st.markdown('<div class="section-header">Por tipo de tarea</div>', unsafe_allow_html=True)
            if "Tipo" in dfs.columns:
                td = dfs.groupby("Tipo")["Horas"].sum().reset_index().sort_values("Horas")
                cmap = {t: color_for(i) for i,t in enumerate(td["Tipo"].unique())}
                fig = px.bar(td,x="Horas",y="Tipo",orientation="h",
                             color="Tipo",color_discrete_map=cmap,text="Horas")
                fig.update_traces(texttemplate="%{text:.2f}h",textposition="outside")
                fig.update_layout(**CHART,height=280,showlegend=False,
                                  xaxis={**GRID,"title":"Horas"},yaxis={**GRID,"title":""})
                st.plotly_chart(fig,use_container_width=True)

        with cr:
            st.markdown('<div class="section-header">Por proyecto</div>', unsafe_allow_html=True)
            if "Proyecto" in dfs.columns:
                pd2 = dfs.groupby("Proyecto")["Horas"].sum().reset_index()
                cmap2 = {p: color_for(i) for i,p in enumerate(pd2["Proyecto"].unique())}
                fig2 = px.pie(pd2,values="Horas",names="Proyecto",
                              color="Proyecto",color_discrete_map=cmap2,hole=0.45)
                fig2.update_traces(texttemplate="%{label}<br>%{value:.1f}h (%{percent})")
                fig2.update_layout(**CHART,height=280,showlegend=False)
                st.plotly_chart(fig2,use_container_width=True)

        st.markdown('<div class="section-header">Evolución semanal</div>', unsafe_allow_html=True)
        evo = df_all.groupby("Semana")["Horas"].sum().reset_index()
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(x=evo["Semana"],y=evo["Horas"],name="Horas",
                               marker_color="#185FA5",
                               text=evo["Horas"].apply(lambda x:f"{x:.1f}h"),
                               textposition="outside"))
        if planes_all:
            plan_line = pd.DataFrame([
                {"Semana":s,"Plan":plan_total_h(d)} for s,d in planes_all.items()])
            fig3.add_trace(go.Scatter(x=plan_line["Semana"],y=plan_line["Plan"],
                                       mode="lines+markers",name="Plan",
                                       line=dict(color="#854F0B",dash="dash",width=2),
                                       marker=dict(size=6)))
        fig3.update_layout(**CHART,height=300,xaxis={**GRID,"title":"Semana"},
                            yaxis={**GRID,"title":"Horas"},
                            legend=dict(orientation="h",y=1.1))
        st.plotly_chart(fig3,use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — ANÁLISIS
# ══════════════════════════════════════════════════════════════════════════════
with t_analisis:
    if len(df_all)==0:
        st.info("Agrega registros primero.")
    else:
        dfhb = df_all[df_all.get("HoraInicio","").notna()].copy() if "HoraInicio" in df_all.columns else pd.DataFrame()
        if len(dfhb)>0:
            st.markdown('<div class="section-header">Por bloque horario</div>', unsafe_allow_html=True)
            dfhb["Bloque"] = dfhb["HoraInicio"].apply(bloque)
            orden = ["Madrugada (<9h)","Mañana (9–13h)","Tarde (13–17h)",
                     "Noche (17–21h)","Noche tarde (21h+)"]
            bd = dfhb.groupby("Bloque")["Horas"].sum().reindex(orden,fill_value=0).reset_index()
            fb = px.bar(bd,x="Bloque",y="Horas",
                        color_discrete_sequence=["#3C3489"],text="Horas")
            fb.update_traces(texttemplate="%{text:.1f}h",textposition="outside")
            fb.update_layout(**CHART,height=260,
                              xaxis={**GRID},yaxis={**GRID,"title":"Horas"})
            st.plotly_chart(fb,use_container_width=True)

        ca,cb = st.columns(2)
        with ca:
            st.markdown('<div class="section-header">Duración media por tipo</div>', unsafe_allow_html=True)
            if "Tipo" in df_all.columns:
                at = df_all.groupby("Tipo")["Minutos"].mean().reset_index()
                at = at.sort_values("Minutos")
                cmap3 = {t:color_for(i) for i,t in enumerate(at["Tipo"].unique())}
                fat = px.bar(at,x="Minutos",y="Tipo",orientation="h",
                             color="Tipo",color_discrete_map=cmap3,text="Minutos")
                fat.update_traces(texttemplate="%{text:.0f} min",textposition="outside")
                fat.update_layout(**CHART,showlegend=False,height=280,
                                   xaxis={**GRID,"title":"Minutos"},
                                   yaxis={**GRID,"title":""})
                st.plotly_chart(fat,use_container_width=True)

        with cb:
            st.markdown('<div class="section-header">Estado de tareas</div>', unsafe_allow_html=True)
            if "Estado" in df_all.columns:
                est = df_all.groupby("Estado")["Horas"].sum().reset_index()
                cmap4 = {"Terminado":"#3B6D11","En Proceso":"#185FA5","Bloqueado":"#A32D2D"}
                fe2 = px.bar(est,x="Estado",y="Horas",color="Estado",
                             color_discrete_map=cmap4,text="Horas")
                fe2.update_traces(texttemplate="%{text:.1f}h",textposition="outside")
                fe2.update_layout(**CHART,showlegend=False,height=280,
                                   xaxis={**GRID},yaxis={**GRID,"title":"Horas"})
                st.plotly_chart(fe2,use_container_width=True)

        st.markdown('<div class="section-header">Heatmap semana × tipo</div>', unsafe_allow_html=True)
        if "Tipo" in df_all.columns:
            pivot = df_all.pivot_table(index="Tipo",columns="Semana",
                                        values="Horas",aggfunc="sum",fill_value=0)
            fhm = px.imshow(pivot,color_continuous_scale="Blues",
                             labels=dict(x="Semana",y="Tipo",color="Horas"),
                             aspect="auto",text_auto=".1f")
            fhm.update_layout(**CHART,height=300)
            st.plotly_chart(fhm,use_container_width=True)

        st.markdown('<div class="section-header">Resumen por semana</div>', unsafe_allow_html=True)
        res = df_all.groupby("Semana").agg(
            Horas=("Horas","sum"), Sesiones=("Horas","count"),
            Avg_min=("Minutos","mean")).reset_index()
        res["Plan"] = res["Semana"].apply(
            lambda s: f"{plan_total_h(planes_all.get(s,{})):.1f}h" if s in planes_all else "—")
        res["Horas"]   = res["Horas"].apply(lambda x:f"{x:.1f}h")
        res["Avg_min"] = res["Avg_min"].apply(lambda x:f"{x:.0f} min")
        res.columns    = ["Semana","Horas totales","Sesiones","Avg. sesión","Plan"]
        st.dataframe(res,use_container_width=True,hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════
with t_config:
    st.markdown('<div class="section-header">Proyectos</div>', unsafe_allow_html=True)
    st.caption("Agrega o elimina proyectos. Los existentes en registros no se borran.")

    col_p1, col_p2 = st.columns([3,1])
    with col_p1:
        nuevo_proy = st.text_input("Nombre del nuevo proyecto",
                                    placeholder="Ej: Tesis, LaboralPeru, FAO...")
    with col_p2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ Agregar proyecto") and nuevo_proy.strip():
            if nuevo_proy.strip() not in proyectos:
                proyectos.append(nuevo_proy.strip())
                save_config(proyectos, tipos)
                st.success(f"Proyecto '{nuevo_proy}' agregado.")
                st.rerun()

    st.markdown("**Proyectos actuales:**")
    for i, p in enumerate(proyectos):
        cp1, cp2 = st.columns([4,1])
        with cp1: st.markdown(f'<span class="pill">{p}</span>', unsafe_allow_html=True)
        with cp2:
            if p not in DEFAULT_PROYECTOS:
                if st.button("🗑", key=f"del_p_{i}"):
                    proyectos.remove(p)
                    save_config(proyectos, tipos)
                    st.rerun()

    st.markdown("---")
    st.markdown('<div class="section-header">Tipos de tarea</div>', unsafe_allow_html=True)

    col_t1, col_t2 = st.columns([3,1])
    with col_t1:
        nuevo_tipo = st.text_input("Nombre del nuevo tipo",
                                    placeholder="Ej: Redacción, Visualización...")
    with col_t2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ Agregar tipo") and nuevo_tipo.strip():
            if nuevo_tipo.strip() not in tipos:
                tipos.append(nuevo_tipo.strip())
                save_config(proyectos, tipos)
                st.success(f"Tipo '{nuevo_tipo}' agregado.")
                st.rerun()

    st.markdown("**Tipos actuales:**")
    for i, t in enumerate(tipos):
        ct1, ct2 = st.columns([4,1])
        with ct1: st.markdown(f'<span class="pill">{t}</span>', unsafe_allow_html=True)
        with ct2:
            if t not in DEFAULT_TIPOS:
                if st.button("🗑", key=f"del_t_{i}"):
                    tipos.remove(t)
                    save_config(proyectos, tipos)
                    st.rerun()

    st.markdown("---")
    st.markdown('<div class="section-header">Estado de la base de datos</div>',
                unsafe_allow_html=True)
    if USE_DB:
        st.success("✅ Conectado a Supabase — datos sincronizados entre dispositivos")
    else:
        st.error("❌ Sin conexión a Supabase — datos solo en esta sesión")
        st.markdown("""
**Para activar la sincronización entre dispositivos:**

1. Crea cuenta gratis en supabase.com
2. Crea un proyecto nuevo
3. Ve a **SQL Editor** y ejecuta:

        create table sessions (
          id text primary key,
          "Fecha" text, "Semana" int, "Dia" text,
          "Proyecto" text, "Tipo" text, "Descripcion" text,
          "Minutos" float, "Horas" float, "Estado" text,
          "HoraInicio" text, "HoraFin" text
        );

        create table planes (
          semana int primary key,
          datos text
        );

        create table config (
          clave text primary key,
          valor text
        );

4. Por seguridad, no crees el archivo secrets en GitHub.
5. Ve directamente a Streamlit Cloud → Settings → Secrets → y pega ahí tus credenciales.
""")
