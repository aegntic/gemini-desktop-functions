"""
Tool manager module.

This module handles the lifecycle of function tools, including loading,
saving, validating, and managing tool definitions.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

logger = logging.getLogger(__name__)

class ToolManager:
    """
    Manager for function tools/schemas.
    
    This class handles loading, saving, validating, and managing
    function tool definitions that can be used with the Gemini API.
    """
    
    def __init__(self, storage_dir: Union[str, Path] = None):
        """
        Initialize the ToolManager.
        
        Args:
            storage_dir: Optional directory for storing tool definitions.
                         If not provided, a default location will be used.
        """
        if storage_dir is None:
            # Use default location in user's home directory
            home_dir = Path.home()
            self._storage_dir = home_dir / ".gemini-function-manager" / "tools"
        else:
            self._storage_dir = Path(storage_dir)
        
        # Create directory if it doesn't exist
        os.makedirs(self._storage_dir, exist_ok=True)
        
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._enabled_tools: List[str] = []
        
        logger.debug(f"ToolManager initialized with storage directory: {self._storage_dir}")
        
        # Load existing tools
        self.load_tools()
    
    def load_tools(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all tool definitions from storage.
        
        Returns:
            Dict of tool definitions, keyed by tool ID.
        """
        try:
            self._tools = {}
            tool_files = list(self._storage_dir.glob("*.json"))
            
            for tool_file in tool_files:
                try:
                    with open(tool_file, "r") as f:
                        tool_data = json.load(f)
                    
                    tool_id = tool_data.get("id") or tool_file.stem
                    self._tools[tool_id] = tool_data
                    
                    # Check if tool is enabled
                    if tool_data.get("enabled", False):
                        self._enabled_tools.append(tool_id)
                    
                    logger.debug(f"Loaded tool: {tool_id}")
                
                except json.JSONDecodeError:
                    logger.error(f"Error parsing tool file: {tool_file}")
                except Exception as e:
                    logger.error(f"Error loading tool file {tool_file}: {e}")
            
            logger.info(f"Loaded {len(self._tools)} tools from storage")
            return self._tools
            
        except Exception as e:
            logger.error(f"Error loading tools: {e}")
            return {}
    
    def save_tool(self, tool: Dict[str, Any]) -> bool:
        """
        Save a tool definition to storage.
        
        Args:
            tool: The tool definition to save.
            
        Returns:
            bool: True if saved successfully, False otherwise.
        """
        try:
            tool_id = tool.get("id")
            if not tool_id:
                raise ValueError("Tool definition must have an 'id' field")
            
            # Validate tool schema
            if not self.validate_tool(tool):
                logger.error(f"Tool validation failed: {tool_id}")
                return False
            
            # Save to storage
            file_path = self._storage_dir / f"{tool_id}.json"
            with open(file_path, "w") as f:
                json.dump(tool, f, indent=2)
            
            # Update in-memory cache
            self._tools[tool_id] = tool
            
            # Update enabled status
            if tool.get("enabled", False) and tool_id not in self._enabled_tools:
                self._enabled_tools.append(tool_id)
            elif not tool.get("enabled", False) and tool_id in self._enabled_tools:
                self._enabled_tools.remove(tool_id)
            
            logger.info(f"Saved tool: {tool_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving tool: {e}")
            return False
    
    def delete_tool(self, tool_id: str) -> bool:
        """
        Delete a tool definition from storage.
        
        Args:
            tool_id: The ID of the tool to delete.
            
        Returns:
            bool: True if deleted successfully, False otherwise.
        """
        try:
            file_path = self._storage_dir / f"{tool_id}.json"
            
            if file_path.exists():
                file_path.unlink()
                
                # Remove from in-memory cache
                if tool_id in self._tools:
                    del self._tools[tool_id]
                
                # Remove from enabled tools
                if tool_id in self._enabled_tools:
                    self._enabled_tools.remove(tool_id)
                
                logger.info(f"Deleted tool: {tool_id}")
                return True
            else:
                logger.warning(f"Tool not found for deletion: {tool_id}")
                return False
            
        except Exception as e:
            logger.error(f"Error deleting tool {tool_id}: {e}")
            return False
    
    def get_tool(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a tool definition by ID.
        
        Args:
            tool_id: The ID of the tool to retrieve.
            
        Returns:
            The tool definition, or None if not found.
        """
        return self._tools.get(tool_id)
    
    def get_all_tools(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all tool definitions.
        
        Returns:
            Dict of all tool definitions, keyed by tool ID.
        """
        return self._tools
    
    def get_enabled_tools(self) -> List[Dict[str, Any]]:
        """
        Get all enabled tool definitions.
        
        Returns:
            List of enabled tool definitions.
        """
        return [self._tools[tool_id] for tool_id in self._enabled_tools if tool_id in self._tools]
    
    def enable_tool(self, tool_id: str) -> bool:
        """
        Enable a tool by ID.
        
        Args:
            tool_id: The ID of the tool to enable.
            
        Returns:
            bool: True if enabled successfully, False otherwise.
        """
        if tool_id in self._tools:
            if tool_id not in self._enabled_tools:
                self._enabled_tools.append(tool_id)
                
                # Update tool definition
                tool = self._tools[tool_id]
                tool["enabled"] = True
                
                # Save updated tool
                return self.save_tool(tool)
            return True  # Already enabled
        else:
            logger.warning(f"Cannot enable non-existent tool: {tool_id}")
            return False
    
    def disable_tool(self, tool_id: str) -> bool:
        """
        Disable a tool by ID.
        
        Args:
            tool_id: The ID of the tool to disable.
            
        Returns:
            bool: True if disabled successfully, False otherwise.
        """
        if tool_id in self._tools:
            if tool_id in self._enabled_tools:
                self._enabled_tools.remove(tool_id)
                
                # Update tool definition
                tool = self._tools[tool_id]
                tool["enabled"] = False
                
                # Save updated tool
                return self.save_tool(tool)
            return True  # Already disabled
        else:
            logger.warning(f"Cannot disable non-existent tool: {tool_id}")
            return False
    
    def validate_tool(self, tool: Dict[str, Any]) -> bool:
        """
        Validate a tool definition.
        
        Args:
            tool: The tool definition to validate.
            
        Returns:
            bool: True if valid, False otherwise.
        """
        try:
            # Basic validation
            required_fields = ["id", "name", "description"]
            for field in required_fields:
                if field not in tool:
                    logger.error(f"Tool is missing required field: {field}")
                    return False
            
            # Check for function schema
            if "function" not in tool:
                logger.error("Tool is missing 'function' definition")
                return False
            
            function = tool["function"]
            
            # Validate function schema
            if "name" not in function:
                logger.error("Function is missing 'name' field")
                return False
            
            if "description" not in function:
                logger.error("Function is missing 'description' field")
                return False
            
            # Check parameters schema
            if "parameters" in function:
                parameters = function["parameters"]
                
                # Validate parameters schema
                if not isinstance(parameters, dict):
                    logger.error("Function parameters must be an object")
                    return False
                
                # Check for required fields in parameters
                if "type" not in parameters:
                    logger.error("Parameters missing 'type' field")
                    return False
                
                # Additional validation could be performed here
            
            logger.debug(f"Tool validated successfully: {tool.get('id')}")
            return True
            
        except Exception as e:
            logger.error(f"Error validating tool: {e}")
            return False
    
    def create_tool_from_template(self, template_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Create a new tool from a template.
        
        Args:
            template_id: The ID of the template to use.
            **kwargs: Additional parameters to customize the template.
            
        Returns:
            The new tool definition, or None if creation failed.
        """
        # Placeholder implementation
        # In a real implementation, this would load templates from a separate store
        
        # Example template for a weather tool
        if template_id == "weather":
            tool = {
                "id": kwargs.get("id", "get_weather"),
                "name": kwargs.get("name", "Get Weather"),
                "description": kwargs.get("description", "Get weather information for a location"),
                "enabled": kwargs.get("enabled", False),
                "function": {
                    "name": "get_weather",
                    "description": "Get weather information for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The location to get weather for, e.g., 'London', 'New York', etc."
                            },
                            "units": {
                                "type": "string",
                                "enum": ["metric", "imperial"],
                                "description": "The units to use for temperature and wind speed"
                            }
                        },
                        "required": ["location"]
                    }
                }
            }
            return tool
        
        # Example template for a calculator tool
        elif template_id == "calculator":
            tool = {
                "id": kwargs.get("id", "calculate"),
                "name": kwargs.get("name", "Calculator"),
                "description": kwargs.get("description", "Perform mathematical calculations"),
                "enabled": kwargs.get("enabled", False),
                "function": {
                    "name": "calculate",
                    "description": "Perform a mathematical calculation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "The mathematical expression to evaluate, e.g., '2 + 2', 'sin(30)', etc."
                            }
                        },
                        "required": ["expression"]
                    }
                }
            }
            return tool
        
        else:
            logger.warning(f"Unknown template ID: {template_id}")
            return None
