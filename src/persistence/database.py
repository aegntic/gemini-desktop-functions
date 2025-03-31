"""
Database module for persistence.

This module manages SQLite database connections and operations
for storing conversation history, tool definitions, and settings.
"""

import logging
import os
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple

logger = logging.getLogger(__name__)

class Database:
    """
    Database manager for the application.
    
    This class manages SQLite database connections and operations
    for storing conversation history, settings, and other persistent data.
    """
    
    def __init__(self, db_path: Union[str, Path] = None):
        """
        Initialize the database manager.
        
        Args:
            db_path: Optional path to the SQLite database file.
                     If not provided, a default location will be used.
        """
        if db_path is None:
            # Use default location in user's home directory
            home_dir = Path.home()
            db_dir = home_dir / ".gemini-function-manager"
            os.makedirs(db_dir, exist_ok=True)
            self._db_path = db_dir / "gemini_function_manager.db"
        else:
            self._db_path = Path(db_path)
        
        logger.debug(f"Database initialized with path: {self._db_path}")
        
        # Initialize database
        self._create_tables_if_not_exist()
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        Get a database connection.
        
        Returns:
            A SQLite connection object.
        """
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        return conn
    
    def _create_tables_if_not_exist(self):
        """Create database tables if they don't exist."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Conversations table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Messages table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id)
            )
            ''')
            
            # Function calls table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS function_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER,
                function_name TEXT NOT NULL,
                function_args TEXT NOT NULL,
                function_result TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES messages (id)
            )
            ''')
            
            # Settings table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Tool definitions table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS tool_definitions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                schema TEXT NOT NULL,
                enabled INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Tool versions table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS tool_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                schema TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tool_id) REFERENCES tool_definitions (id)
            )
            ''')
            
            conn.commit()
            logger.info("Database tables created/verified successfully")
            
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            raise
        finally:
            conn.close()
    
    # Conversation Methods
    
    def create_conversation(self, title: str = None) -> int:
        """
        Create a new conversation.
        
        Args:
            title: Optional title for the conversation.
            
        Returns:
            The ID of the created conversation.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO conversations (title, created_at, updated_at) VALUES (?, ?, ?)",
                (title or "Conversation", now, now)
            )
            
            conversation_id = cursor.lastrowid
            conn.commit()
            
            logger.debug(f"Created conversation with ID: {conversation_id}")
            return conversation_id
            
        except Exception as e:
            logger.error(f"Error creating conversation: {e}")
            raise
        finally:
            conn.close()
    
    def update_conversation(self, conversation_id: int, title: str) -> bool:
        """
        Update a conversation's title.
        
        Args:
            conversation_id: The ID of the conversation to update.
            title: The new title for the conversation.
            
        Returns:
            True if the update was successful, False otherwise.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            cursor.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, now, conversation_id)
            )
            
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.debug(f"Updated conversation {conversation_id} with title: {title}")
            else:
                logger.warning(f"No conversation found with ID: {conversation_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating conversation {conversation_id}: {e}")
            return False
        finally:
            conn.close()
    
    def delete_conversation(self, conversation_id: int) -> bool:
        """
        Delete a conversation and all its messages.
        
        Args:
            conversation_id: The ID of the conversation to delete.
            
        Returns:
            True if the deletion was successful, False otherwise.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # First, get all message IDs to delete related function calls
            cursor.execute("SELECT id FROM messages WHERE conversation_id = ?", (conversation_id,))
            message_ids = [row["id"] for row in cursor.fetchall()]
            
            # Delete function calls related to these messages
            if message_ids:
                placeholders = ", ".join("?" for _ in message_ids)
                cursor.execute(f"DELETE FROM function_calls WHERE message_id IN ({placeholders})", message_ids)
            
            # Delete all messages in the conversation
            cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            
            # Delete the conversation
            cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.debug(f"Deleted conversation with ID: {conversation_id}")
            else:
                logger.warning(f"No conversation found with ID: {conversation_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error deleting conversation {conversation_id}: {e}")
            return False
        finally:
            conn.close()
    
    def get_conversation(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a conversation by ID.
        
        Args:
            conversation_id: The ID of the conversation to retrieve.
            
        Returns:
            A dictionary containing the conversation details, or None if not found.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
            row = cursor.fetchone()
            
            if row:
                conversation = dict(row)
                
                # Get all messages for this conversation
                cursor.execute("""
                    SELECT * FROM messages 
                    WHERE conversation_id = ? 
                    ORDER BY timestamp ASC
                """, (conversation_id,))
                
                messages = []
                for msg_row in cursor.fetchall():
                    message = dict(msg_row)
                    
                    # Get function calls for this message
                    cursor.execute("""
                        SELECT * FROM function_calls 
                        WHERE message_id = ? 
                        ORDER BY timestamp ASC
                    """, (message["id"],))
                    
                    function_calls = [dict(fc_row) for fc_row in cursor.fetchall()]
                    if function_calls:
                        message["function_calls"] = function_calls
                    
                    messages.append(message)
                
                conversation["messages"] = messages
                
                logger.debug(f"Retrieved conversation {conversation_id} with {len(messages)} messages")
                return conversation
            else:
                logger.warning(f"No conversation found with ID: {conversation_id}")
                return None
            
        except Exception as e:
            logger.error(f"Error retrieving conversation {conversation_id}: {e}")
            return None
        finally:
            conn.close()
    
    def get_all_conversations(self) -> List[Dict[str, Any]]:
        """
        Get all conversations.
        
        Returns:
            A list of dictionaries containing conversation details.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, title, created_at, updated_at FROM conversations 
                ORDER BY updated_at DESC
            """)
            
            conversations = [dict(row) for row in cursor.fetchall()]
            
            # For each conversation, get the count of messages
            for conv in conversations:
                cursor.execute("""
                    SELECT COUNT(*) as message_count FROM messages 
                    WHERE conversation_id = ?
                """, (conv["id"],))
                
                result = cursor.fetchone()
                conv["message_count"] = result["message_count"] if result else 0
            
            logger.debug(f"Retrieved {len(conversations)} conversations")
            return conversations
            
        except Exception as e:
            logger.error(f"Error retrieving conversations: {e}")
            return []
        finally:
            conn.close()
    
    # Message Methods
    
    def add_message(self, conversation_id: int, message_type: str, content: str) -> int:
        """
        Add a message to a conversation.
        
        Args:
            conversation_id: The ID of the conversation to add the message to.
            message_type: The type of message (e.g., 'user', 'gemini').
            content: The message content.
            
        Returns:
            The ID of the added message.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Update conversation's updated_at timestamp
            now = datetime.now().isoformat()
            cursor.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id)
            )
            
            # Insert the message
            cursor.execute(
                "INSERT INTO messages (conversation_id, type, content, timestamp) VALUES (?, ?, ?, ?)",
                (conversation_id, message_type, content, now)
            )
            
            message_id = cursor.lastrowid
            conn.commit()
            
            logger.debug(f"Added {message_type} message {message_id} to conversation {conversation_id}")
            return message_id
            
        except Exception as e:
            logger.error(f"Error adding message to conversation {conversation_id}: {e}")
            raise
        finally:
            conn.close()
    
    def add_function_call(self, message_id: int, function_name: str, function_args: Dict[str, Any], function_result: Dict[str, Any] = None) -> int:
        """
        Add a function call to a message.
        
        Args:
            message_id: The ID of the message associated with the function call.
            function_name: The name of the function that was called.
            function_args: The arguments passed to the function.
            function_result: Optional result of the function call.
            
        Returns:
            The ID of the added function call.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Convert dictionaries to JSON strings
            args_json = json.dumps(function_args)
            result_json = json.dumps(function_result) if function_result else None
            
            now = datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO function_calls (message_id, function_name, function_args, function_result, timestamp) VALUES (?, ?, ?, ?, ?)",
                (message_id, function_name, args_json, result_json, now)
            )
            
            call_id = cursor.lastrowid
            conn.commit()
            
            logger.debug(f"Added function call {call_id} to message {message_id}")
            return call_id
            
        except Exception as e:
            logger.error(f"Error adding function call to message {message_id}: {e}")
            raise
        finally:
            conn.close()
    
    def update_function_result(self, call_id: int, function_result: Dict[str, Any]) -> bool:
        """
        Update the result of a function call.
        
        Args:
            call_id: The ID of the function call to update.
            function_result: The result of the function call.
            
        Returns:
            True if the update was successful, False otherwise.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            result_json = json.dumps(function_result)
            cursor.execute(
                "UPDATE function_calls SET function_result = ? WHERE id = ?",
                (result_json, call_id)
            )
            
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.debug(f"Updated function call result for call ID: {call_id}")
            else:
                logger.warning(f"No function call found with ID: {call_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating function call result {call_id}: {e}")
            return False
        finally:
            conn.close()
    
    # Settings Methods
    
    def get_setting(self, key: str, default_value: Any = None) -> Any:
        """
        Get a setting value.
        
        Args:
            key: The setting key.
            default_value: Default value to return if the setting doesn't exist.
            
        Returns:
            The setting value, or the default value if not found.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            
            if row:
                # Try to parse as JSON, fall back to string if not valid JSON
                try:
                    return json.loads(row["value"])
                except json.JSONDecodeError:
                    return row["value"]
            else:
                return default_value
            
        except Exception as e:
            logger.error(f"Error retrieving setting {key}: {e}")
            return default_value
        finally:
            conn.close()
    
    def set_setting(self, key: str, value: Any) -> bool:
        """
        Set a setting value.
        
        Args:
            key: The setting key.
            value: The setting value (will be converted to JSON).
            
        Returns:
            True if the setting was set successfully, False otherwise.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Convert value to JSON string if it's not already a string
            if not isinstance(value, str):
                value = json.dumps(value)
            
            now = datetime.now().isoformat()
            cursor.execute(
                """
                INSERT INTO settings (key, value, updated_at) 
                VALUES (?, ?, ?) 
                ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?
                """,
                (key, value, now, value, now)
            )
            
            conn.commit()
            logger.debug(f"Setting {key} set successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error setting setting {key}: {e}")
            return False
        finally:
            conn.close()
    
    def delete_setting(self, key: str) -> bool:
        """
        Delete a setting.
        
        Args:
            key: The setting key to delete.
            
        Returns:
            True if the setting was deleted successfully, False otherwise.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM settings WHERE key = ?", (key,))
            
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.debug(f"Setting {key} deleted successfully")
            else:
                logger.warning(f"No setting found with key: {key}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error deleting setting {key}: {e}")
            return False
        finally:
            conn.close()
    
    def get_all_settings(self) -> Dict[str, Any]:
        """
        Get all settings.
        
        Returns:
            A dictionary of all settings.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT key, value FROM settings")
            
            settings = {}
            for row in cursor.fetchall():
                key = row["key"]
                value = row["value"]
                
                # Try to parse as JSON, fall back to string if not valid JSON
                try:
                    settings[key] = json.loads(value)
                except json.JSONDecodeError:
                    settings[key] = value
            
            logger.debug(f"Retrieved {len(settings)} settings")
            return settings
            
        except Exception as e:
            logger.error(f"Error retrieving all settings: {e}")
            return {}
        finally:
            conn.close()
    
    # Tool Definition Methods
    
    def save_tool_definition(self, tool_id: str, name: str, description: str, schema: Dict[str, Any], enabled: bool = False) -> bool:
        """
        Save a tool definition.
        
        Args:
            tool_id: The unique ID of the tool.
            name: The display name of the tool.
            description: The description of the tool.
            schema: The tool's schema definition.
            enabled: Whether the tool is enabled.
            
        Returns:
            True if the tool was saved successfully, False otherwise.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Check if tool already exists
            cursor.execute("SELECT id FROM tool_definitions WHERE id = ?", (tool_id,))
            existing = cursor.fetchone()
            
            schema_json = json.dumps(schema)
            now = datetime.now().isoformat()
            
            if existing:
                # Update existing tool
                cursor.execute(
                    """
                    UPDATE tool_definitions 
                    SET name = ?, description = ?, schema = ?, enabled = ?, updated_at = ? 
                    WHERE id = ?
                    """,
                    (name, description, schema_json, 1 if enabled else 0, now, tool_id)
                )
            else:
                # Insert new tool
                cursor.execute(
                    """
                    INSERT INTO tool_definitions (id, name, description, schema, enabled, created_at, updated_at) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (tool_id, name, description, schema_json, 1 if enabled else 0, now, now)
                )
            
            # Save version history
            cursor.execute(
                """
                SELECT MAX(version) as latest_version FROM tool_versions WHERE tool_id = ?
                """,
                (tool_id,)
            )
            row = cursor.fetchone()
            latest_version = row["latest_version"] if row["latest_version"] is not None else 0
            
            # Increment version number
            new_version = latest_version + 1
            
            cursor.execute(
                """
                INSERT INTO tool_versions (tool_id, version, schema, created_at) 
                VALUES (?, ?, ?, ?)
                """,
                (tool_id, new_version, schema_json, now)
            )
            
            conn.commit()
            logger.debug(f"Tool {tool_id} saved successfully (version {new_version})")
            return True
            
        except Exception as e:
            logger.error(f"Error saving tool definition {tool_id}: {e}")
            return False
        finally:
            conn.close()
    
    def get_tool_definition(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a tool definition by ID.
        
        Args:
            tool_id: The ID of the tool to retrieve.
            
        Returns:
            A dictionary containing the tool definition, or None if not found.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM tool_definitions WHERE id = ?", (tool_id,))
            row = cursor.fetchone()
            
            if row:
                tool = dict(row)
                
                # Parse schema JSON
                try:
                    tool["schema"] = json.loads(tool["schema"])
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in tool schema for {tool_id}")
                
                # Convert enabled to boolean
                tool["enabled"] = bool(tool["enabled"])
                
                # Get version history
                cursor.execute(
                    """
                    SELECT * FROM tool_versions 
                    WHERE tool_id = ? 
                    ORDER BY version DESC
                    """,
                    (tool_id,)
                )
                
                versions = []
                for v_row in cursor.fetchall():
                    version = dict(v_row)
                    
                    # Parse schema JSON for each version
                    try:
                        version["schema"] = json.loads(version["schema"])
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in tool version schema for {tool_id} v{version['version']}")
                    
                    versions.append(version)
                
                tool["versions"] = versions
                
                logger.debug(f"Retrieved tool definition for {tool_id} with {len(versions)} versions")
                return tool
            else:
                logger.warning(f"No tool definition found with ID: {tool_id}")
                return None
            
        except Exception as e:
            logger.error(f"Error retrieving tool definition {tool_id}: {e}")
            return None
        finally:
            conn.close()
    
    def delete_tool_definition(self, tool_id: str) -> bool:
        """
        Delete a tool definition and its version history.
        
        Args:
            tool_id: The ID of the tool to delete.
            
        Returns:
            True if the tool was deleted successfully, False otherwise.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Delete version history first (due to foreign key constraint)
            cursor.execute("DELETE FROM tool_versions WHERE tool_id = ?", (tool_id,))
            
            # Delete tool definition
            cursor.execute("DELETE FROM tool_definitions WHERE id = ?", (tool_id,))
            
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.debug(f"Deleted tool definition {tool_id}")
            else:
                logger.warning(f"No tool definition found with ID: {tool_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error deleting tool definition {tool_id}: {e}")
            return False
        finally:
            conn.close()
    
    def get_all_tool_definitions(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """
        Get all tool definitions.
        
        Args:
            enabled_only: If True, only return enabled tools.
            
        Returns:
            A list of tool definitions.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if enabled_only:
                cursor.execute("SELECT * FROM tool_definitions WHERE enabled = 1")
            else:
                cursor.execute("SELECT * FROM tool_definitions")
            
            tools = []
            for row in cursor.fetchall():
                tool = dict(row)
                
                # Parse schema JSON
                try:
                    tool["schema"] = json.loads(tool["schema"])
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in tool schema for {tool['id']}")
                
                # Convert enabled to boolean
                tool["enabled"] = bool(tool["enabled"])
                
                tools.append(tool)
            
            logger.debug(f"Retrieved {len(tools)} tool definitions")
            return tools
            
        except Exception as e:
            logger.error(f"Error retrieving tool definitions: {e}")
            return []
        finally:
            conn.close()
    
    def get_tool_version(self, tool_id: str, version: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific version of a tool.
        
        Args:
            tool_id: The ID of the tool.
            version: The version number to retrieve.
            
        Returns:
            The tool version data, or None if not found.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT * FROM tool_versions 
                WHERE tool_id = ? AND version = ?
                """,
                (tool_id, version)
            )
            
            row = cursor.fetchone()
            
            if row:
                version_data = dict(row)
                
                # Parse schema JSON
                try:
                    version_data["schema"] = json.loads(version_data["schema"])
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in tool version schema for {tool_id} v{version}")
                
                logger.debug(f"Retrieved version {version} of tool {tool_id}")
                return version_data
            else:
                logger.warning(f"No version {version} found for tool {tool_id}")
                return None
            
        except Exception as e:
            logger.error(f"Error retrieving tool version {version} for {tool_id}: {e}")
            return None
        finally:
            conn.close()
