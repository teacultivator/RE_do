import os, requests, time, re, json
from datetime import datetime, date
import google.generativeai as genai
from dotenv import load_dotenv, find_dotenv
import pandas as pd
from ast import literal_eval
from dateutil.relativedelta import relativedelta

try:
    env_path = find_dotenv()
    load_dotenv(env_path if env_path else None)
except Exception:
    pass

API_KEY = os.getenv("AMADEUS_API_KEY")
API_SECRET = os.getenv("AMADEUS_API_SECRET")

print(API_KEY, API_SECRET)

ACCESS_TOKEN = None
TOKEN_EXPIRY = 0

# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# AIRPORTS_FILE = os.path.join(BASE_DIR, "Airports1.csv")

# COMMON_AIRPORTS = {
#     'paris': 'CDG',
#     'london': 'LON',
#     'new york': 'NYC',
#     'los angeles': 'LAX',
#     'tokyo': 'NRT', 
#     'madrid': 'MAD',
#     'barcelona': 'BCN',
#     'rome': 'FCO',
#     'amsterdam': 'AMS',
#     'frankfurt': 'FRA',
#     'munich': 'MUC',
#     'berlin': 'BER',
#     'vienna': 'VIE',
#     'zurich': 'ZRH',
#     'geneva': 'GVA'
# }

# try:
#     _airports_df = pd.read_csv(AIRPORTS_FILE)
#     if 'City' in _airports_df.columns and 'IATA_Code' in _airports_df.columns:
#         _airports_df = _airports_df[["City", "IATA_Code"]].dropna()
#     elif 'city' in _airports_df.columns and 'iata_code' in _airports_df.columns:
#         _airports_df = _airports_df[["city", "iata_code"]].dropna()
#         _airports_df = _airports_df.rename(columns={"city": "City", "iata_code": "IATA_Code"})
#     elif 'CITY' in _airports_df.columns and 'IATA' in _airports_df.columns:
#         _airports_df = _airports_df[["CITY", "IATA"]].dropna()
#         _airports_df = _airports_df.rename(columns={"CITY": "City", "IATA": "IATA_Code"})
    
#     _airports_df["City"] = _airports_df["City"].str.strip().str.lower()
#     print(f"Loaded {len(_airports_df)} airport codes from CSV")
    
# except Exception as e:
#     print(f"Error loading airports CSV: {e}")
#     _airports_df = pd.DataFrame(columns=["City", "IATA_Code"])

# def validate_date(date_str: str) -> tuple[bool, str]:
#     try:
#         flight_date = datetime.strptime(date_str, "%Y-%m-%d").date()
#         today = date.today()
        
#         if flight_date < today:
#             days_diff = (today - flight_date).days
#             return False, f"Date {date_str} is {days_diff} days in the past"
        
#         max_days_ahead = 330
#         if (flight_date - today).days > max_days_ahead:
#             return False, f"Date {date_str} is too far in the future"
            
#         return True, ""
        
#     except ValueError as e:
#         return False, f"Invalid date format '{date_str}'"

def get_access_token():
    global ACCESS_TOKEN, TOKEN_EXPIRY
        
    if ACCESS_TOKEN and time.time() < TOKEN_EXPIRY:
        return ACCESS_TOKEN
 
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": API_KEY,
        "client_secret": API_SECRET
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
    try:
        if not API_KEY or not API_SECRET:
            missing = []
            if not API_KEY:
                missing.append("AMADEUS_API_KEY")
            if not API_SECRET:
                missing.append("AMADEUS_API_SECRET")
            raise Exception(f"Missing environment variables: {', '.join(missing)}. Ensure they are set in your .env or environment.")

        response = requests.post(url, data=data, headers=headers, timeout=10)
        if response.status_code != 200:
            try:
                err_body = response.json()
            except Exception:
                err_body = {"raw": response.text}
            raise Exception(f"Failed to generate access token: {response.status_code} - {err_body}")
        
        data = response.json()
        ACCESS_TOKEN = data["access_token"]
        TOKEN_EXPIRY = time.time() + int(data["expires_in"]) - 20 # 20 sec buffer
        
        return ACCESS_TOKEN
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network error while getting access token: {e}")

