import streamlit as st
from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool
import os
import requests
import re
import warnings
from geopy.distance import geodesic
from streamlit_extras.stylable_container import stylable_container
 
warnings.filterwarnings("ignore", category=UserWarning)
 
# API Keys
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
OPENROUTE_API_KEY = os.getenv("OPENROUTE_API_KEY", "")

if not all([GOOGLE_API_KEY, SERPER_API_KEY, OPENROUTE_API_KEY]):
    st.error("❌ One or more API keys are missing. Please set them in your environment.")
    st.stop()
 
# Setup tools
search_tool = SerperDevTool()
llm = LLM(model="gemini/gemini-1.5-flash", verbose=True, temperature=0.5, api_key=os.environ["GOOGLE_API_KEY"])
 
st.set_page_config(page_title="Smart Travel Planner", page_icon="🧳", layout="wide")
st.title("🧳 Smart Travel Planner")
st.markdown("Plan your dream vacation with an optimized budget, itinerary, stay recommendations, and booking links!")
 
# Input UI
with st.form(key="travel_form"):
    starting_point = st.text_input("Starting Point (e.g., Hyderabad)")
    destination = st.text_input("Destination (e.g., Warangal or New York)")
    transport_mode = st.selectbox("Preferred Mode of Transport", ["Flight", "Train", "Bus", "Car", "Bike"])
    budget_inr = st.number_input("Budget (₹)", min_value=0, step=1000, format="%d")
    days = st.number_input("Number of Vacation Days", min_value=1, max_value=30, step=1)
    submit_button = st.form_submit_button(label="Plan My Trip")
 
# Function: Get Distance and Duration
def get_distance_km(from_city, to_city, mode):
 
    geocode_url = "https://api.openrouteservice.org/geocode/search"
    headers = {"Authorization": OPENROUTE_API_KEY}
 
    from_coords = requests.get(geocode_url, params={"api_key": OPENROUTE_API_KEY, "text": from_city}).json()
    to_coords = requests.get(geocode_url, params={"api_key": OPENROUTE_API_KEY, "text": to_city}).json()
 
    try:
        from_loc = from_coords["features"][0]["geometry"]["coordinates"]
        to_loc = to_coords["features"][0]["geometry"]["coordinates"]
    except:
        return None, None
 
    # For flight, use geodesic distance (straight-line)
    if mode == "Flight":
        distance = round(geodesic((from_loc[1], from_loc[0]), (to_loc[1], to_loc[0])).km, 1)
        duration = round(distance / 800, 1)  # Average flight speed is ~800 km/h
        return distance, duration
 
    transport_map = {
        "Car": "driving-car",
        "Bike": "cycling-regular",
        "Bus": "driving-hgv",
        "Train": "driving-car"
    }
 
    if mode not in transport_map:
        return None, None
 
    route_url = f"https://api.openrouteservice.org/v2/directions/{transport_map[mode]}"
    params = {"start": f"{from_loc[0]},{from_loc[1]}", "end": f"{to_loc[0]},{to_loc[1]}"}
    response = requests.get(route_url, params=params, headers=headers).json()
 
    try:
        meters = response["features"][0]["properties"]["segments"][0]["distance"]
        duration = response["features"][0]["properties"]["segments"][0]["duration"] / 3600  # Convert to hours
        return round(meters / 1000, 1), round(duration, 1)
    except:
        return None, None
 
