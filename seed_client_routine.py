import datetime
from google.cloud import firestore

FIRESTORE_PROJECT = "qwiklabs-gcp-04-f85cd1da7915"

def seed_client_and_menu():
    db = firestore.Client(project=FIRESTORE_PROJECT)
    print(f"Connecting to Firestore in project: {FIRESTORE_PROJECT}")

    # 1. Seed Breakfast Menu Items (Chilaquiles & Café)
    new_menu_items = [
        {
            "id": "chilaquiles-verdes",
            "name": "Chilaquiles Verdes Tradicionales con Pollo",
            "category": "Breakfast",
            "price": 12.50,
            "description": "Totopos de maíz crujientes bañados en salsa verde de tomatillo asado, pechuga de pollo deshebrada, crema fresca, queso cotija, cebolla morada y cilantro.",
            "dietary": ["gluten-free"],
            "calories": 580,
            "is_available": True,
            "tags": ["mexican", "breakfast", "chilaquiles", "desayuno", "popular", "morning"],
        },
        {
            "id": "cafe-de-olla",
            "name": "Café de Olla Artesanal",
            "category": "Beverage",
            "price": 4.50,
            "description": "Café de grano oscuro mexicano infusionado en barro con piloncillo de caña, canela en rama y un toque de piel de naranja.",
            "dietary": ["vegan", "gluten-free"],
            "calories": 60,
            "is_available": True,
            "tags": ["beverage", "coffee", "cafe", "breakfast", "desayuno", "morning", "warm"],
        },
        {
            "id": "chilaquiles-rojos",
            "name": "Chilaquiles Rojos con Huevos Estrellados",
            "category": "Breakfast",
            "price": 13.00,
            "description": "Totopos dorados en salsa roja de jitomate y guajillo, coronados con dos huevos tiernos estrellados, aguacate fresco y queso fresco.",
            "dietary": ["vegetarian", "gluten-free"],
            "calories": 620,
            "is_available": True,
            "tags": ["mexican", "breakfast", "chilaquiles", "desayuno"],
        }
    ]

    for item in new_menu_items:
        db.collection("menu").document(item["id"]).set(item)
        print(f"✓ Menu seeded: {item['name']} ({item['id']})")

    # 2. Seed Customer Record
    customer_ids = ["carlos_mora", "web-user", "customer_guest"]
    customer_data = {
        "customer_id": "carlos_mora",
        "name": "Carlos Mora",
        "email": "carlos.mora@example.com",
        "routine": {
            "daily_breakfast_time": "08:00 AM",
            "favorite_dish": "Chilaquiles Verdes Tradicionales con Pollo",
            "favorite_beverage": "Café de Olla Artesanal",
            "notes": "Cliente frecuente de todas las mañanas a las 8:00 AM. Siempre compra chilaquiles o café de olla para iniciar el día."
        },
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }
    db.collection("customers").document("carlos_mora").set(customer_data)
    print("✓ Customer record created: carlos_mora")

    # 3. Seed Frequent Morning Purchase History (Orders at 8:00 AM)
    now = datetime.datetime.now(datetime.timezone.utc)
    for user_id in customer_ids:
        for days_ago in range(1, 5):
            order_time = (now - datetime.timedelta(days=days_ago)).replace(hour=8, minute=0, second=0, microsecond=0)
            order_id = f"ORD-BF-{user_id[:4]}-{order_time.strftime('%Y%m%d')}"
            
            order_doc = {
                "order_id": order_id,
                "user_id": user_id,
                "customer_name": "Carlos Mora" if user_id == "carlos_mora" else "Cliente Habitual",
                "status": "completed",
                "items": [
                    {
                        "dish_id": "chilaquiles-verdes",
                        "name": "Chilaquiles Verdes Tradicionales con Pollo",
                        "quantity": 1,
                        "price": 12.50
                    },
                    {
                        "dish_id": "cafe-de-olla",
                        "name": "Café de Olla Artesanal",
                        "quantity": 1,
                        "price": 4.50
                    }
                ],
                "subtotal": 17.00,
                "tax": 1.53,
                "total": 18.53,
                "delivery_or_table": "Mesa 2 - Desayuno Express",
                "notes": "Desayuno habitual de las 8:00 AM (Chilaquiles verdes + Café de olla).",
                "created_at": order_time.isoformat()
            }
            db.collection("orders").document(order_id).set(order_doc)
            print(f"✓ Seeded purchase history: {order_id} for {user_id} at 08:00 AM")

if __name__ == "__main__":
    seed_client_and_menu()
