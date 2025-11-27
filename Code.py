import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time

# --- 1. CONFIGURATION & LAYOUT ---
st.set_page_config(
    page_title="Master Command Center",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS to make it look denser and professional
st.markdown("""
<style>
    .block-container {padding-top: 1rem; padding-bottom: 0rem;}
    [data-testid="stMetricValue"] {font-size: 1.5rem;}
    hr {margin-top: 0.5rem; margin-bottom: 0.5rem;}
</style>
""", unsafe_allow_html=True)

# --- 2. ROBUST DATA LOADER ---
@st.cache_data
def load_data_robust(file_path):
    # Status container for feedback
    with st.status("🚀 Iniciando Motor de Datos...", expanded=True) as status:
        st.write("📂 Leyendo archivo crudo...")
        
        # Try Latin-1 first (common for Spanish Excel), then UTF-8
        try:
            df = pd.read_csv(file_path, encoding='latin-1', sep=',', on_bad_lines='skip')
        except:
            df = pd.read_csv(file_path, encoding='utf-8', sep=',', on_bad_lines='skip')

        st.write("🧹 Normalizando cabeceras...")
        # FORCE UPPERCASE AND STRIP to prevent "AttributeError"
        df.columns = df.columns.str.strip().str.upper()

        # ROBUST MAPPING (All Keys Uppercase)
        col_map = {
            'FECHA PLANIFICADA': 'Fecha',
            'PLANNED DATE': 'Fecha',
            'DESC. ESTADO': 'Estado',
            'STATUS DESCRIPTION': 'Estado',
            'URGENCIA': 'Urgencia',
            'URGENCY': 'Urgencia',
            'NOMBRE CENTRO': 'Centro',
            'CENTER NAME': 'Centro',
            'DESCRIPCIÓN': 'Descripcion',
            'DESCRIPTION': 'Descripcion',
            'CONTRATISTA': 'Contratista',
            'CONTRACTOR': 'Contratista',
            'CCAA': 'CCAA',
            'AUTONOMOUS COMMUNITY': 'CCAA',
            'TIPO TRABAJO': 'Tipo_Raw',
            'JOB TYPE': 'Tipo_Raw',
            'ESPECIALIDAD': 'Especialidad',
            'SPECIALTY': 'Especialidad',
            'COSTES (€)': 'Coste'
        }
        
        # Rename columns that match
        df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)

        # Validation
        if 'Fecha' not in df.columns or 'Estado' not in df.columns:
            st.error(f"⚠️ Error Crítico: Faltan columnas clave. Columnas detectadas: {list(df.columns)}")
            st.stop()

        st.write("📅 Procesando fechas y lógica de negocio...")
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Fecha'])

        # Logic: Work Category
        def get_category(val):
            val = str(val).upper()
            if 'COR' in val: return 'Correctivo'
            if 'PRV' in val: return 'Preventivo'
            if 'MOD' in val: return 'Modificativo'
            return 'Otros'
            
        col_type = 'Tipo_Raw' if 'Tipo_Raw' in df.columns else 'Tipo_de_Trabajo' # Fallback
        if col_type in df.columns:
            df['Categoria'] = df[col_type].apply(get_category)
        else:
            df['Categoria'] = 'General'

        # Logic: Cost Handling
        if 'Coste' in df.columns:
            df['Coste'] = pd.to_numeric(df['Coste'], errors='coerce').fillna(0)
        else:
            df['Coste'] = 0

        status.update(label="✅ Sistema Listo", state="complete", expanded=False)
        return df

# LOAD DATA
df = load_data_robust('PDS - Hoja1.csv') # <--- VERIFY FILENAME

# --- 3. SIDEBAR FILTERS (DEEP GRANULARITY) ---
st.sidebar.title("🎛️ Panel de Control")

# Date Range
min_d, max_d = df['Fecha'].min().date(), df['Fecha'].max().date()
date_range = st.sidebar.date_input("Periodo de Análisis", [min_d, max_d])

# Multi-Select Filters
st.sidebar.subheader("Segmentación")
sel_ccaa = st.sidebar.multiselect("📍 Comunidad", sorted(df['CCAA'].unique()), default=sorted(df['CCAA'].unique()))
sel_cat = st.sidebar.multiselect("🔧 Tipo Trabajo", sorted(df['Categoria'].unique()), default=sorted(df['Categoria'].unique()))
sel_urg = st.sidebar.multiselect("⚠️ Urgencia", sorted(df['Urgencia'].unique()), default=sorted(df['Urgencia'].unique()))

# Advanced Text Search
search_q = st.sidebar.text_input("🔎 Buscar en Descripción (ID, Texto...)")

# Apply Logic
mask = (
    (df['Fecha'].dt.date >= date_range[0]) &
    (df['Fecha'].dt.date <= date_range[1]) &
    (df['CCAA'].isin(sel_ccaa)) &
    (df['Categoria'].isin(sel_cat)) &
    (df['Urgencia'].isin(sel_urg))
)

if search_q:
    mask = mask & (df['Descripcion'].astype(str).str.contains(search_q, case=False, na=False))

df_f = df[mask]

# --- 4. MAIN DASHBOARD ---

# Top Header with Global Stats
st.title("🏢 Dashboard de Operaciones y Mantenimiento")

