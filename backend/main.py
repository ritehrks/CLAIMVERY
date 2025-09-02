# main.py

import os
import json
import re
import asyncio
import aiohttp
import sys
import traceback
from typing import TypedDict, List, Dict, Literal
from google.cloud import aiplatform, vision
import vertexai
from vertexai.generative_models import GenerativeModel
from serpapi import GoogleSearch
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime

# --- Configuration and Setup ---
try:
    if 'GOOGLE_APPLICATION_CREDENTIALS' not in os.environ and 'GCLOUD_AUTH_APPLICATION_DEFAULT_CLIENT_ID' not in os.environ:
        raise EnvironmentError("Google Cloud Authentication Error: Credentials not found. Please run 'gcloud auth application-default login' in your terminal.")

    SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
    GCLOUD_PROJECT = os.getenv("GCLOUD_PROJECT")

    if not SERPAPI_API_KEY or not GCLOUD_PROJECT:
        raise EnvironmentError("Missing environment variables: SERPAPI_API_KEY and GCLOUD_PROJECT must be set in the .env file.")

    vertexai.init(project=GCLOUD_PROJECT, location="us-central1")
    llm = GenerativeModel("gemini-2.5-flash")
    vision_client = vision.ImageAnnotatorClient()

except Exception as e:
    print(json.dumps({"error": "Initialization Failed", "details": str(e)}), file=sys.stderr)
    sys.exit(1)


# --- Agent "Tools" ---
# These are the functions the AI can choose to call as part of its plan.

def get_current_date() -> str:
    """Returns the current date and time. The agent's first step should always be to call this tool to establish temporal context."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def google_search(query: str, time_period: str = None) -> str:
    """
    Performs a Google search. Can be filtered by time.
    Args:
        query (str): The search query.
        time_period (str, optional): Can be 'past_hour', 'past_day', 'past_week'. Defaults to None.
    """
    try:
        params = {"q": query, "api_key": SERPAPI_API_KEY, "num": 7}
        
        time_map = {
            'past_hour': 'qdr:h',
            'past_day': 'qdr:d',
            'past_week': 'qdr:w'
        }
        if time_period and time_period in time_map:
            params['tbs'] = time_map[time_period]

        search = GoogleSearch(params)
        results = search.get_dict().get("organic_results", [])
        clean_results = [{"title": r.get("title"), "link": r.get("link"), "snippet": r.get("snippet"), "date": r.get("date")} for r in results]
        
        if not clean_results:
            return f"No search results found for this query with the time filter '{time_period}'."
        return json.dumps(clean_results, indent=2)
    except Exception as e:
        return f"Error during search: {e}"

def extract_text_from_image(image_path: str) -> str:
    """Extracts text from an image file using Google Cloud Vision OCR."""
    try:
        with open(image_path, "rb") as image_file:
            content = image_file.read()
        image = vision.Image(content=content)
        response = vision_client.text_detection(image=image)
        texts = response.text_annotations
        if texts:
            return f"Successfully extracted text: {texts[0].description}"
        return "No text could be found in the provided image."
    except Exception as e:
        return f"Error during OCR: {e}"


async def _fetch_page_content(session, url):
    """Asynchronous helper to fetch web page content."""
    try:
        async with session.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'}) as response:
            return await response.text() if response.status == 200 else None
    except Exception:
        return None

def scrape_website(url: str) -> str:
    """Scrapes the primary text content of a single URL."""
    try:
        async def run_scrape():
            async with aiohttp.ClientSession() as session:
                html = await _fetch_page_content(session, url)
                if html:
                    soup = BeautifulSoup(html, 'html.parser')
                    content = ' '.join(p.get_text() for p in soup.find_all('p'))
                    return content[:4000] if content else "Could not find any paragraph text on the page."
                return "Failed to retrieve content from the URL."
        return asyncio.run(run_scrape())
    except Exception as e:
        return f"Error during scraping: {e}"

# --- Planner-Executor Agent Core ---

def create_research_plan(claim: str, source: str, image_path: str) -> List[Dict]:
    """
    The first step of the agent. It analyzes the user's query and creates a structured plan.
    """
    initial_request = f"Initial Text: \"{claim}\"\nSource Identifier: \"{source}\""
    if image_path and image_path != 'null':
        initial_request = f"An image has been provided at path '{image_path}'. The user's text input was '{claim}'."

    prompt = f"""
You are a research planner. Your job is to create a step-by-step plan to investigate a user's query.
The plan should be a list of actions using the available tools.

