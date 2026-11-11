"""Fortograph plugin — remote selective-encryption redaction for Hermes."""

import logging

from . import schemas, tools

logger = logging.getLogger(__name__)


def register(ctx):
    """Wire Fortograph tool schemas to their handlers."""
    tools.configure(ctx)

    ctx.register_tool(
        name="fortograph_status",
        toolset="fortograph",
        schema=schemas.STATUS,
        handler=tools.fortograph_status,
        description="Check the remote Fortograph API is reachable",
    )
    ctx.register_tool(
        name="fortograph_redact",
        toolset="fortograph",
        schema=schemas.REDACT,
        handler=tools.fortograph_redact,
        description="Redact image regions via the Fortograph API",
    )
    ctx.register_tool(
        name="fortograph_unredact",
        toolset="fortograph",
        schema=schemas.UNREDACT,
        handler=tools.fortograph_unredact,
        description="Restore Fortograph-redacted image regions",
    )

    logger.debug("fortograph plugin registered 3 tools")
