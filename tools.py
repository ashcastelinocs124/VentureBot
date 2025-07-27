import anthropic
import logging
import time
from typing import Dict, Any, List
import os
from dotenv import load_dotenv
from openai import OpenAI



def ask_sonar(title: str, description: str):
    api_key = os.getenv("PERPLEXITY_API_KEY")

    if not api_key:
        print("⚠️ PERPLEXITY_API_KEY not found in environment variables")
        # Provide a direct fallback for testing
        api_key = "API-KEY"  # Replace with your key

    print("Entering sonar")
    model = "sonar-pro"  # Use online model for most current data
    client = OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")

    system_prompt = f"""
    <role>
    You are an AI Web Researcher responsible for validating venture ideas with comprehensive market research.
    </role>

    <context>
    Perform detailed research on this business idea: "{title}: {description}"
    
    Focus on finding:
    1. Market size data (TAM, growth rates)
    2. Detailed competitor analysis (funding, users, strengths/weaknesses)
    3. Underserved market segments and opportunities
    4. Current market trends and future outlook
    5. Entry barriers and regulatory considerations
    6. Strategic recommendations for market entry

    IMPORTANT: You MUST include proper markdown hyperlinks for your sources like [Source Name](https://example.com)
    Don't just paste plain URLs - format them as proper clickable links using markdown.
    
    For each point, cite at least one specific source with a hyperlink.
    Include at least 5 different sources total.
    
    Format your response as:
    
    ## Market Analysis
    [Research findings with hyperlinks]
    [Citation Link]
    
    ## Competitors
    [Research findings with hyperlinks]
    [Citation Link]
    
    
    ## Opportunities
    [Research findings with hyperlinks]
    [Citation Link]
    
    
    ## Market Trends
    [Research findings with hyperlinks]
    [Citation Link]
    
    ## Entry Barriers
    [Research findings with hyperlinks]
    [Citation Link]
    
    
    ## Strategic Recommendations
    [Research-based recommendations]
    [Citation Link]
    
    </context>
    """
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Research this venture idea thoroughly: {title} - {description}"}
        ]
    )
    print("perplexity search results", response.choices[0].message.content)
    return response.choices[0].message.content

"""
answer = ask_sonar("Validate my idea which is cursor for slides", "venture idea for badm 350 at gies college of business")
print(answer)
"""
