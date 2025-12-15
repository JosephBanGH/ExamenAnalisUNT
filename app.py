import streamlit as st
import requests
import base64
from PIL import Image
import io

class ExamEvaluator:
    def __init__(self):
        self.n8n_webhook_url = "http://localhost:5678/webhook-test/exam-auto-grader"
        self.results = None
        self.statistics = None
    
    def process_image(self, image_file, exam_id="mobile-exam", student_id="mobile01", answer_key=None):
        """Envía imagen a n8n para procesamiento"""
        try:
            # Leer la imagen y convertir a base64
            image_bytes = image_file.getvalue()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Preparar payload JSON con base64
            payload = {
                'student_id': student_id,
                'exam_id': exam_id,
                'exam_image': image_base64,  # Base64 puro, sin prefijo
                'answer_key': answer_key or '{}',  # JSON string con respuestas correctas
                'timestamp': str(st.session_state.get('timestamp', ''))
            }
            
            with st.spinner('🔍 Analizando examen...'):
                response = requests.post(
                    self.n8n_webhook_url, 
                    json=payload,  # Enviar como JSON, NO como files
                    headers={'Content-Type': 'application/json'},
                    timeout=180
                )

            #PROVICIONAL      
            st.write("🧾 Estado:", response.status_code)
            st.write("📄 Texto recibido:", response.text)
                
            if response.status_code == 200:
                result = response.json()

                self.results = result
                return result
            else:
                st.error(f"Error en el procesamiento: {response.status_code}")
                st.error(f"Detalle: {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            st.error("⏱️ Timeout: El servidor tardó demasiado en responder")
            return None
        except requests.exceptions.ConnectionError:
            st.error("🔌 Error de conexión: No se pudo conectar con n8n")
            st.info("Verifica que n8n esté corriendo en http://localhost:5678")
            return None
        except Exception as e:
            st.error(f"Error inesperado: {str(e)}")
            return None
    
    def display_results(self, results):
        """Muestra los resultados del examen"""
        if not results:
            st.warning("No hay resultados para mostrar")
            return
        
        if isinstance(results, dict) and 'evaluador' in results:
            try:
                results_flat = results['evaluador'][0]['json']
                results_flat['raw_ocr_text'] = results.get('raw_ocr_text', '')
                results = results_flat
            except Exception as e:
                st.error(f"Error procesando estructura de resultados: {e}")
                return
            
        # Métricas principales
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("✅ Correctas", results.get('correct_count', 0))
        with col2:
            st.metric("❌ Incorrectas", results.get('incorrect_count', 0))
        with col3:
            score = results.get('percent_correct', 0)
            st.metric("📊 Nota", f"{score}%", 
                    delta=f"{score - 70:.1f}" if score >= 70 else f"{score - 70:.1f}")
        
        # Detalles por pregunta
        st.subheader("📝 Detalle por Pregunta")
        answers = results.get('answers', [])
        
        if answers:
            for ans in answers:
                col1, col2, col3, col4 = st.columns([1, 2, 2, 1])
                with col1:
                    st.write(f"**Q{ans['question']}**")
                with col2:
                    st.write(f"Tu respuesta: {ans.get('studentValue', 'N/A')}")
                with col3:
                    st.write(f"Correcta: {ans.get('correctValue', 'N/A')}")
                with col4:
                    if ans.get('isCorrect'):
                        st.success("✓")
                    else:
                        st.error("✗")
        else:
            st.info("No se detectaron respuestas en el examen")
        
        # Mostrar texto OCR extraído (útil para debug)
        with st.expander("🔍 Ver texto extraído (OCR)"):
            raw_text = results.get('raw_ocr_text', 'No disponible')
            st.text(raw_text)


# ===== Interfaz de Streamlit =====

def main():
    st.set_page_config(page_title="Exam Grader", page_icon="📝", layout="wide")
    
    st.title("📝 Automatic Exam Grader")
    st.markdown("Sube una foto de tu examen y obtén tu calificación al instante")
    
    # Inicializar evaluador
    if 'evaluator' not in st.session_state:
        st.session_state.evaluator = ExamEvaluator()
    
    evaluator = st.session_state.evaluator
    
    # Sidebar para configuración
    with st.sidebar:
        st.header("⚙️ Configuración")
        exam_id = st.text_input("ID del Examen", "EXAM001")
        
        student_id = st.text_input("ID de estudiante","mobile01")

        st.subheader("🔑 Clave de Respuestas")
        st.caption("Formato JSON: {\"1\":\"A\",\"2\":\"B\",...}")
        answer_key_input = st.text_area(
            "Answer Key",
            '{"1":"A","2":"B","3":"C","4":"D","5":"A","6":"A"}',
            height=150
        )
        
        # Validar JSON
        try:
            import json
            json.loads(answer_key_input)
            answer_key_valid = True
        except:
            st.error("⚠️ JSON inválido")
            answer_key_valid = False
    
    # Área principal
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📤 Subir Examen")
        uploaded_file = st.file_uploader(
            "Sube una imagen del examen",
            type=['png', 'jpg', 'jpeg'],
            help="Asegúrate de que la imagen sea clara y legible"
        )
        
        if uploaded_file:
            # Mostrar preview
            image = Image.open(uploaded_file)
            st.image(image, caption="Vista previa", use_column_width=True)
            
            # Botón de procesamiento
            if st.button("🚀 Evaluar Examen", type="primary", disabled=not answer_key_valid):
                results = evaluator.process_image(
                    uploaded_file, 
                    exam_id=exam_id,
                    student_id=student_id,
                    answer_key=answer_key_input
                )
                print(results)
                if results:
                    st.success("✅ Examen procesado exitosamente!")
                    st.session_state.last_results = results
    
    with col2:
        st.subheader("📊 Resultados")
        if hasattr(st.session_state, 'last_results'):
            
            evaluator.display_results(st.session_state.last_results)
        else:
            st.info("👈 Sube un examen para ver los resultados aquí")
    
    # Footer
    st.markdown("---")
    st.caption("💡 Tip: Para mejores resultados, usa imágenes con buena iluminación y sin sombras")


if __name__ == "__main__":
    main()