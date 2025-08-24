import re

from google.genai import types
from pydantic_ai import RunContext, Tool as PydanticTool
from pydantic_ai.tools import ToolDefinition
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Tool as MCPTool
from contextlib import AsyncExitStack
from dotenv import load_dotenv
from typing import Any, List, Dict
import asyncio
import logging
import shutil
import json
import os

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

class ToolMCPToGeminiConvertor:

    @staticmethod
    def simplify_description(description: str) -> str:
        """
        Simplifies a Python docstring into a concise, one-line description.
        It takes the first non-empty line and removes extra whitespace and docstring artifacts.
        """
        # Remove standard docstring sections like Args:, Returns:, etc.
        clean_desc = re.split(r'\n\s*(Args|Returns|Raises):', description, 1)[0]

        # Take the first meaningful line from the potentially multi-line description
        lines = [line.strip() for line in clean_desc.strip().split('\n')]
        first_line = next((line for line in lines if line), "")

        # Consolidate all whitespace into single spaces
        return re.sub(r'\s+', ' ', first_line).strip()

    @staticmethod
    def convert_mcp_objects_to_gemini_tool_config(
            mcp_tools: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        Converts a list of MCP tool objects into the Gemini function calling format,
        correctly handling array types.

        Args:
            mcp_tools: A list of objects with .name, .description, and .inputSchema attributes.

        Returns:
            A dictionary structured for Gemini's `tool_config`.
        """
        gemini_tool_config = []

        for tool in mcp_tools:
            tool_name = tool.name
            tool_description = tool.description
            input_schema_dict = tool.inputSchema

            gemini_properties = {}
            source_properties = input_schema_dict.get('properties', {})

            for param_name, param_details in source_properties.items():
                # Create a clean description, adding default value if present
                prop_description = param_details.get('description', '')
                if 'default' in param_details:
                    prop_description += f" (Default: {param_details['default']})"

                param_type = param_details.get('type') if param_details.get('type') else 'string'

                if param_type == 'array':
                    # For arrays, we must define the type of items they contain.
                    # Assuming 'string' as a default if not specified in MCP schema.
                    gemini_properties[param_name] = {
                        'type': 'array',
                        'description': prop_description.strip(),
                        'items': {
                            'type': 'string'  # Assuming array of strings
                        }
                    }
                else:
                    # Original logic for simple types like string, integer, boolean.
                    gemini_properties[param_name] = {
                        'type': param_type,
                        'description': prop_description.strip()
                    }

            function_declaration = {
                "name": tool_name,
                "description": ToolMCPToGeminiConvertor.simplify_description(tool_description),
                "parameters": {
                    "type": "object",
                    "properties": gemini_properties,
                    "required": input_schema_dict.get('required', [])
                }
            }

            gemini_tool_config.append(function_declaration)

        return gemini_tool_config


class GeminiMCPClient:
    """Manages connections to one or more MCP servers based on mcp_config.json"""

    def __init__(self, config_path:str) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config_path = config_path
        self.servers: List[Any] = []
        self.config: dict[str, Any] = {}
        self.tools: List[Any] = []
        self.tool_to_session_map: Dict[str: Any] = {}
        self.exit_stack = AsyncExitStack()

    async def launch_server(self, server_name: str, server_config:Dict[str, Any]):
        """
        Launches a single MCP server and returns its session and discovered tools.
        """
        print(f"[Manager] Starting MCP server: {server_name}...")
        print(f"[Manager] Starting MCP server: {server_config['args']}...")
        server_params = StdioServerParameters(
            command=server_config['command'],
            args=server_config['args'],
            env=server_config['env'] if 'env' in server_config else os.environ
        )

        # Note: The stdio_client context needs to be managed carefully.
        # For a robust solution, you might manage these connections in a class.
        # This is a simplified example.

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        read, write = stdio_transport
        session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await session.initialize()

        discovered_tools = await session.list_tools()

        # Store which server a tool belongs to by prefixing or using a dictionary
        # Here, we'll just return the session and tools together.
        self.logger.info(f"Init server {server_name}")
        return {
            "server_name": server_name,
            "session": session,
            "tools": discovered_tools.tools,
            "gemini_tools": ToolMCPToGeminiConvertor.convert_mcp_objects_to_gemini_tool_config(discovered_tools.tools)
        }

    async def load_servers(self, config_path: str) -> None:
        """Load server configuration from a JSON file (typically mcp_config.json)
        and creates an instance of each server (no active connection until 'start' though).

        Args:
            config_path: Path to the JSON configuration file.
        """
        with open(config_path, "r") as config_file:
            self.config = json.load(config_file)

        self.servers = [await self.launch_server(name, config) for name, config in self.config["mcpServers"].items()]


    async def launch_all(self) -> List[Any]:

        self.tools = []
        await self.load_servers(self.config_path)
        gemini_tools = []
        for server in self.servers:
            session = server['session']
            for tool in server['tools']:
                # Important: Ensure tool names are unique across all servers!
                # If not, you may need to add a prefix, e.g., f"{server['server_name']}_{tool.name}"
                # and adjust the name in the gemini_tool_config as well.
                if tool.name in self.tool_to_session_map:
                    self.logger.warning(f"Warning: Duplicate tool name '{tool.name}' found. The last one will be used.")

                self.tool_to_session_map[tool.name] = session
            gemini_tools += server['gemini_tools']
        return gemini_tools

    async def tool_call(self, tool_name, tool_args) -> str:
        if tool_name in self.tool_to_session_map:
            # Find the correct session for the requested tool
            target_session = self.tool_to_session_map[tool_name]

            print(f"[Manager] Routing call for '{tool_name}' to its server.")

            # Call the tool using the correct session
            tool_result = await target_session.call_tool(tool_name, tool_args)
            return tool_result.content[0].text

            # part = types.Part.from_function_response(
            #     name=tool_name,
            #     response={"result": tool_result.content[0].text}
            # )
            # # part2 = types.Part.from_text("TTTT") ## text('Please tell me the result')
            # call_content = types.Content(
            #     role="tool", parts=[part]
            # )
            # return call_content
        else:
            raise KeyError(f"Error: Tool '{tool_name}' not found in any active MCP server.")

    async def cleanup_servers(self) -> None:
        """Clean up all servers properly."""
        self.logger.info("Stopping all servers...")
        await self.exit_stack.aclose()