# def _get_iata_from_city(city: str) -> str:
#     if not city:
#         raise ValueError("City name is required")
    
#     city_norm = city.strip().lower()
    
#     exact_match = _airports_df[_airports_df["City"].str.lower() == city_norm]
#     if not exact_match.empty:
#         return exact_match.iloc[0]["IATA_Code"]
    
#     partial_match = _airports_df[_airports_df["City"].str.contains(city_norm, na=False)]
#     if not partial_match.empty:
#         return partial_match.iloc[0]["IATA_Code"]
    
#     if city_norm in COMMON_AIRPORTS:
#         return COMMON_AIRPORTS[city_norm]
    
#     available_cities = _airports_df["City"].str.title().tolist()[:15]
#     raise ValueError(f"No IATA code found for city: '{city}'")

# def _is_iata_code(value: str) -> bool:
#     return bool(re.fullmatch(r"[A-Z]{3}", value or ""))

def ensure_future_date(d: date, today:date):
    # if (d < d.today()):
    #     d.year = datetime.now().year 
    # if (d < d.today()):
    #     return d + relativedelta(years=1)
    # else: 
    if (d.month < today.month or d.month==today.month and d.day<today.day):
        d = d.replace(year = today.year + 1)
    else:
        d = d.replace(year = today.year)
    return d
    

