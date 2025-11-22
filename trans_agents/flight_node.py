from typing import Dict
from graph.state import State
from trans_agents.API_helper import get_access_token, search_flights
from graph.state import State
from typing import Dict #, Any

def flight_node(state: State) -> Dict:
    """
    Flight search agent that integrates with the main workflow.
    Searches for flights and returns results with proper state management.
    """

    try:
        print(f"\nSearching for flights from {state['origin']} to {state['destination']} on {state['date']}...")

        token = get_access_token()
        results = search_flights(
            state["origin"], state["origin_country"], state["destination"],state["destination_country"], state["date"], token
        )
        state["flight_options"] = results
    except Exception as e:
        error_msg = f" Error searching for flights: {str(e)}"
        print(f"\n{error_msg}")

        state["flight_options"] = []


    return {
        "flight_options": state.get("flight_options") or [],
        "needs_refresh": False,
    }
