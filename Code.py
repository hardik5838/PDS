import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time

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
def load_data_engine(file_path):
    with st.spinner("🚀 Cargando Motor de Análisis..."):
        try:
            # INTENTO 1: Latin-1 con separador de punto y coma
            df = pd.read_csv(file_path, encoding='latin-1', sep=';', on_bad_lines='skip')
        except Exception:
            try:
                # INTENTO 2: UTF-8 con separador de punto y coma
                df = pd.read_csv(file_path, encoding='utf-8', sep=';', on_bad_lines='skip')
            except Exception:
                # INTENTO 3: Detección automática (más lento pero seguro)
                df = pd.read_csv(file_path, sep=None, engine='python', on_bad_lines='skip')

        # 1. LIMPIEZA DE CABECERAS (CRUCIAL)
        # Convertir todas las cabeceras a mayúsculas y eliminar espacios para estandarizar
        df.columns = df.columns.str.strip().str.upper()

        # 2. MAPEO DE COLUMNAS (ESPAÑOL -> SISTEMA)
        # Se asegura que la columna 'TIPO TRABAJO' o 'TIPO DE TRABAJO' se mapee a 'Categoria'
        # y que 'COSTES (€)' o 'Costes (€)' se mapee a 'Coste' antes de la lógica de categorización.
        COLUMN_MAPPING = {
            'FECHA PLANIFICADA': 'Fecha', 'PLANNED DATE': 'Fecha',
            'DESC. ESTADO': 'Estado', 'STATUS DESCRIPTION': 'Estado',
            'URGENCIA': 'Urgencia', 'URGENCY': 'Urgencia',
            'NOMBRE CENTRO': 'Centro', 'CENTER NAME': 'Centro',
            'DESCRIPCIÓN': 'Descripcion', 'DESCRIPTION': 'Descripcion',
            'CONTRATISTA': 'Contratista', 'CONTRACTOR': 'Contratista',
            'CCAA': 'CCAA', 
            'TIPO DE TRABAJO': 'Categoria_Raw',  # Mapear a RAW para aplicar la lógica
            'TIPO TRABAJO': 'Categoria_Raw',     # Opción alternativa de la cabecera
            'COSTES (€)': 'Coste',               # Columna Coste original
            'ESPECIALIDAD': 'Especialidad',
            'INICIO REAL': 'Inicio_Real'
        }
        
        # Aplicar el mapeo de columnas
        df.rename(columns=COLUMN_MAPPING, inplace=True)
        
        # 3. CONVERSIÓN DE FECHAS (FORMATO EUROPEO DIA/MES/AÑO)
        if 'Fecha' in df.columns:
            # dayfirst=True maneja formatos DD/MM/YYYY
            df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
            # Eliminar filas donde la fecha no se pudo leer (NaT)
            df = df.dropna(subset=['Fecha'])

        # --- RESTAURACIÓN DE LÓGICA DE CÁLCULO ---
        
        # 4. Work Category Logic (Restored from your initial request logic)
        def categorize(val):
            """Clasifica el tipo de trabajo basado en la descripción."""
            s = str(val).upper()
            if 'COR' in s: return 'Correctivo'
            if 'PRV' in s: return 'Preventivo'
            if 'MOD' in s: return 'Modificativo'
            return 'Otros'
            
        # Priorizar la columna Categoria_Raw si existe (mapeada desde TIPO TRABAJO/TIPO DE TRABAJO)
        if 'Categoria_Raw' in df.columns:
            df['Categoria'] = df['Categoria_Raw'].apply(categorize)
        else:
            # Fallback si no se encontró la columna de tipo de trabajo.
            df['Categoria'] = 'General'

        # 5. Cost Logic (Restored)
        if 'Coste' in df.columns:
            # Limpiar la columna de coste, asumiendo formato con punto como separador de miles y coma como decimal
            df['Coste'] = (
                df['Coste']
                .astype(str)
                .str.replace('.', '', regex=False)  # Remove thousands separator (e.g., 1.000.000)
                .str.replace(',', '.', regex=False)  # Replace decimal comma with dot (e.g., 10,50)
            )
            df['Coste'] = pd.to_numeric(df['Coste'], errors='coerce').fillna(0)
        else:
            df['Coste'] = 0

        # 6. Duration Logic (Simulated if start date exists - Restored)
        if 'Inicio_Real' in df.columns:
            df['Inicio_Real'] = pd.to_datetime(df['Inicio_Real'], dayfirst=True, errors='coerce')
            # Calculamos la diferencia entre la fecha planificada y el inicio real en días
            df['Dias_Ejecucion'] = (df['Fecha'] - df['Inicio_Real']).dt.days
            df['Dias_Ejecucion'] = df['Dias_Ejecucion'].fillna(0)
        else:
            df['Dias_Ejecucion'] = 0
            
        # Re-check for the critical column before returning
        if 'Categoria' not in df.columns:
             # This should not happen now, but provides a safety net
             df['Categoria'] = 'Missing'
             
        return df

