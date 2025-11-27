import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- Page Config ---
st.set_page_config(
    page_title="Dashboard de Mantenimiento Avanzado",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed" # Starts with more screen real estate
)

# --- 1. Compact & Optimized Data Loading ---
@st.cache_data
def load_data(file_path):
    # We use a context manager for the loading status to keep it compact
    try:
        # Load Raw Data
        df = pd.read_csv(file_path, sep=',', encoding='utf-8', on_bad_lines='skip')
        
        # Clean Column Names
        df.columns = df.columns.str.strip()
        
        # Map specific column names based on your CSV structure
        # Note: Adjust these if your CSV headers change slightly
        col_map = {
            'Actual Start': 'Fecha_Inicio',
            'Planned Date': 'Fecha_Plan',
            'Status Description': 'Estado',
            'Job Type': 'Tipo_Trabajo_Raw', # There are two Job Types, pandas usually suffixes the second
            'Urgency': 'Urgencia',
            'Center Name': 'Centro',
            'Specialty': 'Especialidad',
            'Description': 'Descripcion',
            'Contractor': 'Contratista',
            'Autonomous Community': 'CCAA'
        }
        # Rename available columns safely
        df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)
        
        # Date Conversion
        df['Fecha_Plan'] = pd.to_datetime(df['Fecha_Plan'], format='%d/%m/%Y', errors='coerce')
        
        # Feature Engineering: Extract "Work Type" (COR, PRV) from the code
        # Assuming format like "H001COR" -> COR
        def extract_type(code):
            code = str(code).upper()
            if 'COR' in code: return 'Correctivo'
            if 'PRV' in code: return 'Preventivo'
            if 'MOD' in code: return 'Modificativo'
            return 'Otros'

        if 'Tipo_Trabajo_Raw' in df.columns:
            df['Tipo_Categoria'] = df['Tipo_Trabajo_Raw'].apply(extract_type)
        else:
            df['Tipo_Categoria'] = 'Desconocido'

        return df

    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame()

# --- Load Data with Status Animation ---
with st.status("🔄 Procesando archivo maestro...", expanded=True) as status:
    st.write("📂 Leyendo CSV crudo...")
    df = load_data('PDS - Hoja1.csv') # CHANGE THIS TO YOUR FILE PATH
    st.write("🛠️ Normalizando fechas y categorías...")
    st.write("📊 Calculando métricas iniciales...")
    status.update(label="✅ Datos cargados y listos para análisis", state="complete", expanded=False)

if df.empty:
    st.stop()

# --- 2. Granular Top Filter Bar ---
st.title("🏗️ Control de Mantenimiento e Incidencias")

with st.expander("🔍 FILTROS AVANZADOS (Click para expandir)", expanded=True):
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    
    with col_f1:
        # Date Filter
        min_date = df['Fecha_Plan'].min()
        max_date = df['Fecha_Plan'].max()
        date_range = st.date_input("Rango de Fechas", [min_date, max_date])

    with col_f2:
        # Work Category Filter (The extracted logic)
        selected_cats = st.multiselect("Categoría Trabajo", df['Tipo_Categoria'].unique(), default=df['Tipo_Categoria'].unique())
        
    with col_f3:
        # Status Filter
        selected_status = st.multiselect("Estado", df['Estado'].unique(), default=df['Estado'].unique())

    with col_f4:
        # Urgency Filter
        if 'Urgencia' in df.columns:
            selected_urgency = st.multiselect("Urgencia", df['Urgencia'].unique(), default=df['Urgencia'].unique())
        else:
            selected_urgency = []

    # Secondary Row of Filters
    col_f5, col_f6 = st.columns(2)
    with col_f5:
        selected_ccaa = st.multiselect("Comunidad Autónoma", df['CCAA'].unique())
    with col_f6:
         # Search bar for text
        search_text = st.text_input("Búsqueda por palabra clave en Descripción (ej. 'Puerta', 'Agua')")

# --- Apply Filters ---
mask = (
    (df['Fecha_Plan'] >= pd.to_datetime(date_range[0])) & 
    (df['Fecha_Plan'] <= pd.to_datetime(date_range[1])) &
    (df['Tipo_Categoria'].isin(selected_cats)) &
    (df['Estado'].isin(selected_status))
)

if selected_urgency:
    mask = mask & (df['Urgencia'].isin(selected_urgency))
