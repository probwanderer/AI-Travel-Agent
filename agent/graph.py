from langgraph.graph import StateGraph, END
from .state import TravelState
from .nodes import planner_node, researcher_node, drafter_node, validator_node

def should_continue(state: TravelState):
    """Decides whether to finish or likely loop back."""
    # If we have a critique and haven't looped too many times, go back to planner
    # For simplicity in this demo, if critique is present, we loop back to Planner to re-plan
    # taking into account the feedback.
    
    if state.get("final_itinerary"):
        return END
    
    if state["revision_number"] > 3:
        # Avoid infinite loops
        return END
        
    return "planner"

# Build the Graph
workflow = StateGraph(TravelState)

# Add Nodes
workflow.add_node("planner", planner_node)
workflow.add_node("researcher", researcher_node)
workflow.add_node("drafter", drafter_node)
workflow.add_node("validator", validator_node)

# Set Entry Point
workflow.set_entry_point("planner")

# Add Edges
workflow.add_edge("planner", "researcher")
workflow.add_edge("researcher", "drafter")
workflow.add_edge("drafter", "validator")

# Conditional Edge from Validator
workflow.add_conditional_edges(
    "validator",
    should_continue,
    {
        "planner": "planner",
        END: END
    }
)

# Compile
app = workflow.compile()
