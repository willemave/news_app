"""
This module manages the LLM integration for:
1. Preference-based filtering.
2. Summarization (short and detailed).

Uses Google Gemini Flash 2.5 for all LLM operations.
"""
import json
import os
from datetime import datetime
from google import genai
from google.genai import types
from .config import settings
from .schemas import ArticleSummary, FilterResult
from pydantic import BaseModel

class PdfAnalysis(BaseModel):
    """Schema for PDF analysis including title extraction and summarization."""
    title: str
    short_summary: str
    detailed_summary: str

# Removed global genai.configure(api_key=settings.GOOGLE_API_KEY)

def _log_llm_response_to_file(response_text: str, function_name: str, error_details: str) -> None:
    """
    Log the entire LLM response to a file for debugging purposes.
    
    Args:
        response_text: The complete response text from the LLM
        function_name: Name of the function where the error occurred
        error_details: Details about the parsing error
    """
    try:
        # Create logs directory if it doesn't exist
        logs_dir = "logs"
        os.makedirs(logs_dir, exist_ok=True)
        
        # Generate timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
        filename = f"llm_response_error_{function_name}_{timestamp}.log"
        filepath = os.path.join(logs_dir, filename)
        
        # Prepare log content
        log_content = f"""=== LLM Response Error Log ===
Timestamp: {datetime.now().isoformat()}
Function: {function_name}
Error Details: {error_details}
Response Length: {len(response_text)} characters

=== Full Response Text ===
{response_text}

=== End of Response ===
"""
        
        # Write to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(log_content)
        
        print(f"Full LLM response logged to: {filepath}")
        
    except Exception as log_error:
        print(f"Failed to log LLM response to file: {log_error}")

def _unescape_json_string(escaped_string: str) -> str:
    """
    Properly unescape a JSON string, handling all standard JSON escape sequences.
    """
    # Handle standard JSON escape sequences
    unescaped = escaped_string.replace('\\"', '"')
    unescaped = unescaped.replace('\\\\', '\\')
    unescaped = unescaped.replace('\\/', '/')
    unescaped = unescaped.replace('\\b', '\b')
    unescaped = unescaped.replace('\\f', '\f')
    unescaped = unescaped.replace('\\n', '\n')
    unescaped = unescaped.replace('\\r', '\r')
    unescaped = unescaped.replace('\\t', '\t')
    
    # Handle unicode escape sequences (\uXXXX)
    import re
    def replace_unicode(match):
        return chr(int(match.group(1), 16))
    
    unescaped = re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode, unescaped)
    
    return unescaped

def _normalize_summary_data(summary_data: dict) -> dict:
    """
    Normalize summary data to ensure all fields are strings.
    Converts lists to formatted strings if needed.
    """
    normalized = summary_data.copy()
    
    # Handle short_summary
    if isinstance(normalized.get('short_summary'), list):
        normalized['short_summary'] = ' '.join(str(item) for item in normalized['short_summary'])
    
    # Handle detailed_summary
    if isinstance(normalized.get('detailed_summary'), list):
        # Format list items as bullet points
        items = [str(item) for item in normalized['detailed_summary']]
        normalized['detailed_summary'] = '\n'.join(f"• {item}" for item in items)
    
    return normalized

