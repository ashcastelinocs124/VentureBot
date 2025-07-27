from langchain.chat_models import init_chat_model
from langgraph.graph import StateGraph, START, END
from schema import Idea_Generation_Schema, Validator_Agent_Schema,ProductManagerSchema,MarketInsight,SonarInput,PromptEngineer,ManagerAgentSchema
from prompt import manager_agent_prompt, validator_prompt,product_manager_prompt,prompt_engineer_prompt,onboard_agent
from State import AgentState
from langchain.tools import StructuredTool, Tool
from tools import ask_sonar
from langchain.agents import create_openai_functions_agent
from langchain.agents import AgentExecutor
from langchain.memory import ConversationBufferMemory
import os
from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder, SystemMessagePromptTemplate
from langchain.agents import initialize_agent, AgentType
from pathlib import Path


load_dotenv()


#API Key
openai_api_key = os.getenv("OPENAI_API_KEY")

os.environ["OPENAI_API_KEY"] = openai_api_key

available_tools = [
    StructuredTool.from_function(
        name="Ask_Sonar",
        func=ask_sonar,
        description="Performs a validation search on the venture product. Requires title and description."
    ),
]

def manager_agent(state):
    """Acts more of a classification agent"""
    llm = init_chat_model("gpt-4o-2024-08-06", temperature=0.0, model_provider="openai")

    # Get the user's question
    user_query = state.user_query
    print("DEBUG: Processing query in manager_agent:", user_query)
    
    # Gather all available information
    ideas = getattr(state, 'Idea', [])
    idea_info = "\n".join([f"- {i+1}. {idea.title}: {idea.description}" for i, idea in enumerate(ideas)])
    
    # Format the prompt with all available information
    system_prompt = manager_agent_prompt.format(
        onboarding_agent=idea_info,  # Pass the formatted idea information
        previous_answer=getattr(state, 'previous_answer', "No previous answer"),
        validator_agent=getattr(state, 'validation_results', "No validation yet"),
        product_manager_agent=getattr(state, 'prd', "No PRD yet"),
        prompt_engineer_agent=getattr(state, 'prompt_text', "No prompt yet")
    )
    
    # Correct message format with separate dictionaries
    user_prompt = f"Answer this question from the user: {user_query}"
    
    # Use structured output
    llm = llm.with_structured_output(ManagerAgentSchema)
    
    # Properly formatted messages
    result = llm.invoke([
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt}
    ])
    print("DEBUG: Manager agent result:", result)
    
    # Store result for UI access
    state.classification = result.answer
    
    return state

    

def onboarding_agent(state):
    """Generate initial ideas"""
    llm = init_chat_model("gpt-4o-2024-08-06", temperature=0.0, model_provider="openai")
    
    if hasattr(state,'Idea') and state.Idea:
        return state
    
    user_preferences = getattr(state, 'user_preferences', 'general business')
    experience = getattr(state, 'experience', '0')
    
    system_prompt = onboard_agent.format(Preference=user_preferences)
    user_prompt = f"Give venture ideas based on BADM 350 concepts and {experience} years of experience"
    
    llm = llm.with_structured_output(Idea_Generation_Schema)
    result = llm.invoke([
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt}
    ])
    
    state.Idea = result.Ideas
    return state

def validator_agent(state):
    """Validate the selected idea with help from research tools"""
    if not hasattr(state, 'selected_idea_number'):
        return state
        
    selected_idx = state.selected_idea_number - 1
    selected_idea = state.Idea[selected_idx]
    
    # First, perform the market research directly
    print(f"DEBUG: Starting direct research for {selected_idea.title}")
    try:
        # Call the search function directly first
        research_data = ask_sonar(
            title=selected_idea.title,
            description=selected_idea.description
        )
        print("DEBUG: Research data obtained successfully")
    except Exception as e:
        print(f"DEBUG: Error calling search tool directly: {str(e)}")
        research_data = "Error retrieving market research data."
    
    # Now format the results using structured output
    llm = init_chat_model("gpt-4o-2024-08-06", temperature=0.0, model_provider="openai")
    llm = llm.with_structured_output(Validator_Agent_Schema)
    
    # Include the research data in the prompt
    validation = llm.invoke([
        {'role': 'system', 'content': validator_prompt},
        {'role': 'user', 'content': f"""Provide a detailed validation analysis for this venture idea:
        
        Title: {selected_idea.title}
        Description: {selected_idea.description}
        BADM Concept: {selected_idea.badm_concept}
        
        Here is market research data to incorporate in your analysis:
        
        {research_data}
        
        Include the hyperlinks from the research in your analysis where relevant.
        """}
    ])
    
    # Store validation results in state
    state.validation_results = validation.validation
    # Also store raw research data
    state.research_data = research_data
    
    return state

