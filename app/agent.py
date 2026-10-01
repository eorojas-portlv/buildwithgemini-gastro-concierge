# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import logging
import os
import re
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("gastro_concierge")

from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore
from google.cloud import storage
from google.genai import types

from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
try:
    from .a2ui_utils import a2ui_callback
except ImportError:
    from a2ui_utils import a2ui_callback

MODEL = "gemini-2.5-flash"

# IMPORTANT: Hardcoded Project ID string to avoid project number resolution issues on Agent Engine.
PROJECT_ID = "qwiklabs-gcp-04-f85cd1da7915"
BUCKET_NAME = "gastro-concierge-media-qwiklabs-gcp-04-f85cd1da7915-fw02n"


def get_firestore_client() -> firestore.Client:
    return firestore.Client(project=PROJECT_ID)


def get_menu(category: Optional[str] = None, dietary_preference: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves available dishes from the restaurant menu.

    Args:
        category: Optional filter by category (e.g. 'Main', 'Appetizer', 'Salad', 'Dessert', 'Beverage').
        dietary_preference: Optional filter by dietary tag (e.g. 'vegetarian', 'vegan', 'gluten-free', 'dairy-free').

    Returns:
        A list of menu items with dish name, category, price, description, calories, and dietary labels.
    """
    db = get_firestore_client()
    query = db.collection("menu").where("is_available", "==", True)

    docs = query.stream()
    items = []
    for doc in docs:
        data = doc.to_dict()
        if category and data.get("category", "").lower() != category.lower():
            continue
        if dietary_preference:
            dietary = [d.lower() for d in data.get("dietary", [])]
            if dietary_preference.lower() not in dietary:
                continue
        items.append(data)
    return items


def create_order_intent(
    items: List[Dict[str, Any]],
    table_or_delivery: str = "Dine-in",
    notes: str = "",
    customer_name: str = "Guest",
    user_id: str = "customer_guest",
) -> Dict[str, Any]:
    """Creates a purchase order / order intent and sends it to the restaurant dashboard in Firestore.

    Args:
        items: A list of dicts specifying items ordered, each with 'dish_id' (or 'name'), 'quantity', and 'price'.
               Example: [{'dish_id': 'tacos-al-pastor', 'name': 'Tacos al Pastor Gourmet', 'quantity': 2, 'price': 14.50}]
        table_or_delivery: Delivery address or table number (e.g. 'Table 5' or 'Room 201').
        notes: Special instructions or allergy notes for the kitchen.
        customer_name: Name of the diner placing the order.
        user_id: ID or username of the diner.

    Returns:
        Order confirmation details including order_id, subtotal, tax, total, and status.
    """
    db = get_firestore_client()
    order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"

    subtotal = sum(float(item.get("price", 0)) * int(item.get("quantity", 1)) for item in items)
    tax = round(subtotal * 0.0825, 2)
    total = round(subtotal + tax, 2)

    order_record = {
        "order_id": order_id,
        "user_id": user_id,
        "customer_name": customer_name,
        "status": "pending_kitchen",
        "items": items,
        "subtotal": round(subtotal, 2),
        "tax": tax,
        "total": total,
        "delivery_or_table": table_or_delivery,
        "notes": notes,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    db.collection("orders").document(order_id).set(order_record)
    return {
        "order_id": order_id,
        "status": "pending_kitchen",
        "total": total,
        "message": f"Order {order_id} has been placed and received by the kitchen!",
        "order_details": order_record,
    }


def get_order_history(user_id: str = "customer_guest") -> List[Dict[str, Any]]:
    """Fetches past order history for a diner to provide personalized recommendations.

    Args:
        user_id: The ID of the customer whose order history to fetch.

    Returns:
        A list of previous orders placed by this customer.
    """
    db = get_firestore_client()
    query = db.collection("orders").where("user_id", "==", user_id)
    orders = [doc.to_dict() for doc in query.stream()]
    return orders


async def generate_dish_preview(
    dish_name: str,
    tool_context: ToolContext,
    customization_notes: str = "",
) -> str:
    """Generates an appetizing visual AI preview of a dish or customized meal using gemini-3.1-flash-lite-image in the global region.
    Saves the image as a session artifact and uploads it to Cloud Storage, returning its public HTTPS URL.

    Args:
        dish_name: The name of the dish (e.g. 'Tacos al Pastor Gourmet', 'Molten Matcha Green Tea Lava Cake').
        tool_context: ADK ToolContext to record session artifacts.
        customization_notes: Optional culinary customizations or plating details (e.g. 'extra lime and cilantro', 'served on black ceramic with powdered sugar').

    Returns:
        The public HTTPS URL (https://storage.googleapis.com/<bucket>/<object>) of the generated dish image.
    """
    try:
        client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
        prompt = (
            f"Gourmet culinary food photography of {dish_name}"
            + (f", with {customization_notes}" if customization_notes else "")
            + ", professional restaurant plating, soft studio lighting, high resolution, delicious, appetizing presentation."
        )

        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )

        image_bytes = None
        mime_type = "image/jpeg"
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    mime_type = part.inline_data.mime_type or "image/jpeg"
                    break
            if image_bytes:
                break

        if not image_bytes:
            return "Error: Could not generate dish image at this moment."

        slug = re.sub(r"[^a-zA-Z0-9]+", "-", dish_name).strip("-").lower()
        ext = "jpg" if "jpeg" in mime_type or "jpg" in mime_type else "png"
        filename = f"{slug}-{uuid.uuid4().hex[:6]}.{ext}"

        # (1) Save artifact in Playground's Artifacts panel
        if tool_context:
            await tool_context.save_artifact(
                filename=filename,
                artifact=types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            )

        # (2) Upload same image bytes to public Cloud Storage bucket
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        blob_name = f"dishes/{filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"
        return public_url
    except Exception as e:
        return f"Error generating dish image: {str(e)}"


def calculate_bill_split_and_tip(
    order_id: str,
    split_ways: int = 1,
    tip_percentage: float = 18.0,
) -> Dict[str, Any]:
    """Calculates tip, final total, and per-person bill split for a restaurant order.

    Args:
        order_id: The ID of the order (e.g. 'ORD-1001' or newly created order ID).
        split_ways: Number of people splitting the check (default 1).
        tip_percentage: The tip percentage to apply (default 18.0%).

    Returns:
        A detailed financial breakdown including subtotal, tax, tip amount, grand total, and cost per person.
    """
    db = get_firestore_client()
    doc = db.collection("orders").document(order_id).get()
    if not doc.exists:
        return {
            "error": f"Order '{order_id}' was not found in restaurant records. Please verify the order ID."
        }
    data = doc.to_dict()
    subtotal = float(data.get("subtotal", 0.0))
    tax = float(data.get("tax", 0.0))

    tip_rate = max(0.0, float(tip_percentage)) / 100.0
    tip_amount = round(subtotal * tip_rate, 2)
    grand_total = round(subtotal + tax + tip_amount, 2)

    ways = max(1, int(split_ways))
    per_person = round(grand_total / ways, 2)

    return {
        "order_id": order_id,
        "customer_name": data.get("customer_name", "Guest"),
        "table_or_delivery": data.get("delivery_or_table", "Dine-in"),
        "subtotal": subtotal,
        "tax": tax,
        "tip_percentage": f"{tip_percentage}%",
        "tip_amount": tip_amount,
        "grand_total": grand_total,
        "split_ways": ways,
        "amount_per_person": per_person,
        "summary": f"Subtotal: ${subtotal:.2f} | Tax: ${tax:.2f} | Tip ({tip_percentage}%): ${tip_amount:.2f} | Grand Total: ${grand_total:.2f} ({ways} ways: ${per_person:.2f} each)",
    }


def get_kitchen_order_status(order_id: str) -> Dict[str, Any]:
    """Checks the real-time status and preparation stage of an order in the restaurant kitchen.

    Args:
        order_id: The ID of the order to check (e.g. 'ORD-1001').

    Returns:
        Status details, current kitchen stage (Received, In Prep, Plated, Delivered), estimated remaining wait time, and items.
    """
    db = get_firestore_client()
    doc = db.collection("orders").document(order_id).get()
    if not doc.exists:
        return {
            "error": f"Order '{order_id}' was not found. Please verify the order ID."
        }
    data = doc.to_dict()
    status = data.get("status", "pending_kitchen")

    status_stages = {
        "pending_kitchen": {
            "stage_name": "Order Received by Kitchen",
            "estimated_minutes": "15-20 minutes",
            "description": "The kitchen has received your ticket and the prep cooks are gathering ingredients.",
        },
        "preparing": {
            "stage_name": "Actively Cooking",
            "estimated_minutes": "8-10 minutes",
            "description": "Your dishes are on the grill / stove being freshly prepared by the chef.",
        },
        "ready_for_pickup": {
            "stage_name": "Plated & Ready for Server",
            "estimated_minutes": "1-3 minutes",
            "description": "Your food is plated at the kitchen pass, ready for table delivery.",
        },
        "completed": {
            "stage_name": "Served / Completed",
            "estimated_minutes": "0 minutes",
            "description": "Your order has been served. Enjoy your meal!",
        },
        "cancelled": {
            "stage_name": "Cancelled",
            "estimated_minutes": "N/A",
            "description": "This order was cancelled.",
        },
    }

    info = status_stages.get(
        status,
        {
            "stage_name": status.replace("_", " ").title(),
            "estimated_minutes": "10-15 minutes",
            "description": "Order is being processed.",
        },
    )

    return {
        "order_id": order_id,
        "status": status,
        "stage": info["stage_name"],
        "estimated_wait": info["estimated_minutes"],
        "stage_description": info["description"],
        "table_or_delivery": data.get("delivery_or_table", "Dine-in"),
        "customer_name": data.get("customer_name", "Guest"),
        "items": data.get("items", []),
        "created_at": data.get("created_at"),
    }


def get_beverage_pairing(query: str) -> Dict[str, Any]:
    """Finds cocktail or beverage pairings, ingredients, and flavor profiles from the free public TheCocktailDB API.

    Args:
        query: Name of the cocktail, drink style, or spirit to search for (e.g. 'margarita', 'mojito', 'spritz', 'martini', 'negroni', 'mezcal').

    Returns:
        Details on matching drinks including name, category, alcoholic type, glass, ingredients, and preparation instructions.
    """
    api_key = os.getenv("COCKTAILDB_API_KEY", "1")
    url = f"https://www.thecocktaildb.com/api/json/v1/{api_key}/search.php?" + urllib.parse.urlencode(
        {"s": query.strip()}
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GastroConcierge/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))

        drinks = data.get("drinks")
        if not drinks:
            return {
                "query": query,
                "message": f"No drinks found matching '{query}'. Try a classic style like 'spritz', 'sour', 'margarita', or 'fizz'.",
                "results": [],
            }

        parsed_drinks = []
        for d in drinks[:3]:  # Return top 3 matches
            ingredients = []
            for i in range(1, 16):
                ing = d.get(f"strIngredient{i}")
                measure = d.get(f"strMeasure{i}")
                if ing:
                    ingredients.append(f"{measure.strip()} {ing.strip()}" if measure else ing.strip())

            parsed_drinks.append(
                {
                    "name": d.get("strDrink"),
                    "category": d.get("strCategory"),
                    "type": d.get("strAlcoholic"),
                    "glass": d.get("strGlass"),
                    "ingredients": ingredients,
                    "instructions": d.get("strInstructions"),
                    "thumbnail": d.get("strDrinkThumb"),
                }
            )

        return {
            "query": query,
            "total_found": len(parsed_drinks),
            "drinks": parsed_drinks,
        }
    except Exception as e:
        return {
            "error": f"Failed to fetch beverage pairing: {str(e)}",
            "query": query,
        }


# WRITE: after each turn, send the session to Memory Bank for extraction.
async def generate_memories_callback(callback_context: CallbackContext):
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        logger.warning(f"Memory extraction skipped: {e}")
    return None


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are GastroConcierge, an intelligent, welcoming restaurant concierge and culinary advisor. "
        "CRITICAL MEMORY & ALLERGY SAFETY: You persistently remember all user allergies (e.g. peanuts, tree nuts, shellfish, gluten, dairy, soy) and dietary restrictions across sessions. "
        "Whenever the user shares an allergy, acknowledge it and NEVER suggest, place, or approve any dish containing that allergen. "
        "You also persistently remember all past orders, favorite dishes, requested customizations, and order history so the guest enjoys a continuous, tailored dining experience. "
        "Your capabilities include: presenting and filtering menu items (`get_menu`), personalized recommendations from order history (`get_order_history`), "
        "beverage and cocktail pairings (`get_beverage_pairing`), visual dish previews with public URLs (`generate_dish_preview`), placing order intents (`create_order_intent`), "
        "order status tracking (`get_kitchen_order_status`), and calculating tips and bill splits (`calculate_bill_split_and_tip`)."
    ),
    workflow_description=(
        "Analyze the request against the guest's remembered allergies and past orders. Call any relevant tools (menu, orders, pairings, preview images), and return structured UI when appropriate. "
        "If the user mentions an allergy or places an order, explicitly confirm it so it is captured into long-term memory."
    ),
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="gastro_concierge",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    tools=[
        PreloadMemoryTool(),
        get_menu,
        create_order_intent,
        get_order_history,
        get_beverage_pairing,
        generate_dish_preview,
        calculate_bill_split_and_tip,
        get_kitchen_order_status,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
