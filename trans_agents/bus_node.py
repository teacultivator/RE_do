from typing import Dict, List, Optional
from graph.state import State
from trans_agents.API_helper import get_buses_from_api
from datetime import datetime

def bus_node(state: State) -> Dict:
    """
    Bus search agent that integrates with the main workflow.
    Searches for bus routes and returns results with proper state management.
    """
    try:
        origin = state.get("origin", "")
        destination = state.get("destination", "")
        
        if not origin or not destination:
            raise ValueError("Origin and destination are required")
            
        print(f"\n🚍 Searching for buses from {origin} to {destination}...")

        # Convert date string to datetime object
        departure_time = datetime.strptime(state.get('date', datetime.now().strftime('%Y-%m-%d')), '%Y-%m-%d')
        
        # Call the bus API helper function
        results = get_buses_from_api(
            origin=origin,
            destination=destination,
            date_time=departure_time
        )
        state["bus_options"] = results  # Store just the list of routes
        print(f"✅ Found {len(results)} bus routes")
        return {
            "bus_options": results,
            "needs_refresh": False,
        }
        
    except Exception as e:
        error_msg = f"❌ Error searching for buses: {str(e)}"
        print(f"\n{error_msg}")
        state["bus_error"] = str(e)
        state["bus_options"] = []  # Empty list on error
        
        return {
            "bus_options": [],
            "bus_error": str(e),
            "needs_refresh": False,
        }
