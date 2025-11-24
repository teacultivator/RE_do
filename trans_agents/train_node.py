from typing import Dict, Optional
from graph.state import State
from trans_agents.API_helper import get_trains_from_api
from datetime import datetime

def train_node(state: State) -> Dict:
    """
    Train search agent that integrates with the main workflow.
    Searches for train routes and returns results with proper state management.
    """
    try:
        origin = state.get("origin", "")
        destination = state.get("destination", "")
        
        if not origin or not destination:
            raise ValueError("Origin and destination are required for train search")
            
        print(f"\n🚆 Searching for trains from {origin} to {destination}...")

        # Convert date string to datetime object
        departure_time = datetime.strptime(
            state.get('date', datetime.now().strftime('%Y-%m-%d')), 
            '%Y-%m-%d'
        )
        
        # Call the train API helper function
        results = get_trains_from_api(
            origin=origin,
            destination=destination,
            date_time=departure_time
        )
        state["train_options"] = results  # Store just the list of routes
        
        print(f"✅ Found {len(results)} train routes")
        return {
            "train_options": results,
            "needs_refresh": False,
        }
        
    except Exception as e:
        error_msg = f"❌ Error searching for trains: {str(e)}"
        print(f"\n{error_msg}")
        state["train_error"] = str(e)
        state["train_options"] = []  # Empty list on error
        
        return {
            "train_options": [],
            "train_error": str(e),
            "needs_refresh": False,
        }
