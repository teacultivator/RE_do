from typing import Dict, List, Optional
from graph.state import State
from trans_agents.API_helper import get_buses_from_api
from datetime import datetime


def format_bus_route(route: Dict) -> Dict:
    """Format a single bus route for display and storage with enhanced fare handling."""
    if not route or not isinstance(route, dict):
        return {}
        
    try:
        segments = route.get("segments", [])
        if not isinstance(segments, list):
            segments = []
            
        first_segment = segments[0] if segments else {}
        last_segment = segments[-1] if segments else {}
        
        # Extract fare information with better formatting
        total_fare = route.get("total_fare", "")
        if not total_fare or total_fare == "0" or total_fare == "0.0":
            total_fare = "Fare not available"
        elif isinstance(total_fare, (int, float)):
            total_fare = f"₹{total_fare:,.2f}"  # Format as currency
        
        # Extract fare currency if available
        fare_currency = ""
        if isinstance(route.get("fare_currency"), str):
            fare_currency = route["fare_currency"]
        
        return {
            "bus_name": str(first_segment.get("bus_name", "Unknown Bus")),
            "departure_time": str(first_segment.get("departure_time", "")),
            "arrival_time": str(last_segment.get("arrival_time", "")),
            "departure_stop": str(first_segment.get("departure_stop", "")),
            "arrival_stop": str(last_segment.get("arrival_stop", "")),
            "total_fare": total_fare,
            "fare_currency": fare_currency,
            "total_transfers": int(route.get("total_transfers", 0)),
            "num_segments": len(segments),
            "distance_km": float(route.get("distance_km", 0.0)),
            "transport_type": "bus",
            "details": route  # Keep full details in case they're needed
        }
    except Exception as e:
        print(f"⚠️ Error formatting bus route: {str(e)}")
        return {}


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
        
        # Process and store only essential information in state
        routes = results.get("routes", [])
        formatted_routes = [format_bus_route(route) for route in routes]
        
        # Store in state
        state["bus_options"] = formatted_routes  # Store just the list of routes
        state["bus_metadata"] = {  # Store metadata separately
            "origin": origin,
            "destination": destination,
            "departure_time": departure_time.isoformat(),
            "last_updated": datetime.now().isoformat()
        }
        
        print(f"✅ Found {len(formatted_routes)} bus routes")
        return {
            "bus_options": formatted_routes,
            "bus_metadata": state["bus_metadata"],
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
