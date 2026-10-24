from backend.ai_automation.replacement_engine import find_replacements


# ============================================================
# TEST DATA
# ============================================================

# Product that has been recalled
recalled_product = {
    "id": 1,
    "name": "Organic Romaine Hearts",
    "category": "Leafy Greens",
    "description": "Organic romaine lettuce hearts",
    "variety": "Romaine",
    "package_size": "18 oz"
}


# Temporary supplier data
# Later this will be replaced by data from the database.
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


# Number of replacement units required
quantity_needed = 800


# ============================================================
# RUN COMPLETE REPLACEMENT ENGINE
# ============================================================

result = find_replacements(
    recalled_product,
    candidates,
    quantity_needed
)


# ============================================================
# DISPLAY RESULT
# ============================================================

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
    print(
        f"ETA: "
        f"{recommended['estimated_lead_time_hours']} hours"
    )
    print(
        f"Distance: "
        f"{recommended['distance_miles']} miles"
    )
    print(
        f"Price: "
        f"${recommended['unit_price']}/unit"
    )
    print(
        f"AI reason: "
        f"{recommended['match_reason']}"
    )


    print("\nALTERNATIVES")
    print("------------------------")

    if not result["alternatives"]:
        print("No other eligible alternatives.")

    else:

        for alternative in result["alternatives"]:

            print(
                f"\nSupplier: "
                f"{alternative['supplier']}"
            )

            print(
                f"Product: "
                f"{alternative['product_name']}"
            )

            print(
                f"Available: "
                f"{alternative['quantity_available']} units"
            )

            print(
                f"ETA: "
                f"{alternative['estimated_lead_time_hours']} hours"
            )

            print(
                f"Distance: "
                f"{alternative['distance_miles']} miles"
            )

            print(
                f"Price: "
                f"${alternative['unit_price']}/unit"
            )

            print(
                f"AI reason: "
                f"{alternative['match_reason']}"
            )