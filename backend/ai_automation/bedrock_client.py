import boto3

client = boto3.client(
    "bedrock-runtime",
    region_name="us-east-1"
)

def call_bedrock(prompt):
    response = client.converse(
        modelId="us.amazon.nova-2-lite-v1:0",
        messages=[
            {
                "role": "user",
                "content": [
                    {"text": prompt}
                ]
            }
        ],
        inferenceConfig={
            "temperature": 0.1,
            "maxTokens": 1000
        }
    )

    return response["output"]["message"]["content"][0]["text"]
