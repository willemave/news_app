#!/usr/bin/env python3
"""
Script to test OpenAI structured summary generation directly with mocked data.
"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.openai_llm import get_openai_summarization_service

# Mock content data
mock_content = {
    "url": "https://xbow.com/blog/gpt-5",
    "title": "GPT-5: The Next Generation of AI",
    "raw_content": """
    # GPT-5: The Next Generation of AI
    
    OpenAI has announced the development of GPT-5, the next generation of their large language model.
    
    ## Key Features
    
    - **Enhanced Reasoning**: GPT-5 shows significant improvements in logical reasoning and problem-solving.
    - **Multimodal Capabilities**: Native support for text, images, audio, and video processing.
    - **Reduced Hallucinations**: New training techniques have dramatically reduced factual errors.
    - **Efficiency**: 10x more efficient than GPT-4 while being more capable.
    
    ## Release Timeline
    
    "We expect GPT-5 to be ready for initial testing in Q2 2025," said Sam Altman, CEO of OpenAI.
    "This represents a major leap forward in artificial general intelligence."
    
    ## Industry Impact
    
    Experts predict GPT-5 will revolutionize:
    - Scientific research and discovery
    - Software development and debugging
    - Creative content generation
    - Medical diagnosis and treatment planning
    
    ## Ethical Considerations
    
    OpenAI has implemented new safety measures including:
    - Advanced content filtering
    - Bias reduction techniques
    - Transparent decision-making processes
    
    The AI community is watching closely as this technology develops.
    """,
    "platform": "generic"
}


def test_structured_summary():
    """Test the structured summary generation."""
    print("Initializing OpenAI service...")
    llm_service = get_openai_summarization_service()
    
    print("\nGenerating structured summary for mock content...")
    print(f"URL: {mock_content['url']}")
    print(f"Title: {mock_content['title']}")
    print("-" * 60)
    
    try:
        # Call the summarize_content method
        summary = llm_service.summarize_content(
            content=mock_content['raw_content'],
            max_bullet_points=6,
            max_quotes=3,
            content_type="article"
        )
        
        if summary:
            print("\n✅ Structured summary generated successfully!")
            print("\nSummary Data:")
            print("=" * 60)
            
            # Handle both Pydantic model and dict
            if hasattr(summary, 'title'):
                # It's a Pydantic model
                print(f"Title: {summary.title}")
                print(f"Classification: {summary.classification}")
                print(f"\nOverview: {summary.overview}")
                
                print(f"\nTopics: {', '.join(summary.topics)}")
                
                if summary.bullet_points:
                    print(f"\nBullet Points ({len(summary.bullet_points)} items):")
                    for i, bp in enumerate(summary.bullet_points[:3], 1):  # Show first 3
                        print(f"  {i}. [{bp.category}] {bp.text}")
                    if len(summary.bullet_points) > 3:
                        print(f"  ... and {len(summary.bullet_points) - 3} more")
                
                if summary.quotes:
                    print(f"\nQuotes ({len(summary.quotes)} items):")
                    for i, q in enumerate(summary.quotes[:2], 1):  # Show first 2
                        print(f"  {i}. \"{q.text}\"")
                        print(f"     Context: {q.context}")
                    if len(summary.quotes) > 2:
                        print(f"  ... and {len(summary.quotes) - 2} more")
            else:
                # It's a dict or JSON string
                if isinstance(summary, str):
                    summary_data = json.loads(summary)
                else:
                    summary_data = summary
                
                print(f"Title: {summary_data.get('title', 'N/A')}")
                print(f"Classification: {summary_data.get('classification', 'N/A')}")
                print(f"\nOverview: {summary_data.get('overview', 'N/A')}")
            
            print("\n" + "=" * 60)
            return True
        else:
            print("\n❌ Failed to generate structured summary (returned None)")
            return False
            
    except Exception as e:
        print(f"\n❌ Error generating structured summary: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("Testing OpenAI Structured Summary Generation")
    print("=" * 60)
    
    success = test_structured_summary()
    
    if success:
        print("\n✅ Test completed successfully!")
    else:
        print("\n❌ Test failed!")
        sys.exit(1)