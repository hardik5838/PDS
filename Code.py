import streamlit as st
import pandas as pd
import plotly.express as px
import time

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="Dashboard Profesional",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. ROBUST DATA LOADER ---
@st.cache_data
def load_data_robust(file_path):
    with st.status("🔄 Procesando datos...", expanded=True) as status:
        st.write("📂 Leyendo archivo...")
        try:
            # Flexible reading
            df = pd.read_csv(file_path, encoding='latin-1', on_bad_lines='skip')
        except:
            df = pd.read_csv(file_path, encoding='utf-8', on_bad_lines='skip')

        st.write("🧹 Limpiando nombres de columna...")
        # 1. Strip spaces and Upper case all headers for matching
        df.columns = df.columns.str.strip().str.upper()

        # 2. Define Mapping (UPPERCASE KEYS)
        # This maps your Spanish headers to internal standard names
        col_map = {
            'FECHA PLANIFICADA': 'Fecha',
            'PLANNED DATE': 'Fecha',
            'DESC. ESTADO': 'Estado',
            'STATUS DESCRIPTION': 'Estado',
            'URGENCIA': 'Urgencia',
            'NOMBRE CENTRO': 'Centro',
            'CENTER NAME': 'Centro',
            'DESCRIPCIÓN': 'Descripcion',
            'CONTRATISTA': 'Contratista',
            'CCAA': 'CCAA',
            'AUTONOMOUS COMMUNITY': 'CCAA',
            'TIPO TRABAJO': 'Tipo_Raw',
            'ESPECIALIDAD': 'Especialidad',
            'COSTES (€)': 'Coste'
        }
        
        # 3. Rename
        df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)

        # 4. Check critical columns exist
        if 'Fecha' not in df.columns:
            st.error("❌ No se encontró la columna de FECHA. Verifique el CSV.")
            st.stop()

        # 5. Process Data
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Fecha'])

        # Categorization Logic
        def get_category(val):
            val = str(val).upper()
            if 'COR' in val: return 'Correctivo'
            if 'PRV' in val: return 'Preventivo'
            return 'Otros'
            
        col_type = 'Tipo_Raw' if 'Tipo_Raw' in df.columns else 'Tipo_de_Trabajo'
        if col_type in df.columns:
            df['Categoria'] = df[col_type].apply(get_category)
        else:
            df['Categoria'] = 'General'

        status.update(label="✅ Datos cargados correctamente", state="complete", expanded=False)
        return df

# LOAD
df = load_data_robust('PDS - Hoja1.csv')

# --- 3. SIDEBAR CONTROLS ---
st.sidebar.title("🎛️ Filtros")

# Date
min_d, max_d = df['Fecha'].min().date(), df['Fecha'].max().date()
date_range = st.sidebar.date_input("Periodo", [min_d, max_d])

# Filters
ccaa_opts = sorted(df['CCAA'].dropna().unique()) if 'CCAA' in df.columns else []
sel_ccaa = st.sidebar.multiselect("Comunidad", ccaa_opts, default=ccaa_opts)

status_opts = sorted(df['Estado'].dropna().unique())
sel_status = st.sidebar.multiselect("Estado", status_opts, default=status_opts)

# Apply Filter
mask = (
    (df['Fecha'].dt.date >= date_range[0]) &
    (df['Fecha'].dt.date <= date_range[1]) &
    (df['Estado'].isin(sel_status))
)
if 'CCAA' in df.columns:
    mask = mask & (df['CCAA'].isin(sel_ccaa))

df_f = df[mask]

# --- 4. MAIN DASHBOARD ---
st.title("📊 Análisis de Mantenimiento")

# --- NEW FEATURE: AGGREGATION TOGGLE ---
st.write("### 👁️ Configuración de Vista")
col_view1, col_view2 = st.columns([1, 3])
with col_view1:
    # THE TOGGLE YOU REQUESTED
    agg_level = st.radio(
        "Agrupar gráficos por:",
        ["Comunidad (Región)", "Centro (Individual)"],
        horizontal=True
    )

