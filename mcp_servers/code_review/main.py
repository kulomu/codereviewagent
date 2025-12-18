import sys
import json
import asyncio
from pathlib import Path
import argparse
from typing import List, Optional
from mcp.types import Tool

from .instance import airc
from . import tools, prompts
from .config import define_mcp

@airc.config()
async def get_config() -> dict:
    config = define_mcp()
    if isinstance(config, str):
        # Prevent accidental string return that breaks MCP protocol
        raise TypeError("define_mcp() must return a dict, not a string")
    return config

def run():    
    airc.run(transport="stdio")

if __name__ == "__main__":
    if "--dump-config" in sys.argv:
        try:
            config = asyncio.run(airc.get_config())
            if not isinstance(config, dict):
                raise ValueError("Returned config must be a dict")
            print(json.dumps(config))
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            sys.exit(1)
    else:
        run()
