import chainlit as cl
import asyncio
from agents import workflow
from State import AgentState  # Import from State file directly
from enum import Enum

BOT_AVATAR = "https://raw.githubusercontent.com/chainlit/chainlit/main/avatar.png" 

class WorkflowPhase(Enum):
    ONBOARDING = "onboarding"
    IDEA_GENERATION = "idea_generation"
    VALIDATION = "validation"
    PRODUCT_MANAGEMENT = "product_management"
    PROMPT_ENGINEERING = "prompt_engineering"
    
# Workflow sequence and handlers mapping
WORKFLOW_SEQUENCE = {
    WorkflowPhase.ONBOARDING: {
        "next": WorkflowPhase.VALIDATION,
        "handler": "handle_onboarding",
        "description": "gathering your preferences and experience"
    },
    WorkflowPhase.VALIDATION: {
        "next": WorkflowPhase.PRODUCT_MANAGEMENT,
        "handler": "handle_validation",
        "description": "validating your selected idea"
    },
    WorkflowPhase.PRODUCT_MANAGEMENT: {
        "next": WorkflowPhase.PROMPT_ENGINEERING,
        "handler": "handle_product",
        "description": "creating a product requirements document"
    },
    WorkflowPhase.PROMPT_ENGINEERING: {
        "next": WorkflowPhase.IDEA_GENERATION,  # Loop back to ideas
        "handler": "prompt_engineer",
        "description": "creating implementation prompts"
    }
}

# Enable chat persistence
cl.ChatSettings(
    persistent_chat_history=True,  # Enable chat persistence
    chat_history_limit=20,         # Store up to 20 conversations
)

@cl.on_chat_start
async def on_chat_start():
    """Initialize the chat session"""
    # Initialize the agent state
    initial_state = AgentState()
    
    # Storing the current state
    cl.user_session.set("agent_state", initial_state)
    cl.user_session.set("workflow_step", "onboarding")
    
    elements = [
        cl.Text(
            content=(
                "👋 Welcome to your solopreneur journey! I’m **VentureBot**, your AI co-pilot, here to guide you every step of the way — "
                "from idea to launch.\n\n"
                "🚀 Whether you're exploring new product ideas, validating concepts, or building out your AI-powered MVP, I’m here to make the process faster, smarter, and more fun.\n\n"
                "📚 You can click the **README** above to learn more about how I work, or dive right in and start building your next big idea!"
                ),
                name="welcome_text"
        )
    ]

    # Setting elements to  open the sidebar
    await cl.ElementSidebar.set_elements(elements)
    await cl.ElementSidebar.set_title("Welcome text from VentureBot!")
    
    await cl.Message(
        content="""🚀 **Welcome to VentureBot!**
        
I'm here to help you generate innovative venture ideas based on BADM 350 concepts.

Let's start by learning about your preferences and experience!

**What are your interests or areas you're passionate about?**
        """,
        author="🤖 VentureBot"
    ).send()

