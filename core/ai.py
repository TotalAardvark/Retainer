import json
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field
from google import genai
from google.genai import types


class FlashcardItem(BaseModel):
    tier: Literal["Core Concept", "Deep Dive"] = Field(
        description="Categorize into 'Core Concept' (foundational thesis, mental model, or essential vocabulary) or 'Deep Dive' (actionable mechanisms, empirical evidence, trade-offs, and conversational nuance)."
    )
    front: str = Field(description="Specific, atomic question adhering to the Minimum Information Principle. Do not be vague or multi-barreled.")
    back: str = Field(description="Concise, factual answer. 1-2 sentences maximum.")


class OutlineChapter(BaseModel):
    title: str = Field(description="Title of this chapter or section.")
    start_seconds: int = Field(description="Start time in seconds.")
    end_seconds: Optional[int] = Field(default=None, description="End time in seconds if identifiable.")
    timestamp_display: str = Field(description="Formatted timestamp range or start time, e.g. '0:40 - 2:40' or '12:31 - 18:00'.")
    summary: str = Field(description="Rich, comprehensive summary of the concepts and steps explained in this section. Must be formatted using markdown bullet points and indentation (e.g. '- Main point' and '  - Sub-point or step') to visually organize ideas instead of a solid paragraph block.")


class VideoRetentionAnalysis(BaseModel):
    suggested_title: str = Field(
        description="A concise 4-10 word title geared towards easy recall for a reader, capturing the true core topic and practical thesis (e.g. 'Model Context Protocol Architecture and Transports'). Avoid clickbait, vague summaries, and filler words."
    )
    core_topic_or_purpose: str = Field(
        description="A concise definition of the genuine pedagogical purpose, argument, practical thesis, major actionable concepts or frameworks."
    )
    executive_summary: str = Field(
        description="A 30-40 word, high-impact one or two sentence Executive Summary distilling the overarching premise and outcome of the video."
    )
    tags: List[str] = Field(
        description="Comprehensive list of subject matter tags for every significant concept, tool, architecture, or topic discussed (lowercase, hyphenated, e.g. 'mcp', 'docker-desktop', 'json-rpc')."
    )
    short_abstract: str = Field(
        description="Concise abstract of the video's core thesis and outcomes (<100 words)."
    )
    detailed_abstract: str = Field(
        description="Comprehensive, detailed technical abstract (~300 words) explaining context, methodology, architecture, and significance."
    )
    key_takeaways: List[str] = Field(
        description="List of 4-8 distinct technical insights, mechanisms, formulas, or pivotal insights."
    )
    outline: List[OutlineChapter] = Field(
        description="Detailed, chapter-by-chapter outline covering the entire video chronologically without skipping anything. Each item has title, timestamp display, and thorough summary."
    )
    flashcards: List[FlashcardItem] = Field(
        description="Dynamically generated flashcards strictly reflecting the evaluated conceptual density and cumulative runtime of the transcript across both 'Core Concept' and 'Deep Dive' tiers."
    )


PROMPT_SYSTEM = """You are an expert cognitive scientist, technical analyst, and spaced-repetition flashcard author.
Your task is to analyze the provided YouTube video transcript and produce deep, high-yield learning artifacts.

CRITICAL INSTRUCTIONS & DE-BIASING:
1. Title & Executive Summary:
   - Formulate a clean, memorable 4-10 word title geared towards easy recall for a reader, capturing the true core topic, key framework, and practical thesis.
   - Ignore clickbait video titles; ground your title and core topic entirely on what is actually taught, demonstrated, and concluded.
   - Craft a punchy, 30-40 word Executive Summary (1-2 sentences) summarizing what the video teaches and why it matters.
2. Outline:
   - Organize the outline chronologically by Chapters. If explicit chapters are provided in the input, follow and enrich them with thorough explanations. If no official chapters are present, divide the video into logical, coherent chapters based on the timestamps in the transcript.
   - Do NOT skip over any meaningful segment, code walkthrough, setup step, or technical nuance.
   - Structure each chapter's summary using nested markdown bullet points and indentation (e.g. '- Core concept or mechanism' and '  - Practical step, parameter, or detail') for visual clarity. Avoid solid blocks of paragraph text.
3. Flashcards (Density Scaling & Epistemological Tiers):
   - First ingest and evaluate the entire transcript chronologically and conceptually. Do not assume or enforce arbitrary card count quotas.
   - Categorize every flashcard into one of two tiers:
     a) 'Core Concept' (Strict Scarcity):
        - Focuses on the overarching thesis, paradigm shift, central mental model, or indispensable foundational vocabulary.
        - Strict test: If a learner forgets this card, their fundamental grasp of the entire subject collapses.
        - Evaluate rigorously: Most works—even dense 45-minute lectures—revolve around just 1 to 3 truly core theses or foundational terms. Only generate as many Core Concept cards as the material legitimately justifies (often only 1-3). Never invent filler to meet an imagined quota.
     b) 'Deep Dive' (Actionability, Evidence & Conversational Depth):
        - Focuses on actionable mechanisms, empirical evidence, historical precedents, subtle trade-offs, and critical nuances that enable intelligent conversational competence and practical application.
        - Does this test concrete real-world cause-and-effect, architectural/legislative/stylistic specifics, or troubleshooting caveats?
   - Scale dynamically by (Cumulative Runtime * Information Density):
     - Evaluate substantive takeaways across all timestamped chapters.
     - A 40-minute dense lecture covering multiple sub-topics must yield substantially more Deep Dive cards than a 10-minute video of similar density.
     - Conversely, low-density or entertainment-heavy videos with high volume but low factual signal should yield very few cards (e.g. 1 Core Concept, 1-3 Deep Dives).
   - Strict Minimum Information Principle & Anti-Trivia:
     - Questions must be atomic, precise, and unambiguous with 1-2 sentence direct answers.
     - Strictly ban trivia, anecdotal banter, rhetorical jokes, or sponsor segments.
4. Formatted Paragraph Transcript:
   - Synthesize and segment information clearly for rapid long-term recall.
"""


def analyze_transcript(
    api_key: str,
    title: str,
    channel: str,
    transcript_annotated: str,
    chapters: Optional[List[Dict[str, Any]]] = None,
    content_type: str = "video",
) -> Dict[str, Any]:
    """Call Google Gemini 3.8 Flash (Low) with structured JSON schema output."""
    if not api_key:
        raise ValueError("Gemini API key is not configured. Please open Settings and enter your API key.")

    client = genai.Client(api_key=api_key)

    chapters_context = ""
    if chapters:
        chapters_lines = [f"- [{c.get('start_seconds', 0)}s] {c.get('title', '')}" for c in chapters]
        chapters_context = "Official Video Chapters:\n" + "\n".join(chapters_lines) + "\n\n"

    source_label = "Article / Web Source" if content_type == "article" else "YouTube Video"
    source_author_label = "Source / Domain / Author" if content_type == "article" else "Channel"
    body_label = "Article Content (Markdown)" if content_type == "article" else "Timestamped Transcript"

    user_content = f"""{source_label} Title (for reference only, may be clickbait): {title}
{source_author_label}: {channel}

{chapters_context}{body_label}:
\"\"\"
{transcript_annotated[:85000]}
\"\"\"

Analyze this content and produce the structured output according to the schema.
"""

    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=PROMPT_SYSTEM,
            response_mime_type="application/json",
            response_schema=VideoRetentionAnalysis,
            thinking_config=types.ThinkingConfig(thinking_budget=1024),
            temperature=0.2,
        ),
    )

    if not response.text:
        raise RuntimeError("Gemini returned an empty response.")

    return json.loads(response.text)
