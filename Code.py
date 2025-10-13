# Import necessary libraries
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- Page Configuration ---
st.set_page_config(
    page_title="Dashboard de Mantenimiento - Asepeyo",
    page_icon="📊",
    layout="wide",
)

# --- OPTIMIZED Data Loading and Caching ---
@st.cache_data
def load_data(file_path):
    """
    Loads and processes data from a large CSV file using memory-efficient techniques.
    """
    try:
        st.info("Iniciando la carga optimizada del archivo CSV...")

        # --- Optimization 1: Specify only the columns we need ---
        # This prevents loading the entire large file into memory.
        columns_to_load = [
            'Fecha Planificada', 'Fecha cierre', 'CCAA', 'Nombre Centro',
            'Desc. Equipo', 'Tipo Trabajo', 'Desc. Estado', 'Contratista'
        ]

        # --- Optimization 2: Specify efficient data types ---
        # Using 'category' for repetitive text columns saves a lot of memory.
        data_types = {
            'CCAA': 'category',
            'Nombre Centro': 'category',
            'Desc. Equipo': 'category',
            'Tipo Trabajo': 'category',
            'Desc. Estado': 'category',
            'Contratista': 'category'
        }

        # Load the data with the optimizations
        df = pd.read_csv(file_path, usecols=columns_to_load, dtype=data_types)
        
        st.info(f"✅ Archivo CSV cargado con éxito. {len(df):,} filas procesadas.")
        
        # --- Data Cleaning and Preparation ---
        st.info("Limpiando y preparando los datos...")
        df.columns = df.columns.str.strip()
        df.rename(columns={
            'Nombre Centro': 'Centro',
            'Desc. Estado': 'Estado',
            'Desc. Equipo': 'Instalacion',
            'Tipo Trabajo': 'Tipo_Trabajo',
            'Fecha Planificada': 'Fecha_Planificada',
            'Fecha cierre': 'Fecha_Cierre'
        }, inplace=True)

        # Efficient Date Conversion
        st.info("Convirtiendo columnas de fecha...")
        df['Fecha_Planificada'] = pd.to_datetime(df['Fecha_Planificada'], format='%d/%m/%Y', errors='coerce')
        df['Fecha_Cierre'] = pd.to_datetime(df['Fecha_Cierre'], format='%d/%m/%Y', errors='coerce')
        st.info("✅ Fechas convertidas.")
        
        df.dropna(subset=['Fecha_Planificada'], inplace=True)

        df['Año'] = df['Fecha_Planificada'].dt.year
        df['Mes'] = df['Fecha_Planificada'].dt.month
        
        st.info("Agrupando tipos de trabajo...")
        def clean_tipo_trabajo(tipo):
            if not isinstance(tipo, str):
                tipo = str(tipo)
            
            tipo_upper = tipo.upper()
            if 'COR' in tipo_upper: return 'Correctivo'
            if 'PRV' in tipo_upper: return 'Preventivo'
            if 'SIN' in tipo_upper: return 'Siniestro'
            if 'INS' in tipo_upper: return 'Inspeccion'
            return 'Otro'

        df['Tipo_Trabajo_Agrupado'] = df['Tipo_Trabajo'].apply(clean_tipo_trabajo)
        st.success("🎉 ¡Datos listos para el análisis!")
        
        return df

    except FileNotFoundError:
        st.error(f"Error: El archivo '{file_path}' no se encontró.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Ocurrió un error al procesar el archivo: {e}")
        return pd.DataFrame()

# Load the data using the optimized function
df = load_data('PDS - Hoja1.csv')

