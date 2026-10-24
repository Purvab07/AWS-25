from product_matcher import match_products


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