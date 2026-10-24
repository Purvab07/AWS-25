from product_matcher import match_products
from replacement_ranker import rank_replacements
from replacement_engine import find_replacements

recalled_product = {
    "id": 1,
    "name": "Organic Romaine Hearts",
    "category": "Leafy Greens",
    "description": "Organic romaine lettuce hearts",
    "variety": "Romaine",
    "package_size": "18 oz"
}


candidates = [
    {
        "id": 2,
        "name": "Organic Romaine Lettuce Hearts",
        "category": "Leafy Greens",
        "description": "Organic romaine lettuce hearts",
        "variety": "Romaine",
        "package_size": "18 oz"
    },
    {
        "id": 3,
        "name": "Iceberg Lettuce",
        "category": "Leafy Greens",
        "description": "Fresh iceberg lettuce",
        "variety": "Iceberg",
        "package_size": "18 oz"
    },
    {
        "id": 4,
        "name": "Romaine Hearts 3-Pack",
        "category": "Leafy Greens",
        "description": "Fresh romaine lettuce hearts",
        "variety": "Romaine",
        "package_size": "18 oz"
    }
]


result = match_products(
    recalled_product,
    candidates
)


print("\nBEDROCK PRODUCT MATCHING")
print("------------------------")

for item in result["matches"]:
    status = "MATCH" if item["is_match"] else "NOT MATCH"

    print(
        f"Product {item['product_id']}: "
        f"{status}"
    )

    print(
        f"Reason: {item['reason']}\n"
    )

candidates = [
    {
        "supplier": "Green Valley Farms",
        "product_name": "Organic Romaine Lettuce Hearts",
        "is_match": True,
        "quantity_available": 1000,
        "estimated_lead_time_hours": 2,
        "distance_miles": 25,
        "unit_price": 1.25,
        "is_available": True
    },

    {
        "supplier": "Fresh Fields Farm",
        "product_name": "Iceberg Lettuce",
        "is_match": False,
        "quantity_available": 2000,
        "estimated_lead_time_hours": 1,
        "distance_miles": 10,
        "unit_price": 1.00,
        "is_available": True
    },

    {
        "supplier": "Sunrise Produce",
        "product_name": "Romaine Hearts 3-Pack",
        "is_match": True,
        "quantity_available": 1200,
        "estimated_lead_time_hours": 4,
        "distance_miles": 40,
        "unit_price": 1.15,
        "is_available": True
    }
]


quantity_needed = 800


ranked = rank_replacements(
    candidates,
    quantity_needed
)


print("\nREPLACEMENT RANKING")
print("------------------------------")

for index, candidate in enumerate(ranked, start=1):

    print(
        f"{index}. {candidate['supplier']}"
    )

    print(
        f"   Product: {candidate['product_name']}"
    )

    print(
        f"   Stock: {candidate['quantity_available']}"
    )

    print(
        f"   ETA: {candidate['estimated_lead_time_hours']} hours"
    )

    print(
        f"   Distance: {candidate['distance_miles']} miles"
    )

    print(
        f"   Price: ${candidate['unit_price']}"
    )

    print()

# Product that was recalled
recalled_product = {
    "id": 1,
    "name": "Organic Romaine Hearts",
    "category": "Leafy Greens",
    "description": "Organic romaine lettuce hearts",
    "variety": "Romaine",
    "package_size": "18 oz"
}


# Temporary supplier data
# Later this will come from your database.
candidates = [
    {
        "product_id": 2,
        "product_name": "Organic Romaine Lettuce Hearts",
        "category": "Leafy Greens",
        "description": "Organic romaine lettuce hearts",
        "variety": "Romaine",
        "package_size": "18 oz",

        "supplier": "Green Valley Farms",
        "quantity_available": 1000,
        "unit_price": 1.25,
        "estimated_lead_time_hours": 2,
        "distance_miles": 25,
        "is_available": True
    },

    {
        "product_id": 3,
        "product_name": "Iceberg Lettuce",
        "category": "Leafy Greens",
        "description": "Fresh iceberg lettuce",
        "variety": "Iceberg",
        "package_size": "18 oz",

        "supplier": "Fresh Fields Farm",
        "quantity_available": 2000,
        "unit_price": 1.00,
        "estimated_lead_time_hours": 1,
        "distance_miles": 10,
        "is_available": True
    },

    {
        "product_id": 4,
        "product_name": "Romaine Hearts 3-Pack",
        "category": "Leafy Greens",
        "description": "Fresh romaine lettuce hearts",
        "variety": "Romaine",
        "package_size": "18 oz",

        "supplier": "Sunrise Produce",
        "quantity_available": 1200,
        "unit_price": 1.15,
        "estimated_lead_time_hours": 4,
        "distance_miles": 40,
        "is_available": True
    }
]


quantity_needed = 800


result = find_replacements(
    recalled_product,
    candidates,
    quantity_needed
)


print("\n================================")
print("REPLACEMENT RECOMMENDATION")
print("================================")

recommended = result["recommended"]

if recommended is None:
    print(result["message"])

else:
    print("\nBEST OPTION")
    print("------------------------")

    print(f"Supplier: {recommended['supplier']}")
    print(f"Product: {recommended['product_name']}")
    print(f"Available: {recommended['quantity_available']} units")
    print(f"Required: {quantity_needed} units")
    print(f"ETA: {recommended['estimated_lead_time_hours']} hours")
    print(f"Distance: {recommended['distance_miles']} miles")
    print(f"Price: ${recommended['unit_price']}/unit")
    print(f"AI reason: {recommended['match_reason']}")

    print("\nALTERNATIVES")
    print("------------------------")

    for alternative in result["alternatives"]:
        print(f"Supplier: {alternative['supplier']}")
        print(f"Product: {alternative['product_name']}")
        print(f"Available: {alternative['quantity_available']} units")
        print(f"ETA: {alternative['estimated_lead_time_hours']} hours")
        print()