"""Unified Lambda handler for all Bedrock Agent actions."""
import json
import logging
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """Route requests to appropriate action handlers.

    Args:
        event: Lambda event from Bedrock Agent
        context: Lambda context

    Returns:
        Response for Bedrock Agent
    """
    logger.info(f"Received event: {json.dumps(event)}")

    # Extract routing info
    action_group = event.get('actionGroup', '')
    api_path = event.get('apiPath', '')
    http_method = event.get('httpMethod', '')

    # Route to appropriate handler
    if api_path == '/getCustomerInfo':
        response_data = handle_get_customer_info(event)
    elif api_path == '/processOrder':
        response_data = handle_process_order(event)
    elif api_path == '/checkInventory':
        response_data = handle_check_inventory(event)
    elif api_path == '/initiateReturn':
        response_data = handle_initiate_return(event)
    else:
        response_data = {"error": f"Unknown API path: {api_path}"}

    # Format response for Bedrock Agent
    response_body = {
        "application/json": {
            "body": json.dumps(response_data)
        }
    }

    api_response = {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": action_group,
            "apiPath": api_path,
            "httpMethod": http_method,
            "httpStatusCode": 200,
            "responseBody": response_body
        }
    }

    logger.info(f"Returning response: {json.dumps(api_response)}")
    return api_response


def get_parameters(event):
    """Extract parameters from GET request."""
    params = {}
    for param in event.get('parameters', []):
        params[param['name']] = param['value']
    return params


def get_request_body(event):
    """Extract body from POST request."""
    request_body = event.get('requestBody', {})
    body_content = request_body.get('content', {})
    json_body = body_content.get('application/json', {})

    params = {}
    for prop in json_body.get('properties', []):
        params[prop['name']] = prop['value']
    return params


# =============================================================================
# Handler: Get Customer Info
# =============================================================================
def handle_get_customer_info(event):
    """Get customer information."""
    params = get_parameters(event)
    customer_id = params.get('customerId')
    email = params.get('email')

    logger.info(f"Looking up customer - ID: {customer_id}, Email: {email}")

    # Mock customer data
    return {
        "customerId": customer_id or "CUST-12345",
        "name": "John Doe",
        "email": email or "john.doe@example.com",
        "accountStatus": "active",
        "memberSince": "2022-03-15",
        "loyaltyTier": "Gold",
        "recentOrders": [
            {"orderId": "ORD-98765", "date": "2024-01-15", "status": "Delivered", "total": 149.99},
            {"orderId": "ORD-98764", "date": "2024-01-10", "status": "Delivered", "total": 79.50}
        ],
        "preferences": {"notifications": True, "newsletter": True}
    }


# =============================================================================
# Handler: Process Order
# =============================================================================
def handle_process_order(event):
    """Process order actions (create, modify, cancel, status)."""
    params = get_request_body(event)
    action = params.get('action', 'status')
    order_id = params.get('orderId')
    customer_id = params.get('customerId')

    logger.info(f"Processing order action: {action}")

    if action == 'create':
        return {
            "success": True,
            "orderId": f"ORD-{uuid.uuid4().hex[:8].upper()}",
            "status": "Processing",
            "message": f"Order created successfully for customer {customer_id}",
            "estimatedDelivery": (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        }
    elif action == 'cancel':
        return {
            "success": True,
            "orderId": order_id,
            "status": "Cancelled",
            "message": f"Order {order_id} has been cancelled. Refund will be processed within 3-5 business days."
        }
    elif action == 'modify':
        return {
            "success": True,
            "orderId": order_id,
            "status": "Modified",
            "message": f"Order {order_id} has been updated with your changes."
        }
    else:  # status
        return {
            "orderId": order_id or "ORD-12345",
            "status": "In Transit",
            "lastUpdate": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "estimatedDelivery": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
            "trackingNumber": "1Z999AA10123456784",
            "carrier": "UPS"
        }


# =============================================================================
# Handler: Check Inventory
# =============================================================================
def handle_check_inventory(event):
    """Check product inventory."""
    params = get_parameters(event)
    product_id = params.get('productId', 'PROD-001')
    warehouse_id = params.get('warehouseId')

    logger.info(f"Checking inventory for product: {product_id}")

    return {
        "productId": product_id,
        "productName": "Widget Pro",
        "inStock": True,
        "quantity": 150,
        "warehouses": [
            {"warehouseId": "WH-001", "location": "New York", "quantity": 75},
            {"warehouseId": "WH-002", "location": "Los Angeles", "quantity": 75}
        ],
        "restockDate": None
    }


# =============================================================================
# Handler: Initiate Return
# =============================================================================
def handle_initiate_return(event):
    """Initiate product return."""
    params = get_request_body(event)
    order_id = params.get('orderId')
    reason = params.get('reason', 'other')
    preferred_resolution = params.get('preferredResolution', 'refund')

    logger.info(f"Initiating return for order: {order_id}, reason: {reason}")

    return_id = f"RET-{uuid.uuid4().hex[:8].upper()}"

    return {
        "success": True,
        "returnId": return_id,
        "returnLabel": f"https://returns.example.com/label/{return_id}",
        "instructions": "Please print the return label and attach it to your package. Drop off at any UPS location.",
        "estimatedRefundDate": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    }
