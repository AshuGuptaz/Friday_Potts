"""
Tool registry — imports and registers all tool modules with the MCP server.
"""

from friday.tools import web, system, utils, network, tickets, macos, lights


def register_all_tools(mcp):
    web.register(mcp)
    system.register(mcp)
    utils.register(mcp)
    network.register(mcp)
    tickets.register(mcp)
    macos.register(mcp)
    lights.register(mcp)
