from typing import TypedDict, List, Optional

class TravelState(TypedDict):
    request: str
    origin: str
    destination: str
    dates: str
    budget: str
    interests: List[str]
    
    # Internal agent state
    plan: List[str]             # List of search queries needed
    search_results: List[str]   # Raw search data
    draft: str                  # The generated itinerary
    critique: Optional[str]     # Feedback from validator
    revision_number: int        # Loop counter
    final_itinerary: str        # Final output