def _parse_malformed_summary_response(response_text: str) -> ArticleSummary:
    """
    Fallback parser for malformed JSON responses from LLM.
    Attempts to extract short_summary and detailed_summary from the response.
    """
    import re
    
    try:
        # Handle empty or whitespace-only responses early
        if not response_text or response_text.isspace():
            return ArticleSummary(
                short_summary="Error parsing summary",
                detailed_summary="Error parsing detailed summary"
            )
        
        # Try to find short_summary and detailed_summary in the response
        # More robust regex patterns that handle various malformed JSON scenarios
        
        # Pattern 1: Try to match complete quoted strings with proper delimiters
        short_match = re.search(r'"short_summary"\s*:\s*"((?:[^"\\]|\\.)*)"\s*[,}\n]', response_text, re.DOTALL)
        detailed_match = re.search(r'"detailed_summary"\s*:\s*"((?:[^"\\]|\\.)*)"\s*[,}\n]', response_text, re.DOTALL)
        
        # Pattern 2: If that fails, try to match even without proper closing delimiters (for truncated responses)
        if not short_match:
            short_match = re.search(r'"short_summary"\s*:\s*"((?:[^"\\]|\\.)*)', response_text, re.DOTALL)
        
        if not detailed_match:
            detailed_match = re.search(r'"detailed_summary"\s*:\s*"((?:[^"\\]|\\.)*)', response_text, re.DOTALL)
        
        # Pattern 3: Handle cases where quotes might be missing or malformed
        if not short_match:
            short_match = re.search(r'"short_summary"\s*:\s*([^,}\n]*)', response_text, re.DOTALL)
        
        if not detailed_match:
            detailed_match = re.search(r'"detailed_summary"\s*:\s*([^,}\n]*)', response_text, re.DOTALL)
        
        short_summary = "Error parsing summary"
        detailed_summary = "Error parsing detailed summary"
        
        if short_match:
            extracted = short_match.group(1).strip()
            # Remove surrounding quotes if present
            if extracted.startswith('"') and extracted.endswith('"'):
                extracted = extracted[1:-1]
            elif extracted.startswith('"'):
                extracted = extracted[1:]
            if extracted and not extracted.isspace():
                short_summary = _unescape_json_string(extracted)
        
        if detailed_match:
            extracted = detailed_match.group(1).strip()
            # Remove surrounding quotes if present
            if extracted.startswith('"') and extracted.endswith('"'):
                extracted = extracted[1:-1]
            elif extracted.startswith('"'):
                extracted = extracted[1:]
            if extracted and not extracted.isspace():
                detailed_summary = _unescape_json_string(extracted)
        
        # Clean up any trailing ellipsis or incomplete text
        if short_summary.endswith('...'):
            short_summary = short_summary[:-3].strip()
        if detailed_summary.endswith('...'):
            detailed_summary = detailed_summary[:-3].strip()
            
        # Ensure we have meaningful content
        if not short_summary or short_summary.isspace():
            short_summary = "Error parsing summary"
        if not detailed_summary or detailed_summary.isspace():
            detailed_summary = "Error parsing detailed summary"
        
        return ArticleSummary(
            short_summary=short_summary,
            detailed_summary=detailed_summary
        )
    except Exception as e:
        print(f"Error in fallback parsing: {e}")
        return ArticleSummary(
            short_summary="Error parsing summary",
            detailed_summary="Error parsing detailed summary"
        )

def _parse_malformed_filter_response(response_text: str) -> tuple[bool, str]:
    """
    Fallback parser for malformed JSON responses from filter_article.
    Attempts to extract matches and reason from the response.
    """
    import re
    
    try:
        # Handle empty or whitespace-only responses early
        if not response_text or response_text.isspace():
            return False, "Error parsing filter response"
        
        # Try to find matches and reason in the response
        matches_match = re.search(r'"matches"\s*:\s*(true|false)', response_text, re.IGNORECASE)
        
        # More robust regex patterns for reason field
        # Pattern 1: Try to match complete quoted strings with proper delimiters
        reason_match = re.search(r'"reason"\s*:\s*"((?:[^"\\]|\\.)*)"\s*[,}\n]', response_text, re.DOTALL)
        
        # Pattern 2: If that fails, try to match even without proper closing delimiters (for truncated responses)
        if not reason_match:
            reason_match = re.search(r'"reason"\s*:\s*"((?:[^"\\]|\\.)*)', response_text, re.DOTALL)
        
        # Pattern 3: Handle cases where quotes might be missing or malformed
        if not reason_match:
            reason_match = re.search(r'"reason"\s*:\s*([^,}\n]*)', response_text, re.DOTALL)
        
        matches = False
        reason = "Error parsing filter response"
        
        if matches_match:
            matches = matches_match.group(1).lower() == 'true'
        
        if reason_match:
            extracted = reason_match.group(1).strip()
            # Remove surrounding quotes if present
            if extracted.startswith('"') and extracted.endswith('"'):
                extracted = extracted[1:-1]
            elif extracted.startswith('"'):
                extracted = extracted[1:]
            if extracted and not extracted.isspace():
                reason = _unescape_json_string(extracted)
        
        # Clean up any trailing ellipsis or incomplete text
        if reason.endswith('...'):
            reason = reason[:-3].strip()
            
        # Ensure we have meaningful content
        if not reason or reason.isspace():
            reason = "Error parsing filter response"
        
        print(f"Filter result (fallback): matches={matches}, reason: {reason}")
        return matches, reason
    except Exception as e:
        print(f"Error in fallback filter parsing: {e}")
        return False, "Error parsing filter response"

