"""
Structured Logging Configuration

Uses structlog for structured, JSON-formatted logging.
Following official structlog documentation:
https://www.structlog.org/en/stable/
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor

from app.config.settings import settings


def setup_logging() -> None:
    """
    Configure structured logging for the application.
    
    Sets up:
    - Structured log formatting (JSON in production, colored console in dev)
    - Correlation ID tracking
    - Request/response logging preprocessors
    - Standard library logging integration
    """
    
    # Determine if we're in development or production
    is_dev = settings.app_env == "development"
    
    # Shared processors for all environments
    shared_processors: list[Processor] = [
        # Add timestamp
        structlog.processors.TimeStamper(fmt="iso"),
        # Add log level (compatible with all loggers)
        structlog.processors.add_log_level,
        # Add caller info (file, line, function)
        structlog.processors.CallsiteParameterAdder(
            [
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.LINENO,
                structlog.processors.CallsiteParameter.FUNC_NAME,
            ]
        ),
        # Process stack info
        structlog.processors.StackInfoRenderer(),
        # Format exceptions
        structlog.processors.format_exc_info,
        # Ensure event is a string
        structlog.processors.UnicodeDecoder(),
    ]
    
    if is_dev:
        # Development: Pretty console output with colors
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.rich_traceback,
            )
        ]
    else:
        # Production: JSON output for log aggregation
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if settings.debug else logging.INFO
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if settings.debug else logging.INFO,
    )
    
    # Set third-party loggers to WARNING to reduce noise
    for logger_name in ["httpx", "httpcore", "urllib3", "asyncio"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> Any:
    """
    Get a structured logger instance.
    
    Args:
        name: Optional logger name. If not provided, uses the calling module name.
        
    Returns:
        A structlog BoundLogger instance.
        
    Usage:
        logger = get_logger(__name__)
        logger.info("Processing article", article_id=article_id, source="BBC")
    """
    return structlog.get_logger(name)


# Create a default logger for quick access
logger = get_logger("app")
