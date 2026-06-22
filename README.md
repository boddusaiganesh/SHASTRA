# SHASTRA 
**Spatial Hotspot & Advanced Societal Threat Recognition Architecture**

SHASTRA is a state-of-the-art Crime Intelligence & Analytical Platform designed for the Karnataka State Police (KSP). It integrates sociological insights and criminological intelligence with cutting-edge AI and Machine Learning technology to transform how police forces analyze, track, and prevent crime.

---

## The Challenge: Moving Beyond Manual Records

The Karnataka State Police (KSP) maintains extensive crime records capturing incidents, offenders, and victims. However, the current analytical ecosystem faces significant hurdles:

- **Data Silos & Manual Processes**: Current records are often managed in independent silos, heavily reliant on Excel-based reporting rather than integrated, automated systems.
- **Lack of Advanced Analytics**: There is a notable absence of AI-driven approaches, leaving deeper behavioral patterns, social interactions, and interconnected criminal networks undiscovered.
- **Information Gaps**: The State Crime Records Bureau (SCRB) currently receives limited, fragmented information, hindering its ability to perform comprehensive state-wide analysis.
- **Reactive vs. Proactive**: Policing remains largely reactive; without a systematic exploration of emerging trends, investigators lack the tools for proactive policing strategies and evidence-based prevention.

---

## The Solution: Crime Intelligence & Analytical Platform

The goal is to move the SCRB from reactive reporting to a **Strategic Intelligence Hub**. SHASTRA replaces static sheets with interactive dashboards, AI-driven predictive forecasting, and geospatial maps to track crime clusters across districts.

### Key Capabilities

#### 1. Advanced Visualization
*Data visualization moves beyond static charts into dynamic, spatial, and relational storytelling.*
- **District-Level Drill-down**: Interactive maps allow SCRB to visualize crime patterns across districts and specific police stations.
- **Spatiotemporal Clusters**: Identification of "Crime Hotspots" by layering time of day with location, enabling proactive resource deployment.
- **Emerging Trend Alerts**: Visual indicators (e.g., aggressive red-zone pulsing animations) when a specific crime category spikes in a region compared to historical averages.

#### 2. Criminological Network & Link Analysis
*This functionality replaces "independent silos" by visually connecting fragmented data points to reveal organized crime structures.*
- **Relationship Mapping**: A node-based visualization showing connections between suspects, victims, and recurring locations.
- **Repeat Offender Tracking**: Visual profiles that link an individual to multiple incidents, highlighting their specific Modus Operandi (MO) across different jurisdictions.
- **Association Detection**: Identifying hidden criminal associations that are impossible to spot in isolated Excel sheets.

#### 3. Sociological & AI-Driven Predictive Dashboards
*Utilizing statistical analytics and Machine Learning to move beyond simple mapping.*
- **Socio-Economic Correlation**: Overlays crime data with urbanization patterns, population distribution, and socio-economic indicators to understand the "why" behind the "where".
- **Predictive Risk Scoring**: AI-driven charts (powered by Facebook Prophet) that forecast potential "High-Risk" areas or emerging crime typologies based on hidden correlations.
- **Anomaly Detection**: Visual call-outs (powered by Scikit-Learn Isolation Forests) for incidents that deviate from standard behavioral patterns, assisting investigators in linking complex cases.

---

## Technical Architecture

The platform is divided into a robust, decoupled architecture:

### Frontend (React + Vite + TailwindCSS)
- `react-leaflet` for dynamic geospatial mapping.
- `cytoscape.js` for complex criminal network graphing.
- `framer-motion` for smooth, responsive UI animations and critical alert pulses.
- `recharts` for interactive trend analysis.
- Resilient architecture with built-in mock data fallbacks for offline development.

### Backend (Python FastAPI)
- **Asynchronous APIs**: High-performance REST endpoints serving the React frontend.
- **Machine Learning Engine**: 
  - `scikit-learn` (Isolation Forest) for statistical anomaly detection.
  - `prophet` for 30-day time-series crime forecasting.
- **Background Scheduler**: `APScheduler` acting as an ETL pipeline to run ML scans continuously in the background.
- **Database Integration**: SQLAlchemy ORM for PostgreSQL and Cypher queries for Neo4j graph databases.

---

## Getting Started

### 1. Run the Backend API
```bash
cd crime_backend/MODULE_2_BACKEND
python -m venv venv
source venv/bin/activate  # (or venv\Scripts\activate on Windows)
pip install -r requirements.txt
python main.py
```
*The API will be available at `http://localhost:8000`*

### 2. Run the Frontend Dashboard
```bash
cd crime_frontend
npm install
npm run dev
```
*The Dashboard will be available at `http://localhost:5173`*

*(Note: If local databases are not running, the frontend and API will gracefully fall back to utilizing sophisticated mock intelligence data to ensure continuous operation during development and testing).*
