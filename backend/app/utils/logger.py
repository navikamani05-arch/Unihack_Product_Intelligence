"""Environment-aware logging configuration."""
import logging
import os
import sys


logger = logging.getLogger("ai_product_intelligence")
_level_name = os.getenv("LOGGING_LEVEL", "INFO").upper()
_level = getattr(logging, _level_name, logging.INFO)
logger.setLevel(_level)
logger.propagate = False

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(_level)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
else:
    for handler in logger.handlers:
        handler.setLevel(_level)