# Row 1: High Level Metrics
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Órdenes Totales", f"{len(df_f):,}", delta=f"{len(df_f)} vs Total")
m2.metric("Correctivos", len(df_f[df_f['Categoria']=='Correctivo']), delta_color="inverse")
m3.metric("Preventivos", len(df_f[df_f['Categoria']=='Preventivo']))
m4.metric("Coste Estimado", f"€{df_f['Coste'].sum():,.0f}")
# Calc Pending %
pending_count = len(df_f[df_f['Estado'].astype(str).str.contains('Pend|Wait|Open', case=False, regex=True)])
pct_pending = (pending_count/len(df_f)*100) if len(df_f)>0 else 0
m5.metric("% Pendiente", f"{pct_pending:.1f}%", delta_color="off")

st.markdown("---")

# TABS FOR DETAIL
tab1, tab2, tab3, tab4 = st.tabs(["📊 Visión General", "🌍 Mapa y Regiones", "👷 Contratistas y Especialidad", "📑 Datos Crudos"])

# --- TAB 1: OVERVIEW & TRENDS ---
with tab1:
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.subheader("Tendencia de Creación de Órdenes")
        # Area chart by Category
        df_trend = df_f.groupby([pd.Grouper(key='Fecha', freq='W'), 'Categoria']).size().reset_index(name='Count')
        fig_trend = px.area(df_trend, x='Fecha', y='Count', color='Categoria', 
                            title="Evolución Semanal por Tipo", template="plotly_white")
        st.plotly_chart(fig_trend, use_container_width=True)
        
    with c2:
        st.subheader("Estado Actual")
        # Donut Chart
        fig_donut = px.pie(df_f, names='Estado', hole=0.4, title="Distribución de Estados")
        fig_donut.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_donut, use_container_width=True)

    # Row 2 in Tab 1
    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Relación Urgencia vs Tipo")
        # Heatmap
        df_heat = df_f.groupby(['Urgencia', 'Categoria']).size().reset_index(name='Total')
        fig_heat = px.density_heatmap(df_heat, x='Categoria', y='Urgencia', z='Total', text_auto=True, color_continuous_scale="Viridis")
        st.plotly_chart(fig_heat, use_container_width=True)
    
    with c4:
        st.subheader("Top 10 Centros con Más Incidencias")
        top_centers = df_f['Centro'].value_counts().head(10).sort_values(ascending=True)
        fig_bar = px.bar(top_centers, x=top_centers.values, y=top_centers.index, orientation='h', text_auto=True)
        st.plotly_chart(fig_bar, use_container_width=True)

# --- TAB 2: GEOGRAPHIC (HIERARCHY) ---
with tab2:
    st.subheader("Desglose Jerárquico: CCAA ➡ Centro ➡ Estado")
    st.write("Haga clic en los sectores para profundizar.")
    
    # Sunburst Chart (Very high detail visualization)
    # Handle NaN values for hierarchy
    df_sun = df_f[['CCAA', 'Centro', 'Estado']].dropna()
    # Limit to top data to keep chart responsive
    if len(df_sun) > 5000:
        df_sun = df_sun.head(5000)
        st.info("Visualizando las primeras 5000 filas para optimizar rendimiento.")
        
    fig_sun = px.sunburst(df_sun, path=['CCAA', 'Centro', 'Estado'], 
                          color='CCAA', title="Mapa Solar de Incidencias")
    fig_sun.update_layout(height=700)
    st.plotly_chart(fig_sun, use_container_width=True)
    
    st.subheader("Análisis de Volumen (Treemap)")
    fig_tree = px.treemap(df_f, path=['CCAA', 'Categoria', 'Urgencia'], color='Categoria')
    st.plotly_chart(fig_tree, use_container_width=True)

# --- TAB 3: CONTRACTORS & SPECIALTY ---
with tab3:
    col_con1, col_con2 = st.columns(2)
    
    with col_con1:
        st.subheader("Rendimiento de Contratistas (Top 15)")
        top_contr = df_f['Contratista'].value_counts().head(15)
        fig_con = px.bar(x=top_contr.index, y=top_contr.values, color=top_contr.values, 
                         labels={'x':'Contratista', 'y':'Órdenes'}, title="Carga de Trabajo por Empresa")
        st.plotly_chart(fig_con, use_container_width=True)
        
    with col_con2:
        st.subheader("Especialidades Requeridas")
        if 'Especialidad' in df_f.columns:
            top_spec = df_f['Especialidad'].value_counts().head(15)
            fig_spec = px.pie(values=top_spec.values, names=top_spec.index, title="Mix de Especialidades")
            st.plotly_chart(fig_spec, use_container_width=True)
        else:
            st.warning("Columna Especialidad no detectada.")

# --- TAB 4: RAW DATA & EXPORT ---
with tab4:
    st.subheader("Explorador de Datos Detallado")
    
    # Column Selector
    all_cols = list(df_f.columns)
    show_cols = st.multiselect("Seleccionar columnas a visualizar:", all_cols, default=['Fecha', 'CCAA', 'Centro', 'Descripcion', 'Estado', 'Urgencia', 'Categoria'])
    
    # Show Dataframe with configured columns for better UX
    st.dataframe(
        df_f[show_cols].sort_values('Fecha', ascending=False),
        use_container_width=True,
        height=600,
        column_config={
            "Fecha": st.column_config.DateColumn("Fecha Plan", format="DD/MM/YYYY"),
            "Coste": st.column_config.NumberColumn("Coste", format="€ %.2f"),
            "Descripcion": st.column_config.TextColumn("Detalle", width="large"),
            "Urgencia": st.column_config.TextColumn("Prioridad", width="small"),
            "Estado": st.column_config.Column("Status", width="medium"),
        }
    )
    
    # Download Button
    csv = df_f.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Descargar Datos Filtrados (CSV)",
        data=csv,
        file_name='reporte_mantenimiento_filtrado.csv',
        mime='text/csv',
    )
