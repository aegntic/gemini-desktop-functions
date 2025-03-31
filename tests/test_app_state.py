"""
Unit tests for the AppState class.
"""

import unittest
from unittest.mock import patch, MagicMock

from src.core.app_state import AppState

class TestAppState(unittest.TestCase):
    """Test cases for the AppState class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Reset the singleton instance
        AppState._instance = None
    
    def test_singleton_pattern(self):
        """Test that AppState implements the singleton pattern correctly."""
        state1 = AppState()
        state2 = AppState()
        
        # Both variables should reference the same instance
        self.assertIs(state1, state2)
    
    def test_api_key_getter_setter(self):
        """Test the API key getter and setter methods."""
        state = AppState()
        
        # Initially None
        self.assertIsNone(state.api_key)
        
        # Set a test key
        test_key = "test_api_key_12345"
        state.api_key = test_key
        
        # Should return obfuscated version
        self.assertEqual(state.api_key, "****5")
        
        # Setting to None should work
        state.api_key = None
        self.assertIsNone(state.api_key)
    
    def test_authentication_status(self):
        """Test the authentication status getter and setter methods."""
        state = AppState()
        
        # Initially False
        self.assertFalse(state.is_authenticated)
        
        # Set to True
        state.is_authenticated = True
        self.assertTrue(state.is_authenticated)
        
        # Set back to False
        state.is_authenticated = False
        self.assertFalse(state.is_authenticated)
    
    def test_active_tools_management(self):
        """Test adding and removing tools from the active tools list."""
        state = AppState()
        
        # Initially empty
        self.assertEqual(len(state.active_tools), 0)
        
        # Add a tool
        tool1 = {"id": "tool1", "name": "Test Tool 1"}
        state.add_tool(tool1)
        self.assertEqual(len(state.active_tools), 1)
        self.assertEqual(state.active_tools[0], tool1)
        
        # Add another tool
        tool2 = {"id": "tool2", "name": "Test Tool 2"}
        state.add_tool(tool2)
        self.assertEqual(len(state.active_tools), 2)
        
        # Remove a tool
        state.remove_tool("tool1")
        self.assertEqual(len(state.active_tools), 1)
        self.assertEqual(state.active_tools[0], tool2)
        
        # Remove a non-existent tool (should not error)
        state.remove_tool("non_existent")
        self.assertEqual(len(state.active_tools), 1)
    
    def test_conversation_history_management(self):
        """Test adding and clearing messages in the conversation history."""
        state = AppState()
        
        # Initially empty
        self.assertEqual(len(state.conversation_history), 0)
        
        # Add a message
        message1 = {"type": "user", "content": "Test message 1"}
        state.add_message(message1)
        self.assertEqual(len(state.conversation_history), 1)
        self.assertEqual(state.conversation_history[0], message1)
        
        # Add another message
        message2 = {"type": "gemini", "content": "Test message 2"}
        state.add_message(message2)
        self.assertEqual(len(state.conversation_history), 2)
        
        # Clear history
        state.clear_conversation_history()
        self.assertEqual(len(state.conversation_history), 0)
    
    def test_app_settings_management(self):
        """Test getting and updating application settings."""
        state = AppState()
        
        # Check default settings
        self.assertEqual(state.app_settings["theme"], "system")
        self.assertTrue(state.app_settings["save_history"])
        self.assertEqual(state.app_settings["max_history_items"], 100)
        
        # Update settings
        new_settings = {
            "theme": "dark",
            "save_history": False
        }
        state.update_settings(new_settings)
        
        # Check updated settings
        self.assertEqual(state.app_settings["theme"], "dark")
        self.assertFalse(state.app_settings["save_history"])
        self.assertEqual(state.app_settings["max_history_items"], 100)  # Unchanged
    
    def test_history_trimming(self):
        """Test that history is trimmed when it exceeds the maximum size."""
        state = AppState()
        
        # Set max history to a small value
        state.update_settings({"max_history_items": 3})
        
        # Add more messages than the maximum
        for i in range(5):
            state.add_message({"type": "user", "content": f"Message {i}"})
        
        # Should only keep the most recent 3
        self.assertEqual(len(state.conversation_history), 3)
        self.assertEqual(state.conversation_history[0]["content"], "Message 2")
        self.assertEqual(state.conversation_history[1]["content"], "Message 3")
        self.assertEqual(state.conversation_history[2]["content"], "Message 4")

if __name__ == "__main__":
    unittest.main()