# --- Data Loading and Initial Checks ---
df = load_data_engine('PDS - Hoja1.csv')
if df.empty:
    st.error("⚠️ Error Crítico: No se pudo cargar el archivo o quedó vacío tras la limpieza. Verifique 'PDS - Hoja1.csv' y sus cabeceras.")
    st.stop()

# --- 4. SIDEBAR: MAXIMUM GRANULARITY ---
st.sidebar.title("🎛️ FILTROS MAESTROS")

# SECTION 1: TIME
with st.sidebar.expander("📅 TIEMPO Y FECHA", expanded=True):
    min_d, max_d = df['Fecha'].min().date(), df['Fecha'].max().date()
    # Check if max_d is before min_d and adjust for safe default
    if min_d > max_d:
        date_range = st.date_input("Rango", [min_d, min_d])
    else:
        date_range = st.date_input("Rango", [min_d, max_d])

# SECTION 2: WORK TYPES (COWORKER REQUEST)
with st.sidebar.expander("🔧 TIPO DE TRABAJO (REQ)", expanded=True):
    # Toggle for Category
    # FIX: This line now runs successfully because 'Categoria' is guaranteed to exist.
    cat_opts = sorted(df['Categoria'].unique())
    sel_cat = st.multiselect("Categoría (COR/PRV)", cat_opts, default=cat_opts)
    
    # Granular Specialty
    if 'Especialidad' in df.columns:
        spec_opts = sorted(df['Especialidad'].dropna().unique())
        sel_spec = st.multiselect("Especialidad Técnica", spec_opts, default=spec_opts)
    else:
        sel_spec = []

# SECTION 3: GEOGRAPHY & OPS
with st.sidebar.expander("🌍 UBICACIÓN Y ESTADO", expanded=False):
    ccaa_opts = sorted(df['CCAA'].dropna().unique())
    sel_ccaa = st.multiselect("Comunidades", ccaa_opts, default=ccaa_opts)
    
    status_opts = sorted(df['Estado'].dropna().unique())
    sel_status = st.multiselect("Estado Orden", status_opts, default=status_opts)
    
    urg_opts = sorted(df['Urgencia'].dropna().unique())
    sel_urg = st.multiselect("Urgencia", urg_opts, default=urg_opts)

# SECTION 4: CONTRACTORS
with st.sidebar.expander("👷 CONTRATISTAS", expanded=False):
    contr_opts = sorted(df['Contratista'].dropna().unique())
    sel_contr = st.multiselect("Empresa", contr_opts, default=contr_opts)

# APPLY FILTERS
# Convert date_range to datetime objects for comparison
if len(date_range) == 2:
    start_date = pd.to_datetime(date_range[0])
    end_date = pd.to_datetime(date_range[1])

    mask = (
        (df['Fecha'] >= start_date) & (df['Fecha'] <= end_date) &
        (df['Categoria'].isin(sel_cat)) & (df['CCAA'].isin(sel_ccaa)) &
        (df['Estado'].isin(sel_status)) & (df['Urgencia'].isin(sel_urg)) &
        (df['Contratista'].isin(sel_contr))
    )
    if sel_spec and 'Especialidad' in df.columns: 
        mask = mask & (df['Especialidad'].isin(sel_spec))
    
    df_f = df[mask]
