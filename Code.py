import streamlit as st
import pandas as pd
import plotly.express as px
import time

# --- Page Configuration ---
st.set_page_config(
    page_title="Dashboard Ejecutivo",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- HELPER: Simple Progress Bar ---
def load_with_progress(file_path):
    # Create placeholders
    progress_text = "Iniciando sistema..."
    my_bar = st.progress(0, text=progress_text)
    
    try:
        # Step 1: Read File (20%)
        my_bar.progress(20, text="📂 Leyendo archivo CSV...")
        # We use latin-1 or utf-8 depending on how Excel saved it. 
        # 'on_bad_lines' skips broken rows to prevent crashes.
        df = pd.read_csv(file_path, encoding='utf-8', on_bad_lines='skip') 
        
        # Step 2: Clean Headers (40%)
        my_bar.progress(40, text="🧹 Limpiando cabeceras...")
        df.columns = df.columns.str.strip() # Remove hidden spaces
        
        # --- CRITICAL UPDATE: REAL SPANISH MAPPING ---
        col_map = {
            'Inicio Real': 'Fecha_Inicio',
            'Fecha Planificada': 'Fecha_Plan',
            'Desc. Estado': 'Estado',       # We use the Description (e.g. Pending), not the code
            'Tipo Trabajo': 'Tipo_Trabajo_Raw',
            'Urgencia': 'Urgencia',
            'Nombre Centro': 'Centro',
            'Descripción': 'Descripcion',
            'Contratista': 'Contratista',
            'CCAA': 'CCAA',
            'Costes (€)': 'Coste',
            'Especialidad': 'Especialidad'
        }
        
        # Rename columns safely
        df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)

        # Step 3: Date Conversion (60%)
        my_bar.progress(60, text="📅 Normalizando fechas...")
        if 'Fecha_Plan' in df.columns:
            # Force conversion to datetime, errors become NaT (Not a Time)
            df['Fecha_Plan'] = pd.to_datetime(df['Fecha_Plan'], dayfirst=True, errors='coerce')
            df = df.dropna(subset=['Fecha_Plan']) # Remove rows with no date
        else:
            st.error(f"Error: No se encontró la columna 'Fecha Planificada'. Cabeceras leídas: {list(df.columns)}")
            st.stop()

        # Step 4: Categorization Logic (80%)
        my_bar.progress(80, text="⚙️ Clasificando tipos de trabajo...")
        
        def get_category(val):
            val = str(val).upper()
            if 'COR' in val: return 'Correctivo'
            if 'PRV' in val: return 'Preventivo'
            if 'MOD' in val: return 'Modificativo'
            return 'Otros'

        if 'Tipo_Trabajo_Raw' in df.columns:
            df['Categoria'] = df['Tipo_Trabajo_Raw'].apply(get_category)
        else:
            df['Categoria'] = 'Desconocido'

        # Step 5: Finish (100%)
        my_bar.progress(100, text="✅ Carga completa")
        time.sleep(0.5) 
        my_bar.empty() # Removes the bar
        
        return df

    except Exception as e:
        my_bar.empty()
        st.error(f"Error detallado leyendo el archivo: {e}")
        return pd.DataFrame()

# --- MAIN EXECUTION ---

# 1. Load Data
df = load_with_progress('PDS - Hoja1.csv') # Ensure this matches your file name

if df.empty:
    st.stop()

# 2. TOP LEVEL SEGMENTATION (The "Switch")
st.title("📊 Análisis de Mantenimiento")

# Toggle for high-level filtering
view_mode = st.radio(
    "Modo de Vista:",
    ["🌍 VISIÓN GLOBAL", "🔧 SOLO CORRECTIVOS", "🛡️ SOLO PREVENTIVOS"],
    horizontal=True,
    label_visibility="collapsed"
)

# Apply Top Filter
if view_mode == "🔧 SOLO CORRECTIVOS":
    df_view = df[df['Categoria'] == 'Correctivo']
elif view_mode == "🛡️ SOLO PREVENTIVOS":
    df_view = df[df['Categoria'] == 'Preventivo']
else:
    df_view = df.copy()

st.markdown("---")

# 3. SIDEBAR FILTERS (Detailed)
st.sidebar.header("Filtros")

# Date Range
min_d = df_view['Fecha_Plan'].min().date()
max_d = df_view['Fecha_Plan'].max().date()
date_range = st.sidebar.date_input("Rango de Fechas", [min_d, max_d])

# CCAA Filter
all_ccaa = sorted(df_view['CCAA'].dropna().unique())
sel_ccaa = st.sidebar.multiselect("Comunidad Autónoma", all_ccaa, default=all_ccaa)

