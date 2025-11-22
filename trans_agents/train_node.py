from typing import Dict, Optional
from graph.state import State
from trans_agents.API_helper import get_trains_from_api
from datetime import datetime


def format_train_route(route: Dict) -> Dict:
    """Format a single train route for display and storage."""
    if not route:
        return {}
        
    segments = route.get("segments", [])
    first_segment = segments[0] if segments else {}
    last_segment = segments[-1] if segments else {}
    
    return {
        "train_name": first_segment.get("bus_name", "Unknown Train").replace("Bus", "Train"),
        "departure_time": first_segment.get("departure_time", ""),
        "arrival_time": last_segment.get("arrival_time", ""),
        "departure_station": first_segment.get("departure_stop", ""),
        "arrival_station": last_segment.get("arrival_stop", ""),
        "duration": route.get("duration", ""),
        "distance_km": route.get("distance_km", 0),
        "total_fare": route.get("total_fare", "Fare not available"),
        "total_transfers": route.get("total_transfers", 0),
        "num_segments": len(segments),
        "details": route  # Keep full details in case they're needed
    }


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
        
        # Process and store only essential information in state
        routes = results.get("routes", [])
        formatted_routes = [format_train_route(route) for route in routes]
        
        # Store in state
        state["train_search"] = {
            "origin": origin,
            "destination": destination,
            "departure_time": departure_time.isoformat(),
            "routes": formatted_routes,
            "last_updated": datetime.now().isoformat()
        }
        
        print(f"✅ Found {len(formatted_routes)} train routes")
        
    except Exception as e:
        error_msg = f"❌ Error searching for trains: {str(e)}"
        print(f"\n{error_msg}")
        state["train_error"] = str(e)
        state["train_search"] = {
            "routes": [],
            "error": str(e),
            "last_updated": datetime.now().isoformat()
        }

    return {
        "train_search": state.get("train_search", {"routes": []}),
        "needs_refresh": False,
    }