@cl.on_message
async def on_message(message):  # Remove the incorrect type annotation
    """Handle incoming messages using the flexible workflow system"""
    print(message.content)
    
    # Get current state and workflow phase
    agent_state = cl.user_session.get("agent_state")
    current_phase = cl.user_session.get("workflow_phase", WorkflowPhase.ONBOARDING)
    
    try:
        # Check if user wants to move to next phase
        if any(phrase in message.content.lower() for phrase in ["next phase", "next step", "continue", "move on"]):
            next_phase = WORKFLOW_SEQUENCE[current_phase]["next"]
            await cl.Message(
                content=f"📋 Moving to next phase: **{next_phase.value}** ({WORKFLOW_SEQUENCE[next_phase]['description']})",
                author="🤖 VentureBot"
            ).send()
            cl.user_session.set("workflow_phase", next_phase)
            # Execute the first step of the new phase
            handler_name = WORKFLOW_SEQUENCE[next_phase]["handler"]
            handler_func = globals()[handler_name]  # Get function by name
            await handler_func(message.content, agent_state)  # Pass message.content
            return
            
        # Check if user wants to go back or start over
        if any(phrase in message.content.lower() for phrase in ["start over", "reset", "go back", "new ideas"]):
            await cl.Message(
                content="🔄 Starting over with the idea generation phase!",
                author="🤖 VentureBot"
            ).send()
            cl.user_session.set("workflow_phase", WorkflowPhase.IDEA_GENERATION)
            # Create a new state but keep preferences
            new_state = AgentState()
            new_state.user_preferences = agent_state.user_preferences
            new_state.experience = agent_state.experience
            cl.user_session.set("agent_state", new_state)
            await generate_ideas(new_state)  # Pass the state directly
            return
        
        # NEW: Check if this is a question rather than a progression input
        if any(q in message.content.lower() for q in ["?", "what is", "how do", "explain", "tell me about", "why", "expand"]):
            # This looks like a question - send to classification agent
            await classification_agent(message.content, agent_state)  # Pass message.content
            return
            
        # Handle current phase through its handler
        handler_name = WORKFLOW_SEQUENCE[current_phase]["handler"]
        handler_func = globals()[handler_name]  # Get function by name
        await handler_func(message.content, agent_state)  # Pass message.content
        
    except Exception as e:
        await cl.Message(
            content=f"❌ Sorry, I encountered an error: {str(e)}",
            author="🤖 VentureBot"
        ).send()

async def handle_onboarding(user_input: str, agent_state: AgentState):
    """Handle the onboarding process"""
    
    # Get current step from session
    onboarding_step = cl.user_session.get("onboarding_step", "preferences")
    
    if onboarding_step == "preferences":
        # First input is preferences
        agent_state.user_preferences = user_input
        cl.user_session.set("agent_state", agent_state)
        cl.user_session.set("onboarding_step", "experience")
        
        await cl.Message(
            content=f"""✅ Got it! Your interests: **{user_input}**

**Now, how many years of experience do you have in business or entrepreneurship?**
(You can say 0 if you're just starting out)""",
            author="🤖 VentureBot"
        ).send()
        
    elif onboarding_step == "experience":
        # Second input is experience
        agent_state.experience = user_input
        cl.user_session.set("agent_state", agent_state)
        cl.user_session.set("workflow_step", "generating")
        
        # Now run the workflow to generate ideas
        idea = await generate_ideas(agent_state)
        agent_state = idea
        cl.user_session.set("workflow_step", "validation")

async def generate_ideas(agent_state: AgentState):
    """Generate ideas using the LangGraph workflow"""
    try:
        agent_state.mode = "onboarding_agent"
        thinking_msg = cl.Message(
            content="🧠 Thinking...",
            author="🤖 VentureBot"
        )
        await thinking_msg.send()
        print(agent_state)
        
        # Run the workflow with proper error handling
        try:
            result = await asyncio.to_thread(lambda: workflow.invoke(agent_state))
            print("The result is here",result)
        except AttributeError as e:
            # Use elements instead of content for updates
            await thinking_msg.stream_token("⚠️ Workflow configuration error. Please check the agent setup.")
            raise e
        except Exception as e:
            # Stream the error message
            await thinking_msg.stream_token(f"❌ Error: {str(e)}")
            raise e

        # Process results
        ideas = result['Idea']
        agent_state.Idea = result['Idea']
        agent_state.previous_answer = result['Idea']
        formatideas = format_ideas(ideas)
        
        await cl.Message(
            content = formatideas,
            author="🤖 VentureBot"
            
        ).send()
        

            
    except Exception as e:
        await cl.Message(
            content=f"❌ Error: {str(e)}",
            author="🤖 VentureBot"
        ).send()