def filter_article(content: str) -> tuple[bool, str]:
    """
    Decide whether an article matches user preferences using Google Gemini.
    Returns tuple of (matches: bool, reason: str).
    """
    system_prompt = """You are an intelligent news filter. 
    Your task is to determine if an article matches the following preferences:

- Focus on technology, physics, longevity, biology, AI, and strategy.
- Skip news reports and marketing pieces. 
- Include opinion pieces only if they provide unqiue insights.
- Exclude articles primarily intended as marketing or promotional material unless the promotional content is minimal and clearly secondary to substantial informative content.
    
    Respond with whether the article matches and provide a brief explanation."""

    try:
        # Initialize client with API key
        client = genai.Client(
            api_key=settings.GOOGLE_API_KEY,
        )

        model = "gemini-2.5-flash-preview-05-20"
        prompt = f"{system_prompt}\n\nArticle content:\n{content}"
        
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            ),
        ]
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=FilterResult,
        )

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        
        # Use structured output with fallback
        try:
            if hasattr(response, 'parsed') and response.parsed:
                # Use the parsed Pydantic object
                result = response.parsed
                print(f"Filter result (structured): matches={result.matches}, reason: {result.reason}")
                return result.matches, result.reason
            else:
                # Fallback to JSON parsing
                result = json.loads(response.text)
                matches = result.get('matches', False)
                reason = result.get('reason', 'No reason provided')
                print(f"Filter result (JSON): matches={matches}, reason: {reason}")
                return matches, reason
        except (json.JSONDecodeError, AttributeError) as json_error:
            error_msg = f"JSON parsing error in filter_article: {json_error}"
            print(error_msg)
            print(f"Raw response text: {response.text[:500]}...")
            
            # Log the entire response to file for debugging
            _log_llm_response_to_file(response.text, "filter_article", error_msg)
            
            # Try fallback parsing for filter response
            return _parse_malformed_filter_response(response.text)
    except Exception as e:
        error_msg = f"Error during filtering: {str(e)}"
        print(f"Filter result: matches=False (error), reason: {error_msg}")
        return False, error_msg  # Default to excluding on error

def summarize_article(content: str) -> ArticleSummary:
    """
    Generate short and detailed summaries for the content using Google Gemini.
    Returns an ArticleSummary pydantic model.
    """
    system_prompt = """You are an expert at summarizing articles, 
    you want to provide a dense and information rich summary of the article.
    
    You are going to create two summaries of the article.
    1. A Short 2 sentence summary for brief scanning.
    2. A detailed summary that has the following: 
        Bullet points of the key topics. 
        A few paragraphs summarizing the document. 
        Some quotes that convey the meaning of the article.

    IMPORTANT: Both fields must be strings, not arrays. Format bullet points as text with line breaks."""

    try:
        # Initialize client with API key
        client = genai.Client(
            api_key=settings.GOOGLE_API_KEY,
        )

        model = "gemini-2.5-flash-preview-05-20"
        prompt = f"{system_prompt}\n\nArticle content:\n{content}"
        
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            ),
        ]
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ArticleSummary,
        )

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        
        # Use structured output with fallback
        try:
            if hasattr(response, 'parsed') and response.parsed:
                # Use the parsed Pydantic object
                result = response.parsed
                print(f"Article summary (structured): {result.short_summary[:100]}...")
                return result
            else:
                # Fallback to JSON parsing
                summary_data = json.loads(response.text)
                # Normalize data to handle lists
                normalized_data = _normalize_summary_data(summary_data)
                
                # Handle missing fields by providing defaults before Pydantic validation
                if 'short_summary' not in normalized_data:
                    normalized_data['short_summary'] = "Error parsing summary"
                if 'detailed_summary' not in normalized_data:
                    normalized_data['detailed_summary'] = "Error parsing detailed summary"
                
                # Handle empty or whitespace-only fields
                if not normalized_data['short_summary'] or normalized_data['short_summary'].isspace():
                    normalized_data['short_summary'] = "Error parsing summary"
                if not normalized_data['detailed_summary'] or normalized_data['detailed_summary'].isspace():
                    normalized_data['detailed_summary'] = "Error parsing detailed summary"
                    
                return ArticleSummary(**normalized_data)
        except (json.JSONDecodeError, AttributeError) as json_error:
            error_msg = f"JSON parsing error in summarize_article: {json_error}"
            print(error_msg)
            print(f"Raw response text: {response.text}")
            
            # Log the entire response to file for debugging
            _log_llm_response_to_file(response.text, "summarize_article", error_msg)
            
            # Try to extract summaries from malformed JSON using fallback parsing
            return _parse_malformed_summary_response(response.text)
        except Exception as pydantic_error:
            error_msg = f"Pydantic validation error in summarize_article: {pydantic_error}"
            print(error_msg)
            print(f"Raw response text: {response.text}")
            
            # Log the entire response to file for debugging
            _log_llm_response_to_file(response.text, "summarize_article", error_msg)
            
            # Try to extract summaries from malformed JSON using fallback parsing
            return _parse_malformed_summary_response(response.text)
    
    except Exception as e:
        print(f"Error in summarize_article: {e}")
        return ArticleSummary(
            short_summary="Error generating summary",
            detailed_summary="Error generating detailed summary"
        )

