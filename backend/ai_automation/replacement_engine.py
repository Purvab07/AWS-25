try:
    from .product_matcher import match_products
    from .replacement_ranker import rank_replacements
except ImportError:
    from product_matcher import match_products
    from replacement_ranker import rank_replacements


def find_replacements(recalled_product, candidates, quantity_needed):
    """
    Runs the complete replacement recommendation workflow.

    1. Send candidate products to Bedrock for compatibility matching.
    2. Attach Bedrock's match results to each supplier.
    3. Filter/rank eligible suppliers.
    4. Return the best recommendation and alternatives.
    """

    # ---------------------------------------------------------
    # STEP 1: Prepare product information for Bedrock
    # ---------------------------------------------------------

    products_for_ai = []

    for candidate in candidates:
        product = {
            "id": candidate["product_id"],
            "name": candidate["product_name"],
            "category": candidate.get("category"),
            "description": candidate.get("description"),
            "variety": candidate.get("variety"),
            "package_size": candidate.get("package_size")
        }

        products_for_ai.append(product)


    # ---------------------------------------------------------
    # STEP 2: Remove duplicate products
    #
    # Multiple suppliers may sell the same product.
    # Bedrock only needs to evaluate that product once.
    # ---------------------------------------------------------

    unique_products = {
        product["id"]: product
        for product in products_for_ai
    }

    products_for_ai = list(unique_products.values())


    # ---------------------------------------------------------
    # STEP 3: Ask Bedrock which products are compatible
    # ---------------------------------------------------------

    ai_result = match_products(
        recalled_product,
        products_for_ai
    )


    # ---------------------------------------------------------
    # STEP 4: Convert AI results into a lookup dictionary
    #
    # Example:
    #
    # {
    #     2: {
    #         "is_match": True,
    #         "reason": "Same product type..."
    #     }
    # }
    # ---------------------------------------------------------

    match_lookup = {
        match["product_id"]: match
        for match in ai_result["matches"]
    }


    # ---------------------------------------------------------
    # STEP 5: Attach AI results to each supplier candidate
    # ---------------------------------------------------------

    evaluated_candidates = []

    for candidate in candidates:

        product_id = candidate["product_id"]

        ai_match = match_lookup.get(product_id)

        # If Bedrock didn't return this product,
        # don't consider it.
        if ai_match is None:
            continue

        candidate_copy = candidate.copy()

        candidate_copy["is_match"] = ai_match["is_match"]

        candidate_copy["match_reason"] = ai_match["reason"]

        evaluated_candidates.append(candidate_copy)


    # ---------------------------------------------------------
    # STEP 6: Rank the eligible suppliers
    # ---------------------------------------------------------

    ranked = rank_replacements(
        evaluated_candidates,
        quantity_needed
    )


    # ---------------------------------------------------------
    # STEP 7: Handle case where nothing qualifies
    # ---------------------------------------------------------

    if not ranked:
        return {
            "recommended": None,
            "alternatives": [],
            "message": "No eligible replacement supplier found."
        }


    # ---------------------------------------------------------
    # STEP 8: Return best supplier + alternatives
    # ---------------------------------------------------------

    return {
        "recommended": ranked[0],
        "alternatives": ranked[1:3],
        "message": "Replacement suppliers found."
    }