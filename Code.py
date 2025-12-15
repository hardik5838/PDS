import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
import os

# --- 1. PAGE CONFIGURATION (MAX WIDE MODE) ---
st.set_page_config(
    page_title="COMMAND CENTER PRO",
    page_icon="☢️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CSS FOR HIGH DENSITY (NASA STYLE) ---
st.markdown("""
<style>
    .block-container {padding-top: 1rem; padding-bottom: 2rem;}
    [data-testid="stMetricValue"] {font-size: 1.4rem !important;}
    h1, h2, h3 {margin-bottom: 0.5rem;}
    .stTabs [data-baseweb="tab-list"] {gap: 4px;}
    .stTabs [data-baseweb="tab"] {height: 40px; white-space: pre-wrap; padding-top: 10px; padding-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

# --- 3. ROBUST ENGINE (CRASH PROOF) ---
@st.cache_data
def load_data_engine(file_path_or_buffer):
    with st.spinner("🚀 Cargando Motor de Análisis..."):
        try:
            # INTENTO 1: Latin-1 con separador de punto y coma
            df = pd.read_csv(file_path_or_buffer, encoding='latin-1', sep=';', on_bad_lines='skip')
        except Exception:
            try:
                if hasattr(file_path_or_buffer, 'seek'): file_path_or_buffer.seek(0)
                # INTENTO 2: UTF-8 con separador de punto y coma
                df = pd.read_csv(file_path_or_buffer, encoding='utf-8', sep=';', on_bad_lines='skip')
            except Exception:
                if hasattr(file_path_or_buffer, 'seek'): file_path_or_buffer.seek(0)
                # INTENTO 3: Detección automática
                df = pd.read_csv(file_path_or_buffer, sep=None, engine='python', on_bad_lines='skip')

        # 1. LIMPIEZA DE CABECERAS
        df.columns = df.columns.str.strip().str.upper()

        # 2. MAPEO DE COLUMNAS (ESPAÑOL -> SISTEMA)
        col_map = {
            'FECHA PLANIFICADA': 'Fecha', 'PLANNED DATE': 'Fecha',
            'DESC. ESTADO': 'Estado', 'STATUS DESCRIPTION': 'Estado',
            'URGENCIA': 'Urgencia', 'URGENCY': 'Urgencia',
            'NOMBRE CENTRO': 'Centro', 'CENTER NAME': 'Centro',
            'DESCRIPCIÓN': 'Descripcion', 'DESCRIPTION': 'Descripcion',
            'CONTRATISTA': 'Contratista', 'CONTRACTOR': 'Contratista',
            'CCAA': 'CCAA', 
            'TIPO DE TRABAJO': 'Categoria_Raw', 
            'TIPO TRABAJO': 'Categoria_Raw', 
            'COSTES (€)': 'Coste', 'COSTES': 'Coste', # Added fallback
            'ESPECIALIDAD': 'Especialidad',
            'INICIO REAL': 'Inicio_Real'
        }
        df.rename(columns=col_map, inplace=True)
        
        # --- FIX CRITICO: ELIMINAR COLUMNAS DUPLICADAS ---
        df = df.loc[:, ~df.columns.duplicated()]
        
        # 3. CONVERSIÓN DE FECHAS
        if 'Fecha' in df.columns:
            df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
            df = df.dropna(subset=['Fecha'])

        # 4. Work Category Logic (COR/PRV/MOD)
        def categorize(val):
            s = str(val).upper()
            if 'COR' in s: return 'Correctivo'
            if 'PRV' in s: return 'Preventivo'
            if 'MOD' in s: return 'Modificativo'
            return 'Otros'
            
        if 'Categoria_Raw' in df.columns:
            df['Categoria'] = df['Categoria_Raw'].apply(categorize)
        else:
            df['Categoria'] = 'General'

        # --- FIX MEJORADO: LIMPIEZA DE COSTES ---
        if 'Coste' in df.columns:
            # Forzamos conversión a string para manipular
            df['Coste'] = df['Coste'].astype(str)
            
            # Limpieza agresiva:
            # 1. Reemplazar 'nan' string por 0
            # 2. Quitar símbolo de Euro y espacios
            # 3. Quitar puntos de miles (1.000 -> 1000)
            # 4. Reemplazar coma decimal por punto (73,5 -> 73.5)
            df['Coste'] = (
                df['Coste']
                .str.lower()
                .str.replace('nan', '0', regex=False)
                .str.replace('none', '0', regex=False)
                .str.replace('€', '', regex=False)
                .str.strip()
                .str.replace('.', '', regex=False)  # Quita separador de miles
                .str.replace(',', '.', regex=False) # Cambia coma decimal a punto
            )
            
            # Convertir a número, los errores se vuelven 0
            df['Coste'] = pd.to_numeric(df['Coste'], errors='coerce').fillna(0)
        else:
            df['Coste'] = 0

        # 6. Duration Logic (Cálculo de días)
        if 'Inicio_Real' in df.columns:
            df['Inicio_Real'] = pd.to_datetime(df['Inicio_Real'], dayfirst=True, errors='coerce')
            df['Dias_Ejecucion'] = (df['Fecha'] - df['Inicio_Real']).dt.days
            df['Dias_Ejecucion'] = df['Dias_Ejecucion'].fillna(0)
        else:
            df['Dias_Ejecucion'] = 0

        return df

# --- 4. DATA LOADING LOGIC ---
st.sidebar.title("🎛️ DATOS")
uploaded_file = st.sidebar.file_uploader("📂 Cargar 'PDS - Hoja1.csv'", type=['csv', 'txt'])

df = None
if uploaded_file is not None:
    df = load_data_engine(uploaded_file)
else:
    local_path = 'PDS - Hoja1.csv'
    if os.path.exists(local_path):
        df = load_data_engine(local_path)
    else:
        # Fallback if specific name is not found but others exist? No, strict check for safety.
        st.warning("⚠️ Esperando archivo. Suba el CSV en el panel lateral.")
        st.stop()

if df is None or df.empty:
    st.error("⚠️ El archivo está vacío o no se pudo procesar.")
    st.stop()

# --- 5. SIDEBAR: FILTERS ---
st.sidebar.markdown("---")
st.sidebar.title("FILTROS MAESTROS")

# SECTION 1: TIME
with st.sidebar.expander("📅 TIEMPO Y FECHA", expanded=True):
    min_d, max_d = df['Fecha'].min().date(), df['Fecha'].max().date()
    if min_d > max_d: date_range = st.date_input("Rango", [min_d, min_d])
    else: date_range = st.date_input("Rango", [min_d, max_d])

# SECTION 2: GEOGRAPHY (Hierarchical)
with st.sidebar.expander("🌍 UBICACIÓN (CCAA y CENTRO)", expanded=True):
    # 1. Filtro CCAA
    ccaa_opts = sorted(df['CCAA'].dropna().unique())
    sel_ccaa = st.multiselect("Comunidades", ccaa_opts, default=ccaa_opts)
    
    # 2. Filtro CENTRO (Depende de las CCAA seleccionadas)
    # --- NEW: Logic to filter centers based on CCAA selection ---
    if sel_ccaa:
        filtered_centers_list = df[df['CCAA'].isin(sel_ccaa)]['Centro'].dropna().unique()
    else:
        filtered_centers_list = df['Centro'].dropna().unique()
        
    center_opts = sorted(filtered_centers_list)
    # Default: Select ALL available centers to avoid empty charts initially
    sel_center = st.multiselect("Centros", center_opts, default=center_opts)

# SECTION 3: WORK TYPES & DETAILS
with st.sidebar.expander("🔧 TIPO Y DETALLES", expanded=False):
    cat_opts = sorted(df['Categoria'].unique())
    sel_cat = st.multiselect("Categoría", cat_opts, default=cat_opts)
    
    status_opts = sorted(df['Estado'].dropna().unique())
    sel_status = st.multiselect("Estado", status_opts, default=status_opts)
    
    urg_opts = sorted(df['Urgencia'].dropna().unique())
    sel_urg = st.multiselect("Urgencia", urg_opts, default=urg_opts)
    
    if 'Especialidad' in df.columns:
        spec_opts = sorted(df['Especialidad'].dropna().unique())
        sel_spec = st.multiselect("Especialidad", spec_opts, default=spec_opts)
    else:
        sel_spec = []

# SECTION 4: CONTRACTORS
with st.sidebar.expander("👷 CONTRATISTAS", expanded=False):
    contr_opts = sorted(df['Contratista'].dropna().unique())
    sel_contr = st.multiselect("Empresa", contr_opts, default=contr_opts)

# APPLY FILTERS
if len(date_range) == 2:
    start_date = pd.to_datetime(date_range[0])
    end_date = pd.to_datetime(date_range[1])

    mask = (
        (df['Fecha'] >= start_date) & (df['Fecha'] <= end_date) &
        (df['CCAA'].isin(sel_ccaa)) & 
        (df['Centro'].isin(sel_center)) & # --- NEW: Apply Center Filter ---
        (df['Categoria'].isin(sel_cat)) & 
        (df['Estado'].isin(sel_status)) & 
        (df['Urgencia'].isin(sel_urg)) &
        (df['Contratista'].isin(sel_contr))
    )
    if sel_spec and 'Especialidad' in df.columns: 
        mask = mask & (df['Especialidad'].isin(sel_spec))
    
    df_f = df[mask]
else:
    df_f = df.copy()

if df_f.empty:
    st.info("No hay datos que coincidan con los filtros seleccionados.")
    st.stop()

# --- 6. TOP TOGGLES & KPIS ---
st.title("📟 MONITOR DE OPERACIONES")

c_tog1, c_tog2 = st.columns([1,1])
with c_tog1:
    view_metric = st.radio("Métrica:", ["Volumen (#)", "Coste (€)"], horizontal=True)
with c_tog2:
    view_geo = st.radio("Agrupación:", ["Región (CCAA)", "Centro"], horizontal=True)

# KPI DECK
k1, k2, k3, k4, k5, k6 = st.columns(6)
total_vol = len(df_f)
total_cost = df_f['Coste'].sum()
crit_count = len(df_f[df_f['Urgencia'].astype(str).str.contains('CRITIC|URGENTE', case=False)])

k1.metric("Órdenes", f"{total_vol:,}")
k2.metric("Coste Total", f"€{total_cost:,.2f}") # Formatted to show decimals
k3.metric("Urgentes", crit_count)
k4.metric("Correctivos", len(df_f[df_f['Categoria']=='Correctivo']))
k5.metric("Preventivos", len(df_f[df_f['Categoria']=='Preventivo']))
k6.metric("Contratistas", df_f['Contratista'].nunique())

st.markdown("---")

# --- 7. CHARTS & VISUALIZATIONS ---
y_val = 'Coste' if view_metric == "Coste (€)" else 'Value' 
# Logic for grouping based on toggle
x_geo = 'CCAA' if view_geo == "Región (CCAA)" else 'Centro'

if view_metric == "Coste (€)":
    df_agg = df_f.groupby([x_geo, 'Categoria'])['Coste'].sum().reset_index()
    df_agg.rename(columns={'Coste': 'Value'}, inplace=True)
else:
    df_agg = df_f.groupby([x_geo, 'Categoria']).size().reset_index(name='Value')

tab_main, tab_deep, tab_perf, tab_raw = st.tabs(["📊 ANÁLISIS GLOBAL", "🔬 DRILL-DOWN", "🏆 RENDIMIENTO", "📄 DATASET"])

with tab_main:
    row1_1, row1_2 = st.columns([2, 1])
    with row1_1:
        st.subheader(f"Distribución por {x_geo}")
        # Limit centers chart to top 20 to avoid overcrowding if grouping by Center
        limit_rows = 20 if x_geo == 'Centro' else 50
        
        fig_bar = px.bar(df_agg.groupby(x_geo)['Value'].sum().reset_index().sort_values('Value').tail(limit_rows), 
                          x='Value', y=x_geo, orientation='h', 
                          text='Value', title=f"Top {limit_rows} {x_geo}",
                          color_discrete_sequence=px.colors.qualitative.Bold)
        fig_bar.update_traces(texttemplate='%{text:.2s}' if view_metric == "Coste (€)" else '%{text}')
        st.plotly_chart(fig_bar, use_container_width=True)
    with row1_2:
        st.subheader("Estado")
        fig_don = px.pie(df_f, names='Estado', hole=0.5, color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig_don, use_container_width=True)

    row2_1, row2_2 = st.columns(2)
    with row2_1:
        st.subheader("Evolución Mensual")
        # Ensure we count or sum correctly for the line chart
        if view_metric == "Coste (€)":
            df_time_agg = df_f.groupby([pd.Grouper(key='Fecha', freq='M'), 'Categoria'])['Coste'].sum().reset_index(name='Value')
        else:
            df_time_agg = df_f.groupby([pd.Grouper(key='Fecha', freq='M'), 'Categoria']).size().reset_index(name='Value')
            
        fig_line = px.line(df_time_agg, x='Fecha', y='Value', color='Categoria', markers=True)
        st.plotly_chart(fig_line, use_container_width=True)
    with row2_2:
        st.subheader("Mapa de Calor (Urgencia vs Estado)")
        heat_data = df_f.groupby(['Urgencia', 'Estado']).size().reset_index(name='Count')
        fig_heat = px.density_heatmap(heat_data, x='Estado', y='Urgencia', z='Count', text_auto=True, color_continuous_scale='Viridis')
        st.plotly_chart(fig_heat, use_container_width=True)

with tab_deep:
    c_deep1, c_deep2 = st.columns(2)
    with c_deep1:
        st.subheader("Jerarquía Solar")
        # Limit data for sunburst to avoid lag with 10k+ rows
        path = ['CCAA', 'Centro', 'Categoria'] if x_geo == 'CCAA' else ['Categoria', 'CCAA', 'Centro']
        fig_sun = px.sunburst(df_f, path=path, values='Coste' if view_metric == "Coste (€)" else None, color='Categoria')
        fig_sun.update_layout(height=500)
        st.plotly_chart(fig_sun, use_container_width=True)
    with c_deep2:
        st.subheader("Composición (Treemap)")
        fig_tree = px.treemap(df_f, path=['Categoria', 'Urgencia', 'Estado'], values='Coste' if view_metric == "Coste (€)" else None)
        st.plotly_chart(fig_tree, use_container_width=True)

with tab_perf:
    c_perf1, c_perf2, c_perf3 = st.columns(3)
    with c_perf1:
        st.subheader("Top Contratistas")
        # Aggregation logic based on metric
        if view_metric == "Coste (€)":
            top_con = df_f.groupby('Contratista')['Coste'].sum().sort_values(ascending=False).head(10)
        else:
            top_con = df_f['Contratista'].value_counts().head(10)
            
        fig_c = px.bar(x=top_con.index, y=top_con.values, title="Top Contratistas")
        st.plotly_chart(fig_c, use_container_width=True)
        
    with c_perf2:
        st.subheader("Top Especialidades")
        if 'Especialidad' in df_f.columns:
            if view_metric == "Coste (€)":
                top_s = df_f.groupby('Especialidad')['Coste'].sum().sort_values(ascending=False).head(10)
            else:
                top_s = df_f['Especialidad'].value_counts().head(10)
            fig_s = px.bar(x=top_s.values, y=top_s.index, orientation='h', title="Top Especialidades")
            st.plotly_chart(fig_s, use_container_width=True)
            
    with c_perf3:
        st.subheader("Embudo de Estados")
        funnel_data = df_f['Estado'].value_counts().reset_index()
        funnel_data.columns = ['Estado', 'Count']
        fig_fun = px.funnel(funnel_data, x='Count', y='Estado')
        st.plotly_chart(fig_fun, use_container_width=True)

with tab_raw:
    cols_to_show = st.multiselect("Columnas", list(df_f.columns), default=list(df_f.columns)[:10])
    
    st.dataframe(
        df_f.sort_values('Fecha', ascending=False)[cols_to_show], 
        use_container_width=True,
        column_config={"Coste": st.column_config.NumberColumn(format="€ %.2f")}
    )
    
    csv_data = df_f.to_csv(index=False).encode('utf-8')
    st.download_button("📥 DESCARGAR CSV FILTRADO", csv_data, "data_export.csv", "text/csv")
