"""Evaluate Bedrock Agent with test cases."""
import argparse
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from typing import List, Dict, Any

# Install boto3 with Bedrock support (container may have old version)
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "boto3>=1.34.0", "botocore>=1.34.0"])

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_test_cases(test_cases_dir: str) -> List[Dict[str, Any]]:
    """Load test cases from directory.
    
    Args:
        test_cases_dir: Directory containing test case files
        
    Returns:
        List of test cases
    """
    test_cases = []
    
    # Try to load test_cases.json
    test_file = os.path.join(test_cases_dir, 'test_cases.json')
    if os.path.exists(test_file):
        with open(test_file, 'r') as f:
            test_cases = json.load(f)
        logger.info(f"Loaded {len(test_cases)} test cases from {test_file}")
    else:
        # Use default test cases
        test_cases = get_default_test_cases()
        logger.info(f"Using {len(test_cases)} default test cases")
    
    return test_cases


def get_default_test_cases() -> List[Dict[str, Any]]:
    """Get default test cases for agent evaluation.
    
    Returns:
        List of default test cases
    """
    return [
        {
            "name": "greeting",
            "input": "Hello, I need help with my order",
            "expected_keywords": ["help", "assist", "order"],
            "expected_behavior": "greeting_response"
        },
        {
            "name": "order_status",
            "input": "What is the status of my order #12345?",
            "expected_keywords": ["order", "status"],
            "expected_behavior": "should_use_action"
        },
        {
            "name": "return_policy",
            "input": "What is your return policy?",
            "expected_keywords": ["return", "policy", "days"],
            "expected_behavior": "should_search_kb"
        },
        {
            "name": "product_inquiry",
            "input": "Tell me about your premium widget product",
            "expected_keywords": ["product", "widget"],
            "expected_behavior": "should_search_kb"
        },
        {
            "name": "refund_request",
            "input": "I want to request a refund for order #98765",
            "expected_keywords": ["refund", "return", "process"],
            "expected_behavior": "should_use_action"
        }
    ]


def get_agent_by_name(bedrock_agent_client, agent_name: str) -> dict | None:
    """Get agent by name.
    
    Args:
        bedrock_agent_client: Bedrock Agent client
        agent_name: Agent name
        
    Returns:
        Agent details if found
    """
    try:
        response = bedrock_agent_client.list_agents()
        for agent in response.get('agentSummaries', []):
            if agent['agentName'] == agent_name:
                return agent
    except ClientError as e:
        logger.error(f"Error listing agents: {e}")
    return None


def get_agent_alias(bedrock_agent_client, agent_id: str, alias_name: str = "staging") -> dict | None:
    """Get agent alias by name.
    
    Args:
        bedrock_agent_client: Bedrock Agent client
        agent_id: Agent ID
        alias_name: Alias name to find
        
    Returns:
        Alias details if found
    """
    try:
        response = bedrock_agent_client.list_agent_aliases(agentId=agent_id)
        for alias in response.get('agentAliasSummaries', []):
            if alias['agentAliasName'] == alias_name:
                return alias
    except ClientError as e:
        logger.error(f"Error listing aliases: {e}")
    return None


def invoke_agent(
    bedrock_runtime,
    agent_id: str,
    agent_alias_id: str,
    prompt: str,
    session_id: str
) -> str:
    """Invoke the agent and get response.
    
    Args:
        bedrock_runtime: Bedrock Agent Runtime client
        agent_id: Agent ID
        agent_alias_id: Agent alias ID
        prompt: Input prompt
        session_id: Session ID
        
    Returns:
        Agent response text
    """
    try:
        response = bedrock_runtime.invoke_agent(
            agentId=agent_id,
            agentAliasId=agent_alias_id,
            sessionId=session_id,
            inputText=prompt
        )
        
        # Collect response chunks
        full_response = ""
        for event in response.get('completion', []):
            if 'chunk' in event:
                chunk = event['chunk']
                if 'bytes' in chunk:
                    full_response += chunk['bytes'].decode('utf-8')
        
        return full_response
        
    except Exception as e:
        logger.error(f"Error invoking agent: {e}")
        return ""


