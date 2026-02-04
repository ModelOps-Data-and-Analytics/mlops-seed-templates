"""Lambda function handler for processing orders."""
import json
import logging
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """Handle requests from Bedrock Agent to process orders.
    
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
    request_body = event.get('requestBody', {})
    
    # Parse request body
    body_content = request_body.get('content', {})
    json_body = body_content.get('application/json', {})
    properties = json_body.get('properties', [])
    
    # Extract properties into dict
    params = {}
    for prop in properties:
        params[prop['name']] = prop['value']
    
    action = params.get('action', 'status')
    order_id = params.get('orderId')
    customer_id = params.get('customerId')
    
    logger.info(f"Processing order action: {action}")
    
    # Handle different actions
    if action == 'create':
        response_data = create_order(customer_id, params)
    elif action == 'cancel':
        response_data = cancel_order(order_id)
    elif action == 'modify':
        response_data = modify_order(order_id, params)
    else:  # status
        response_data = get_order_status(order_id)
    
    # Format response for Bedrock Agent
    response_body = {
        "application/json": {
            "body": json.dumps(response_data)
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


def create_order(customer_id: str, params: dict) -> dict:
    """Create a new order.
    
    Args:
        customer_id: Customer ID
        params: Order parameters
        
    Returns:
        Order creation response
    """
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    estimated_delivery = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
    
    return {
        "success": True,
        "orderId": order_id,
        "status": "Processing",
        "message": f"Order {order_id} created successfully for customer {customer_id}",
        "estimatedDelivery": estimated_delivery
    }


def cancel_order(order_id: str) -> dict:
    """Cancel an order.
    
    Args:
        order_id: Order ID to cancel
        
    Returns:
        Cancellation response
    """
    return {
        "success": True,
        "orderId": order_id,
        "status": "Cancelled",
        "message": f"Order {order_id} has been cancelled. Refund will be processed within 3-5 business days."
    }


def modify_order(order_id: str, params: dict) -> dict:
    """Modify an existing order.
    
    Args:
        order_id: Order ID to modify
        params: Modification parameters
        
    Returns:
        Modification response
    """
    return {
        "success": True,
        "orderId": order_id,
        "status": "Modified",
        "message": f"Order {order_id} has been updated with your changes."
    }


def get_order_status(order_id: str) -> dict:
    """Get order status.
    
    Args:
        order_id: Order ID to check
        
    Returns:
        Order status response
    """
    # Mock order data
    return {
        "orderId": order_id or "ORD-12345",
        "status": "In Transit",
        "lastUpdate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "estimatedDelivery": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
        "trackingNumber": "1Z999AA10123456784",
        "carrier": "UPS",
        "items": [
            {"productId": "PROD-001", "name": "Widget Pro", "quantity": 2}
        ]
    }
