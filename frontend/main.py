"""Minimal FastAPI proxy for a deployed A2A agent (Agent Runtime, agents-cli 1.1.0+).

The browser talks ONLY to this proxy (same origin, no CORS, no GCP creds in the
browser). The proxy authenticates with Application Default Credentials and
forwards chat to the deployed agent over the A2A protocol, returning replies as
structured parts the chat UI knows how to show:

  * {"kind": "text", "text": ...}  -> a normal chat bubble
  * {"kind": "a2ui", "data": ...}  -> one A2UI message (beginRendering /
    surfaceUpdate); static/index.html renders these as a card.

Why A2A: agents-cli 1.1.0 (GA) deploys ADK agents to Agent Runtime as A2A agents
and no longer registers the reasoning-engine operation schema the old
`agent_engines.get(...).stream_query()` path relied on (operation_schemas() comes
back empty). The container serves the A2A protocol over the Agent Engine HTTP
passthrough, so this proxy fetches the agent's card and sends messages with the
a2a-sdk client (the same path `agents-cli run --mode a2a` uses). This works for
both A2A and plain ADK 1.1.0 deployments (the container serves A2A either way).

Run:
  pip install -r requirements.txt
  export AGENT_ENGINE_RESOURCE_NAME="projects/.../locations/.../reasoningEngines/..."
  export AGENT_DIRECTORY="app"   # your agent's app directory (agents-cli-manifest.yaml)
  python main.py                 # -> http://localhost:8080
"""

import os
import uuid

import google.auth
import google.auth.transport.requests
import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.types import (
    AgentCard,
    FilePart,
    Message,
    Part,
    Role,
    TaskArtifactUpdateEvent,
    TextPart,
    TransportProtocol,
)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

RESOURCE = os.environ["AGENT_ENGINE_RESOURCE_NAME"]
# The agent's app directory (matches agent_directory in agents-cli-manifest.yaml).
AGENT_DIRECTORY = os.environ.get("AGENT_DIRECTORY", "app")
# Location is embedded in the resource name: projects/<p>/locations/<loc>/reasoningEngines/<id>.
LOCATION = RESOURCE.split("/locations/")[1].split("/")[0]

# A2A endpoint for an Agent Runtime deployment, via the Agent Engine HTTP
# passthrough. The card lives at the well-known path under this base.
A2A_BASE = (
    f"https://{LOCATION}-aiplatform.googleapis.com/reasoningEngines/v1/"
    f"{RESOURCE}/api/a2a/{AGENT_DIRECTORY}"
)
A2A_CARD_URL = f"{A2A_BASE}/.well-known/agent-card.json"

# The agent tags its A2UI data parts with this mime type.
_A2UI_MIME = "application/json+a2ui"

# One set of ADC credentials, refreshed per request (access tokens expire ~1h).
_creds, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)


def _auth_headers() -> dict[str, str]:
    _creds.refresh(google.auth.transport.requests.Request())
    return {
        "Authorization": f"Bearer {_creds.token}",
        "Content-Type": "application/json",
    }


app = FastAPI()


@app.exception_handler(Exception)
async def _json_errors(request: Request, exc: Exception):
    # Always return JSON so the browser never receives a plain-text 500 page
    # (which shows up in the chat as "Unexpected token 'I', "Internal S"... is
    # not valid JSON"). Any server-side failure now surfaces as a readable
    # message in the chat bubble instead.
    return JSONResponse(
        status_code=200,
        content={
            "parts": [{"kind": "text", "text": f"Error: {type(exc).__name__}: {exc}"}]
        },
    )


# Reuse ONE A2A context per user so the agent remembers the conversation.
_contexts: dict[str, str] = {}
# Cache the agent card after the first fetch.
_card: AgentCard | None = None


async def _get_card(client: httpx.AsyncClient) -> AgentCard:
    global _card
    if _card is None:
        resp = await client.get(A2A_CARD_URL)
        resp.raise_for_status()
        card = AgentCard(**resp.json())
        # Agent Runtime does not serve a public card URL, so point the client at
        # the passthrough base for message sends.
        card.url = A2A_BASE
        card.additional_interfaces = []
        _card = card
    return _card