else:
    # If the date range is invalid (e.g., only one date selected), prevent crash
    st.warning("Seleccione un rango de fechas válido. Mostrando datos sin filtro de fecha.")
    df_f = df.copy() # Use the full data if range is invalid/incomplete

if df_f.empty:
    st.info("No hay datos que coincidan con los filtros seleccionados.")
    st.stop()
    
# --- 5. TOP TOGGLES & KPIS (THE "NO UPPER LIMIT" PART) ---
st.title("📟 MONITOR DE OPERACIONES")

# Toggles for Analysis Mode
c_tog1, c_tog2, c_tog3 = st.columns([1,1,2])
with c_tog1:
    view_metric = st.radio("Métrica Principal:", ["Volumen (#)", "Coste (€)"], horizontal=True)
with c_tog2:
    view_geo = st.radio("Nivel Geo:", ["Región", "Centro"], horizontal=True)

# KPI DECK (6 Metrics)
k1, k2, k3, k4, k5, k6 = st.columns(6)
total_vol = len(df_f)
total_cost = df_f['Coste'].sum()
crit_count = len(df_f[df_f['Urgencia'].astype(str).str.contains('CRITIC|URGENTE', case=False)])

k1.metric("Órdenes", f"{total_vol:,}", delta="Total Filtrado")
k2.metric("Coste Acumulado", f"€{total_cost:,.0f}", delta_color="inverse")
k3.metric("Urgentes/Críticas", crit_count, delta=f"{crit_count/total_vol*100:.1f}% del total" if total_vol else "0%")
k4.metric("Correctivos", len(df_f[df_f['Categoria']=='Correctivo']), delta="Break-fix")
k5.metric("Preventivos", len(df_f[df_f['Categoria']=='Preventivo']), delta="Planned")
k6.metric("Contratistas Activos", df_f['Contratista'].nunique())

st.markdown("---")

# --- 6. CHARTS: THE "BUNCH OF FEATURES" ---

# Determine Y-Axis based on Toggle
# Note: 'Count' is used in the grouping size() function, not as a column name in the df
y_val = 'Coste' if view_metric == "Coste (€)" else 'Value' 
# Determine X-Axis based on Toggle
x_geo = 'CCAA' if view_geo == "Región" else 'Centro'

# Prepare Aggregated Data
if view_metric == "Coste (€)":
    df_agg = df_f.groupby([x_geo, 'Categoria'])['Coste'].sum().reset_index()
    df_agg.rename(columns={'Coste': 'Value'}, inplace=True)
else:
    df_agg = df_f.groupby([x_geo, 'Categoria']).size().reset_index(name='Value')

# TAB SYSTEM FOR DENSITY
tab_main, tab_deep, tab_perf, tab_raw = st.tabs(["📊 ANÁLISIS GLOBAL", "🔬 DRILL-DOWN", "🏆 RENDIMIENTO", "📄 DATASET"])

with tab_main:
    row1_1, row1_2 = st.columns([2, 1])
    
    with row1_1:
        st.subheader(f"Distribución por {x_geo}")
        # BAR CHART
        fig_bar = px.bar(df_agg.sort_values('Value', ascending=True).tail(20), 
                          x='Value', y=x_geo, color='Categoria', orientation='h', 
                          text='Value', title=f"Top 20 {x_geo} por {view_metric}",
                          color_discrete_sequence=px.colors.qualitative.Bold)
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with row1_2:
        st.subheader("Estado Actual")
        # DONUT CHART
        fig_don = px.pie(df_f, names='Estado', hole=0.5, title="Mix de Estados")
        fig_don.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_don, use_container_width=True)

    row2_1, row2_2 = st.columns(2)
    with row2_1:
        st.subheader("Tendencia Temporal (Lineas)")
        # TIME SERIES
        df_time = df_f.copy()
        # Resampling is safer than using .dt.to_period('M') for time series
        # Aggregate by week or month and sum the counts
        df_time_agg = df_time.groupby([pd.Grouper(key='Fecha', freq='M'), 'Categoria']).size().reset_index(name='Count')
        
        fig_line = px.line(df_time_agg, x='Fecha', y='Count', color='Categoria', markers=True, title="Evolución Mensual")
        st.plotly_chart(fig_line, use_container_width=True)
        
    with row2_2:
        st.subheader("Mapa de Calor: Urgencia vs Estado")
        # HEATMAP
        heat_data = df_f.groupby(['Urgencia', 'Estado']).size().reset_index(name='Count')
        fig_heat = px.density_heatmap(heat_data, x='Estado', y='Urgencia', z='Count', text_auto=True, color_continuous_scale='Viridis')
        fig_heat.update_layout(xaxis_title="Estado", yaxis_title="Urgencia")
        st.plotly_chart(fig_heat, use_container_width=True)