def search_flights(origin_city: str, destination_city: str, date: str, token: str) -> list:
    # is_valid_date, date_error = validate_date(date)
    # if not is_valid_date:
    #     return (
    #         (str(), dict()),
    #         {
    #         "error": "INVALID_DATE",
    #         "message": date_error,
    #         "data": []
    #         }
    #     )

    load_dotenv()

    genai.configure(api_key = os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel("gemini-2.5-flash")

    # flight_offers_search_get_params = [
    # "originLocationCode",       # IATA code for origin (city or airport), e.g. "DEL".
    # "destinationLocationCode",  # IATA code for destination (city or airport), e.g. "BKK".
    # "departureDate",            # Outbound date in YYYY-MM-DD (required for a one-way/search leg).
    # "returnDate",               # Return date in YYYY-MM-DD (for round-trip searches).
    # "adults",                   # Number of adult passengers (age 12+).
    # "children",                 # Number of child passengers (age 2–11).
    # "infants",                  # Number of infants (age 0–2).
    # "travelClass",              # Cabin class: ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST.
    # "includedAirlineCodes",     # Comma-separated airline IATA codes to include (e.g. "AI,EK").
    # "excludedAirlineCodes",     # Comma-separated airline IATA codes to exclude.
    # "nonStop",                  # true/false — restrict results to nonstop flights only.
    # "currencyCode",             # Preferred currency for prices (ISO 4217 code, e.g. "USD").
    # "maxPrice",                 # Max price filter (decimal), total price per traveler.
    # "max"                       # Maximum number of flight offers to return (limit).
    # ]

    # prompt = f"""
    # You are a data filtering agent used by a flights booking agency. Given a user query, you need to generate the filter condition matching user query text.
    # Filter condition example: origin=city1 && destination=city2 && stops=0 && preferred_time>18:00 && travelClass=Business
    # Here is the complete set of standard parameters: {flight_offers_search_get_params}
    # Then, compare your filter condition with the standard parameters list.
    # Whichever parameters from the standard parameters list semantically appear in the filter condition, include them in a python dictionary (dict) with their value equalt to the value obtained in the filter condition.
    # Return a python tuple of the form: ((fliter_condition_python_str, params_python_dict)). Strictly do not include any markdown.
    # Example-1:
    # User query: Find me nonstop first class early morning flights from Zurich to Delhi on 23 November 2025.
    # Filter condition (python string): "origin=ZRH && destination=DEL && stops=0 && preferred_time>=5:00 && preferred_time<=8:00 && travelClass=FIRST"
    # python dictionary: {{
    #     "originLocationCode": "ZRH", # IATA code for origin (city or airport)
    #     "destinationLocationCode": "DEL", # IATA code for destination (city or airport), e.g. "BKK".
    #     "departureDate": "2025-11-23", # Outbound date in YYYY-MM-DD (required for a one-way/search leg).
    #     "adults": 1 # Number of adult passengers (age 12+).
    #     "nonStop": "true", # true/false — restrict results to nonstop flights only.
    #     "travelClass": "FIRST", # Cabin class: ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST.
    # }}
    # Example-2:
    # User query: Find me quickest flights from Bangalore to New York on 31 December 2025 for 2 adults.
    # Filter condition (python string): "origin=city1 && destination=city2 && sort_criteria=duration" # Here sort_criteria is important, but it was not important in Example-1
    # python dictionary: {{
    #     "originLocationCode": "BLR", # IATA code for origin (city or airport)
    #     "destinationLocationCode": "NYC", # IATA code for destination (city or airport), e.g. "BKK".
    #     "departureDate": "2025-12-31", # Outbound date in YYYY-MM-DD (required for a one-way/search leg).
    #     "adults": 2 # Number of adult passengers (age 12+).
    # }}
    # Note that originLocationCode, destinationLocationCode, departureDate and adults fields are mandatory in this dictionary.
    # originLocationCode and destinationLocationCode must be in their respective IATA codes. Prefer city IATA codes instead of sticking to a particular airport. For example, for London, use "LON" instead of "LHR".
    # Now your task begins:
    # User query: {user_query}
    # Strictly do not include any markdown.
    # """

    # prompt = f"""
    # You are a data filtering agent used by a flights booking agency. Given a user query, you need to generate the filter condition matching user query text.
    # Filter condition example (python string): "origin=city1 && destination=city2 && stops=0 && preferred_time>18:00 && travelClass=Business"
    # Here is the complete set of standard parameters: {flight_offers_search_get_params}
    # Then, compare your filter condition with the standard parameters list.
    # Whichever parameters from the standard parameters list semantically appear in the filter condition, include them in a python dictionary (dict) with their value equal to the value obtained in the filter condition, and remove those parameters from the filter condition.
    # Example-1:
    # User query: Find me nonstop first class early morning flights from Zurich to Delhi on 23 November 2025.
    # Initial filter condition generated(python string): "origin=ZRH && destination=DEL && stops=0 && preferred_time>=5:00 && preferred_time<=8:00 && travelClass=FIRST"
    # python dictionary: {{
    #     "originLocationCode": "ZRH", # IATA code for origin (city or airport)
    #     "destinationLocationCode": "DEL", # IATA code for destination (city or airport), e.g. "BKK".
    #     "departureDate": "2025-11-23", # Outbound date in YYYY-MM-DD (required for a one-way/search leg).
    #     "adults": 1 # Number of adult passengers (age 12+).
    #     "nonStop": "true", # true/false — restrict results to nonstop flights only.
    #     "travelClass": "FIRST", # Cabin class: ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST.
    # }}
	# Final Filter Condition (python string): "preferred_time>=5:00 && preferred_time<=8:00" # for early morning flights
    # Example-2:
    # User query: Find me quickest flights from Bangalore to New York on 31 December 2025 for 2 adults. I prefer check-in luggage more than 30 kg.
    # Initial Filter condition (python string): "origin=city1 && destination=city2 && sort_criteria=duration && baggage>=30kg" # Here sort_criteria is important, but it was not important in Example-1.
    # python dictionary: {{
    #     "originLocationCode": "BLR", # IATA code for origin (city or airport)
    #     "destinationLocationCode": "NYC", # IATA code for destination (city or airport).
    #     "departureDate": "2025-12-31", # Outbound date in YYYY-MM-DD (required for a one-way/search leg).
    #     "adults": 2 # Number of adult passengers (age 12+).
    # }}
	# Final Filter condition (python string): "sort_criteria=duration && baggage>=30kg" 

    # Return a Python tuple of the form: ((final_updated_filter_condition_python_str, params_python_dict)). Strictly do not include any markdown.
    # Note that originLocationCode, destinationLocationCode, departureDate and adults fields are mandatory in this dictionary.
    # originLocationCode and destinationLocationCode must be in their respective IATA codes. Prefer city IATA codes instead of sticking to a particular airport. For example, for London, use "LON" instead of "LHR".
    # Now your task begins:
    # User query: {user_query}
    # Strictly do not include any markdown.
    # """

    prompt1 = f"""
    You are a helpful Flight Agency Assistant.
    Return only a tuple of IATA city codes. Input will be a tuple of 2 city names: (origin_city, destination_city).
    For each city name, identify the correct IATA city code. If the city has multiple airports, return the unified city code instead of individual airport codes.
    Output format must be a python tuple: (IATA_origin, IATA_destination).
    Do not add explanations, descriptions, markdown, or extra text.
    Your task: {(origin_city, destination_city)}
    Examples:
    input: (Mumbai, London) ->  output: (BOM, LON) # Here IATA code corresponding to London must be LON and not LHR.
    input: (Dubai, Zurich) ->  output: (DXB, ZRH)
    """

    # start = time.time()
    codes = model.generate_content(prompt1).text
    # # end = time.time()
    # llm_latency1 = end - start
    print(codes)
    codes = literal_eval(codes)

    try:
        try:
            # params = filter[1]
            # dep_date = params.get("departureDate")
            # from datetime import date
            # dep_date = datetime.strptime(dep_date, "%Y-%m-%d").date()
            today = date.today()
            if (date < today):
                date = ensure_future_date(date, today)
                # params["departureDate"] = .strftime("%Y-%m-%d")
            #         today = date.today()

            #         # Increment year until date is in the future
            #         while dep_date < today:
            #             dep_date = dep_date.replace(year=dep_date.year + 1)

            #         # Update the params dict
            #         params["departureDate"] = dep_date.strftime("%Y-%m-%d")
            # except Exception as e:
            #     print("⚠️ Error normalizing departure date:", e)
        except Exception as e:
            print("Error while updating date: ", str(e))
            # print("While creating params, an exception occured.",e,sep='\n')
            # try:
            #     origin_code = origin_city if _is_iata_code(origin_city) else _get_iata_from_city(origin_city)
            #     destination_code = destination_city if _is_iata_code(destination_city) else _get_iata_from_city(destination_city)
            # except ValueError as e:
            #     try: filterCond = filter[0]
            #     except Exception: filterCond = str()
            #     return (
            #         filterCond,
            #         []
            #     )
        params = {
            "originLocationCode": codes[0],
            "destinationLocationCode": codes[1],
            "departureDate": date,
            "adults": 1
        }
        url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
        
        print("Parameters before API call:",params,sep='\n')
        headers = {"Authorization": f"Bearer {token}"}

        # start_time = time.time()
        response = requests.get(url, params=params, headers=headers, timeout=90)
        # end_time = time.time()
        # api_latency = end_time - start_time
        # print("Amadeus API latency:",api_latency,"sec",end="\n\n\n")

        # with open("AmadeusAPILatency.txt", "a") as fp:
        #     fp.write(f"User query: {user_query}\nAPI Latency: {end_time-start_time}\n")

        result = response.json()
        print("Number of flight offers returned by Amadeus:", len(result["data"]), end="\n\n")
        # print(result)
        # with open("AmadeusAPIResults.json", "w") as fp:
        #     json.dump(result, fp, indent=2)

        if response.status_code != 200:
            error_msg = "Unknown API error"
            if "errors" in result and result["errors"]:
                error = result["errors"][0]
                error_msg = f"{error.get('title', '')}: {error.get('detail', '')}"
            
            # return (
            #     filter[0],
            #     # {
            #     # "error": f"API_ERROR_{response.status_code}",
            #     # "message": error_msg,
            #     # "data": []
            #     # },
            #     [],
            #     api_latency,
            #     llm_latency1
            # )
            return []
            
        # return (filter[0], result["data"], api_latency, llm_latency1)
        return result["data"]
        
    except Exception as e:
        print(f"An exception occured during/after the API call: {str(e)}")
        # return (
        #     filter[0],
        #     # {
        #     # "error": "SEARCH_ERROR",
        #     # "message": str(e),
        #     # "data": []
        #     # },
        #     [],
        #     api_latency, 
        #     llm_latency1
        # )
        return []