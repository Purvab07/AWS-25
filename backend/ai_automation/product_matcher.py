import json

try:
    from .bedrock_client import call_bedrock
except ImportError:
    from bedrock_client import call_bedrock


def match_products(recalled_product, candidates):
    """
    Uses Amazon Bedrock to determine which candidate products
    are potential replacements for a recalled product.
    """

    prompt = f"""
You are assisting a food supply-chain replacement system.

A food product has been recalled.

Your task is to determine which candidate products could be
reasonable potential replacements for the recalled product.

Consider:
- product type
- category
- variety
- package size
- relevant product characteristics

Do NOT consider:
- supplier distance
- inventory quantity
- price
- delivery time

Those factors will be handled separately by the backend.

Do NOT claim that any product is safe.
Only determine product compatibility based on the information provided.

RECALLED PRODUCT:
{json.dumps(recalled_product, indent=2)}

CANDIDATE PRODUCTS:
{json.dumps(candidates, indent=2)}

Return ONLY valid JSON.

Use exactly this format:

{{
    "matches": [
        {{
            "product_id": 2,
            "is_match": true,
            "reason": "Same product type, variety, and similar package size."
        }}
    ]
}}

Requirements:
- Include every candidate.
- product_id must match the candidate's id.
- is_match must be true or false.
- Keep each reason short.
"""

    response = call_bedrock(prompt)

    # Clean possible Markdown formatting
    response = response.strip()

    if response.startswith("```json"):
        response = response[7:]
    elif response.startswith("```"):
        response = response[3:]

    if response.endswith("```"):
        response = response[:-3]

    response = response.strip()

    try:
        return json.loads(response)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Bedrock returned invalid JSON:\n{response}"
        ) from error