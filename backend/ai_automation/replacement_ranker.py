def rank_replacements(candidates, quantity_needed):
    """
    Filter and rank potential replacement suppliers.

    Requirements:
    - Product must be an AI-approved match
    - Supplier must currently be available
    - Supplier must have enough inventory

    Ranking priority:
    1. Shortest lead time
    2. Shortest distance
    3. Lowest price
    """

    eligible = []

    for candidate in candidates:

        # Product must be approved by product_matcher
        if not candidate.get("is_match", False):
            continue

        # Supplier must currently be available
        if not candidate.get("is_available", True):
            continue

        # Supplier must have enough inventory
        if candidate.get("quantity_available", 0) < quantity_needed:
            continue

        eligible.append(candidate)

    # Rank eligible suppliers
    eligible.sort(
        key=lambda candidate: (
            candidate.get(
                "estimated_lead_time_hours",
                float("inf")
            ),
            candidate.get(
                "distance_miles",
                float("inf")
            ),
            candidate.get(
                "unit_price",
                float("inf")
            )
        )
    )

    return eligible