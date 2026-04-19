# SourceGraph Overwatch: Project Architecture

**SourceGraph Overwatch** is an ultra-high performance, distributed anti-piracy intelligence engine. It utilizes dimensional reduction and multi-modal vector similarity mathematically mapped across visual streams (512-D) and text transcripts (384-D) to detect structural media piracy instantly. 

The architecture is composed of an **Ingestion Frontend** leveraging the Next.js App Router following strict "Linear/Apple" design systems, talking to an asynchronous **FastAPI Orchestrator backend**.

---

## 1. Directory Structure

```text
orchestrator/
├── frontend/                     # Next.js 16 (App Router) React Frontend
│   ├── app/                      
│   │   ├── globals.css           # Vercel/Linear dark mode tailwind v4 foundation
│   │   ├── layout.tsx            # Global HTML/Body Wrapper
│   │   ├── (marketing)/          # Route Group: Isolated Marketing Context
│   │   │   └── page.tsx          # Cinematic Landing Page ('/')
│   │   ├── (ingest)/             # Route Group: Isolated UX (No Navbar)
│   │   │   └── upload/page.tsx   # Zen-Mode Upload File Dropzone
│   │   └── (dashboard)/          # Route Group: Dashboard Context
│   │       ├── layout.tsx        # Command Center Layout (Includes Navbar)
│   │       ├── dashboard/page.tsx# Command Center Telemetry Feed
│   │       └── insights/page.tsx # Future: Deep Insights / Graph Modality
│   ├── components/               
│   │   └── Navbar.tsx            # Global Command Center Application Header
│   └── package.json
│
├── backend/                      # Python FastAPI Distributed Engine
│   ├── main.py                   # FastAPI Application Entrypoint & Middleware
│   ├── requirements.txt          
│   ├── app/                      
│   │   ├── controllers/          # API Route Definitions (Ingest, Vector, Queries)
│   │   ├── core/                 # Central Configurations (Logger, Settings, Security)
│   │   ├── models/               # Pydantic Schemas / DB Models (Schemas.py)
│   │   ├── repositories/         # Database / Storage abstraction (Vector_Repo)
│   │   └── services/             # Core Business Logic
│   │       ├── similarity_service.py # Core Vector Distance Mathematics (Fused Scoring)
│   │       └── buffer_service.py     # Asynchronous Feed Management
│   └── docker-compose.yml        # Infrastructure deployment definition
```

---

## 2. Component deep-dive

### A. The Next.js Frontend
The frontend follows a highly rigorous **Progressive Disclosure** routing strategy to prevent cognitive overload.


### B. The FastAPI Backend
The backend utilizes Python specifically optimized for high-concurrency vector matching operations and buffer state management.

- **`controllers/`**: Maps standard HTTP `POST` and `GET` requests from the frontend down into raw python object interactions.
- **`services/similarity_service.py`**: The "brain" of Overwatch. It handles the math mapping 512-D and 384-D vector distance models mathematically calculating standard Euclidean or Cosine matrices predicting threshold breaches indicating Pirated matched material.
- **`services/buffer_service.py`**: A synchronized worker model keeping multiple input streams alive and ensuring heavy ML transformation traces do not block the central FastAPI async event loop.

---

## 3. Technology Stack

- **Framework**: Next.js 16 (App Router) / Python FastAPI
- **Styling**: Tailwind CSS v4
- **Animation**: Framer Motion
- **Icons**: Lucide React
- **Data Persistence**: TBD (usually Qdrant, Milvus, or PgVector for dimensional storage)
- **Networking**: Simulated asynchronous processing over standard `fetch()` API calls.

## 4. Work In Progress (Next Steps)
- **Step 5 (`app/(dashboard)/insights`)**: Building the complex Nexus Graph leveraging `reactflow` to plot lineage logic visualizing *exact* source attribution between a pirated asset match and its associated Golden Source.