with tab_deep:
    c_deep1, c_deep2 = st.columns(2)
    with c_deep1:
        st.subheader("Jerarquía Solar (Sunburst)")
        st.info("Click en el centro para expandir")
        # SUNBURST
        path = ['CCAA', 'Centro', 'Categoria'] if x_geo == 'CCAA' else ['Centro', 'Categoria', 'Estado']
        # Limit data for performance (5000 rows is a good limit for interactive Plotly charts)
        fig_sun = px.sunburst(df_f.head(5000), path=path, color='Categoria', title="Exploración Jerárquica")
        fig_sun.update_layout(height=500)
        st.plotly_chart(fig_sun, use_container_width=True)
        
    with c_deep2:
        st.subheader("Volumen Relativo (Treemap)")
        # TREEMAP
        fig_tree = px.treemap(df_f, path=['Categoria', 'Urgencia', 'Estado'], title="Composición del Trabajo")
        st.plotly_chart(fig_tree, use_container_width=True)

with tab_perf:
    c_perf1, c_perf2, c_perf3 = st.columns(3)
    
    with c_perf1:
        st.subheader("Top Contratistas")
        top_con = df_f['Contratista'].value_counts().head(10)
        fig_c = px.bar(x=top_con.index, y=top_con.values, title="Órdenes por Empresa")
        st.plotly_chart(fig_c, use_container_width=True)
        
    with c_perf2:
        st.subheader("Top Especialidades")
        if 'Especialidad' in df_f.columns:
            top_s = df_f['Especialidad'].value_counts().head(10)
            fig_s = px.bar(x=top_s.values, y=top_s.index, orientation='h', title="Especialidades")
            fig_s.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_s, use_container_width=True)
            
    with c_perf3:
        st.subheader("Embudo de Estados")
        # FUNNEL CHART
        funnel_data = df_f['Estado'].value_counts().reset_index()
        funnel_data.columns = ['Estado', 'Count']
        # Sort by a desired order (e.g., typical workflow)
        order = ['Pendiente', 'En Curso', 'Finalizada', 'Facturada', 'Cancelada'] 
        funnel_data['Estado'] = pd.Categorical(funnel_data['Estado'], categories=order, ordered=True)
        funnel_data.sort_values('Estado', inplace=True)
        
        fig_fun = px.funnel(funnel_data, x='Count', y='Estado')
        st.plotly_chart(fig_fun, use_container_width=True)

with tab_raw:
    st.subheader("Explorador de Datos Crudos")
    
    # SAFE MULTISELECT LOGIC (Prevents crashes)
    all_cols = list(df_f.columns)
    # Define ideal columns
    ideal = ['Fecha', 'CCAA', 'Centro', 'Descripcion', 'Categoria', 'Estado', 'Urgencia', 'Contratista', 'Coste', 'Dias_Ejecucion']
    # Filter ideal columns to only those that exist
    defaults = [c for c in ideal if c in all_cols]
    
    cols_to_show = st.multiselect("Columnas Visibles", all_cols, default=defaults)
    
    st.dataframe(
        df_f[cols_to_show].sort_values('Fecha', ascending=False),
        use_container_width=True,
        column_config={
            "Coste": st.column_config.NumberColumn(format="€ %.2f")
        }
    )
    
    # CSV DOWNLOAD
    csv_data = df_f.to_csv(index=False).encode('utf-8')
    st.download_button("📥 DESCARGAR CSV COMPLETO", csv_data, "dashboard_export.csv", "text/csv")
