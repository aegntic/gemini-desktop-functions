"""
Main application entry point module.

This module initializes and coordinates all components of the application.
"""

import logging
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any

from .core.app_state import AppState
from .api_client.gemini_client import GeminiClient
from .tool_manager.tool_manager import ToolManager
from .persistence.database import Database
from .simulation_environment.sandbox import FunctionSandbox
from .local_executor.executor import LocalExecutor, ExecutionPermission
from .analytics_logging.analytics import AnalyticsManager, EventType

logger = logging.getLogger(__name__)

class Application:
    """
    Main application class that initializes and coordinates all components.
    
    This class serves as the central coordinating point for the application,
    initializing components, handling high-level operations, and providing
    a clean shutdown process.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the application with all required components.
        
        Args:
            config_path: Optional path to a configuration file.
        """
        logger.info("Initializing application")
        
        # Initialize components
        self.app_state = AppState()
        self.database = Database()
        self.tool_manager = ToolManager()
        self.api_client = GeminiClient()
        self.function_sandbox = FunctionSandbox()
        self.local_executor = LocalExecutor(
            default_permission=ExecutionPermission.NONE,
            sandbox_enabled=True,
            user_confirmation_callback=self._confirm_local_execution
        )
        self.analytics = AnalyticsManager()
        
        # Load settings from database
        self._load_settings()
        
        # Load API key if available
        self._load_api_key()
        
        # Load tools
        self._load_tools()
        
        logger.info("Application initialized successfully")
    
    def _load_settings(self):
        """Load application settings from the database."""
        logger.debug("Loading application settings")
        
        settings = self.database.get_all_settings()
        self.app_state.update_settings(settings)
        
        # Apply settings to components
        if "analytics_enabled" in settings:
            self.analytics.enabled = settings["analytics_enabled"]
        
        if "default_execution_permission" in settings:
            permission = ExecutionPermission.from_string(settings["default_execution_permission"])
            self.local_executor._default_permission = permission
        
        if "sandbox_enabled" in settings:
            self.local_executor._sandbox_enabled = settings["sandbox_enabled"]
        
        if "function_timeout" in settings:
            self.function_sandbox._timeout = settings["function_timeout"]
        
        logger.debug(f"Loaded {len(settings)} application settings")
    
    def _load_api_key(self):
        """Load Gemini API key from secure storage."""
        logger.debug("Loading API key")
        
        # In a real implementation, this would use keyring or another secure storage
        api_key = os.environ.get("GEMINI_API_KEY")
        
        if api_key:
            self.app_state.api_key = api_key
            self.app_state.is_authenticated = self.api_client.authenticate(api_key)
            
            if self.app_state.is_authenticated:
                logger.info("Successfully authenticated with Gemini API")
            else:
                logger.warning("Failed to authenticate with Gemini API")
        else:
            logger.warning("No API key found")
    
    def _load_tools(self):
        """Load and register tools from storage."""
        logger.debug("Loading tools")
        
        # Load tools from database
        tools = self.database.get_all_tool_definitions()
        
        # Register tools with the API client
        enabled_tools = [tool for tool in tools if tool.get("enabled", False)]
        self.api_client.register_tools(enabled_tools)
        
        logger.debug(f"Loaded {len(tools)} tools, {len(enabled_tools)} enabled")
    
    def _confirm_local_execution(self, function_name: str, arguments: Dict[str, Any]) -> bool:
        """
        Callback for confirming local function execution.
        
        In a real implementation, this would show a dialog to the user.
        
        Args:
            function_name: The name of the function to execute.
            arguments: The arguments to the function.
            
        Returns:
            True if execution is allowed, False otherwise.
        """
        logger.info(f"Request to execute local function: {function_name}")
        logger.info(f"Arguments: {arguments}")
        
        # In a real implementation, this would show a dialog to the user
        # For now, always deny execution
        return False
    
    async def send_message(self, message: str) -> Dict[str, Any]:
        """
        Send a message to the Gemini API.
        
        Args:
            message: The message to send.
            
        Returns:
            The response from the API.
        """
        logger.debug(f"Sending message to Gemini API")
        
        if not self.app_state.is_authenticated:
            logger.error("Cannot send message: Not authenticated")
            return {"error": "Not authenticated with Gemini API"}
        
        try:
            # Add message to history
            conversation_id = self.app_state.app_settings.get("current_conversation_id")
            if not conversation_id:
                # Create a new conversation
                conversation_id = self.database.create_conversation()
                self.app_state.app_settings["current_conversation_id"] = conversation_id
            
            # Log message to database
            message_id = self.database.add_message(conversation_id, "user", message)
            
            # Log analytics event
            self.analytics.log_event(EventType.MESSAGE_SENT, {"message_length": len(message)})
            
            # Add to state (in memory)
            self.app_state.add_message({
                "id": message_id,
                "type": "user",
                "content": message
            })
            
            # Send to API
            history = self.app_state.conversation_history
            response = await self.api_client.send_message(message, history)
            
            # Handle function calls in response
            if "function_calls" in response and response["function_calls"]:
                # Process function calls
                for function_call in response["function_calls"]:
                    # Log function call to database
                    function_name = function_call.get("name", "unknown")
                    arguments = function_call.get("arguments", {})
                    
                    call_id = self.database.add_function_call(message_id, function_name, arguments)
                    
                    # Log analytics event
                    self.analytics.log_function_call(function_name, arguments)
                    
                    # Handle function execution (not implemented in this example)
                    # In a real implementation, this would execute the function
                    # or prompt the user for the result
                    
                    # Update function call with result
                    result = {"result": "Function execution not implemented"}
                    self.database.update_function_result(call_id, result)
                    
                    # Send function response to API
                    function_response = {
                        "name": function_name,
                        "response": result
                    }
                    
                    # Get updated response
                    response = await self.api_client.send_function_response(function_response, history)
            
            # Log response to database
            response_id = self.database.add_message(conversation_id, "gemini", response.get("text", ""))
            
            # Log analytics event
            self.analytics.log_event(EventType.MESSAGE_RECEIVED, {"response_length": len(response.get("text", ""))})
            
            # Add to state (in memory)
            self.app_state.add_message({
                "id": response_id,
                "type": "gemini",
                "content": response.get("text", "")
            })
            
            return response
            
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            self.analytics.log_error(str(e), "api_error")
            return {"error": str(e)}
    
    def shutdown(self):
        """
        Perform a clean shutdown of the application.
        
        This method ensures all components are properly closed and
        data is saved before exiting.
        """
        logger.info("Shutting down application")
        
        # Log analytics event
        self.analytics.log_event(EventType.APP_EXIT, {
            "session_stats": self.analytics.get_session_stats()
        })
        
        # Save settings
        # In a real implementation, this would save any pending changes
        
        logger.info("Application shutdown complete")

def create_app(config_path: Optional[Path] = None) -> Application:
    """
    Create and initialize the application.
    
    Args:
        config_path: Optional path to a configuration file.
        
    Returns:
        An initialized Application instance.
    """
    return Application(config_path)