if not df.empty:
    # --- Sidebar for Filters ---
    st.sidebar.header('Filtros del Dashboard')

    # Date Range Filter
    min_date = df['Fecha_Planificada'].min().date()
    max_date = df['Fecha_Planificada'].max().date()
    start_date = st.sidebar.date_input('Fecha de inicio', min_date, min_value=min_date, max_value=max_date)
    end_date = st.sidebar.date_input('Fecha de fin', max_date, min_value=min_date, max_value=max_date)

    start_datetime = pd.to_datetime(start_date)
    end_datetime = pd.to_datetime(end_date)

    df_filtered = df[(df['Fecha_Planificada'] >= start_datetime) & (df['Fecha_Planificada'] <= end_datetime)].copy()

    # --- Geographic Filters (dynamic) ---
    st.sidebar.subheader('Filtros Geográficos')
    default_communities = sorted(df_filtered['CCAA'].dropna().unique().tolist())
    selected_communities = st.sidebar.multiselect('Comunidad Autónoma', default_communities, default=default_communities)

    if selected_communities:
        df_filtered = df_filtered[df_filtered['CCAA'].isin(selected_communities)]

    if not df_filtered.empty:
        default_centros = sorted(df_filtered['Centro'].dropna().unique().tolist())
        selected_centros = st.sidebar.multiselect('Centro', default_centros, default=default_centros)
        if selected_centros:
            df_filtered = df_filtered[df_filtered['Centro'].isin(selected_centros)]

    if not df_filtered.empty:
        default_instalaciones = sorted(df_filtered['Instalacion'].dropna().unique().tolist())
        selected_instalaciones = st.sidebar.multiselect('Instalación', default_instalaciones, default=default_instalaciones)
        if selected_instalaciones:
            df_filtered = df_filtered[df_filtered['Instalacion'].isin(selected_instalaciones)]

    # --- Main Dashboard Area ---
    st.title("Dashboard de Órdenes de Trabajo")

    # Create tabs
    tab1, tab2 = st.tabs(["Análisis ASEPEYO", "Análisis CONTRATISTAS"])

    # --- ASEPEYO TAB ---
    with tab1:
        st.header("Análisis de Órdenes de Trabajo de ASEPEYO")

        if df_filtered.empty:
            st.warning("No hay datos disponibles para los filtros seleccionados.")
        else:
            # --- KPIs ---
            st.subheader("Indicadores Clave de Rendimiento (KPIs)")
            kpi_cols = st.columns(4)
            tipos_trabajo = ['Preventivo', 'Correctivo', 'Siniestro', 'Inspeccion']
            for i, tipo in enumerate(tipos_trabajo):
                count = df_filtered[df_filtered['Tipo_Trabajo_Agrupado'] == tipo].shape[0]
                kpi_cols[i].metric(label=f"Total {tipo}s", value=f"{count:,}")
            
            st.markdown("---")

            # --- Visualizations ---
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Trabajos por Comunidad Autónoma")
                df_grouped = df_filtered.groupby(['CCAA', 'Tipo_Trabajo_Agrupado']).size().reset_index(name='Conteo')
                fig = px.bar(df_grouped, x='CCAA', y='Conteo', color='Tipo_Trabajo_Agrupado',
                             title="Distribución de Trabajos por CCAA", barmode='stack')
                fig.update_layout(xaxis={'categoryorder':'total descending'})
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.subheader("Trabajos por Centro")
                df_grouped_centro = df_filtered.groupby(['Centro', 'Tipo_Trabajo_Agrupado']).size().reset_index(name='Conteo')
                fig_centro = px.bar(df_grouped_centro, x='Centro', y='Conteo', color='Tipo_Trabajo_Agrupado',
                                    title="Distribución de Trabajos por Centro", barmode='stack')
                fig_centro.update_layout(xaxis={'categoryorder':'total descending'})
                st.plotly_chart(fig_centro, use_container_width=True)

            # --- Work Order Status Analysis ---
            st.subheader("Análisis por Estado de Orden de Trabajo")
            col_status1, col_status2 = st.columns(2)

            with col_status1:
                st.markdown("**Estado de Preventivos y Correctivos**")
                df_prv_cor = df_filtered[df_filtered['Tipo_Trabajo_Agrupado'].isin(['Preventivo', 'Correctivo'])]
                status_counts = df_prv_cor['Estado'].value_counts()
                fig_pie = px.pie(status_counts, names=status_counts.index, values=status_counts.values, 
                                 title="Porcentaje por Estado (PRV y COR)", hole=0.3)
                st.plotly_chart(fig_pie, use_container_width=True)

            with col_status2:
                st.markdown("**Emisión Mensual de Correctivos**")
                df_correctivos = df_filtered[df_filtered['Tipo_Trabajo_Agrupado'] == 'Correctivo'].copy()
                df_correctivos['Mes_Año'] = df_correctivos['Fecha_Planificada'].dt.to_period('M').astype(str)
                monthly_correctives = df_correctivos.groupby('Mes_Año').size().reset_index(name='Conteo')
                monthly_correctives.sort_values('Mes_Año', inplace=True)
                
                fig_line = px.line(monthly_correctives, x='Mes_Año', y='Conteo',
                                   title="Evolución Mensual de Correctivos Emitidos", markers=True)
                fig_line.update_layout(xaxis_title="Mes", yaxis_title="Número de Correctivos")
                st.plotly_chart(fig_line, use_container_width=True)

    # --- CONTRATISTAS TAB ---
    with tab2:
        st.header("Análisis de Rendimiento de Contratistas")

        if df_filtered.empty:
            st.warning("No hay datos disponibles para los filtros seleccionados.")
        else:
            # --- Contractor Workload Analysis ---
            st.subheader("Distribución de Trabajo por Contratista")
            contratista_counts = df_filtered['Contratista'].value_counts().nlargest(20) # Top 20
            fig_contratista = px.bar(contratista_counts, x=contratista_counts.index, y=contratista_counts.values,
                                     title="Top 20 Contratistas por Nº de Órdenes de Trabajo")
            fig_contratista.update_layout(xaxis_title="Contratista", yaxis_title="Número de Órdenes",
                                          xaxis={'categoryorder':'total descending'})
            st.plotly_chart(fig_contratista, use_container_width=True)

            # --- Work Order Status by Contractor ---
            st.subheader("Estado de las Órdenes de Trabajo por Contratista")
            df_contratista_status = df_filtered.groupby(['Contratista', 'Estado']).size().reset_index(name='Conteo')
            fig_status_contratista = px.bar(df_contratista_status, x='Contratista', y='Conteo', color='Estado',
                                            title="Desglose de Estados por Contratista", barmode='stack')
            fig_status_contratista.update_layout(xaxis={'categoryorder':'total descending'})
            st.plotly_chart(fig_status_contratista, use_container_width=True)

            # --- Compliance Ratio ---
            st.subheader("Ratio de Cumplimiento (Órdenes Cerradas en el Mismo Mes)")
            df_ratio = df_filtered.dropna(subset=['Fecha_Planificada', 'Fecha_Cierre']).copy()
            
            df_ratio['Mismo_Mes'] = df_ratio['Fecha_Planificada'].dt.month == df_ratio['Fecha_Cierre'].dt.month
            df_ratio['Mes_Creacion'] = df_ratio['Fecha_Planificada'].dt.to_period('M').astype(str)
            
            monthly_compliance = df_ratio.groupby('Mes_Creacion')['Mismo_Mes'].agg(['count', 'sum']).reset_index()
            monthly_compliance.rename(columns={'count': 'Total_Abiertas', 'sum': 'Cerradas_Mismo_Mes'}, inplace=True)
            
            if not monthly_compliance.empty and monthly_compliance['Total_Abiertas'].sum() > 0:
                monthly_compliance['Ratio_Cumplimiento'] = (monthly_compliance['Cerradas_Mismo_Mes'] / monthly_compliance['Total_Abiertas']) * 100
            
                st.write("Este ratio muestra el porcentaje de órdenes de trabajo que se cerraron en el mismo mes en que se planificaron.")
                
                fig_ratio = go.Figure()
                fig_ratio.add_trace(go.Bar(x=monthly_compliance['Mes_Creacion'], y=monthly_compliance['Total_Abiertas'], name='Total Abiertas', marker_color='lightblue'))
                fig_ratio.add_trace(go.Bar(x=monthly_compliance['Mes_Creacion'], y=monthly_compliance['Cerradas_Mismo_Mes'], name='Cerradas Mismo Mes', marker_color='blue'))
                fig_ratio.update_layout(title='Órdenes Abiertas vs. Cerradas en el Mismo Mes', barmode='overlay')
                st.plotly_chart(fig_ratio, use_container_width=True)

                st.dataframe(monthly_compliance.style.format({'Ratio_Cumplimiento': "{:.2f}%"}))
            else:
                st.info("No hay suficientes datos de cierre para calcular el ratio de cumplimiento.")

else:
    st.warning("Esperando a que los datos se carguen...")