def analyze_pdf(pdf_data: bytes) -> PdfAnalysis:
    """
    Analyze PDF content to extract title and generate summaries using Google Gemini.
    
    Args:
        pdf_data: Raw PDF bytes data
    
    Returns:
        PdfAnalysis pydantic model with title, short_summary, and detailed_summary
    """
    system_prompt = """You are an expert at analyzing PDF documents.
    
    Your task is to:
    1. Extract the title of the document
    2. Create a short 2 sentence summary for brief scanning
    3. A detailed summary that has the following: 
        Bullet points of the key topics. 
        A few paragraphs summarizing the document. 
        Some quotes that convey the meaning of the article.
        Please include descriptions of diagrams.
    
    IMPORTANT: All fields must be strings, not arrays. Format bullet points as text with line breaks."""

    try:
        # Initialize client with API key
        client = genai.Client(
            api_key=settings.GOOGLE_API_KEY,
        )

        model = "gemini-2.5-flash-preview-05-20"
        
        contents = [
            types.Part.from_bytes(
                data=pdf_data,
                mime_type='application/pdf',
            ),
            system_prompt
        ]
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=PdfAnalysis,
        )

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        
        # Use structured output with fallback
        try:
            if hasattr(response, 'parsed') and response.parsed:
                # Use the parsed Pydantic object
                result = response.parsed
                print(f"PDF analysis (structured): title='{result.title}', summary: {result.short_summary[:100]}...")
                return result
            else:
                # Fallback to JSON parsing
                analysis_data = json.loads(response.text)
                
                # Handle missing fields by providing defaults before Pydantic validation
                if 'title' not in analysis_data:
                    analysis_data['title'] = "Untitled PDF Document"
                if 'short_summary' not in analysis_data:
                    analysis_data['short_summary'] = "Error parsing summary"
                if 'detailed_summary' not in analysis_data:
                    analysis_data['detailed_summary'] = "Error parsing detailed summary"
                
                # Handle empty or whitespace-only fields
                if not analysis_data['title'] or analysis_data['title'].isspace():
                    analysis_data['title'] = "Untitled PDF Document"
                if not analysis_data['short_summary'] or analysis_data['short_summary'].isspace():
                    analysis_data['short_summary'] = "Error parsing summary"
                if not analysis_data['detailed_summary'] or analysis_data['detailed_summary'].isspace():
                    analysis_data['detailed_summary'] = "Error parsing detailed summary"
                    
                return PdfAnalysis(**analysis_data)
        except (json.JSONDecodeError, AttributeError) as json_error:
            error_msg = f"JSON parsing error in analyze_pdf: {json_error}"
            print(error_msg)
            print(f"Raw response text: {response.text}")
            
            # Log the entire response to file for debugging
            _log_llm_response_to_file(response.text, "analyze_pdf", error_msg)
            
            # Return fallback analysis
            return PdfAnalysis(
                title="Error extracting title",
                short_summary="Error parsing summary",
                detailed_summary="Error parsing detailed summary"
            )
        except Exception as pydantic_error:
            error_msg = f"Pydantic validation error in analyze_pdf: {pydantic_error}"
            print(error_msg)
            print(f"Raw response text: {response.text}")
            
            # Log the entire response to file for debugging
            _log_llm_response_to_file(response.text, "analyze_pdf", error_msg)
            
            # Return fallback analysis
            return PdfAnalysis(
                title="Error extracting title",
                short_summary="Error parsing summary",
                detailed_summary="Error parsing detailed summary"
            )
    
    except Exception as e:
        print(f"Error in analyze_pdf: {e}")
        return PdfAnalysis(
            title="Error analyzing PDF",
            short_summary="Error generating PDF summary",
            detailed_summary="Error generating detailed PDF summary"
        )


