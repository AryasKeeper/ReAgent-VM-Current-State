"""
API router for agent-related endpoints.
"""

from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from reagent.agents.base import AgentRole

router = APIRouter()

class AgentStatus(BaseModel):
    name: str
    role: AgentRole
    status: str
    version: str

@router.get("/", response_model=List[AgentStatus])
async def list_agents():
    """List all available agents and their status."""
    # In a real application, this would query a service that tracks agent status.
    # For now, we'll return a static list.
    return [
        {
            "name": "Listing Watcher AU",
            "role": AgentRole.DATA_COLLECTOR,
            "status": "active",
            "version": "1.0.0"
        },
        {
            "name": "Suburb Signal Agent",
            "role": AgentRole.ANALYZER,
            "status": "active",
            "version": "1.0.0"
        },
        {
            "name": "Buyer Matchmaker AU",
            "role": AgentRole.MATCHER,
            "status": "active",
            "version": "1.0.0"
        },
        {
            "name": "Seller Strategy Agent",
            "role": AgentRole.STRATEGIST,
            "status": "active",
            "version": "1.0.0"
        },
        {
            "name": "Off-Market Radar AU",
            "role": AgentRole.ANALYZER,
            "status": "inactive",
            "version": "1.0.0"
        },
        {
            "name": "Agent Whisperer",
            "role": AgentRole.COMMUNICATOR,
            "status": "inactive",
            "version": "1.0.0"
        }
    ]

@router.get("/{agent_name}", response_model=AgentStatus)
async def get_agent(agent_name: str):
    """Get the status of a specific agent."""
    agents = await list_agents()
    for agent in agents:
        if agent["name"] == agent_name:
            return agent
    raise HTTPException(status_code=404, detail="Agent not found")
