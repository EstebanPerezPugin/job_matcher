<<<<<<< HEAD
# 🤖 JobAgent AI - Agente Búsqueda de Empleos & Dashboard HTML

Un agente de inteligencia artificial que se ejecuta automáticamente en **GitHub Actions** para buscar empleos en LinkedIn, aprender de las postulaciones que realizas y recomendar las mejores oportunidades a través de un **Dashboard HTML local ultra moderno**.

---

## 🌟 Características Principales

- 🔍 **Búsqueda Automatizada en GitHub Actions**: Se ejecuta periódicamente (2 veces al día) o de forma manual para rastrear nuevas vacantes en LinkedIn.
- 🧠 **Motor de Aprendizaje Continuo (NLP)**: Analiza el historial de empleos en los que has postulado (`data/applied.json`) y calcula un **Match Score (0 - 100%)** para cada nueva oferta encontrada.
- 📊 **Dashboard HTML Local Interactivo**:
  - **Vacantes Disponibles**: Ofertas ordenadas por puntuación de afinidad (Match Score) con enlace directo a LinkedIn y botón para registrar la postulación con 1 clic.
  - **Mis Postulaciones**: Control y seguimiento de tus postulaciones en estado (Postulado, Entrevista, Oferta, Rechazado).
  - **Aprendizaje de IA**: Visualizador de palabras clave y habilidades más valoradas según tus postulaciones.
  - **Configuración de Perfil**: Ajusta tus cargos deseados, habilidades y palabras clave de búsqueda.
- 🔒 **Privacidad & GitHub Integration**: Mantiene tus datos guardados en archivos JSON limpios dentro del repositorio sin exponer credenciales.

---

## 🚀 Guía de Inicio Rápido Local

### 1. Requisitos Previos
Tener instalado **Python 3.10+**.

### 2. Instalación de Dependencias
```bash
pip install -r requirements.txt
```

### 3. Ejecutar el Agente Localmente
Para probar el rastreo de empleos y el cálculo de afinidad por IA en tu máquina:
```bash
python src/agent/main.py
```
Esto buscará nuevas ofertas en LinkedIn, calculará el Match Score basándose en tus postulaciones previas y actualizará `data/jobs.json`.

### 4. Abrir el Dashboard HTML
Abre el archivo `web/index.html` en cualquier navegador web (Chrome, Safari, Firefox, Edge) o ejecuta un servidor HTTP rápido:
```bash
python -m http.server 8000
```
Y navega a `http://localhost:8000/web/index.html`.

---

## ⚙️ Configuración en GitHub Actions

El agente está configurado para ejecutarse automáticamente en GitHub mediante `.github/workflows/job_agent.yml`.

### (Opcional) Configurar Cookie de LinkedIn para Búsquedas Autenticadas
Para evitar limitaciones de tasa de peticiones en LinkedIn:
1. Inicia sesión en [LinkedIn.com](https://www.linkedin.com) en tu navegador.
2. Abre las herramientas de desarrollador (`F12` o `Cmd + Option + I`) -> **Application** -> **Cookies**.
3. Copia el valor de la cookie llamada `li_at`.
4. Ve a tu repositorio en GitHub: **Settings** -> **Secrets and variables** -> **Actions** -> **New repository secret**.
5. Crea un Secret con el nombre `LINKEDIN_COOKIE` y pega el valor de `li_at`.

---

## 📁 Estructura del Proyecto

```
Agente/
├── .github/
│   └── workflows/
│       └── job_agent.yml        # Workflow de automatización en GitHub Actions
├── data/
│   ├── applied.json             # Trabajos postulados (Base de entrenamiento IA)
│   ├── jobs.json                # Trabajos encontrados con su Match Score
│   └── profile.json             # Perfil y preferencias de búsqueda
├── src/
│   └── agent/
│       ├── data_manager.py      # Persistencia de datos JSON
│       ├── linkedin_scraper.py  # Buscador de ofertas en LinkedIn
│       ├── matcher.py           # Algoritmo de NLP y Match Score
│       └── main.py              # CLI principal del agente
├── web/
│   ├── index.html               # UI del Dashboard HTML5
│   ├── styles.css               # Estilos modernos (Glassmorphic Dark Theme)
│   └── app.js                 # Lógica interactiva y cliente JS
├── requirements.txt             # Dependencias Python
└── README.md                    # Documentación del proyecto
```
=======
# job_matcher
busqueda laboral en linkedin
>>>>>>> fafaac60d7f2a62ba8c93b5dbadec46fdb23a96c
