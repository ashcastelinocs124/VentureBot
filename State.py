from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict
from schema import IdeaItem, Validator_Agent_Schema


@dataclass
class AgentState:


    # User information
    user_preferences: Optional[str] = None
    experience: Optional[str] = None

    #General
    mode: Optional[str] = None
    user_query : Optional[str] = None
    previous_answer : Optional[str] = None

    # Output from Idea Generator
    Idea: List[IdeaItem] = field(default_factory=list)

    # Validation state
    selected_idea_number: Optional[int] = None
    validation_results: Optional[Dict] = field(default_factory=dict)

    # Product Management State
    prd: Optional[Any] = None

    prompt_text : Optional[Any] = None

    classification : Optional[str] = None
