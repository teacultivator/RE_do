from typing import Dict, Optional
from graph.state import State
from trans_agents.API_helper import get_trains_from_api
from datetime import datetime


def format_train_route(route: Dict) -> Dict:
    """Format a single train route for display and storage with enhanced fare handling."""
    if not route or not isinstance(route, dict):
        return {}
        
    try:
        segments = route.get("segments", [])
        if not isinstance(segments, list):
            segments = []
            
        first_segment = segments[0] if segments else {}
        last_segment = segments[-1] if segments else {}
        
        # Extract fare information with better formatting
        total_fare = route.get("total_fare")
        fare_display = route.get("fare_display", "Fare not available")
        fare_currency = route.get("fare_currency", "")
        
        # If we have numeric fare but no display string, format it
        if total_fare and isinstance(total_fare, (int, float)) and total_fare > 0 and not fare_display:
            fare_display = f"{fare_currency} {total_fare:,.2f}".strip()
        
        return {
            "train_name": first_segment.get("bus_name", "Unknown Train").replace("Bus", "Train"),
            "departure_time": str(first_segment.get("departure_time", "")),
            "arrival_time": str(last_segment.get("arrival_time", "")),
            "departure_station": str(first_segment.get("departure_stop", "")),
            "arrival_station": str(last_segment.get("arrival_stop", "")),
            "duration": str(route.get("total_duration", "")),
            "distance_km": float(route.get("distance_km", 0.0)),
            "total_fare": total_fare if total_fare is not None else 0.0,
            "fare_display": fare_display,
            "fare_currency": fare_currency,
            "total_transfers": int(route.get("total_transfers", 0)),
            "num_segments": len(segments),
            "transport_type": "train",
            "details": route  # Keep full details in case they're needed
        }
    except Exception as e:
        print(f"⚠️ Error formatting train route: {str(e)}")
        return {}


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
        state["train_options"] = formatted_routes  # Store just the list of routes
        state["train_metadata"] = {  # Store metadata separately
            "origin": origin,
            "destination": destination,
            "departure_time": departure_time.isoformat(),
            "last_updated": datetime.now().isoformat()
        }
        
        print(f"✅ Found {len(formatted_routes)} train routes")
        return {
            "train_options": formatted_routes,
            "train_metadata": state["train_metadata"],
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