def summarize_pdf(pdf_data: bytes) -> ArticleSummary:
    """
    Generate short and detailed summaries for PDF content using Google Gemini.
    
    Args:
        pdf_data: Raw PDF bytes data
    
    Returns:
        ArticleSummary pydantic model
    """
    system_prompt = """You are an expert at summarizing PDF documents.
    
    You are going to create two summaries of the PDF document.
    1. A Short 2 sentence summary for brief scanning.
    2. A detailed summary that starts with bullet points of the key topics
     and then a few paragraphs summarizing the document.

    IMPORTANT: Both fields must be strings, not arrays. Format bullet points as text with line breaks."""

    try:
        # Initialize client with API key
        client = genai.Client(
            api_key=settings.GOOGLE_API_KEY,
        )

        model = "gemini-2.5-flash-preview-05-20"
        
        contents = [
            types.Part.from_bytes(
                data=pdf_data,
                mime_type='application/pdf',
            ),
            system_prompt
        ]
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ArticleSummary,
        )

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        
        # Use structured output with fallback
        try:
            if hasattr(response, 'parsed') and response.parsed:
                # Use the parsed Pydantic object
                result = response.parsed
                print(f"PDF summary (structured): {result.short_summary[:100]}...")
                return result
            else:
                # Fallback to JSON parsing
                summary_data = json.loads(response.text)
                # Normalize data to handle lists
                normalized_data = _normalize_summary_data(summary_data)
                
                # Handle missing fields by providing defaults before Pydantic validation
                if 'short_summary' not in normalized_data:
                    normalized_data['short_summary'] = "Error parsing summary"
                if 'detailed_summary' not in normalized_data:
                    normalized_data['detailed_summary'] = "Error parsing detailed summary"
                
                # Handle empty or whitespace-only fields
                if not normalized_data['short_summary'] or normalized_data['short_summary'].isspace():
                    normalized_data['short_summary'] = "Error parsing summary"
                if not normalized_data['detailed_summary'] or normalized_data['detailed_summary'].isspace():
                    normalized_data['detailed_summary'] = "Error parsing detailed summary"
                    
                return ArticleSummary(**normalized_data)
        except (json.JSONDecodeError, AttributeError) as json_error:
            error_msg = f"JSON parsing error in summarize_pdf: {json_error}"
            print(error_msg)
            print(f"Raw response text: {response.text}")
            
            # Log the entire response to file for debugging
            _log_llm_response_to_file(response.text, "summarize_pdf", error_msg)
            
            # Try to extract summaries from malformed JSON using fallback parsing
            return _parse_malformed_summary_response(response.text)
        except Exception as pydantic_error:
            error_msg = f"Pydantic validation error in summarize_pdf: {pydantic_error}"
            print(error_msg)
            print(f"Raw response text: {response.text}")
            
            # Log the entire response to file for debugging
            _log_llm_response_to_file(response.text, "summarize_pdf", error_msg)
            
            # Try to extract summaries from malformed JSON using fallback parsing
            return _parse_malformed_summary_response(response.text)
    
    except Exception as e:
        print(f"Error in summarize_pdf: {e}")
        return ArticleSummary(
            short_summary="Error generating PDF summary",
            detailed_summary="Error generating detailed PDF summary"
        )


