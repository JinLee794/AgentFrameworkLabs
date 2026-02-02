"""AG-UI server with backend tool rendering."""

import os
from typing import Annotated, Any

from agent_framework import ChatAgent, tool
from agent_framework.azure import AzureOpenAIChatClient
from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint
from azure.identity import AzureCliCredential
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()

# Define function tools
@tool
def get_weather(
    location: Annotated[str, Field(description="The city to get weather for")],
) -> str:
    """Get the current weather for a location."""
    weather_data = {
        "Seattle": {"temp": 18, "condition": "Cloudy", "humidity": 75},
        "San Francisco": {"temp": 22, "condition": "Sunny", "humidity": 60},
        "New York": {"temp": 25, "condition": "Partly cloudy", "humidity": 65},
        "London": {"temp": 15, "condition": "Rainy", "humidity": 85},
    }
    data = weather_data.get(location, {"temp": 20, "condition": "Unknown", "humidity": 50})
    return f"Weather in {location}: {data['condition']}, {data['temp']}°C, {data['humidity']}% humidity"


@tool
def search_restaurants(
    location: Annotated[str, Field(description="The city to search in")],
    cuisine: Annotated[str, Field(description="Type of cuisine")] = "any",
) -> dict[str, Any]:
    """Search for restaurants in a location."""
    return {
        "location": location,
        "cuisine": cuisine,
        "results": [
            {"name": "The Golden Fork", "cuisine": cuisine if cuisine != "any" else "Italian", "rating": 4.5, "price": "$$"},
            {"name": "Spice Haven", "cuisine": "Indian", "rating": 4.7, "price": "$$"},
            {"name": "Green Leaf", "cuisine": "Vegetarian", "rating": 4.3, "price": "$"},
        ]
    }


# Read configuration (deferred validation for DevUI discovery)
endpoint = os.environ.get("PROJECT_ENDPOINT")
deployment_name = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-4o")

chat_client = None
agent = None

if endpoint:
    chat_client = AzureOpenAIChatClient(
        credential=AzureCliCredential(),
        endpoint=endpoint,
        deployment_name=deployment_name,
    )

    # Create agent with tools
    agent = ChatAgent(
        name="TravelAssistant",
        instructions="""You are a helpful travel assistant. Use the available tools to help users:
        - Check weather conditions at destinations
        - Find restaurants by location and cuisine type

        Be friendly and provide helpful recommendations based on the data you gather.""",
        chat_client=chat_client,
        tools=[get_weather, search_restaurants],
    )

# Create FastAPI app with CORS for web clients
app = FastAPI(title="AG-UI Travel Assistant")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the AG-UI endpoint (only if agent is configured)
if agent:
    add_agent_framework_fastapi_endpoint(app, agent, "/")

if __name__ == "__main__":
    if not endpoint:
        raise ValueError("PROJECT_ENDPOINT environment variable is required")
    import uvicorn
    print("Starting AG-UI server at http://127.0.0.1:8888")
    uvicorn.run(app, host="127.0.0.1", port=8888)