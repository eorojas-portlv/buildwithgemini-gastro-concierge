# GastroConcierge

GastroConcierge is an intelligent, multimodal culinary assistant and restaurant concierge built on Google's Agent Development Kit (ADK) and Gemini. It orchestrates menu discovery, dietary safety, personalized order recommendations from past habits, cocktail pairings, culinary image previews, and kitchen order management.

---

## Capabilities & Architecture

GastroConcierge implements a ReAct loop with native Agent-to-Agent (A2A) protocol communication, long-term cross-session memory, and Agent-to-User Interface (A2UI v0.8) rich card rendering.

### Integrated Google Cloud Services

- **Vertex AI Agent Engine (Memory Bank)**: Cross-session persistent memory (`PreloadMemoryTool` and `add_session_to_memory`). Remembers guest allergies (gluten, dairy, nuts, shellfish), dietary preferences, and frequent dining habits (e.g. daily breakfast routine at 8:00 AM) across conversations.
- **Google Cloud Firestore**: Real-time NoSQL database storing:
  - `menu`: Full catalog of appetizers, salads, main courses, desserts, and beverages with prices, allergens, and availability.
  - `orders`: Kitchen order intents, timestamps, statuses, and item breakdowns.
  - `customers`: Guest profiles, dietary notes, and recurrent order habits.
- **Google Cloud Storage (GCS)**: Public media bucket for hosting AI-generated culinary imagery with public HTTPS URLs.
- **Vertex AI Image Generation (`gemini-3.1-flash-lite-image`)**: Generates photorealistic dish previews on demand, uploads them to Cloud Storage, and returns them as session artifacts and inline visual cards.
- **Vertex AI Multimodal Live WebSocket API**: Real-time bidirectional voice assistant (`voice_app.py`) powered by `gemini-live-2.5-flash-native-audio` with voice activity detection.

### Agent Tools (`app/agent.py`)

| Tool Name | Type | Description |
|---|---|---|
| `PreloadMemoryTool` | Vertex AI Memory | Automatically retrieves long-term customer facts, allergies, and dining preferences at the start of each turn. |
| `get_menu` | Firestore Query | Queries dishes with optional filtering by category (`Breakfast`, `Main`, `Appetizer`, `Dessert`, `Beverage`, `Salad`) or dietary restrictions (`vegetarian`, `vegan`, `gluten-free`). |
| `create_order_intent` | Firestore Mutation | Creates a new order in `pending_kitchen` status, calculates line totals and sales tax, and returns an order confirmation. |
| `get_order_history` | Firestore Query | Retrieves past orders for a diner ID to provide personalized recommendations based on past purchase frequency. |
| `get_beverage_pairing` | External REST API | Queries TheCocktailDB API for authentic cocktails, zero-proof mocktails, ingredients, and mixing instructions. |
| `generate_dish_preview` | Vertex AI & GCS | Generates high-resolution food photography for a dish with custom plating notes, uploads it to Cloud Storage, and returns a public URL. |
| `calculate_bill_split_and_tip` | Financial Computation | Computes customizable tip rates, sales tax, grand totals, and per-person cost breakdowns for any order. |
| `get_kitchen_order_status` | Firestore Query | Checks the live status of an active kitchen order (`pending_kitchen`, `preparing`, `completed`). |

### User Interface & Communication Protocols

- **Agent-to-User Interface (A2UI v0.8)**: Generates structured surfaces (Cards, Columns, Rows, Texts, Images, Icons) via `a2ui_callback` rather than raw text, rendered client-side by a lightweight JavaScript renderer.
- **A2A FastAPI Gateway (`frontend/`)**: Reverse proxy forwarding client requests over the A2A protocol to Agent Runtime using Application Default Credentials (ADC) and persistent session context mapping.

---

## Planned / Not Yet Implemented

The following features were scoped during initial design but are **planned, not yet implemented**:
- **External Table Reservation Integration**: Direct booking integration with third-party reservation systems (OpenTable / Resy API).
- **Payment Gateway Processing**: Automated credit card transaction handling via Stripe or Square checkout.

---

## Local Setup & Development

### Prerequisites

- Python 3.12 or 3.13
- `uv` package manager
- `google-agents-cli` (`agents-cli`)
- Google Cloud SDK (`gcloud`) with Application Default Credentials configured:
  ```bash
  gcloud auth application-default login
  ```

### 1. Install Dependencies

```bash
# In the project root
uv sync
```

### 2. Seed Firestore Data

Populate the Firestore database with initial menu items, sample orders, and customer routine data:

```bash
uv run python seed_firestore.py
uv run python seed_client_routine.py
```

### 3. Run the Agent Locally

To launch the ADK playground with Memory Bank integration:

```bash
uv run adk web . --port 8080 --reload_agents --memory_service_uri=agentengine://<YOUR_AGENT_ENGINE_ID>
```

### 4. Run the Web Chat Frontend (A2A Proxy)

To launch the web interface with native A2UI card rendering:

```bash
cd frontend
pip install -r requirements.txt
export AGENT_ENGINE_RESOURCE_NAME="projects/<PROJECT>/locations/<REGION>/reasoningEngines/<REASONING_ENGINE_ID>"
export AGENT_DIRECTORY="app"
export PORT="8080"
python main.py
```

### 5. Run the Real-Time Gemini Live Voice Assistant

To start the standalone voice application:

```bash
uv run python voice_app.py
```

---

## Deployment Summary

- **Agent Engine**: Deployed to Vertex AI Agent Runtime (`deployment_target: "agent_runtime"`) in `us-central1`.
- **Web Frontend**: Containerized and deployed to Google Cloud Run with `roles/aiplatform.user` granted to the service account to access the Agent Engine A2A endpoints.