**Available Tools:**
- `get_current_date[]`: Returns the current date and time.
- `extract_text_from_image[image_path]`: Extracts text from an image.
- `google_search[query, time_period]`: Searches the web. `time_period` is optional and can be 'past_hour', 'past_day', or 'past_week'.
- `scrape_website[url]`: Scrapes a URL.

**Your Task:**
Based on the user's request, create a JSON list of actions (a 'plan') to find the answer.
- **Your FIRST step MUST ALWAYS be `get_current_date` to establish temporal context.**
- If the claim contains words suggesting a recent event (e.g., "breaking", "today"), subsequent search steps MUST use a time filter.
- If an image is provided, your second step MUST be `extract_text_from_image`.
- Your plan should have between 3 and 6 steps.

**User's Request:**
{initial_request}

**Example Plan for a Breaking News Claim:**
[
    {{"tool": "get_current_date", "parameters": {{}}}},
    {{"tool": "google_search", "parameters": {{"query": "earthquake reported off coast of Goa", "time_period": "past_day"}}}},
    {{"tool": "scrape_website", "parameters": {{"url": "https://www.reuters.com/world/india/earthquake-reported..."}}}},
    {{"tool": "google_search", "parameters": {{"query": "National Center for Seismology Goa earthquake report"}}}}
]

Now, create the plan for the user's request. Your response MUST be only the JSON list of plan steps.
"""
    response = llm.generate_content(prompt)
    plan_str = response.text.strip().replace("```json", "").replace("```", "")
    return json.loads(plan_str)


def execute_plan(plan: List[Dict]) -> str:
    """
    The second step. This function takes the plan and executes each step,
    collecting the observations into a log.
    """
    observations = ""
    for i, step in enumerate(plan):
        tool = step.get("tool")
        parameters = step.get("parameters", {})
        observations += f"\n--- Step {i+1}: Executing {tool} with parameters {json.dumps(parameters)} ---\n"
        
        if tool == "google_search":
            result = google_search(parameters.get("query"), parameters.get("time_period"))
        elif tool == "scrape_website":
            result = scrape_website(parameters.get("url"))
        elif tool == "extract_text_from_image":
            result = extract_text_from_image(parameters.get("image_path"))
        elif tool == "get_current_date":
            result = get_current_date()
        else:
            result = f"Unknown tool: {tool}"
        
        observations += f"Observation: {result}\n"
    return observations


def synthesize_final_report(claim: str, source: str, observations: str) -> Dict:
    """
    The final step. The agent takes all the gathered observations and
    synthesizes them into a detailed, structured report.
    """
    prompt = f"""
You are a fact-checking analyst. Based on the user's original query and the full log of research observations,
synthesize a final, detailed report in a valid JSON format.

**User's Original Query:** "{claim}"
**Source Provided:** "{source}"
**Full Research Log:**
{observations}

**Required JSON Output Structure:**
{{
  "final_verdict": "A single, conclusive verdict (e.g., 'Confirmed Recent Event', 'Fictional', 'Complex/Opinion-based')",
  "verdict_explanation": "A detailed paragraph explaining your final verdict. You must reference key observations from the research log, including dates or times if found.",
  "claim_analysis_summary": "Summarize the evidence found. If the query was a question, summarize the different viewpoints or facts discovered.",
  "source_analysis_summary": "Summarize your findings about the source's credibility. If no source was provided, state that.",
  "detailed_sources": [
    {{
      "title": "Title of a key source you found",
      "url": "URL of that source",
      "relevance_summary": "A one-sentence explanation of why this source was important to your investigation."
    }}
  ]
}}
"""
    response = llm.generate_content(prompt)
    report_str = response.text.strip().replace("```json", "").replace("```", "")
    return json.loads(report_str)


def main():
    """The main function that orchestrates the Planner-Executor agent."""
    try:
        if len(sys.argv) != 4:
            raise ValueError("Invalid arguments. Expected: claim, source_identifier, image_path")

        original_claim = sys.argv[1]
        source_identifier = sys.argv[2]
        image_path = sys.argv[3]

        # 1. PLAN
        research_plan = create_research_plan(original_claim, source_identifier, image_path)

        # 2. EXECUTE
        observations = execute_plan(research_plan)

        # 3. SYNTHESIZE
        final_report = synthesize_final_report(original_claim, source_identifier, observations)

        # Print the final, complete report
        print(json.dumps(final_report, indent=2))

    except Exception as e:
        print(json.dumps({
            "error": "An exception occurred during agent execution.",
            "details": str(e),
            "traceback": traceback.format_exc()
        }), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
