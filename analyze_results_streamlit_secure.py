import streamlit as st
import mysql.connector
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from fpdf import FPDF
from datetime import datetime

# --- CONFIGURACIÓN DE USUARIOS ---
USERS = {
    "admin": "admin123",
    "profesor": "clave2025"
}

# --- CONFIGURACIÓN DE BASE DE DATOS ---
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "soft_results"
}

st.set_page_config(page_title="Análisis de Resultados (Seguro)", page_icon="🔒", layout="wide")

# --- FUNCIÓN DE AUTENTICACIÓN ---
def autenticar_usuario():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        st.title("🔐 Inicio de sesión requerido")
        user = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        if st.button("Iniciar sesión"):
            if user in USERS and USERS[user] == password:
                st.session_state.logged_in = True
                st.session_state.user = user
                st.success(f"Bienvenido, {user} 👋")
                st.rerun()
            else:
                st.error("Credenciales incorrectas.")
        st.stop()

    st.sidebar.markdown(f"👤 **Usuario:** {st.session_state.user}")
    if st.sidebar.button("🚪 Cerrar sesión"):
        st.session_state.logged_in = False
        st.experimental_rerun()

# --- FUNCIONES AUXILIARES ---
def load_data():
    conn = mysql.connector.connect(**DB_CONFIG)
    query = "SELECT * FROM exam_results ORDER BY timestamp DESC;"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def generar_estadisticas(df):
    return {
        "Total Exámenes": len(df),
        "Promedio (%)": round(df["percent_correct"].mean(), 2),
        "Máximo (%)": round(df["percent_correct"].max(), 2),
        "Mínimo (%)": round(df["percent_correct"].min(), 2),
        "Desviación estándar": round(df["percent_correct"].std(), 2),
    }

def generar_pdf(df, stats, fig_buffer):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "📊 Reporte Estadístico de Evaluaciones", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "", 12)

    for k, v in stats.items():
        pdf.cell(0, 8, f"{k}: {v}", ln=True)
    pdf.ln(10)

    pdf.image(fig_buffer, x=10, w=180)
    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Resultados Individuales", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", "", 10)
    for _, row in df.iterrows():
        pdf.cell(
            0, 8,
            f"{row['timestamp']} | {row['student_id']} | {row['exam_id']} | {row['percent_correct']}%",
            ln=True
        )

    output = BytesIO()
    pdf.output(output)
    output.seek(0)
    return output

# --- EJECUCIÓN PRINCIPAL ---
autenticar_usuario()

st.title("📊 Panel Seguro - Análisis de Resultados de Exámenes")

try:
    df = load_data()
except Exception as e:
    st.error(f"⚠️ Error al leer la base de datos: {e}")
    st.stop()

if df.empty:
    st.warning("⚠️ No hay registros en la base de datos `results.db`.")
    st.stop()

# --- FILTROS ---
st.sidebar.header("🔍 Filtros")
exam_filter = st.sidebar.multiselect(
    "Selecciona Examen(es)",
    sorted(df["exam_id"].unique().tolist()),
    default=df["exam_id"].unique().tolist()
)

date_min = pd.to_datetime(df["timestamp"]).min()
date_max = pd.to_datetime(df["timestamp"]).max()

date_range = st.sidebar.date_input(
    "Rango de fechas",
    value=(date_min.date(), date_max.date()),
    min_value=date_min.date(),
    max_value=date_max.date()
)

# --- APLICAR FILTROS ---
df["timestamp"] = pd.to_datetime(df["timestamp"])
df_filtered = df[
    (df["exam_id"].isin(exam_filter)) &
    (df["timestamp"].dt.date >= date_range[0]) &
    (df["timestamp"].dt.date <= date_range[1])
]

if df_filtered.empty:
    st.warning("No hay resultados que coincidan con los filtros seleccionados.")
    st.stop()

# --- ESTADÍSTICAS ---
st.subheader("📈 Estadísticas Descriptivas")
stats = generar_estadisticas(df_filtered)
col1, col2, col3 = st.columns(3)
col1.metric("Promedio (%)", stats["Promedio (%)"])
col2.metric("Máximo (%)", stats["Máximo (%)"])
col3.metric("Mínimo (%)", stats["Mínimo (%)"])
st.json(stats)

# --- GRÁFICOS ---
st.subheader("📉 Visualizaciones")

plt.style.use("seaborn-v0_8-whitegrid")
fig, axes = plt.subplots(1, 2, figsize=(12, 4))

axes[0].hist(df_filtered["percent_correct"], bins=10, color="skyblue", edgecolor="black")
axes[0].set_title("Distribución de porcentajes de aciertos")
axes[0].set_xlabel("Porcentaje de aciertos")
axes[0].set_ylabel("Número de estudiantes")

df_sorted = df_filtered.sort_values("percent_correct", ascending=False)
axes[1].bar(df_sorted["student_id"], df_sorted["percent_correct"], color="lightgreen")
axes[1].set_title("Ranking de desempeño")
axes[1].set_xlabel("Estudiante")
axes[1].set_ylabel("Porcentaje (%)")
axes[1].tick_params(axis="x", rotation=45)

plt.tight_layout()
st.pyplot(fig)

# --- EXPORTACIONES ---
fig_buffer = BytesIO()
fig.savefig(fig_buffer, format="png")
fig_buffer.seek(0)
pdf_bytes = generar_pdf(df_filtered, stats, fig_buffer)

# --- TABLA Y EXPORTACIÓN ---
st.subheader("📋 Detalle de Resultados")
st.dataframe(df_filtered[["timestamp", "student_id", "exam_id", "percent_correct"]])

st.subheader("📤 Exportar Datos")

csv_bytes = df_filtered.to_csv(index=False).encode("utf-8")

excel_buffer = BytesIO()
with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
    df_filtered.to_excel(writer, index=False, sheet_name="Resultados")
excel_buffer.seek(0)

col1, col2, col3 = st.columns(3)

with col1:
    st.download_button("📄 CSV", csv_bytes, "resultados.csv", "text/csv")
with col2:
    st.download_button("📊 Excel (.xlsx)", excel_buffer, "resultados.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
with col3:
    st.download_button("📘 PDF (Resumen)", pdf_bytes, "reporte.pdf", "application/pdf")