# Determine the column to use for grouping based on toggle
if agg_level == "Comunidad (Región)":
    group_col = 'CCAA'
    x_label = "Comunidad Autónoma"
else:
    group_col = 'Centro'
    x_label = "Nombre del Centro"

st.markdown("---")

# METRICS
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Órdenes", len(df_f))
m2.metric("Correctivos", len(df_f[df_f['Categoria']=='Correctivo']))
m3.metric("Preventivos", len(df_f[df_f['Categoria']=='Preventivo']))
m4.metric("Coste Total Est.", f"€{df_f['Coste'].sum():,.0f}" if 'Coste' in df_f.columns else "N/A")

# TABS
tab1, tab2, tab3 = st.tabs(["📈 Análisis Principal", "⚡ Detalle Urgencia", "📝 Datos Crudos"])

# TAB 1: DYNAMIC ANALYSIS (Region vs Center)
with tab1:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader(f"Volumen de Trabajo por {x_label}")
        # Dynamic grouping based on toggle
        if group_col in df_f.columns:
            # We limit to top 20 if showing Centers to prevent overcrowding
            limit = 20 if group_col == 'Centro' else 50
            
            df_vol = df_f[group_col].value_counts().head(limit).reset_index()
            df_vol.columns = [group_col, 'Total']
            
            fig_bar = px.bar(df_vol, x='Total', y=group_col, orientation='h', 
                             text='Total', color='Total', title=f"Top {limit} {x_label}")
            fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.warning(f"Columna {group_col} no disponible.")

    with col2:
        st.subheader("Estado de las Órdenes")
        fig_pie = px.pie(df_f, names='Estado', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)

    # Time Series
    st.subheader("Evolución Temporal")
    df_time = df_f.copy()
    df_time['Mes'] = df_time['Fecha'].dt.to_period('M').astype(str)
    # Stack by the selected group column (Region or Center)
    # If grouped by Center, we only show top 5 to avoid mess
    if group_col == 'Centro':
        top_5 = df_f['Centro'].value_counts().head(5).index
        df_time = df_time[df_time['Centro'].isin(top_5)]
    
    df_trend = df_time.groupby(['Mes', group_col]).size().reset_index(name='Ordenes')
    fig_trend = px.area(df_trend, x='Mes', y='Ordenes', color=group_col)
    st.plotly_chart(fig_trend, use_container_width=True)

# TAB 2: URGENCY & HIERARCHY
with tab2:
    st.subheader("Mapa Jerárquico: CCAA -> Centro -> Estado")
    # This chart is great because it handles both levels at once
    cols_sun = [c for c in ['CCAA', 'Centro', 'Estado'] if c in df_f.columns]
    if len(cols_sun) >= 2:
        fig_sun = px.sunburst(df_f, path=cols_sun, title="Click para profundizar")
        fig_sun.update_layout(height=600)
        st.plotly_chart(fig_sun, use_container_width=True)

# TAB 3: DATA (FIXED CRASH)
with tab3:
    st.subheader("Explorador de Datos")
    
    # 1. Get all available columns
    all_cols = list(df_f.columns)
    
    # 2. Define intended defaults
    intended_defaults = ['Fecha', 'CCAA', 'Centro', 'Descripcion', 'Estado', 'Urgencia', 'Categoria']
    
    # 3. SAFETY FILTER: Only use defaults that actually exist in the dataframe
    valid_defaults = [c for c in intended_defaults if c in df_f.columns]
    
    # 4. Create widget using safe list
    show_cols = st.multiselect(
        "Seleccionar columnas a visualizar:", 
        options=all_cols, 
        default=valid_defaults # <--- FIXED LINE
    )
    
    st.dataframe(
        df_f[show_cols].sort_values('Fecha', ascending=False),
        use_container_width=True
    )
    
    # Download
    csv = df_f.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Descargar CSV", csv, "mantenimiento_filtrado.csv", "text/csv")
