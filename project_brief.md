# My agent: GastroConcierge (Restaurant Food Concierge)
One-liner: A conversational agent that helps restaurant diners explore a dynamic menu, receive personalized dish recommendations based on past orders, preview generated visual dishes, and place live purchase orders sent to a restaurant dashboard.

Tool coverage:
- Memory: User dining preferences, dietary restrictions/allergies, order history, and favorite flavor profiles across sessions.
- Tools:
  - `fetch_menu(category, dietary_filter)`: Query available dishes from the restaurant catalog/Firestore.
  - `create_order_intent(items, notes, table_or_delivery_info)`: Places a purchase order / intent record stored for the restaurant dashboard.
  - `get_order_history(user_id)`: Fetches past orders to compute personalized dish recommendations.
- Catalog/UI: Interactive restaurant menu items (name, description, price, allergens) and order summaries rendered as A2UI rich cards and tables.
- Image gen: Generates dummy/preview images of customized or special menu dishes on demand (via Gemini image generation).
- Sandbox: Computes order totals, tip, split bills, and nutrient/calorie aggregations.

Recommended for every project: memory, storage, tools, image generation, A2UI
Agent-specific / stretch (pick what fits): Code sandbox for bill split/pricing calculations, Firestore collection for the live restaurant orders dashboard, Cloud Run frontend with A2UI card renderer.
