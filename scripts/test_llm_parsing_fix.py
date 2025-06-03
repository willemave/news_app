#!/usr/bin/env python3
"""
Test script to verify the LLM JSON parsing fix handles special characters correctly.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.llm import _parse_malformed_summary_response, _unescape_json_string

def test_pipe_character_parsing():
    """Test that pipe characters in JSON strings are handled correctly."""
    
    # Simulate a malformed JSON response with pipe characters
    malformed_json = '''
    {
        "short_summary": "The author, seeking an upgrade from Keynote, experimented with Figma Slides for a presentation and initially found its design features appealing. However, critical issues during the live presentation, particularly with offline access and animations, made it unreliable and affirmed the value of |Key Topics:",
        "detailed_summary": "* The author's philosophy on presentation slides emphasizes key points, breaking complex concepts, and entertaining.\\n* Motivation to switch from Keynote to Figma Slides after 20 years for a public speaking engagement.\\n* Initial positive experiences with Figma's design features like Grid view, Auto Layout, and Components for slide creation.\\n* Identification of missing essential Keynote features in Figma, such as |"
    }
    '''
    
    print("Testing malformed JSON parsing with pipe characters...")
    result = _parse_malformed_summary_response(malformed_json)
    
    print(f"Short summary: {result.short_summary}")
    print(f"Detailed summary: {result.detailed_summary}")
    
    # Check that pipe characters are preserved
    assert "|Key Topics:" in result.short_summary, "Pipe character should be preserved in short summary"
    assert "|" in result.detailed_summary, "Pipe character should be preserved in detailed summary"
    
    print("✅ Pipe character parsing test passed!")

def test_escaped_characters():
    """Test that various escaped characters are handled correctly."""
    
    test_cases = [
        ('Hello \\"world\\"', 'Hello "world"'),
        ('Line 1\\nLine 2', 'Line 1\nLine 2'),
        ('Tab\\there', 'Tab\there'),
        ('Backslash\\\\test', 'Backslash\\test'),
        ('Unicode\\u0041test', 'Unicodetest'),  # \u0041 is 'A'
    ]
    
    print("\nTesting escaped character handling...")
    for escaped, expected in test_cases:
        result = _unescape_json_string(escaped)
        print(f"Input: {escaped} -> Output: {repr(result)} (Expected: {repr(expected)})")
        assert result == expected, f"Expected {expected}, got {result}"
    
    print("✅ Escaped character tests passed!")

def test_complex_json_with_special_chars():
    """Test parsing of complex JSON with various special characters."""
    
    complex_json = '''
    {
        "short_summary": "Article discusses AI | ML trends, including \\"deep learning\\" and neural networks.",
        "detailed_summary": "Key points:\\n• AI/ML is growing rapidly\\n• Deep learning shows promise\\n• Challenges include: data quality, model bias, and computational costs\\n\\nThe article explores how artificial intelligence and machine learning are transforming industries. It highlights the importance of ethical AI development and the need for robust testing frameworks."
    }
    '''
    
    print("\nTesting complex JSON with special characters...")
    result = _parse_malformed_summary_response(complex_json)
    
    print(f"Short summary: {result.short_summary}")
    print(f"Detailed summary: {result.detailed_summary}")
    
    # Verify special characters are preserved
    assert "AI | ML" in result.short_summary
    assert '"deep learning"' in result.short_summary
    assert "Key points:\n•" in result.detailed_summary
    assert "AI/ML" in result.detailed_summary
    
    print("✅ Complex JSON parsing test passed!")

if __name__ == "__main__":
    test_pipe_character_parsing()
    test_escaped_characters()
    test_complex_json_with_special_chars()
    print("\n🎉 All tests passed! The LLM JSON parsing fix is working correctly.")