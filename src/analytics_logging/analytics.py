"""
Analytics and logging module.

This module collects and analyzes usage statistics, performance metrics,
and execution logs for the application.
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple

logger = logging.getLogger(__name__)

class EventType(Enum):
    """Types of events that can be logged for analytics."""
    
    # App events
    APP_START = "app_start"
    APP_EXIT = "app_exit"
    ERROR = "error"
    
    # Chat events
    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    
    # Function events
    FUNCTION_DEFINED = "function_defined"
    FUNCTION_EDITED = "function_edited"
    FUNCTION_DELETED = "function_deleted"
    FUNCTION_ENABLED = "function_enabled"
    FUNCTION_DISABLED = "function_disabled"
    FUNCTION_CALLED = "function_called"
    FUNCTION_EXECUTED = "function_executed"
    
    # Simulation events
    SIMULATION_STARTED = "simulation_started"
    SIMULATION_COMPLETED = "simulation_completed"
    SIMULATION_FAILED = "simulation_failed"

class AnalyticsManager:
    """
    Manager for collecting and analyzing application usage statistics.
    
    This class records events, tracks metrics, and provides analytics
    visualizations for user behavior and application performance.
    """
    
    def __init__(self, storage_dir: Union[str, Path] = None, enabled: bool = True):
        """
        Initialize the analytics manager.
        
        Args:
            storage_dir: Optional directory for storing analytics data.
                         If not provided, a default location will be used.
            enabled: Whether analytics collection is enabled.
        """
        if storage_dir is None:
            # Use default location in user's home directory
            home_dir = Path.home()
            self._storage_dir = home_dir / ".gemini-function-manager" / "analytics"
        else:
            self._storage_dir = Path(storage_dir)
        
        # Create directory if it doesn't exist
        os.makedirs(self._storage_dir, exist_ok=True)
        
        self._enabled = enabled
        self._session_id = datetime.now().strftime("%Y%m%d%H%M%S")
        self._session_start_time = time.time()
        self._event_count = 0
        
        # Create event log file for this session
        self._event_log_path = self._storage_dir / f"events_{self._session_id}.jsonl"
        
        logger.debug(f"AnalyticsManager initialized with storage directory: {self._storage_dir}")
        
        # Log session start event
        if self._enabled:
            self.log_event(EventType.APP_START, {
                "session_id": self._session_id,
                "timestamp": datetime.now().isoformat()
            })
    
    @property
    def enabled(self) -> bool:
        """
        Check if analytics collection is enabled.
        
        Returns:
            True if enabled, False otherwise.
        """
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool):
        """
        Enable or disable analytics collection.
        
        Args:
            value: True to enable, False to disable.
        """
        self._enabled = value
        logger.debug(f"Analytics collection {'enabled' if value else 'disabled'}")
    
    def log_event(self, event_type: EventType, data: Dict[str, Any] = None) -> bool:
        """
        Log an event for analytics.
        
        Args:
            event_type: The type of event to log.
            data: Additional data to include with the event.
            
        Returns:
            True if the event was logged successfully, False otherwise.
        """
        if not self._enabled:
            return False
        
        try:
            timestamp = datetime.now().isoformat()
            
            event = {
                "event_type": event_type.value,
                "timestamp": timestamp,
                "session_id": self._session_id
            }
            
            if data:
                event["data"] = data
            
            # Append to event log file
            with open(self._event_log_path, "a") as f:
                f.write(json.dumps(event) + "\n")
            
            self._event_count += 1
            logger.debug(f"Logged event: {event_type.value}")
            return True
            
        except Exception as e:
            logger.error(f"Error logging event {event_type.value}: {e}")
            return False
    
    def log_error(self, error_message: str, error_type: str = None, stack_trace: str = None) -> bool:
        """
        Log an error event for analytics.
        
        Args:
            error_message: The error message.
            error_type: Optional error type or category.
            stack_trace: Optional stack trace.
            
        Returns:
            True if the error was logged successfully, False otherwise.
        """
        data = {
            "error_message": error_message
        }
        
        if error_type:
            data["error_type"] = error_type
        
        if stack_trace:
            data["stack_trace"] = stack_trace
        
        return self.log_event(EventType.ERROR, data)
    
    def log_function_call(self, function_name: str, arguments: Dict[str, Any], 
                         execution_time: float = None, success: bool = None) -> bool:
        """
        Log a function call event for analytics.
        
        Args:
            function_name: The name of the function that was called.
            arguments: The arguments passed to the function.
            execution_time: Optional execution time in seconds.
            success: Optional success status of the function call.
            
        Returns:
            True if the event was logged successfully, False otherwise.
        """
        data = {
            "function_name": function_name,
            "arguments": arguments
        }
        
        if execution_time is not None:
            data["execution_time"] = execution_time
        
        if success is not None:
            data["success"] = success
        
        return self.log_event(EventType.FUNCTION_CALLED, data)
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get statistics for the current session.
        
        Returns:
            A dictionary of session statistics.
        """
        session_duration = time.time() - self._session_start_time
        
        return {
            "session_id": self._session_id,
            "start_time": datetime.fromtimestamp(self._session_start_time).isoformat(),
            "duration_seconds": session_duration,
            "event_count": self._event_count
        }
    
    def get_event_counts(self, days: int = 7) -> Dict[str, int]:
        """
        Get counts of events by type for the specified number of days.
        
        Args:
            days: Number of days to include in the analysis.
            
        Returns:
            A dictionary of event types and their counts.
        """
        if not self._enabled:
            return {}
        
        try:
            # Calculate start date
            start_date = datetime.now() - timedelta(days=days)
            
            # Find all event log files
            event_files = list(self._storage_dir.glob("events_*.jsonl"))
            
            # Process each file
            event_counts = {}
            
            for file_path in event_files:
                with open(file_path, "r") as f:
                    for line in f:
                        try:
                            event = json.loads(line)
                            event_timestamp = datetime.fromisoformat(event["timestamp"])
                            
                            # Skip events before start date
                            if event_timestamp < start_date:
                                continue
                            
                            event_type = event["event_type"]
                            event_counts[event_type] = event_counts.get(event_type, 0) + 1
                        
                        except Exception as e:
                            logger.warning(f"Error parsing event from {file_path}: {e}")
            
            return event_counts
            
        except Exception as e:
            logger.error(f"Error getting event counts: {e}")
            return {}
    
    def get_function_stats(self, days: int = 7) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for function usage over the specified number of days.
        
        Args:
            days: Number of days to include in the analysis.
            
        Returns:
            A dictionary of function names and their usage statistics.
        """
        if not self._enabled:
            return {}
        
        try:
            # Calculate start date
            start_date = datetime.now() - timedelta(days=days)
            
            # Find all event log files
            event_files = list(self._storage_dir.glob("events_*.jsonl"))
            
            # Process each file
            function_stats = {}
            
            for file_path in event_files:
                with open(file_path, "r") as f:
                    for line in f:
                        try:
                            event = json.loads(line)
                            
                            # Only process function call events
                            if event["event_type"] != EventType.FUNCTION_CALLED.value:
                                continue
                            
                            event_timestamp = datetime.fromisoformat(event["timestamp"])
                            
                            # Skip events before start date
                            if event_timestamp < start_date:
                                continue
                            
                            data = event.get("data", {})
                            function_name = data.get("function_name")
                            
                            if function_name:
                                # Initialize stats for this function if not seen before
                                if function_name not in function_stats:
                                    function_stats[function_name] = {
                                        "call_count": 0,
                                        "success_count": 0,
                                        "error_count": 0,
                                        "total_execution_time": 0,
                                        "avg_execution_time": 0
                                    }
                                
                                # Update stats
                                stats = function_stats[function_name]
                                stats["call_count"] += 1
                                
                                if "success" in data:
                                    if data["success"]:
                                        stats["success_count"] += 1
                                    else:
                                        stats["error_count"] += 1
                                
                                if "execution_time" in data:
                                    stats["total_execution_time"] += data["execution_time"]
                                    stats["avg_execution_time"] = stats["total_execution_time"] / stats["call_count"]
                        
                        except Exception as e:
                            logger.warning(f"Error parsing event from {file_path}: {e}")
            
            return function_stats
            
        except Exception as e:
            logger.error(f"Error getting function stats: {e}")
            return {}
    
    def get_daily_usage(self, days: int = 30) -> Dict[str, int]:
        """
        Get daily usage counts for the specified number of days.
        
        Args:
            days: Number of days to include in the analysis.
            
        Returns:
            A dictionary of dates and their usage counts.
        """
        if not self._enabled:
            return {}
        
        try:
            # Calculate start date
            start_date = datetime.now() - timedelta(days=days)
            
            # Find all event log files
            event_files = list(self._storage_dir.glob("events_*.jsonl"))
            
            # Process each file
            daily_counts = {}
            
            for file_path in event_files:
                with open(file_path, "r") as f:
                    for line in f:
                        try:
                            event = json.loads(line)
                            event_timestamp = datetime.fromisoformat(event["timestamp"])
                            
                            # Skip events before start date
                            if event_timestamp < start_date:
                                continue
                            
                            # Get date string
                            date_str = event_timestamp.date().isoformat()
                            daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
                        
                        except Exception as e:
                            logger.warning(f"Error parsing event from {file_path}: {e}")
            
            return daily_counts
            
        except Exception as e:
            logger.error(f"Error getting daily usage: {e}")
            return {}
    
    def clear_all_data(self) -> bool:
        """
        Clear all analytics data.
        
        Returns:
            True if data was cleared successfully, False otherwise.
        """
        try:
            # Find all event log files
            event_files = list(self._storage_dir.glob("events_*.jsonl"))
            
            # Delete each file
            for file_path in event_files:
                file_path.unlink()
            
            logger.info(f"Cleared all analytics data ({len(event_files)} files)")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing analytics data: {e}")
            return False
    
    def export_data(self, output_path: Union[str, Path]) -> bool:
        """
        Export all analytics data to a file.
        
        Args:
            output_path: Path where the data should be exported.
            
        Returns:
            True if data was exported successfully, False otherwise.
        """
        try:
            output_path = Path(output_path)
            
            # Find all event log files
            event_files = list(self._storage_dir.glob("events_*.jsonl"))
            
            # Combine data from all files
            all_events = []
            
            for file_path in event_files:
                with open(file_path, "r") as f:
                    for line in f:
                        try:
                            event = json.loads(line)
                            all_events.append(event)
                        except Exception as e:
                            logger.warning(f"Error parsing event from {file_path}: {e}")
            
            # Sort events by timestamp
            all_events.sort(key=lambda e: e["timestamp"])
            
            # Write combined data
            with open(output_path, "w") as f:
                json.dump(all_events, f, indent=2)
            
            logger.info(f"Exported {len(all_events)} events to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting analytics data: {e}")
            return False
