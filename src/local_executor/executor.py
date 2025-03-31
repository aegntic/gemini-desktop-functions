"""
Local executor module.

This module provides secure execution of local scripts and commands
with permission controls and sandboxing.
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Callable

logger = logging.getLogger(__name__)

class ExecutionPermission(Enum):
    """Enumeration of permission levels for local execution."""
    
    NONE = "none"  # No execution allowed
    READ_ONLY = "read_only"  # Only read operations allowed (e.g., file reading)
    LIMITED = "limited"  # Limited execution with restrictions
    FULL = "full"  # Full execution with user confirmation
    
    @classmethod
    def from_string(cls, value: str) -> "ExecutionPermission":
        """
        Get an ExecutionPermission from a string value.
        
        Args:
            value: The string value to convert.
            
        Returns:
            The corresponding ExecutionPermission enum value.
            Defaults to NONE if the value is not recognized.
        """
        try:
            return cls(value.lower())
        except ValueError:
            return cls.NONE

class LocalExecutor:
    """
    Manages secure execution of local scripts and commands.
    
    This class provides a secure environment for executing local scripts
    and commands with proper permission controls and sandboxing.
    """
    
    def __init__(self, 
                 default_permission: ExecutionPermission = ExecutionPermission.NONE,
                 sandbox_enabled: bool = True,
                 user_confirmation_callback: Optional[Callable[[str, Dict[str, Any]], bool]] = None):
        """
        Initialize the local executor.
        
        Args:
            default_permission: Default permission level for execution.
            sandbox_enabled: Whether to use sandboxing for execution.
            user_confirmation_callback: Optional callback for user confirmation.
                                        Called with (function_name, arguments) and
                                        should return True if execution is allowed.
        """
        self._default_permission = default_permission
        self._sandbox_enabled = sandbox_enabled
        self._user_confirmation_callback = user_confirmation_callback
        self._function_permissions: Dict[str, ExecutionPermission] = {}
        
        logger.debug(f"LocalExecutor initialized with default permission: {default_permission.value}")
    
    def set_function_permission(self, function_name: str, permission: ExecutionPermission):
        """
        Set the permission level for a specific function.
        
        Args:
            function_name: The name of the function.
            permission: The permission level to set.
        """
        self._function_permissions[function_name] = permission
        logger.debug(f"Set permission for function '{function_name}' to {permission.value}")
    
    def get_function_permission(self, function_name: str) -> ExecutionPermission:
        """
        Get the permission level for a specific function.
        
        Args:
            function_name: The name of the function.
            
        Returns:
            The permission level for the function.
            If not explicitly set, returns the default permission.
        """
        return self._function_permissions.get(function_name, self._default_permission)
    
    def execute_function(self, 
                        function_name: str, 
                        function_code: str, 
                        arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a function with the given arguments.
        
        This method checks permissions, obtains user confirmation if needed,
        and executes the function in a secure environment.
        
        Args:
            function_name: The name of the function to execute.
            function_code: The Python code implementing the function.
            arguments: The arguments to pass to the function.
            
        Returns:
            A dictionary containing the execution results.
        """
        logger.debug(f"Executing function '{function_name}' with arguments: {arguments}")
        
        result = {
            "success": False,
            "result": None,
            "error": None
        }
        
        # Check permission
        permission = self.get_function_permission(function_name)
        if permission == ExecutionPermission.NONE:
            result["error"] = f"Execution not allowed: No permission for function '{function_name}'"
            logger.warning(f"Execution denied for '{function_name}': No permission")
            return result
        
        # Get user confirmation if needed and callback is provided
        if permission == ExecutionPermission.FULL and self._user_confirmation_callback:
            if not self._user_confirmation_callback(function_name, arguments):
                result["error"] = f"Execution not allowed: User denied permission for function '{function_name}'"
                logger.info(f"Execution denied for '{function_name}': User denied permission")
                return result
        
        # Execute the function based on permission level
        if permission == ExecutionPermission.READ_ONLY:
            # Only allow functions with "read" or "get" operations
            if not (function_name.startswith("read_") or 
                   function_name.startswith("get_") or 
                   "read" in function_name or 
                   "get" in function_name):
                result["error"] = f"Execution not allowed: Function '{function_name}' does not appear to be read-only"
                logger.warning(f"Execution denied for '{function_name}': Not a read-only function")
                return result
            
            # Scan function code for potentially unsafe operations
            unsafe_patterns = [
                "open(", ".write(", "subprocess", "os.system", "eval(", "exec(", 
                "import os", "import subprocess", "import shutil", "__import__"
            ]
            
            for pattern in unsafe_patterns:
                if pattern in function_code:
                    result["error"] = f"Execution not allowed: Function code contains potentially unsafe operation: {pattern}"
                    logger.warning(f"Execution denied for '{function_name}': Contains unsafe pattern '{pattern}'")
                    return result
        
        # Actually execute the function
        if self._sandbox_enabled:
            return self._execute_in_sandbox(function_name, function_code, arguments)
        else:
            return self._execute_directly(function_name, function_code, arguments)
    
    def _execute_directly(self, 
                         function_name: str, 
                         function_code: str, 
                         arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a function directly in the current process.
        
        This method is potentially unsafe and should only be used when
        the function code is trusted.
        
        Args:
            function_name: The name of the function to execute.
            function_code: The Python code implementing the function.
            arguments: The arguments to pass to the function.
            
        Returns:
            A dictionary containing the execution results.
        """
        logger.debug(f"Directly executing function '{function_name}'")
        
        result = {
            "success": False,
            "result": None,
            "error": None
        }
        
        try:
            # Create a namespace for the function
            namespace = {}
            
            # Execute the function code in the namespace
            exec(function_code, namespace)
            
            # Check if the function exists in the namespace
            if function_name not in namespace:
                result["error"] = f"Function '{function_name}' not found in the provided code"
                logger.error(f"Function '{function_name}' not found in the provided code")
                return result
            
            # Get the function object
            func = namespace[function_name]
            
            # Execute the function with the provided arguments
            func_result = func(**arguments)
            
            result["success"] = True
            result["result"] = func_result
            
            logger.debug(f"Function '{function_name}' executed successfully")
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error executing function '{function_name}': {str(e)}")
        
        return result
    
    def _execute_in_sandbox(self, 
                           function_name: str, 
                           function_code: str, 
                           arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a function in a sandboxed environment.
        
        This method runs the function in a separate process with restricted
        permissions for better security.
        
        Args:
            function_name: The name of the function to execute.
            function_code: The Python code implementing the function.
            arguments: The arguments to pass to the function.
            
        Returns:
            A dictionary containing the execution results.
        """
        logger.debug(f"Executing function '{function_name}' in sandbox")
        
        result = {
            "success": False,
            "result": None,
            "error": None
        }
        
        try:
            # Create a temporary file for the function code
            with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w') as temp_file:
                temp_file_path = temp_file.name
                
                # Prepare the sandbox script
                sandbox_script = f"""
import sys
import json
import traceback

# The function code provided by the user
{function_code}

# Execute the function with provided arguments
if __name__ == "__main__":
    try:
        # Parse arguments from command line
        args_json = sys.argv[1]
        args = json.loads(args_json)
        
        # Call the function with the arguments
        result = {function_name}(**args)
        
        # Return the result as JSON
        print(json.dumps({{"success": True, "result": result}}))
        
    except Exception as e:
        error_msg = str(e)
        traceback_str = traceback.format_exc()
        
        print(json.dumps({{"success": False, "error": error_msg, "traceback": traceback_str}}))
"""
                
                temp_file.write(sandbox_script)
            
            # Run the sandbox script in a subprocess
            try:
                args_json = json.dumps(arguments)
                
                # Determine sandboxing method based on platform
                if sys.platform == "linux":
                    # Use bubblewrap or firejail if available
                    if os.path.exists("/usr/bin/bwrap"):  # bubblewrap
                        cmd = [
                            "/usr/bin/bwrap",
                            "--ro-bind", "/usr", "/usr",
                            "--ro-bind", "/lib", "/lib",
                            "--ro-bind", "/lib64", "/lib64",
                            "--proc", "/proc",
                            "--dev", "/dev",
                            "--unshare-all",
                            "--die-with-parent",
                            sys.executable, temp_file_path, args_json
                        ]
                    elif os.path.exists("/usr/bin/firejail"):  # firejail
                        cmd = [
                            "/usr/bin/firejail",
                            "--quiet",
                            "--private",
                            "--caps.drop=all",
                            "--disable-mnt",
                            sys.executable, temp_file_path, args_json
                        ]
                    else:  # fallback to regular python
                        cmd = [sys.executable, temp_file_path, args_json]
                else:
                    # For non-Linux platforms, just use regular python
                    cmd = [sys.executable, temp_file_path, args_json]
                
                # Execute the command
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                stdout, stderr = process.communicate(timeout=10)  # 10-second timeout
                
                if process.returncode == 0:
                    try:
                        output = json.loads(stdout)
                        result.update(output)
                    except json.JSONDecodeError:
                        result["error"] = "Failed to parse function output"
                        logger.error(f"Failed to parse output from function '{function_name}'")
                else:
                    result["error"] = f"Function process exited with code {process.returncode}"
                    result["stderr"] = stderr
                    logger.error(f"Function '{function_name}' exited with code {process.returncode}: {stderr}")
            
            except subprocess.TimeoutExpired:
                result["error"] = "Function execution timed out"
                logger.error(f"Function '{function_name}' execution timed out")
            
            except Exception as e:
                result["error"] = f"Error executing function: {str(e)}"
                logger.error(f"Error executing function '{function_name}': {str(e)}")
            
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file {temp_file_path}: {str(e)}")
        
        except Exception as e:
            result["error"] = f"Error preparing sandbox: {str(e)}"
            logger.error(f"Error preparing sandbox for function '{function_name}': {str(e)}")
        
        return result
    
    def execute_command(self, command: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a system command with the given arguments.
        
        This method is particularly sensitive and requires the highest
        permission level (FULL) as well as user confirmation.
        
        Args:
            command: The command to execute.
            arguments: Optional arguments to format into the command.
            
        Returns:
            A dictionary containing the execution results.
        """
        logger.debug(f"Executing command: {command}")
        
        result = {
            "success": False,
            "result": None,
            "error": None,
            "stdout": "",
            "stderr": ""
        }
        
        # Always require FULL permission for command execution
        if self._default_permission != ExecutionPermission.FULL:
            result["error"] = "Command execution requires FULL permission level"
            logger.warning("Command execution denied: Requires FULL permission level")
            return result
        
        # Always require user confirmation
        if self._user_confirmation_callback:
            if not self._user_confirmation_callback("execute_command", {"command": command, "arguments": arguments}):
                result["error"] = "Command execution denied by user"
                logger.info("Command execution denied by user")
                return result
        else:
            result["error"] = "Command execution requires user confirmation callback"
            logger.warning("Command execution denied: No user confirmation callback provided")
            return result
        
        try:
            # Format command with arguments if provided
            if arguments:
                for key, value in arguments.items():
                    # Simple string replacement - in a real implementation,
                    # we would use a more secure method for argument substitution
                    placeholder = f"{{{key}}}"
                    command = command.replace(placeholder, str(value))
            
            # Execute the command
            process = subprocess.Popen(
                command,
                shell=True,  # Using shell=True is generally discouraged for security reasons
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(timeout=30)  # 30-second timeout
            
            result["stdout"] = stdout
            result["stderr"] = stderr
            
            if process.returncode == 0:
                result["success"] = True
                result["result"] = stdout
                logger.debug(f"Command executed successfully")
            else:
                result["error"] = f"Command exited with code {process.returncode}"
                logger.error(f"Command exited with code {process.returncode}: {stderr}")
        
        except subprocess.TimeoutExpired:
            result["error"] = "Command execution timed out"
            logger.error("Command execution timed out")
        
        except Exception as e:
            result["error"] = f"Error executing command: {str(e)}"
            logger.error(f"Error executing command: {str(e)}")
        
        return result
