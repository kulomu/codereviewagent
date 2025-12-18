from mcp.server.fastmcp import FastMCP

class aircMCP(FastMCP):
    def __init__(self, name: str = "airc-mcp"):
        super().__init__(name)
        self._config_handler = None

    def config(self):
        def decorator(func):
            self._config_handler = func
            return func
        return decorator

    async def get_config(self) -> dict:
        if self._config_handler:
            return await self._config_handler()
        return {}