if selected_ccaa:
    mask = mask & (df['CCAA'].isin(selected_ccaa))
if search_text:
    mask = mask & (df['Descripcion'].str.contains(search_text, case=False, na=False))

df_filtered = df[mask]

# --- KPI Summary Row ---
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Total Órdenes", f"{len(df_filtered):,}")
kpi2.metric("Correctivos", len(df_filtered[df_filtered['Tipo_Categoria']=='Correctivo']))
kpi3.metric("Preventivos", len(df_filtered[df_filtered['Tipo_Categoria']=='Preventivo']))
# Calculate % Urgent
urgent_count = len(df_filtered[df_filtered['Urgencia'] != 'Not Urgent'])
urgent_pct = (urgent_count / len(df_filtered) * 100) if len(df_filtered) > 0 else 0
kpi4.metric("% Urgencia", f"{urgent_pct:.1f}%")

st.markdown("---")

# --- 3. Advanced Charts (5 New Charts) ---

# Row 1: Time Analysis & Urgency Heatmap
c1, c2 = st.columns([2, 1])

with c1:
    st.subheader("📈 Evolución Temporal por Categoría")
    # Group by Month and Category
    df_time = df_filtered.copy()
    df_time['Mes'] = df_time['Fecha_Plan'].dt.to_period('M').astype(str)
    df_agg = df_time.groupby(['Mes', 'Tipo_Categoria']).size().reset_index(name='Count')
    
    fig_area = px.area(df_agg, x="Mes", y="Count", color="Tipo_Categoria", 
                       title="Volumen de trabajo en el tiempo", markers=True)
    st.plotly_chart(fig_area, use_container_width=True)

with c2:
    st.subheader("🔥 Mapa de Calor: Estado vs Urgencia")
    if 'Urgencia' in df_filtered.columns:
        df_heat = df_filtered.groupby(['Estado', 'Urgencia']).size().reset_index(name='Count')
        fig_heat = px.density_heatmap(df_heat, x="Estado", y="Urgencia", z="Count", 
                                      text_auto=True, color_continuous_scale="Viridis",
                                      title="Concentración de Incidencias")
        st.plotly_chart(fig_heat, use_container_width=True)

# Row 2: Specialty & Contractor Analysis
c3, c4, c5 = st.columns(3)

with c3:
    st.subheader("🛠️ Top Especialidades")
    if 'Especialidad' in df_filtered.columns:
        top_spec = df_filtered['Especialidad'].value_counts().head(10).reset_index()
        top_spec.columns = ['Especialidad', 'Total']
        fig_bar = px.bar(top_spec, x='Total', y='Especialidad', orientation='h', 
                         title="Especialidades más demandadas", color='Total')
        st.plotly_chart(fig_bar, use_container_width=True)

with c4:
    st.subheader("👷 Top Contratistas")
    if 'Contratista' in df_filtered.columns:
        top_cont = df_filtered['Contratista'].value_counts().head(10)
        fig_pie = px.pie(values=top_cont.values, names=top_cont.index, hole=0.4,
                         title="Distribución por Contratista")
        st.plotly_chart(fig_pie, use_container_width=True)

with c5:
    st.subheader("📊 Distribución de Estado")
    fig_funnel = px.funnel(df_filtered['Estado'].value_counts().reset_index(), 
                           x='count', y='Estado', title="Funnel de Estados")
    st.plotly_chart(fig_funnel, use_container_width=True)

# --- 4. Concise Summary Table ---
st.markdown("---")
st.subheader("📑 Detalle de Órdenes Filtradas (Vista Concisa)")

# Select only high-value columns for the summary to keep it clean
cols_to_show = ['Fecha_Plan', 'Tipo_Categoria', 'Descripcion', 'Centro', 'Estado', 'Urgencia', 'Contratista']
# Ensure columns exist before selecting
available_cols = [c for c in cols_to_show if c in df_filtered.columns]

st.dataframe(
    df_filtered[available_cols].sort_values(by='Fecha_Plan', ascending=False),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Fecha_Plan": st.column_config.DateColumn("Fecha Plan", format="DD/MM/YYYY"),
        "Descripcion": st.column_config.TextColumn("Descripción", width="large"),
        "Tipo_Categoria": st.column_config.TextColumn("Tipo", width="small"),
        "Estado": st.column_config.Column("Estado", width="medium"),
    }
)
