"""Script to get pipeline definition as JSON."""
import argparse
import json
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Get SageMaker Pipeline definition")
    parser.add_argument("--module-name", type=str, required=True,
                        help="Python module containing get_pipeline function")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print pipeline definition without creating")
    parser.add_argument("--output", type=str, default=None,
                        help="Output file for pipeline definition JSON")
    parser.add_argument("--kwargs", type=str, default=None,
                        help="JSON string of kwargs for get_pipeline")
    
    args = parser.parse_args()
    
    try:
        # Import the module dynamically
        module = __import__(args.module_name, fromlist=["get_pipeline"])
        get_pipeline = getattr(module, "get_pipeline")
    except Exception as e:
        logger.error(f"Failed to import module {args.module_name}: {e}")
        sys.exit(1)
    
    # Parse kwargs
    kwargs = json.loads(args.kwargs) if args.kwargs else {}
    
    # Get the pipeline
    logger.info(f"Getting pipeline from {args.module_name}")
    pipeline = get_pipeline(**kwargs)
    
    # Get pipeline definition
    definition = json.loads(pipeline.definition())
    
    if args.dry_run:
        print(json.dumps(definition, indent=2))
    elif args.output:
        with open(args.output, 'w') as f:
            json.dump(definition, f, indent=2)
        logger.info(f"Pipeline definition written to {args.output}")
    else:
        print(json.dumps(definition, indent=2))
    
    logger.info(f"Pipeline '{pipeline.name}' has {len(definition.get('Steps', []))} steps")


if __name__ == "__main__":
    main()
