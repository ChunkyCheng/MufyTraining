import os
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Automatically look for a .env file and load it into environment variables
load_dotenv()

# =====================================================================
# 1. PYDANTIC SCHEMAS FOR STRUCTURED OUTPUT
# =====================================================================

class AIBlock(BaseModel):
    """Represents a single micro-task or subtask node."""
    text: str = Field(
        description="The ultra-minimal, action-oriented description of a single step."
    )
    # Using default=[] helps Pydantic initialize an empty list if Gemini leaves it out
    subtasks: List['AIBlock'] = Field(
        default=[], 
        description="Further sub-steps or granular breakdowns required to fulfill this specific step. Leave empty if no further breakdown is needed."
    )

    # A pre-validator to gracefully catch cases where Gemini outputs a raw string instead of an object
    @model_validator(mode='before')
    @classmethod
    def handle_raw_string_nodes(cls, value):
        if isinstance(value, str):
            return {"text": value, "subtasks": []}
        return value

# Rebuild the self-referencing forward references for recursive nesting
AIBlock.model_rebuild()

class AITaskTree(BaseModel):
    """The root container structural object returned by Gemini."""
    main_task_title: str = Field(
        description="The main top-level project, category, or goal title."
    )
    breakdown: List[AIBlock] = Field(
        description="The hierarchical tree list of immediate micro-subtasks for the main goal."
    )

# =====================================================================
# 2. INTERNAL UTILITIES
# =====================================================================

def _convert_schema_to_dict(ai_blocks: List[AIBlock]) -> dict:
    """Recursively strips the Pydantic type layout down into a standard Python dict."""
    clean_list = []
    for block in ai_blocks:
        clean_list.append({
            "text": block.text.strip(),
            "subtasks": _convert_schema_to_dict(block.subtasks)
        })
    return clean_list

# =====================================================================
# 3. PUBLIC API ENTRYPOINT
# =====================================================================

def generate_task_blueprint(prompt: str) -> dict:
    """
    Prompts the gemini-2.5-flash model to decompose a large goal 
    into a hyper-incremental list of bite-sized steps using structured JSON schema.
    """
    if not os.getenv("GEMINI_API_KEY"):
        raise ValueError(
            "Missing API Key! Please verify that your local .env file contains a valid 'GEMINI_API_KEY' assignment."
        )

    # Initialize the modern Google GenAI Client
    client = genai.Client()

    system_instructions = (
        "You are an expert cognitive behavioral coach specializing in managing Executive Dysfunction. "
        "Your absolute priority is to take a large goal and break it down into incredibly minor, non-threatening micro-tasks. "
        "Make the initial starting steps absurdly easy to overcome activation energy barriers "
        "(e.g., 'Stand up and walk to the desk', 'Open an empty web browser tab'). "
        "Nest subtasks logically down 2 to 3 levels to segment multi-phase processes cleanly.\n\n"
        "CRITICAL FOR JSON STRUCTURE:\n"
        "Every single entry in a `subtasks` array MUST be a full JSON object containing both a 'text' key and a 'subtasks' key. "
        "Do NOT ever output a plain string inside a subtask array. If a step has no deeper subtasks, provide an empty list: []"
    )

    # Request the model to fulfill content generation locked to our structure
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=f"Please create a comprehensive micro-step tree layout for this goal: {prompt}",
        config=types.GenerateContentConfig(
            system_instruction=system_instructions,
            response_mime_type="application/json",
            response_schema=AITaskTree,
            temperature=0.2 # Lower temperature slightly to enforce strict schema adherence
        )
    )

    # Coerce raw text JSON output directly against our strict Pydantic model
    structured_data = AITaskTree.model_validate_json(response.text)

    # Package into a vanilla Python dictionary structure
    return {
        "main_task_title": structured_data.main_task_title,
        "breakdown": _convert_schema_to_dict(structured_data.breakdown)
    }