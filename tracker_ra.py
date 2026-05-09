import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, time

st.set_page_config(page_title="RA Productivity Tracker", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")

# ─── CONSTANTES ───────────────────────────────────────────────────────────────
SEMANA_CAMBIO = 19
META_ANTES    = 20.0
META_DESPUES  = 40.0

COLORES_TIPO = {
    "Estimación (Regresiones/Gráficos)":         "#185FA5",
    "Debugging (solución de errores)":            "#3B6D11",
    "Data Wrangling (Limpieza/Merges)":           "#854F0B",
    "Curva de Aprendizaje (Lectura/Sintaxis)":    "#3C3489",
    "Reuniones y Preparación":                    "#A32D2D",
    "Reportes/ actualizaciones":                  "#0F6E56",
    "Otros":                                      "#888780",
}
COLORES_PROY = {"Fintech":"#185FA5","MFI":"#3B6D11","LRC":"#854F0B","Otros":"#888780"}
DIAS = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
PLAN_DIA = {"Lunes":4.0,"Martes":6.0,"Miércoles":4.5,
            "Jueves":5.5,"Viernes":4.0,"Sábado":10.5,"Domingo":5.5}

CHART = dict(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
             font_color="#e0e0e0", margin=dict(l=0,r=20,t=10,b=0))
GRID  = dict(gridcolor="#2a2a3e")

st.markdown("""<style>
.section-header{font-size:15px;font-weight:600;border-left:3px solid #185FA5;
  padding-left:10px;margin:24px 0 12px}
.tag-meta{background:#185FA580;color:#B5D4F4;font-size:11px;
  padding:2px 8px;border-radius:20px}
</style>""", unsafe_allow_html=True)

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def meta_sem(s): return META_DESPUES if s >= SEMANA_CAMBIO else META_ANTES

def parse_h(v):
    try: return float(str(v).replace(",","."))
    except: return 0.0

def bloque(h_str):
    try:
        h = int(str(h_str).split(":")[0])
        if h<9:  return "Madrugada (<9h)"
        if h<13: return "Mañana (9–13h)"
        if h<17: return "Tarde (13–17h)"
        if h<21: return "Noche (17–21h)"
        return "Noche tarde (21h+)"
    except: return "Sin horario"

def load_csv(f):
    df = pd.read_csv(f)
    df.columns = df.columns.str.strip()
    for c in ["Proyecto","Tipo de tarea","Estado"]:
        if c in df.columns: df[c] = df[c].str.strip()
    df["Horas Reales"]  = df["Horas Reales"].apply(parse_h)
    df["Minutos netos"] = pd.to_numeric(df["Minutos netos"],errors="coerce").fillna(0)
    for c in ["Hora inicio","Hora fin","Día semana"]:
        if c not in df.columns: df[c] = None
    df = df.dropna(subset=["Semana","Tipo de tarea"])
    df["Semana"] = df["Semana"].astype(int)
    return df

def empty_df():
    return pd.DataFrame(columns=["Fecha","Proyecto","Tipo de tarea","task description",
                                  "Minutos netos","Horas Reales","Estado","Semana",
                                  "Hora inicio","Hora fin","Día semana"])

# ─── SESSION STATE ─────────────────────────────────────────────────────────────
if "df"      not in st.session_state: st.session_state.df = empty_df()
if "horario" not in st.session_state: st.session_state.horario = {}

# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 RA Tracker")
    st.markdown(f"Sem 12–18 → **{META_ANTES}h** · Sem 19+ → **{META_DESPUES}h**")
    st.markdown("---")
    up = st.file_uploader("Cargar CSV", type=["csv"])
    if up:
        st.session_state.df = load_csv(up)
        st.success(f"{len(st.session_state.df)} registros cargados")
    st.markdown("---")
    if len(st.session_state.df) > 0:
        st.download_button("⬇ Exportar CSV",
                           st.session_state.df.to_csv(index=False).encode("utf-8"),
                           "tracker_ra.csv","text/csv")

st.markdown("# RA Productivity Tracker")
st.markdown("Registro · Dashboard · Horario & Ahorro · Análisis")

df = st.session_state.df
t1,t2,t3,t4 = st.tabs(["📝 Registro","📊 Dashboard","⏱ Horario & Ahorro","🔬 Análisis"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — REGISTRO
# ══════════════════════════════════════════════════════════════════════════════
with t1:
    st.markdown('<div class="section-header">Nueva sesión</div>',unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    with c1:
        fecha    = st.date_input("Fecha", value=date.today())
        proyecto = st.selectbox("Proyecto",["Fintech","MFI","LRC","Otros"])
        dia_sem  = st.selectbox("Día",DIAS)
    with c2:
        tipo   = st.selectbox("Tipo de tarea",list(COLORES_TIPO.keys()))
        estado = st.selectbox("Estado",["Terminado","En Proceso","Bloqueado"])
    with c3:
        h_ini = st.time_input("Hora inicio",value=time(7,0))
        h_fin = st.time_input("Hora fin",   value=time(9,0))

    desc = st.text_area("Descripción",height=80,
                         placeholder="Ej: Debugging merge ubigeo MFI 2002-2012")

    dt_i  = datetime.combine(date.today(),h_ini)
    dt_f  = datetime.combine(date.today(),h_fin)
    mins  = max(int((dt_f-dt_i).total_seconds()/60),0)
    horas = round(mins/60,3)
    sem   = fecha.isocalendar()[1]

    ka,kb,kc,kd = st.columns(4)
    ka.metric("Minutos",mins); kb.metric("Horas",f"{horas:.2f}h")
    kc.metric("Semana ISO",sem); kd.metric("Meta semana",f"{meta_sem(sem)}h")

    if st.button("➕ Agregar",type="primary",use_container_width=True):
        if not desc.strip(): st.warning("Agrega descripción.")
        elif mins<=0: st.warning("Hora fin debe ser posterior a inicio.")
        else:
            nuevo = {"Fecha":fecha.strftime("%d/%m"),"Proyecto":proyecto,
                     "Tipo de tarea":tipo,"task description":desc,
                     "Minutos netos":mins,"Horas Reales":horas,"Estado":estado,
                     "Semana":sem,"Hora inicio":str(h_ini),"Hora fin":str(h_fin),
                     "Día semana":dia_sem}
            st.session_state.df = pd.concat(
                [st.session_state.df,pd.DataFrame([nuevo])],ignore_index=True)
            st.success(f"✅ {horas:.2f}h · {tipo} · {proyecto}"); st.rerun()

    if len(df)>0:
        st.markdown('<div class="section-header">Registros</div>',unsafe_allow_html=True)
        sems = sorted(df["Semana"].unique(),reverse=True)
        sel  = st.selectbox("Filtrar",["Todas"]+[f"Sem {s}" for s in sems])
        dv   = df if sel=="Todas" else df[df["Semana"]==int(sel.split()[1])]
        cols = ["Fecha","Semana","Día semana","Proyecto","Tipo de tarea",
                "task description","Minutos netos","Horas Reales","Estado"]
        dv2  = dv[[c for c in cols if c in dv.columns]].copy()
        if "Horas Reales"  in dv2.columns: dv2["Horas Reales"]  = dv2["Horas Reales"].apply(lambda x:f"{x:.2f}h")
        if "Minutos netos" in dv2.columns: dv2["Minutos netos"] = dv2["Minutos netos"].apply(lambda x:f"{int(x)} min")
        st.dataframe(dv2,use_container_width=True,height=300,
                     column_config={"task description":st.column_config.TextColumn("Descripción",width="large")})

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════
with t2:
    if len(df)==0:
        st.info("Carga un CSV o agrega registros.")
    else:
        sems  = sorted(df["Semana"].unique())
        sem_d = st.selectbox("Semana",sems,index=len(sems)-1,key="sd")
        dfs   = df[df["Semana"]==sem_d]
        dfp   = df[df["Semana"]==sem_d-1] if (sem_d-1) in df["Semana"].values else pd.DataFrame()
        meta  = meta_sem(sem_d)
        h_sem = dfs["Horas Reales"].sum()
        h_prv = dfp["Horas Reales"].sum() if len(dfp)>0 else 0
        delta = round(h_sem-h_prv,2)
        cumpl = round(h_sem/meta*100,1)

        k1,k2,k3,k4,k5 = st.columns(5)
        k1.metric("Horas trabajadas",f"{h_sem:.1f}h",f"{delta:+.1f}h vs ant.")
        k2.metric("Meta semana",f"{meta}h","20h→40h desde sem 19")
        k3.metric("Cumplimiento",f"{cumpl}%")
        k4.metric("Sesiones",len(dfs))
        k5.metric("Horas restantes",f"{max(meta-h_sem,0):.1f}h")

        prog  = min(h_sem/meta,1.0)
        color = "#3B6D11" if prog>=1 else "#185FA5" if prog>=0.7 else "#A32D2D"
        st.markdown(f"""<div style="margin:8px 0 20px">
          <div style="font-size:12px;color:#888;margin-bottom:4px">
            Progreso: {h_sem:.1f}h / {meta}h</div>
          <div style="background:#2a2a3e;border-radius:8px;height:14px;overflow:hidden">
            <div style="background:{color};width:{prog*100:.1f}%;height:100%;border-radius:8px"></div>
          </div></div>""",unsafe_allow_html=True)

        cl,cr = st.columns(2)
        with cl:
            st.markdown('<div class="section-header">Por tipo de tarea</div>',unsafe_allow_html=True)
            td = dfs.groupby("Tipo de tarea")["Horas Reales"].sum().reset_index().sort_values("Horas Reales")
            fig = px.bar(td,x="Horas Reales",y="Tipo de tarea",orientation="h",
                         color="Tipo de tarea",color_discrete_map=COLORES_TIPO,text="Horas Reales")
            fig.update_traces(texttemplate="%{text:.2f}h",textposition="outside")
            fig.update_layout(**CHART,height=280,showlegend=False,
                              xaxis={**GRID,"title":"Horas"},yaxis={**GRID,"title":""})
            st.plotly_chart(fig,use_container_width=True)

        with cr:
            st.markdown('<div class="section-header">Por proyecto</div>',unsafe_allow_html=True)
            pd2 = dfs.groupby("Proyecto")["Horas Reales"].sum().reset_index()
            fig2 = px.pie(pd2,values="Horas Reales",names="Proyecto",
                          color="Proyecto",color_discrete_map=COLORES_PROY,hole=0.45)
            fig2.update_traces(textinfo="label+percent+value",
                               texttemplate="%{label}<br>%{value:.1f}h (%{percent})")
            fig2.update_layout(**CHART,height=280,showlegend=False)
            st.plotly_chart(fig2,use_container_width=True)

        st.markdown('<div class="section-header">Evolución semanal</div>',unsafe_allow_html=True)
        evo = df.groupby("Semana")["Horas Reales"].sum().reset_index()
        evo["Meta"] = evo["Semana"].apply(meta_sem)
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(x=evo["Semana"],y=evo["Horas Reales"],name="Horas",
                               marker_color="#185FA5",
                               text=evo["Horas Reales"].apply(lambda x:f"{x:.1f}h"),
                               textposition="outside"))
        fig3.add_trace(go.Scatter(x=evo["Semana"],y=evo["Meta"],mode="lines",
                                   name="Meta",line=dict(color="#A32D2D",dash="dash",width=2)))
        fig3.add_vline(x=SEMANA_CAMBIO-0.5,line_dash="dot",line_color="#854F0B",
                       annotation_text="20h→40h",annotation_position="top right")
        fig3.update_layout(**CHART,height=300,xaxis={**GRID,"title":"Semana"},
                            yaxis={**GRID,"title":"Horas"},
                            legend=dict(orientation="h",y=1.1))
        st.plotly_chart(fig3,use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — HORARIO & AHORRO
# ══════════════════════════════════════════════════════════════════════════════
with t3:
    st.markdown('<div class="section-header">Registrar horas reales por día</div>',unsafe_allow_html=True)
    st.caption("Ingresa cuántas horas RA trabajaste cada día. "
               "Se compara con el plan del itinerario acordado (40h semanales).")

    col_s,col_i = st.columns([1,3])
    with col_s:
        sem_h = st.number_input("Semana",min_value=1,max_value=60,
                                 value=datetime.now().isocalendar()[1])
    with col_i:
        st.markdown(f"<br><span class='tag-meta'>Meta semana {sem_h}: {meta_sem(sem_h)}h · "
                    f"Plan itinerario: 40h</span>",unsafe_allow_html=True)

    st.markdown("**Horas reales trabajadas por día:**")
    cdias = st.columns(7)
    horas_dia = {}
    for i,dia in enumerate(DIAS):
        plan = PLAN_DIA[dia]
        prev = float(st.session_state.horario.get(sem_h,{}).get(dia,0.0))
        with cdias[i]:
            horas_dia[dia] = st.number_input(
                f"{dia[:3]}\n(plan {plan}h)",
                min_value=0.0,max_value=24.0,value=prev,step=0.25,
                key=f"h_{sem_h}_{dia}")

    if st.button("💾 Guardar semana",type="primary"):
        if sem_h not in st.session_state.horario:
            st.session_state.horario[sem_h] = {}
        st.session_state.horario[sem_h] = dict(horas_dia)
        st.success(f"Semana {sem_h} guardada.")

    if sem_h in st.session_state.horario and any(
            v>0 for v in st.session_state.horario[sem_h].values()):

        real = st.session_state.horario[sem_h]
        rows = []
        for dia in DIAS:
            r = real.get(dia,0.0); p = PLAN_DIA[dia]
            rows.append({"Día":dia,"Plan (h)":p,"Real (h)":r,"Ahorro (h)":round(p-r,2)})
        dfh = pd.DataFrame(rows)
        tp = dfh["Plan (h)"].sum(); tr = dfh["Real (h)"].sum()
        ta = round(tp-tr,2); pct = round(tr/tp*100,1) if tp>0 else 0

        st.markdown('<div class="section-header">Resumen de la semana</div>',unsafe_allow_html=True)
        ka,kb,kc,kd = st.columns(4)
        ka.metric("Horas planificadas",f"{tp}h")
        kb.metric("Horas reales",f"{tr:.1f}h")
        kc.metric("Horas ahorradas",f"{ta:.1f}h",
                  "Trabajaste menos ✓" if ta>=0 else "Trabajaste más",
                  delta_color="normal" if ta>=0 else "inverse")
        kd.metric("% del plan usado",f"{pct}%")

        # Barras agrupadas plan vs real
        st.markdown('<div class="section-header">Plan vs Real por día</div>',unsafe_allow_html=True)
        fg = go.Figure()
        fg.add_trace(go.Bar(name="Plan",x=dfh["Día"],y=dfh["Plan (h)"],
                             marker_color="#3C3489",opacity=0.75,
                             text=dfh["Plan (h)"].apply(lambda x:f"{x}h"),
                             textposition="outside"))
        fg.add_trace(go.Bar(name="Real",x=dfh["Día"],y=dfh["Real (h)"],
                             marker_color="#185FA5",
                             text=dfh["Real (h)"].apply(lambda x:f"{x:.1f}h"),
                             textposition="outside"))
        fg.update_layout(**CHART,barmode="group",height=320,
                          xaxis={**GRID},yaxis={**GRID,"title":"Horas"},
                          legend=dict(orientation="h",y=1.1))
        st.plotly_chart(fg,use_container_width=True)

        # Ahorro por día (verde/rojo)
        st.markdown('<div class="section-header">Ahorro por día</div>',unsafe_allow_html=True)
        colors = ["#3B6D11" if x>=0 else "#A32D2D" for x in dfh["Ahorro (h)"]]
        fa = go.Figure(go.Bar(x=dfh["Día"],y=dfh["Ahorro (h)"],
                               marker_color=colors,
                               text=dfh["Ahorro (h)"].apply(lambda x:f"{x:+.2f}h"),
                               textposition="outside"))
        fa.add_hline(y=0,line_color="#888",line_width=1)
        fa.update_layout(**CHART,height=280,
                          xaxis={**GRID},yaxis={**GRID,"title":"Horas ahorradas"})
        st.plotly_chart(fa,use_container_width=True)

        # Tabla detalle
        dfh["Estado"] = dfh["Ahorro (h)"].apply(
            lambda x: f"🟢 Ahorraste {x:.2f}h" if x>0
                      else (f"🔴 Trabajaste {abs(x):.2f}h extra" if x<0
                            else "⚪ Exacto"))
        st.dataframe(dfh[["Día","Plan (h)","Real (h)","Estado"]],
                     use_container_width=True,hide_index=True)

    # Histórico semanas
    if len(st.session_state.horario)>1:
        st.markdown('<div class="section-header">Ahorro acumulado — todas las semanas</div>',
                    unsafe_allow_html=True)
        rs = []
        for s,dd in sorted(st.session_state.horario.items()):
            tp2 = sum(PLAN_DIA[d] for d in DIAS)
            tr2 = sum(dd.get(d,0) for d in DIAS)
            rs.append({"Semana":s,"Plan":tp2,"Real":round(tr2,2),
                        "Ahorro":round(tp2-tr2,2),"Meta contractual":meta_sem(s),
                        "Cumpl. meta":f"{round(tr2/meta_sem(s)*100,1)}%"})
        dfr = pd.DataFrame(rs)

        fe = go.Figure()
        fe.add_trace(go.Bar(x=dfr["Semana"],y=dfr["Plan"],name="Plan",
                             marker_color="#3C3489",opacity=0.75))
        fe.add_trace(go.Bar(x=dfr["Semana"],y=dfr["Real"],name="Real",
                             marker_color="#185FA5"))
        fe.add_trace(go.Scatter(x=dfr["Semana"],y=dfr["Ahorro"],name="Ahorro",
                                 mode="lines+markers",
                                 line=dict(color="#3B6D11",width=2),
                                 marker=dict(size=7)))
        fe.update_layout(**CHART,barmode="group",height=300,
                          xaxis={**GRID,"title":"Semana"},
                          yaxis={**GRID,"title":"Horas"},
                          legend=dict(orientation="h",y=1.1))
        st.plotly_chart(fe,use_container_width=True)
        st.dataframe(dfr,use_container_width=True,hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — ANÁLISIS
# ══════════════════════════════════════════════════════════════════════════════
with t4:
    if len(df)==0:
        st.info("Carga un CSV o agrega registros.")
    else:
        dfhb = df.dropna(subset=["Hora inicio"]).copy()
        if len(dfhb)>0:
            st.markdown('<div class="section-header">Por bloque horario</div>',unsafe_allow_html=True)
            dfhb["Bloque"] = dfhb["Hora inicio"].apply(bloque)
            orden = ["Madrugada (<9h)","Mañana (9–13h)","Tarde (13–17h)",
                     "Noche (17–21h)","Noche tarde (21h+)"]
            bd = dfhb.groupby("Bloque")["Horas Reales"].sum().reindex(orden,fill_value=0).reset_index()
            fb = px.bar(bd,x="Bloque",y="Horas Reales",
                        color_discrete_sequence=["#3C3489"],text="Horas Reales")
            fb.update_traces(texttemplate="%{text:.1f}h",textposition="outside")
            fb.update_layout(**CHART,height=260,
                              xaxis={**GRID},yaxis={**GRID,"title":"Horas"})
            st.plotly_chart(fb,use_container_width=True)

        ca,cb = st.columns(2)
        with ca:
            st.markdown('<div class="section-header">Duración media por tipo</div>',unsafe_allow_html=True)
            at = df.groupby("Tipo de tarea")["Minutos netos"].mean().reset_index()
            at.columns = ["Tipo","Min promedio"]
            at = at.sort_values("Min promedio")
            fat = px.bar(at,x="Min promedio",y="Tipo",orientation="h",
                         color="Tipo",color_discrete_map=COLORES_TIPO,text="Min promedio")
            fat.update_traces(texttemplate="%{text:.0f} min",textposition="outside")
            fat.update_layout(**CHART,showlegend=False,height=280,
                               xaxis={**GRID,"title":"Minutos"},yaxis={**GRID,"title":""})
            st.plotly_chart(fat,use_container_width=True)

        with cb:
            st.markdown('<div class="section-header">Estado de tareas</div>',unsafe_allow_html=True)
            est = df.groupby("Estado")["Horas Reales"].sum().reset_index()
            fe2 = px.bar(est,x="Estado",y="Horas Reales",color="Estado",
                         color_discrete_map={"Terminado":"#3B6D11",
                                             "En Proceso":"#185FA5","Bloqueado":"#A32D2D"},
                         text="Horas Reales")
            fe2.update_traces(texttemplate="%{text:.1f}h",textposition="outside")
            fe2.update_layout(**CHART,showlegend=False,height=280,
                               xaxis={**GRID},yaxis={**GRID,"title":"Horas"})
            st.plotly_chart(fe2,use_container_width=True)

        st.markdown('<div class="section-header">Heatmap semana × tipo</div>',unsafe_allow_html=True)
        pivot = df.pivot_table(index="Tipo de tarea",columns="Semana",
                                values="Horas Reales",aggfunc="sum",fill_value=0)
        fhm = px.imshow(pivot,color_continuous_scale="Blues",
                         labels=dict(x="Semana",y="Tipo",color="Horas"),
                         aspect="auto",text_auto=".1f")
        fhm.update_layout(**CHART,height=300)
        st.plotly_chart(fhm,use_container_width=True)

        st.markdown('<div class="section-header">Resumen por semana</div>',unsafe_allow_html=True)
        res = df.groupby("Semana").agg(
            Horas=("Horas Reales","sum"),Sesiones=("Horas Reales","count"),
            Avg_min=("Minutos netos","mean"),
            Proyectos=("Proyecto",lambda x:", ".join(sorted(x.dropna().unique())))
        ).reset_index()
        res["Meta"]        = res["Semana"].apply(lambda s:f"{meta_sem(s)}h")
        res["Cumplimiento"]= res.apply(
            lambda r:f"{round(r['Horas']/meta_sem(r['Semana'])*100,1)}%",axis=1)
        res["Horas"]   = res["Horas"].apply(lambda x:f"{x:.1f}h")
        res["Avg_min"] = res["Avg_min"].apply(lambda x:f"{x:.0f} min")
        res.columns    = ["Semana","Horas totales","Sesiones","Avg. sesión",
                          "Proyectos","Meta","Cumplimiento"]
        st.dataframe(res,use_container_width=True,hide_index=True)
