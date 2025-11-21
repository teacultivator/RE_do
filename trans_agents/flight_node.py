from typing import Dict
from graph.state import State
from trans_agents.API_helper import get_access_token, search_flights
from graph.state import State
# from langgraph.graph import StateGraph, END
# from trans_agents.LLM_helper import filter_and_extract_flights, print_flights_table
# from langchain_core.messages import AIMessage
from typing import Dict #, Any
# from time import time

def flight_node(state: State) -> Dict:
    # start_time = time()
    """
    Flight search agent that integrates with the main workflow.
    Searches for flights and returns results with proper state management.
    """
    # print(state)
    # messages = state.get("messages", [])
    
    # Use the original user query if available, else create a fallback
    # user_query = state.get("user_query", 
    #     f"Find me flights from {state['origin']} to {state['destination']} on {state['departure_date']}")

    try:
        print(f"\nSearching for flights from {state['origin']} to {state['destination']} on {state['departure_date']}...")
        
        # Get access token and search flights
        token = get_access_token()
        # filterCondition, results, api_latency, llm_latency1 = search_flights(
        #     user_query, state["origin"], state["destination"], state["departure_date"], token
        # )
        results = search_flights(
            state["origin"], state["destination"], state["departure_date"], token
        )
        state["flight_options"] = results
        # if results:
            # Call LLM for filtering + extraction
            # llm_output, llm_latency2 = filter_and_extract_flights(filterCondition, results)
            
            # Store processed results in state
            # flight_results = llm_output.get("filtered_results", [])
            
            # Print summary + results table to console
            # print("\n✈️ Gemini Summary:")
            # print(llm_output.get("summary", "Flight search completed"))
            # print("\n📊 Flight Results:")
            # print_flights_table(flight_results)
            
            # Create response message for the chat
            # if flight_results:
        #     response_msg = f" Found {len(flight_results)} flights from {state['origin']} to {state['destination']} on {state['departure_date']}. Check the console for detailed flight information."
        # else:
        #     response_msg = f" No suitable flights found from {state['origin']} to {state['destination']} on {state['departure_date']}."
            
            # Return updated state with results
            # end_time = time()
            # total_time = end_time - start_time
            # with open("flight_agent_log.txt", "a") as f:
            #     f.write(f"\nUser query: {user_query}\nFilter Condition: {filterCondition}\nRun completed in {total_time} sec.\nAPI Latency: {api_latency}\nLLM Latency: {llm_latency1+llm_latency2}")
            # print(f"Total time taken: {total_time} sec")

        #     return {
        #         **state,
        #         "flight_results": flight_results,
        #         "messages": messages + [AIMessage(content=response_msg)],
        #         "next_agent": "end",
        #         "needs_user_input": False
        #     }
            
        # else:
        #     response_msg = f" No flights found from {state['origin']} to {state['destination']} on {state['departure_date']}."
        #     print(f"\n{response_msg}")

        #     end_time = time()
        #     total_time = end_time - start_time
        #     with open("flight_agent_log.txt", "a") as f:
        #         f.write(f"\nUser query: {user_query}\nFilter Condition: {filterCondition}\nRun completed in {total_time} sec.\nAPI Latency: {api_latency}\nLLM Latency: {llm_latency1+llm_latency2}")
        #     # print(f"Total time taken: {total_time} sec")

        #     return {
        #         **state,
        #         "flight_results": [],
        #         "messages": messages + [AIMessage(content=response_msg)],
        #         "next_agent": "end",
        #         "needs_user_input": False
            # }

    except Exception as e:
        error_msg = f" Error searching for flights: {str(e)}"
        print(f"\n{error_msg}")
        # end_time = time()
        # total_time = end_time - start_time
        # with open("flight_agent_logs.txt", "a") as f:
        #     f.write(f"\nUser query: {user_query}\nFilter Condition: {filterCondition}\nRun completed in {total_time} sec.\nAPI Latency: {api_latency}\nLLM Latency: {llm_latency1+llm_latency2}")
        # print(f"Total time taken: {total_time} sec")
    
        # return {
        #     **state,
        #     "flight_results": [],
        #     "messages": messages + [AIMessage(content=error_msg)],
        #     "next_agent": "end",
        #     "needs_user_input": False
        # }

        state["flight_options"] = []


    return {
        "flight_options": state.get("flight_options") or [],
        "needs_refresh": False,
    }