def format_ideas(ideas):
    """Helper function to format ideas nicely"""
    text = "🎯 **Here are your personalized venture ideas:**\n\n"
    
    for i, idea in enumerate(ideas, 1):
        text += f"**{i}. {idea.title}**\n"
        text += f"📝 {idea.description}\n"
        text += f"🎓 *BADM 350 Concept: {idea.badm_concept}*\n\n"
    
    text += "\n**Which idea interests you most? Reply with the number (1-5) to get a detailed validation!**"
    return text

async def handle_validation(user_input: str, agent_state: AgentState):
    """Handle idea validation"""
    try:
        selection = int(user_input.strip())
        print(f"DEBUG: User selected idea #{selection}")
        ideas = agent_state.Idea
        
        if 1 <= selection <= len(ideas):
            print(f"DEBUG: Setting selected_idea_number to {selection}")
            agent_state.selected_idea_number = selection
            agent_state.mode = "validator_agent"
            
            # Add this line to update the session state
            cl.user_session.set("agent_state", agent_state)
            
            selected_idea = ideas[selection - 1]
            
            thinking_msg = await cl.Message(
                content="🔍 Analyzing your selected idea...",
                author="🤖 VentureBot"
            ).send()
            
            try:
                result = await asyncio.to_thread(lambda: workflow.invoke(agent_state))
                validation = result['validation_results']
                
                await cl.Message(
                    content=f"""✅ **Validation Analysis for: {selected_idea.title}**

📊 **Market Analysis**:
{validation.market_analysis}

👥 **Target Customer Segments**:
{validation.customer_segments}

⚙️ **Technical Feasibility**:
{validation.technical_feasibility}

🏢 **Competitive Landscape**:
{validation.competitive_analysis}

💰 **Cost Estimation**:
{validation.cost_estimate}

What aspect would you like to explore further?""",
                    author="VentureBot"
                ).send()
                
            except Exception as e:
                print(f"DEBUG: Validation error: {str(e)}")
                await thinking_msg.stream_token(f"❌ Error: {str(e)}")
            
            cl.user_session.set("workflow_step","product_manager")
        else:
            await cl.Message(
                content=f"Please select a valid number between 1 and {len(ideas)}.",
                author="🤖 VentureBot"
            ).send()
            
    except ValueError:
        await cl.Message(
            content="Please reply with a number (1-5) to select an idea.",
            author="🤖 VentureBot"
        ).send()


async def handle_product(user_input: str, agent_state: AgentState):
    """Handle product management"""
    try:
        agent_state.mode = "product_manager"
        
        thinking_msg =  cl.Message(
            content="🔍 Creating a PRD for your venture idea...",
            author="🤖 VentureBot"
        )
        await thinking_msg.send()
        
        try:
            # Run workflow
            result = await asyncio.to_thread(lambda: workflow.invoke(agent_state))
            print("DEBUG: Product manager workflow result:", result)
            
            # Try both dictionary and attribute access methods
            try:
                if isinstance(result, dict) and 'prd' in result:
                    prd = result['prd']
                else:
                    prd = result.prd
                cl.user_session.set("workflow_step","prompt_engineer")
                await cl.Message(
                    content=f"""📋 **Product Requirements Document**

🎯 **Overview**:
{prd.overview}

👥 **User Stories**:
{format_user_stories(prd.user_stories)}

📝 **Key Requirements**:
{format_requirements(prd.functional_requirements)}

📊 **Success Metrics**:
{format_metrics(prd.success_metrics)}

Would you like to:
1. Refine the requirements
2. Move to technical planning
3. Start over with new ideas""",
                    author="VentureBot"
                ).send()
                
            except (AttributeError, KeyError) as e:
                print(f"DEBUG: Error accessing PRD data: {str(e)}")
                print(f"DEBUG: Result structure: {result}")
                await thinking_msg.stream_token(f"❌ Error formatting PRD: {str(e)}")
            
        except Exception as e:
            print(f"DEBUG: Product management error: {str(e)}")
            await thinking_msg.stream_token(f"❌ Error: {str(e)}")
            
    except Exception as e:
        await cl.Message(
            content=f"❌ Error creating PRD: {str(e)}",
            author="VentureBot"
        ).send()


