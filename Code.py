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
        # Use on_bad_lines='skip' to avoid crashing on malformed rows
        df = pd.read_csv(file_path, on_bad_lines='skip') 
        
        # Step 2: Clean Headers (40%)
        my_bar.progress(40, text="🧹 Limpiando cabeceras...")
        df.columns = df.columns.str.strip() # Remove hidden spaces
        
        # Mapping based on your provided RAW snippet
        col_map = {
            'Actual Start': 'Fecha_Inicio',
            'Planned Date': 'Fecha_Plan',
            'Status Description': 'Estado',
            'Job Type': 'Tipo_Trabajo_Raw',
            'Urgency': 'Urgencia',
            'Center Name': 'Centro',
            'Description': 'Descripcion',
            'Contractor': 'Contratista',
            'Autonomous Community': 'CCAA',
            'Costs (€)': 'Coste'
        }
        
        # Rename only columns that exist
        df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)

        # Step 3: Date Conversion (60%)
        my_bar.progress(60, text="📅 Normalizando fechas...")
        if 'Fecha_Plan' in df.columns:
            df['Fecha_Plan'] = pd.to_datetime(df['Fecha_Plan'], format='%d/%m/%Y', errors='coerce')
            # Remove rows where date is invalid
            df = df.dropna(subset=['Fecha_Plan'])
        else:
            st.error(f"Error Crítico: No se encontró la columna 'Planned Date'. Columnas detectadas: {list(df.columns)}")
            st.stop()

        # Step 4: Categorization Logic (80%)
        my_bar.progress(80, text="⚙️ Clasificando tipos de trabajo...")
        
        def get_category(val):
            val = str(val).upper()
            if 'COR' in val: return 'Correctivo'
            if 'PRV' in val: return 'Preventivo'
            return 'Otros'

        if 'Tipo_Trabajo_Raw' in df.columns:
            df['Categoria'] = df['Tipo_Trabajo_Raw'].apply(get_category)
        else:
            df['Categoria'] = 'Desconocido'

        # Step 5: Finish (100%)
        my_bar.progress(100, text="✅ Carga completa")
        time.sleep(0.5) # Short pause to see 100%
        my_bar.empty() # REMOVES the bar from screen
        
        return df

    except Exception as e:
        my_bar.empty()
        st.error(f"Error detallado: {e}")
        return pd.DataFrame()

# --- MAIN EXECUTION ---

# 1. Load Data
df = load_with_progress('PDS - Hoja1.csv') # CHECK FILE NAME

if df.empty:
    st.stop()

# 2. TOP LEVEL SEGMENTATION (The "Switch")
st.title("📊 Análisis de Mantenimiento e Incidencias")

# This creates a big toggle at the top
view_mode = st.radio(
    "Seleccione Vista Principal:",
    ["🌍 VISIÓN GLOBAL", "🔧 SOLO CORRECTIVOS", "🛡️ SOLO PREVENTIVOS"],
    horizontal=True,
    label_visibility="collapsed" # Hides the label to make it cleaner
)

# Apply Top Filter immediately
if view_mode == "🔧 SOLO CORRECTIVOS":
    df_view = df[df['Categoria'] == 'Correctivo']
elif view_mode == "🛡️ SOLO PREVENTIVOS":
    df_view = df[df['Categoria'] == 'Preventivo']
else:
    df_view = df.copy()

st.markdown("---")

# 3. SIDEBAR FILTERS (Granular)
st.sidebar.header("Filtros Detallados")

# Date Filter
min_d, max_d = df_view['Fecha_Plan'].min(), df_view['Fecha_Plan'].max()
date_range = st.sidebar.date_input("Rango de Fechas", [min_d, max_d])

# CCAA Filter (Higher Level)
all_ccaa = sorted(df_view['CCAA'].dropna().unique())
sel_ccaa = st.sidebar.multiselect("Comunidad Autónoma", all_ccaa, default=all_ccaa)

# Status Filter
all_status = sorted(df_view['Estado'].dropna().unique())
sel_status = st.sidebar.multiselect("Estado", all_status, default=all_status)

# Apply Sidebar Filters
mask = (
    (df_view['Fecha_Plan'] >= pd.to_datetime(date_range[0])) &
    (df_view['Fecha_Plan'] <= pd.to_datetime(date_range[1])) &
    (df_view['CCAA'].isin(sel_ccaa)) &
    (df_view['Estado'].isin(sel_status))
)
df_final = df_view[mask]

# --- 4. DASHBOARD CONTENT ---

# KPI Row
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Órdenes", f"{len(df_final):,}")
k2.metric("Comunidades Activas", df_final['CCAA'].nunique())
k3.metric("Centros Afectados", df_final['Centro'].nunique())
most_freq_contractor = df_final['Contratista'].mode()[0] if not df_final.empty else "N/A"
k4.metric("Contratista Principal", most_freq_contractor)

# CHART ROW 1: Community Overview (High Level)
c1, c2 = st.columns([2, 1])

with c1:
    st.subheader(f"🗺️ Volumen por Comunidad Autónoma ({view_mode})")
    # Group by CCAA
    by_ccaa = df_final.groupby('CCAA').size().reset_index(name='Total').sort_values('Total', ascending=True)
    fig_ccaa = px.bar(by_ccaa, x='Total', y='CCAA', orientation='h', text='Total', color='Total')
    fig_ccaa.update_layout(height=400)
    st.plotly_chart(fig_ccaa, use_container_width=True)

with c2:
    st.subheader("⚠️ Distribución de Urgencia")
    if 'Urgencia' in df_final.columns:
        fig_urg = px.pie(df_final, names='Urgencia', hole=0.5, color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig_urg, use_container_width=True)

# CHART ROW 2: Time & Relations
c3, c4 = st.columns(2)

with c3:
    st.subheader("📅 Evolución Temporal")
    # Group by Month and CCAA (Top 5 CCAA to avoid clutter)
    df_time = df_final.copy()
    df_time['Mes'] = df_time['Fecha_Plan'].dt.to_period('M').astype(str)
    
    top_5_ccaa = df_final['CCAA'].value_counts().head(5).index
    df_time_filtered = df_time[df_time['CCAA'].isin(top_5_ccaa)]
    
    by_time = df_time_filtered.groupby(['Mes', 'CCAA']).size().reset_index(name='Ordenes')
    fig_line = px.line(by_time, x='Mes', y='Ordenes', color='CCAA', markers=True)
    st.plotly_chart(fig_line, use_container_width=True)

with c4:
    st.subheader("🏗️ Estado vs Comunidad (Heatmap)")
    heatmap_data = df_final.groupby(['CCAA', 'Estado']).size().reset_index(name='Count')
    fig_heat = px.density_heatmap(heatmap_data, x='CCAA', y='Estado', z='Count', text_auto=True, color_continuous_scale='Blues')
    st.plotly_chart(fig_heat, use_container_width=True)

# --- 5. SUMMARY TABLE (Concise) ---
st.markdown("### 📑 Resumen Ejecutivo")

# Selecting only helpful columns for the user
cols_wanted = ['Fecha_Plan', 'CCAA', 'Centro', 'Descripcion', 'Estado', 'Contratista', 'Urgencia']
final_cols = [c for c in cols_wanted if c in df_final.columns]

st.dataframe(
    df_final[final_cols].sort_values('Fecha_Plan', ascending=False),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Fecha_Plan": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
        "CCAA": st.column_config.TextColumn("Región", width="small"),
        "Descripcion": st.column_config.TextColumn("Detalle Trabajo", width="large"),
        "Estado": st.column_config.Column("Estado Actual", width="medium")
    }
)