def summarize_text(content: str) -> str:
    """
    Generate a summary for the given text content using Google Gemini.
    This is a simplified function for basic summarization needs.
    Returns a single summary string.
    """
    prompt = f"""Please provide a concise summary of the following article content in 2-3 sentences:

{content}"""

    try:
        # Initialize client with API key
        client = genai.Client(
            api_key=settings.GOOGLE_API_KEY,
        )

        model = "gemini-2.5-flash-preview-05-20"
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            ),
        ]
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="text/plain",
        )

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        return response.text.strip()
    except Exception as e:
        print(f"Error in summarize_text: {e}")
        return "Error generating summary"

def summarize_podcast_transcript(transcript_text: str) -> ArticleSummary:
    """
    Generate short and detailed summaries for podcast transcript content using Google Gemini.
    
    Args:
        transcript_text: The transcript text from the podcast
    
    Returns:
        ArticleSummary pydantic model
    """
    system_prompt = """You are an expert at summarizing podcast transcripts.
    
    You are going to create two summaries of the podcast transcript.
    1. A Short 2 sentence summary for brief scanning.
    2. A detailed summary that starts with bullet points of the key topics discussed
     and then a few paragraphs summarizing the main points and insights from the podcast.

    IMPORTANT: Both fields must be strings, not arrays. Format bullet points as text with line breaks."""

    try:
        # Initialize client with API key
        client = genai.Client(
            api_key=settings.GOOGLE_API_KEY,
        )

        model = "gemini-2.5-flash-preview-05-20"
        prompt = f"{system_prompt}\n\nPodcast transcript:\n{transcript_text}"
        
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            ),
        ]
        generate_content_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ArticleSummary,
        )

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        
        # Use structured output with fallback
        try:
            if hasattr(response, 'parsed') and response.parsed:
                # Use the parsed Pydantic object
                result = response.parsed
                print(f"Podcast summary (structured): {result.short_summary[:100]}...")
                return result
            else:
                # Fallback to JSON parsing
                summary_data = json.loads(response.text)
                # Normalize data to handle lists
                normalized_data = _normalize_summary_data(summary_data)
                
                # Handle missing fields by providing defaults before Pydantic validation
                if 'short_summary' not in normalized_data:
                    normalized_data['short_summary'] = "Error parsing summary"
                if 'detailed_summary' not in normalized_data:
                    normalized_data['detailed_summary'] = "Error parsing detailed summary"
                
                # Handle empty or whitespace-only fields
                if not normalized_data['short_summary'] or normalized_data['short_summary'].isspace():
                    normalized_data['short_summary'] = "Error parsing summary"
                if not normalized_data['detailed_summary'] or normalized_data['detailed_summary'].isspace():
                    normalized_data['detailed_summary'] = "Error parsing detailed summary"
                    
                return ArticleSummary(**normalized_data)
        except (json.JSONDecodeError, AttributeError) as json_error:
            error_msg = f"JSON parsing error in summarize_podcast_transcript: {json_error}"
            print(error_msg)
            print(f"Raw response text: {response.text}")
            
            # Log the entire response to file for debugging
            _log_llm_response_to_file(response.text, "summarize_podcast_transcript", error_msg)
            
            # Try to extract summaries from malformed JSON using fallback parsing
            return _parse_malformed_summary_response(response.text)
        except Exception as pydantic_error:
            error_msg = f"Pydantic validation error in summarize_podcast_transcript: {pydantic_error}"
            print(error_msg)
            print(f"Raw response text: {response.text}")
            
            # Log the entire response to file for debugging
            _log_llm_response_to_file(response.text, "summarize_podcast_transcript", error_msg)
            
            # Try to extract summaries from malformed JSON using fallback parsing
            return _parse_malformed_summary_response(response.text)
    
    except Exception as e:
        print(f"Error in summarize_podcast_transcript: {e}")
        return ArticleSummary(
            short_summary="Error generating podcast summary",
            detailed_summary="Error generating detailed podcast summary"
        )