def product_manager(state):
    """Guides PRD Creation and product deployment Strategy"""
    llm = init_chat_model("gpt-4o-2024-08-06", temperature=0.0, model_provider="openai")

    # Get selected idea and validation results
    selected_idx = state.selected_idea_number - 1
    selected_idea = state.Idea[selected_idx]
    validation = state.validation_results
    
    print(f"DEBUG: Creating PRD for idea: {selected_idea.title}")
    
    user_prompt = f"""Create a PRD for this validated venture idea:
    Title: {selected_idea.title}
    Description: {selected_idea.description}
    BADM Concept: {selected_idea.badm_concept}
    
    Include validation insights: {validation}
    """
    # Use structured output with schema
    llm = llm.with_structured_output(ProductManagerSchema)
    result = llm.invoke([
        {'role': 'system', 'content': product_manager_prompt},
        {'role': 'user', 'content': user_prompt}
    ])
    
    print("DEBUG: Product Manager result received")
    
    # Store as dictionary key that will be accessible when returned
    state.prd = result
    
    # Also store as attribute for internal use
    setattr(state, 'prd', result)
    
    return state

def prompt_engineer(state):
    """Makes the prompt for the user's venture idea"""
    print("Entered prompt engineer function")
    llm = init_chat_model("gpt-4o-2024-08-06", temperature=0.7, model_provider="openai")  # Increased temperature for creativity

    selected_idx = state.selected_idea_number - 1
    selected_idea = state.Idea[selected_idx]
    validation_results = state.validation_results
    prd = state.prd

    # First get the result as plain text (not structured)
    user_prompt = f"""
    Create a detailed prompt for Bubble.io (a no-code development platform) to implement:
    
    IDEA: {selected_idea.title} - {selected_idea.description}
    
    Based on the PRD and validation analysis, provide:
    1. A step-by-step guide to building this in Bubble.io
    2. Key UI elements needed
    3. Database structure suggestions
    4. Any API connections required
    5. Specific plugins to consider
    
    Make your response comprehensive and actionable.
    """

    system_prompt = f"""You are an expert no-code development consultant who specializes in creating implementation guides.
    
    The user has a validated business idea with the following PRD:
    {prd}
    
    And validation results:
    {validation_results}
    
    Your job is to create a detailed, structured prompt for the low code tool
    """

    # Get unstructured response first
    result_text = llm.invoke([
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt}
    ])
    print("This is the final result",result_text.content)
    
    
    # Store both structured and raw text
    state.prompt_text = result_text.content
    

    return state


def should_validate(state):
    """Determine next step in workflow"""
    print("DEBUG: Checking state mode:", state.mode)
    print("DEBUG: Checking user_input")
    print("DEBUG checkung",state.user_query)

    if state.mode == "manager_agent":
        return "manager_agent"
    
    if state.mode == "validator_agent":
        return "validator_agent"
    
    elif state.mode == "product_manager":
        return "product_manager"
    
    elif state.mode == "prompt_engineer":
        return "prompt_engineer"
    
    elif not hasattr(state, 'Idea'):
        return "onboarding_agent"
    return "end"


# Create the workflow graph
workflow_graph = StateGraph(AgentState)

# Add nodes
workflow_graph.add_node("onboarding_agent", onboarding_agent)
workflow_graph.add_node("validator_agent", validator_agent)
workflow_graph.add_node("product_manager", product_manager)
workflow_graph.add_node("prompt_engineer",prompt_engineer)
workflow_graph.add_node("manager_agent",manager_agent)



# Set entry point
workflow_graph.set_entry_point("onboarding_agent")

# Add conditional edges with routing function
workflow_graph.add_conditional_edges(
    "onboarding_agent",
    should_validate,
    {
        "manager_agent" : "manager_agent",
        "validator_agent": "validator_agent",
        "onboarding_agent": "onboarding_agent",
        "product_manager": "product_manager",
        "prompt_engineer":"prompt_engineer",
        "end": END
    }
)

"""
workflow_graph.add_conditional_edges(
    "manager_agent",
    {
        "validator_agent": "validator_agent",
        "onboarding_agent": "onboarding_agent",
        "product_manager": "product_manager",
        "prompt_engineer":"prompt_engineer",
    }

)
"""
# Add final edges
workflow_graph.add_edge("validator_agent", END)

# Compile workflow
workflow = workflow_graph.compile()