def evaluate_response(response: str, test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate agent response against test case.
    
    Args:
        response: Agent response
        test_case: Test case with expected results
        
    Returns:
        Evaluation result
    """
    result = {
        "test_name": test_case.get("name", "unknown"),
        "passed": False,
        "keywords_found": [],
        "keywords_missing": [],
        "response_length": len(response)
    }
    
    expected_keywords = test_case.get("expected_keywords", [])
    response_lower = response.lower()
    
    for keyword in expected_keywords:
        if keyword.lower() in response_lower:
            result["keywords_found"].append(keyword)
        else:
            result["keywords_missing"].append(keyword)
    
    # Pass if at least 50% of keywords found (or no keywords expected)
    if not expected_keywords:
        result["passed"] = len(response) > 0
    else:
        keyword_ratio = len(result["keywords_found"]) / len(expected_keywords)
        result["passed"] = keyword_ratio >= 0.5
    
    return result


def run_evaluation(
    agent_id: str,
    agent_alias_id: str,
    test_cases: List[Dict[str, Any]],
    region: str
) -> Dict[str, Any]:
    """Run full evaluation suite.
    
    Args:
        agent_id: Agent ID
        agent_alias_id: Agent alias ID
        test_cases: List of test cases
        region: AWS region
        
    Returns:
        Evaluation results
    """
    bedrock_runtime = boto3.client('bedrock-agent-runtime', region_name=region)
    
    results = {
        "total": len(test_cases),
        "passed": 0,
        "failed": 0,
        "details": []
    }
    
    for i, test_case in enumerate(test_cases):
        logger.info(f"Running test {i+1}/{len(test_cases)}: {test_case.get('name', 'unknown')}")
        
        session_id = f"eval-{uuid.uuid4().hex[:8]}"
        
        try:
            # Invoke agent
            response = invoke_agent(
                bedrock_runtime,
                agent_id,
                agent_alias_id,
                test_case["input"],
                session_id
            )
            
            # Evaluate response
            eval_result = evaluate_response(response, test_case)
            eval_result["input"] = test_case["input"]
            eval_result["response_preview"] = response[:200] if response else ""
            
            if eval_result["passed"]:
                results["passed"] += 1
                logger.info(f"  ✅ PASSED")
            else:
                results["failed"] += 1
                logger.info(f"  ❌ FAILED - Missing keywords: {eval_result['keywords_missing']}")
            
            results["details"].append(eval_result)
            
        except Exception as e:
            logger.error(f"  ❌ ERROR: {e}")
            results["failed"] += 1
            results["details"].append({
                "test_name": test_case.get("name", "unknown"),
                "passed": False,
                "error": str(e)
            })
        
        # Small delay between tests
        time.sleep(1)
    
    # Calculate success rate
    results["success_rate"] = results["passed"] / results["total"] if results["total"] > 0 else 0
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate Bedrock Agent")
    parser.add_argument("--agent-name", type=str, required=True)
    parser.add_argument("--region", type=str, required=True)
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument("--alias-name", type=str, default="staging")
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Evaluating Bedrock Agent")
    logger.info("=" * 60)
    
    bedrock_agent = boto3.client('bedrock-agent', region_name=args.region)
    
    # Get agent
    agent = get_agent_by_name(bedrock_agent, args.agent_name)
    if not agent:
        logger.error(f"Agent not found: {args.agent_name}")
        sys.exit(1)
    
    agent_id = agent['agentId']
    logger.info(f"Found agent: {agent_id}")
    
    # Get alias
    alias = get_agent_alias(bedrock_agent, agent_id, args.alias_name)
    if not alias:
        logger.error(f"Alias not found: {args.alias_name}")
        sys.exit(1)
    
    agent_alias_id = alias['agentAliasId']
    logger.info(f"Found alias: {agent_alias_id}")
    
    # Load test cases
    test_cases_dir = "/opt/ml/processing/input/test_cases"
    test_cases = load_test_cases(test_cases_dir)
    
    # Run evaluation
    results = run_evaluation(agent_id, agent_alias_id, test_cases, args.region)
    
    # Add metadata
    results["agent_id"] = agent_id
    results["agent_alias_id"] = agent_alias_id
    results["threshold"] = args.threshold
    results["threshold_met"] = results["success_rate"] >= args.threshold
    
    # Create metrics structure for pipeline condition
    output = {
        "metrics": {
            "success_rate": results["success_rate"],
            "total_tests": results["total"],
            "passed_tests": results["passed"],
            "failed_tests": results["failed"]
        },
        "details": results["details"],
        "agent_id": agent_id,
        "agent_alias_id": agent_alias_id,
        "threshold": args.threshold,
        "threshold_met": results["threshold_met"]
    }
    
    # Write output
    output_dir = "/opt/ml/processing/output"
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, "evaluation.json")
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    logger.info(f"Evaluation output written to {output_path}")
    logger.info("=" * 60)
    logger.info(f"Evaluation Results:")
    logger.info(f"  Total tests: {results['total']}")
    logger.info(f"  Passed: {results['passed']}")
    logger.info(f"  Failed: {results['failed']}")
    logger.info(f"  Success rate: {results['success_rate']:.2%}")
    logger.info(f"  Threshold: {args.threshold:.2%}")
    logger.info(f"  Threshold met: {results['threshold_met']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
