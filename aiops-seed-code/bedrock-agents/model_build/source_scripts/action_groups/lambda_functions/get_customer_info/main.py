"""Lambda function handler for getting customer information."""
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """Handle requests from Bedrock Agent to get customer info.
    
    Args:
        event: Lambda event from Bedrock Agent
        context: Lambda context
        
    Returns:
        Response for Bedrock Agent
    """
    logger.info(f"Received event: {json.dumps(event)}")
    
    # Extract parameters from Bedrock Agent request
    action_group = event.get('actionGroup', '')
    api_path = event.get('apiPath', '')
    http_method = event.get('httpMethod', '')
    parameters = event.get('parameters', [])
    
    # Parse parameters
    params = {}
    for param in parameters:
        params[param['name']] = param['value']
    
    customer_id = params.get('customerId')
    email = params.get('email')
    
    logger.info(f"Looking up customer - ID: {customer_id}, Email: {email}")
    
    # Mock customer data - in production, this would query a database
    customer_data = {
        "customerId": customer_id or "CUST-12345",
        "name": "John Doe",
        "email": email or "john.doe@example.com",
        "accountStatus": "active",
        "memberSince": "2022-03-15",
        "loyaltyTier": "Gold",
        "recentOrders": [
            {
                "orderId": "ORD-98765",
                "date": "2024-01-15",
                "status": "Delivered",
                "total": 149.99
            },
            {
                "orderId": "ORD-98764",
                "date": "2024-01-10",
                "status": "Delivered",
                "total": 79.50
            }
        ],
        "preferences": {
            "notifications": True,
            "newsletter": True
        }
    }
    
    # Format response for Bedrock Agent
    response_body = {
        "application/json": {
            "body": json.dumps(customer_data)
        }
    }
    
    action_response = {
        "actionGroup": action_group,
        "apiPath": api_path,
        "httpMethod": http_method,
        "httpStatusCode": 200,
        "responseBody": response_body
    }
    
    api_response = {
        "messageVersion": "1.0",
        "response": action_response
    }
    
    logger.info(f"Returning response: {json.dumps(api_response)}")
    
    return api_response