# Status Filter
all_status = sorted(df_view['Estado'].astype(str).unique())
sel_status = st.sidebar.multiselect("Estado", all_status, default=all_status)

# Urgency Filter
all_urgency = sorted(df_view['Urgencia'].astype(str).unique()) if 'Urgencia' in df_view.columns else []
sel_urgency = st.sidebar.multiselect("Urgencia", all_urgency, default=all_urgency)

# Apply Filters
mask = (
    (df_view['Fecha_Plan'].dt.date >= date_range[0]) &
    (df_view['Fecha_Plan'].dt.date <= date_range[1]) &
    (df_view['CCAA'].isin(sel_ccaa)) &
    (df_view['Estado'].isin(sel_status))
)
if sel_urgency:
    mask = mask & (df_view['Urgencia'].isin(sel_urgency))

df_final = df_view[mask]

# --- 4. DASHBOARD KPIS & CHARTS ---

# KPI Row
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Órdenes", f"{len(df_final):,}")
k2.metric("Comunidades", df_final['CCAA'].nunique())
k3.metric("Centros", df_final['Centro'].nunique())

# Calculate Cost if available, else count Contractors
if 'Coste' in df_final.columns and pd.to_numeric(df_final['Coste'], errors='coerce').notnull().any():
    total_cost = pd.to_numeric(df_final['Coste'], errors='coerce').sum()
    k4.metric("Coste Total Est.", f"€{total_cost:,.0f}")
else:
    k4.metric("Contratistas", df_final['Contratista'].nunique())

# CHART ROW 1: Community & Urgency
c1, c2 = st.columns([2, 1])

with c1:
    st.subheader(f"🗺️ Carga de Trabajo por Comunidad ({view_mode})")
    by_ccaa = df_final.groupby('CCAA').size().reset_index(name='Total').sort_values('Total', ascending=True)
    fig_ccaa = px.bar(by_ccaa, x='Total', y='CCAA', orientation='h', text='Total', 
                      color='Total', color_continuous_scale='Blues')
    st.plotly_chart(fig_ccaa, use_container_width=True)

with c2:
    st.subheader("⚠️ Urgencia")
    if 'Urgencia' in df_final.columns:
        fig_urg = px.pie(df_final, names='Urgencia', hole=0.5, color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig_urg, use_container_width=True)

# CHART ROW 2: Time Evolution & Specialties
c3, c4 = st.columns(2)

with c3:
    st.subheader("📅 Evolución Mensual")
    df_time = df_final.copy()
    df_time['Mes'] = df_time['Fecha_Plan'].dt.to_period('M').astype(str)
    
    # Analyze by Type (if Global) or by Top CCAA (if Filtered)
    if view_mode == "🌍 VISIÓN GLOBAL":
        by_time = df_time.groupby(['Mes', 'Categoria']).size().reset_index(name='Ordenes')
        fig_line = px.area(by_time, x='Mes', y='Ordenes', color='Categoria')
    else:
        # Show top 5 CCAA evolution to prevent clutter
        top_ccaa = df_final['CCAA'].value_counts().head(5).index
        by_time = df_time[df_time['CCAA'].isin(top_ccaa)].groupby(['Mes', 'CCAA']).size().reset_index(name='Ordenes')
        fig_line = px.line(by_time, x='Mes', y='Ordenes', color='CCAA', markers=True)
        
    st.plotly_chart(fig_line, use_container_width=True)

with c4:
    st.subheader("🛠️ Top Especialidades")
    if 'Especialidad' in df_final.columns:
        top_spec = df_final['Especialidad'].value_counts().head(10).reset_index()
        top_spec.columns = ['Especialidad', 'Total']
        fig_spec = px.bar(top_spec, x='Especialidad', y='Total', color='Total')
        st.plotly_chart(fig_spec, use_container_width=True)

# --- 5. CONCISE SUMMARY TABLE ---
st.markdown("---")
st.subheader("📑 Resumen de Datos Filtrados")

# Clean Columns for Display
cols_wanted = ['Fecha_Plan', 'CCAA', 'Centro', 'Descripcion', 'Estado', 'Urgencia', 'Contratista', 'Categoria']
final_cols = [c for c in cols_wanted if c in df_final.columns]

st.dataframe(
    df_final[final_cols].sort_values('Fecha_Plan', ascending=False),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Fecha_Plan": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
        "Descripcion": st.column_config.TextColumn("Descripción", width="large"),
        "Categoria": st.column_config.TextColumn("Tipo", width="small"),
        "CCAA": st.column_config.TextColumn("CCAA", width="medium"),
    }
)