async def prompt_engineer(user_input : str , agent_state : AgentState):
    """Converts the idea into valid prompts for low code tools"""
    print("Entered prompt engineer")
    try:
        agent_state.mode = "prompt_engineer"

        thinking_msg =  cl.Message(
            content="🔍 Creating a prompt..",
            author="🤖 VentureBot"
        )

        await thinking_msg.send()

        try:
            result = await asyncio.to_thread(lambda: workflow.invoke(agent_state))
            await cl.Message(
                content = result['prompt_text'],
                author = "VentureBot"
            ).send()
        except Exception as e:
            await cl.Message(
            content="Streaming error",
            author="🤖 VentureBot"
        ).send()
    except Exception as e:
        await cl.Message(
            content=f"❌ Error creating the prompt: {str(e)}",
            author="VentureBot"
        ).send()

def format_user_stories(stories):
    """Format user stories nicely"""
    return "\n".join([f"• As a {story.role}, I want {story.goal} so that {story.reason}" for story in stories])

def format_requirements(requirements):
    """Format requirements nicely"""
    return "\n".join([f"• {req}" for req in requirements])

def format_metrics(metrics):
    """Format metrics nicely"""
    return "\n".join([f"• {metric}" for metric in metrics])

async def classification_agent(user_input: str, agent_state: AgentState):
    """Classifies general queries and maintains context for follow-ups"""
    print("Using classification agent for:", user_input)
    
    # Store the previous query/answer for context
    if hasattr(agent_state, 'classification'):
        agent_state.previous_answer = agent_state.classification
    
    # Set up the query
    agent_state.user_query = user_input
    agent_state.mode = "manager_agent"
    
    thinking_msg = cl.Message(
        content="🧠 Thinking...",
        author="🤖 VentureBot"
    )
    await thinking_msg.send()
    
    try:
        # Run the manager agent
        result = await asyncio.to_thread(lambda: workflow.invoke(agent_state))
        
        # Get the classification result
        answer = None
        if hasattr(result, 'classification'):
            answer = result.classification
        elif isinstance(result, dict) and 'classification' in result:
            answer = result['classification']
            
        if answer:
            await cl.Message(
                content=answer,
                author="🤖 VentureBot"
            ).send()
            
            # Update the session state with this answer for future context
            agent_state.previous_answer = answer
            cl.user_session.set("agent_state", agent_state)
        else:
            await cl.Message(
                content="I couldn't find specific information about that. Could you clarify your question?",
                author="🤖 VentureBot"
            ).send()
    
    except Exception as e:
        print(f"Classification error: {str(e)}")
        await cl.Message(
            content=f"❌ I encountered an error processing your question: {str(e)}",
            author="🤖 VentureBot"
        ).send()

async def handle_general_query(user_input: str, agent_state: AgentState):
    """Handle general queries after the main workflow"""


    if "new ideas" in user_input.lower() or "generate" in user_input.lower():

        agent_state.mode =  "manager agent"
        # Reset and generate new ideas
        new_state = AgentState()
        new_state.user_preferences = agent_state.user_preferences
        new_state.experience = agent_state.experience
        
        await generate_ideas(new_state)
        
    else:
        await cl.Message(
            content="""I can help you with:

🎯 **Generate new ideas** - Say "generate new ideas"  
📊 **Market research guidance**
👥 **Customer validation strategies**  
💡 **Refining your concept**
🚀 **Next steps planning**

What would you like to explore?""",
            author="🤖 VentureBot"
        ).send()


@cl.on_chat_resume
async def on_chat_resume():
    """Handle chat resume"""
    await cl.Message(
        content="Welcome back! I'm ready to help you with your venture ideas.",
        author="🤖 VentureBot"
    ).send()

        
        # Environment variables
