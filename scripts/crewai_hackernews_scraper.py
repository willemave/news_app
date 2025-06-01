#!/usr/bin/env python3
"""
CrewAI HackerNews Scraper Script

This script uses CrewAI agents to:
1. Fetch the top 10 external article links from Hacker News
2. Scrape and summarize the content of each linked article
3. Generate an HTML report with links and summaries

Requirements:
- OPENAI_API_KEY environment variable
"""

import os
import sys
from crewai import Agent, Task, Crew
from crewai_tools import ScrapeWebsiteTool
from dotenv import load_dotenv

def main():
    """Main function to run the CrewAI HackerNews scraper."""
    
    # Load environment variables from .env file
    load_dotenv()
    
    # Check for required API keys
    openai_api_key = os.getenv("OPENAI_API_KEY")
    
    if not openai_api_key:
        print("Error: OPENAI_API_KEY not found in environment variables.")
        print("Please ensure it is set in your .env file or environment.")
        print("This key is required for LLM-powered summarization.")
        sys.exit(1)
    
    print("✓ API keys found. Starting CrewAI HackerNews Scraper...")
    print("=" * 60)
    
    # Instantiate CrewAI tools
    print("🔧 Initializing CrewAI tools...")

    web_scraper_tool = ScrapeWebsiteTool()  # For scraping and summarizing linked pages
    
    # Define Agent 1: HackerNews Link Collector
    print("🤖 Creating HackerNews Link Collector Agent...")
    link_collector_agent = Agent(
        role='HackerNews Link Collector',
        goal='Find the top 20 external article links from the Hacker News homepage (news.ycombinator.com)',
        backstory='An expert web researcher efficient at finding relevant links from Hacker News. You always return the entire URL not just the domain name.',
        tools=[web_scraper_tool],
        verbose=True,
        allow_delegation=False
    )
    
    # Define Agent 2: Article Summarizer and HTML Report Writer
    print("🤖 Creating Article Summarizer Agent...")
    summarizer_agent = Agent(
        role='Article Summarizer and HTML Report Writer',
        goal='For each provided URL, scrape its entire content, generate a concise multi paragraph summary, and compile all links and summaries into a final HTML report.',
        backstory='A meticulous agent skilled in web content extraction, summarization, and HTML report generation.',
        tools=[web_scraper_tool],
        verbose=True,
        allow_delegation=False
    )
    
    print("✓ Agents created successfully!")
    
    # Define Task 1: Collect Hacker News Links
    print("📋 Creating tasks...")
    collect_links_task = Task(
        description=(
            "Search for the current top 10 external article links on Hacker News (news.ycombinator.com). "
            "Focus on actual articles, not comments or 'Ask HN' posts. "
            "Return a list of these 10 URLs."
        ),
        expected_output='A Python list containing exactly 10 unique URLs of external articles from Hacker News.',
        agent=link_collector_agent
    )
    
    # Define Task 2: Summarize Articles and Create HTML Report
    summarize_and_report_task = Task(
        description=(
            "Process a list of article URLs. For each URL: "
            "1. Scrape the main content of the article using the WebsiteSearchTool. "
            "2. Generate a 1-2 sentence summary of the scraped content. "
            "3. Compile all original article URLs and their summaries into a single HTML formatted string. "
            "The HTML should list each article with its URL (as a clickable link) and its summary."
        ),
        expected_output=(
            "An HTML string containing a list of up to 10 articles. Each article entry should include "
            "the original URL (hyperlinked) and its generated summary. "
            "Example for one article: <p><a href='URL'>Article Title (if available, else URL)</a><br/>Summary text...</p>"
        ),
        agent=summarizer_agent,
        output_file='scripts/hackernews_crew_report.html'
    )
    
    # Assemble the crew
    print("👥 Assembling CrewAI team...")
    hackernews_crew = Crew(
        agents=[link_collector_agent, summarizer_agent],
        tasks=[collect_links_task, summarize_and_report_task],
        verbose=True
    )
    
    # Execute the crew's work
    print("\n🚀 Starting CrewAI execution...")
    print("=" * 60)
    
    try:
        result = hackernews_crew.kickoff()
        
        print("\n" + "=" * 60)
        print("✅ CrewAI HackerNews Scraper completed successfully!")
        print("📄 Report saved to: scripts/hackernews_crew_report.html")
        print("\nYou can open the HTML file in your browser to view the results.")
        
    except Exception as e:
        print(f"\n❌ Error during CrewAI execution: {str(e)}")
        print("Please check your API keys and internet connection.")
        sys.exit(1)

if __name__ == '__main__':
    main()
