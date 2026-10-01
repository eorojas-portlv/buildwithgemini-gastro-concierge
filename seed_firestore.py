import datetime
from google.cloud import firestore

# IMPORTANT: Hardcode the Project ID string as required.
FIRESTORE_PROJECT = "qwiklabs-gcp-04-f85cd1da7915"

def seed_database():
    db = firestore.Client(project=FIRESTORE_PROJECT)
    print(f"Connecting to Firestore in project: {FIRESTORE_PROJECT}")

    # Seed Restaurant Menu Items
    menu_items = [
        {
            "id": "tacos-al-pastor",
            "name": "Tacos al Pastor Gourmet",
            "category": "Main",
            "price": 14.50,
            "description": "Marinated pork roasted on vertical spit with pineapple, fresh cilantro, diced onion, and house salsa verde on handmade corn tortillas.",
            "dietary": ["gluten-free", "dairy-free"],
            "calories": 520,
            "is_available": True,
            "tags": ["mexican", "pork", "spicy", "popular"],
        },
        {
            "id": "truffle-gnocchi",
            "name": "Wild Mushroom & Truffle Gnocchi",
            "category": "Main",
            "price": 22.00,
            "description": "Handcrafted potato gnocchi tossed with wild chanterelles, black truffle cream sauce, and aged parmigiano-reggiano.",
            "dietary": ["vegetarian"],
            "calories": 680,
            "is_available": True,
            "tags": ["italian", "pasta", "truffle", "vegetarian"],
        },
        {
            "id": "hamachi-crudo",
            "name": "Pacific Hamachi Crudo",
            "category": "Appetizer",
            "price": 18.00,
            "description": "Yellowtail sashimi slices with yuzu ponzu, thinly shaved serrano chili, micro cilantro, and white truffle oil.",
            "dietary": ["gluten-free", "dairy-free", "pescatarian"],
            "calories": 310,
            "is_available": True,
            "tags": ["seafood", "raw", "fresh", "japanese"],
        },
        {
            "id": "kale-avocado-bowl",
            "name": "Green Goddess Quinoa & Avocado Bowl",
            "category": "Salad",
            "price": 15.00,
            "description": "Organic baby kale, tri-color quinoa, hass avocado, edamame, cucumber, pumpkin seeds, and green goddess tahini dressing.",
            "dietary": ["vegan", "gluten-free", "dairy-free"],
            "calories": 420,
            "is_available": True,
            "tags": ["healthy", "vegan", "salad", "keto-friendly"],
        },
        {
            "id": "matcha-lava-cake",
            "name": "Molten Matcha Green Tea Lava Cake",
            "category": "Dessert",
            "price": 11.00,
            "description": "Warm Japanese Uji matcha sponge cake with a molten white chocolate-matcha core, served with black sesame gelato.",
            "dietary": ["vegetarian"],
            "calories": 490,
            "is_available": True,
            "tags": ["dessert", "sweet", "matcha", "signature"],
        },
        {
            "id": "hibiscus-mezcal-mocktail",
            "name": "Smoked Hibiscus Spritz (Zero Proof)",
            "category": "Beverage",
            "price": 9.50,
            "description": "Artisanal smoked hibiscus tea, agave nectar, fresh lime juice, pink peppercorn rim, and sparkling soda.",
            "dietary": ["vegan", "gluten-free"],
            "calories": 95,
            "is_available": True,
            "tags": ["beverage", "mocktail", "refreshing"],
        }
    ]

    for item in menu_items:
        doc_id = item["id"]
        db.collection("menu").document(doc_id).set(item)
        print(f"✓ Seeded menu item: {item['name']} ({doc_id})")

    # Seed Sample Initial Purchase Intent / Order for the restaurant dashboard
    sample_order = {
        "order_id": "ORD-1001",
        "user_id": "customer_guest",
        "customer_name": "Valued Guest",
        "status": "pending_kitchen",  # pending_kitchen, preparing, completed, cancelled
        "items": [
            {
                "dish_id": "hamachi-crudo",
                "name": "Pacific Hamachi Crudo",
                "quantity": 1,
                "price": 18.00
            },
            {
                "dish_id": "truffle-gnocchi",
                "name": "Wild Mushroom & Truffle Gnocchi",
                "quantity": 1,
                "price": 22.00
            }
        ],
        "subtotal": 40.00,
        "tax": 3.60,
        "total": 43.60,
        "delivery_or_table": "Table 4",
        "notes": "Extra parmesan on the side please",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    db.collection("orders").document(sample_order["order_id"]).set(sample_order)
    print(f"✓ Seeded sample order: {sample_order['order_id']}")

if __name__ == "__main__":
    seed_database()