def _extract_parts(parts: list) -> list[dict]:
    """Turn A2A response parts into structured parts for the chat UI.

    Text parts pass through as {"kind": "text"}. A2UI data parts (tagged
    application/json+a2ui) become {"kind": "a2ui", "data": <message>} so the UI
    renders the card; each data part is one A2UI message (beginRendering or
    surfaceUpdate).
    """
    import json
    import re

    out: list[dict] = []
    for p in parts:
        root = getattr(p, "root", p)
        if isinstance(root, TextPart) and getattr(root, "text", None):
            txt = root.text.strip()
            if "<a2ui-json>" in txt and "</a2ui-json>" in txt:
                try:
                    match = re.search(r"<a2ui-json>\s*(.*?)\s*</a2ui-json>", txt, re.DOTALL)
                    if match:
                        a2ui_obj = json.loads(match.group(1))
                        prefix = txt[:match.start()].strip()
                        suffix = txt[match.end():].strip()
                        if prefix:
                            out.append({"kind": "text", "text": prefix})
                        out.append({"kind": "a2ui", "data": a2ui_obj})
                        if suffix:
                            out.append({"kind": "text", "text": suffix})
                        continue
                except Exception:
                    pass
            out.append({"kind": "text", "text": root.text})
        elif getattr(root, "data", None) is not None:
            d = root.data
            meta = getattr(root, "metadata", None) or (d.get("metadata") if isinstance(d, dict) else {})
            mime = meta.get("mimeType") if isinstance(meta, dict) else None
            if mime == _A2UI_MIME:
                payload = d.get("data", d) if isinstance(d, dict) else d
                out.append({"kind": "a2ui", "data": payload})
            elif isinstance(d, dict) and any(k in d for k in ("surfaceUpdate", "beginRendering", "components", "surfaceId")):
                out.append({"kind": "a2ui", "data": d})
            elif isinstance(d, dict) and "data" in d and isinstance(d["data"], dict) and any(k in d["data"] for k in ("surfaceUpdate", "beginRendering", "components", "surfaceId")):
                out.append({"kind": "a2ui", "data": d["data"]})
            elif isinstance(d, dict) and "text" in d:
                out.append({"kind": "text", "text": str(d["text"])})
        elif isinstance(root, FilePart):
            uri = getattr(getattr(root, "file", None), "uri", None)
            if uri:
                out.append({"kind": "text", "text": uri})
    return out


@app.get("/api/customer")
async def get_customer(user_id: str = "carlos_mora"):
    try:
        from google.cloud import firestore
        db = firestore.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-f85cd1da7915"))
        doc = db.collection("customers").document(user_id).get()
        if doc.exists:
            return doc.to_dict()
    except Exception:
        pass
    return {
        "customer_id": user_id,
        "name": "Carlos Mora",
        "routine": {
            "daily_breakfast_time": "08:00 AM",
            "favorite_dish": "Chilaquiles Verdes Tradicionales con Pollo",
            "favorite_beverage": "Café de Olla Artesanal",
            "notes": "Cliente habitual de las 8:00 AM. Siempre pide chilaquiles o café.",
        },
    }


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "carlos_mora"
    parts: list[dict] = []

    # Inject client context on first turn if user is carlos_mora
    is_first_turn = user_id not in _contexts
    if user_id == "carlos_mora" and is_first_turn and "[Cliente" not in message:
        outbound_text = f"[Cliente autenticado: Carlos Mora (user_id: carlos_mora)] {message}"
    else:
        outbound_text = message

    async with httpx.AsyncClient(headers=_auth_headers(), timeout=120) as client:
        card = await _get_card(client)
        factory = ClientFactory(
            ClientConfig(
                supported_transports=[
                    TransportProtocol.jsonrpc,
                    TransportProtocol.http_json,
                ],
                httpx_client=client,
            )
        )
        a2a_client = factory.create(card)

        msg = Message(
            message_id=str(uuid.uuid4()),
            role=Role.user,
            parts=[Part(root=TextPart(text=outbound_text))],
            context_id=_contexts.get(user_id),
        )

        last_task = None
        got_artifact_update = False
        async for event in a2a_client.send_message(msg):
            if isinstance(event, tuple):
                task, update = event
            else:
                task = getattr(event, "task", event)
                update = getattr(event, "update", None)

            if task is not None:
                last_task = task
                if getattr(task, "context_id", None):
                    _contexts[user_id] = task.context_id
            if isinstance(update, TaskArtifactUpdateEvent):
                got_artifact_update = True
                parts.extend(_extract_parts(update.artifact.parts))
            elif getattr(update, "artifact", None) is not None:
                parts.extend(_extract_parts(update.artifact.parts))

        # Non-streaming fallback: pull parts from the final task's artifacts.
        if not parts and last_task is not None:
            for artifact in getattr(last_task, "artifacts", None) or []:
                parts.extend(_extract_parts(artifact.parts))

        # Fallback to last agent message in history if parts is still empty
        if not parts and last_task is not None:
            for msg in reversed(getattr(last_task, "history", None) or []):
                if getattr(msg, "role", None) == Role.agent:
                    msg_parts = _extract_parts(getattr(msg, "parts", None) or [])
                    if msg_parts:
                        parts.extend(msg_parts)
                        break

    if not parts:
        # The turn produced no text or UI (e.g. the agent only ran tools, or a
        # tool stalled). Be honest rather than silent.
        parts = [{"kind": "text", "text": "(The agent didn't return a reply.)"}]
    return JSONResponse({"parts": parts})


# Serve the chat UI (keep this mount last so /chat wins).
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