# Handle submission
# Handle submission
if submit_button:
    if starting_point and destination and budget_inr > 0 and days > 0:
        st.success(f"✅ Your Travel Budget: ₹{budget_inr}")
        distance_km,duration= get_distance_km(starting_point, destination, transport_mode)
 
        if distance_km is None:
            st.error("❌ Could not determine route distance. Please check the city names or try a different mode.")
            st.stop()
 
        st.markdown(f"🛣️ **Distance between cities**: {distance_km} km via {transport_mode}")
        st.markdown(f"⏱️ **Estimated Duration**: {duration} hours") 
        # Estimate transport cost
        transport_cost = {
            "Flight": int(budget_inr * 0.3),
            "Train": int(budget_inr * 0.15),
            "Bus": int(budget_inr * 0.1),
            "Car": int(distance_km * 6),
            "Bike": int(distance_km * 2)
        }.get(transport_mode, 0)
 
        hotel_per_day = int(budget_inr * 0.2 / days)
        transport_per_day = int(budget_inr * 0.1 / days)
        food_per_day = int(budget_inr * 0.15 / days)
        misc_per_day = int(budget_inr * 0.1 / days)
 
        total_cost = transport_cost + days * (hotel_per_day + transport_per_day + food_per_day + misc_per_day)
        remaining_budget = budget_inr - total_cost
 
        with stylable_container(key="trip_summary", css_styles=""" .trip-summary { font-size: 18px; color: #333; } .link { color: #007bff; text-decoration: none; } """):
            st.markdown("### 💸 Budget Breakdown")
            st.markdown(f"""
            - 🚍 **Selected Transport**: {transport_mode}
            - 🛣️ **Approx Distance**: {distance_km} km
            - ⏱️ **Estimated Duration**: {duration} hours  
            - 💸 **Transport Cost Estimate**: ₹{transport_cost}
            - 🏨 **Hotel (per day)**: ₹{hotel_per_day} [Booking](https://www.booking.com)
            - 🍽️ **Food (per day)**: ₹{food_per_day} [Restaurants](https://www.google.com/maps/search/restaurants+in+{destination.replace(' ', '+')})
            - 🚇 **Local Transport (per day)**: ₹{transport_per_day}
            - 🛍️ **Miscellaneous (per day)**: ₹{misc_per_day}
            - 📆 **Total Days**: {days}
            - 💰 **Estimated Total Cost**: ₹{total_cost}
            - 🎯 **Remaining Budget**: ₹{remaining_budget if remaining_budget >= 0 else 'Over Budget! ⚠️'}
            """, unsafe_allow_html=True)
        # Show Flight booking link if transport mode is "Flight"
        if transport_mode == "Flight":
                flight_booking_url = f"https://www.google.com/flights?f=0&hl=en#flt={starting_point}.{destination}"
                st.markdown(f"✈️ **Book Your Flight**: [Click here to book your flight](https://www.google.com/flights?f=0&hl=en#flt={starting_point}.{destination})")
        # CrewAI agents
        researcher = Agent(
            role="Travel Researcher",
            goal=f"Find top attractions, public transport, weather, and hotels in {destination}.",
            backstory="Expert travel researcher with local knowledge.",
            verbose=True, memory=True, llm=llm, tools=[search_tool]
        )
 
        budget_planner = Agent(
            role="Budget Planner",
            goal=f"Create budget for a {transport_mode} trip from {starting_point} to {destination} under ₹{budget_inr}.",
            backstory="Finance and budget expert for travelers.",
            verbose=True, memory=True, llm=llm, tools=[search_tool]
        )
 
        itinerary_planner = Agent(
            role="Itinerary Planner",
            goal=f"Create a {days}-day itinerary for {destination}. Include food and activity recommendations.",
            backstory="Award-winning planner for efficient travel.",
            verbose=True, memory=True, llm=llm, tools=[search_tool]
        )
 
        # Tasks
        research_task = Task(
            description=f"List attractions, public transport options, local weather, and top 3 hotels in {destination}.",
            expected_output="Tourist spots, transport info, weather, and hotel suggestions.",
            tools=[search_tool],
            agent=researcher
        )
 
        budget_task = Task(
            description=f"Break down travel expenses for a {transport_mode} trip to {destination} for {days} days under ₹{budget_inr}.",
            expected_output="Cost split across transport, stay, food, and miscellaneous.",
            tools=[search_tool],
            agent=budget_planner
        )
 
        itinerary_task = Task(
            description=f"Design a {days}-day itinerary for {destination}. Include food and sightseeing.",
            expected_output="Day-by-day activities, places to eat, and fun ideas.",
            tools=[search_tool],
            agent=itinerary_planner
        )
 
        # Crew execution
        crew = Crew(
            agents=[researcher, budget_planner, itinerary_planner],
            tasks=[research_task, budget_task, itinerary_task],
            process=Process.sequential
        )
 
        with st.spinner("⏳ Planning your trip..."):
            try:
                result = crew.kickoff(inputs={
                    "starting_point": starting_point,
                    "destination": destination,
                    "budget": str(budget_inr),
                    "days": str(days),
                    "transport": transport_mode
                })
 
                st.success("🎉 Trip Planning Completed!")
                result_str = re.sub(r'\*\*(.*?)\*\*', r'**\1**', str(result))
                days_split = re.split(r'(?i)(Day\s*\d+[:\-]?)', result_str)
                combined_days = [days_split[i] + days_split[i+1] for i in range(1, len(days_split)-1, 2)] if len(days_split) > 2 else [result_str]
 
                for i, day_plan in enumerate(combined_days, 1):
                    st.markdown(f"### 📅 Day {i}")
                    st.markdown(day_plan.strip(), unsafe_allow_html=True)
 
                map_url = f"https://www.google.com/maps/embed/v1/place?key={os.environ['GOOGLE_API_KEY']}&q={destination.replace(' ', '+')}"
                st.markdown(f"### 🗺️ Map of {destination}")
                st.components.v1.iframe(map_url, height=400)
 
            except Exception as e:
                st.error(f"❌ Error during trip planning: {e}")
    else:
        st.warning("⚠️ Please complete all fields to generate your travel plan.")