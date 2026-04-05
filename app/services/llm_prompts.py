"""
Shared LLM prompt generation for content summarization.
Used by both OpenAI and Anthropic LLM services to ensure consistency.
"""

SPECIALIZED_EDITORIAL_TEMPLATE_CONFIGS = {
    "editorial_podcast": {
        "source_name": "a podcast transcript or episode",
        "template": "podcast",
        "source_fields": [
            '    "thesis": "The central claim or frame of the episode",',
            '    "speakers": ["Named speakers or roles"],',
            '    "notable_arguments": ["Important argument or perspective"],',
            '    "practical_takeaways": ["Operational or practical takeaway"]',
        ],
        "source_guidelines": [
            "Capture the guest or host thesis, not just the topic area.",
            "Use speakers to distinguish viewpoints when the conversation includes disagreement or contrast.",
            "Prefer practical takeaways, execution advice, and concrete examples over banter or scene-setting.",
        ],
        "user_message": "Podcast Transcript:\n\n{content}",
    },
    "editorial_substack": {
        "source_name": "a newsletter or essay",
        "template": "substack",
        "source_fields": [
            '    "thesis": "The author\'s central thesis",',
            '    "supporting_arguments": ["Major supporting argument"],',
            '    "evidence": ["Evidence, examples, or references the author uses"],',
            '    "implications": ["What follows if the thesis is right"]',
        ],
        "source_guidelines": [
            "Treat the piece as an argument: identify the thesis, the support, and the implications.",
            "Separate the author's framing from the strongest evidence they actually provide.",
            "Call out omissions or weak support in key_points when relevant.",
        ],
        "user_message": "Essay Content:\n\n{content}",
    },
    "editorial_twitter": {
        "source_name": "an X/Twitter post or linked thread",
        "template": "twitter",
        "source_fields": [
            '    "primary_claim": "The main claim or assertion being made",',
            '    "evidence": ["Evidence directly supplied in the post or linked context"],',
            '    "caveats": ["Important missing context, uncertainty, or caveat"],',
            '    "linked_context": ["Key context from links, screenshots, or embedded references when available"]',
        ],
        "source_guidelines": [
            "Distinguish clearly between what is asserted, what is evidenced, and what remains uncertain.",
            "If the post links to a richer source, prioritize the linked source over the rhetoric of the post.",
            "Keep the narrative tighter and less essay-like than for a long article.",
        ],
        "user_message": "Post and Linked Context:\n\n{content}",
    },
    "editorial_research": {
        "source_name": "a research paper or technical PDF",
        "template": "research",
        "source_fields": [
            '    "hypothesis": "The central research question, thesis, or hypothesis",',
            '    "methods": ["Method, dataset, experiment, or evidence base"],',
            '    "arguments": ["Main claim or result supported by the work"],',
            '    "limitations": ["Important limitation, confound, or scope boundary"],',
            '    "implications": ["Practical or research implication"]',
        ],
        "source_guidelines": [
            "Prioritize hypothesis, methods, results, and limitations over rhetorical framing.",
            "Do not overstate conclusions beyond what the evidence supports.",
            "When possible, preserve quantitative findings, evaluation conditions, and important caveats.",
        ],
        "user_message": "Research Content:\n\n{content}",
    },
    "editorial_github": {
        "source_name": "a GitHub repository or technical project documentation",
        "template": "github",
        "source_fields": [
            '    "overview": "What the project is for and what problem it solves",',
            '    "architecture": ["Core subsystem, design choice, or structural pattern"],',
            '    "interfaces": ["CLI, API, SDK, workflow, or integration surface"],',
            '    "setup_constraints": ["Important dependency, setup, or environment constraint"],',
            '    "maturity_signals": ["Maintenance, documentation, tests, adoption, or stability signal"],',
            '    "best_fit_use_cases": ["Who should use it and for what"]',
        ],
        "source_guidelines": [
            "Summarize the repo like a technical product: purpose, architecture, interfaces, and adoption signals.",
            "Call out setup friction, hidden dependencies, or maturity limits instead of treating the README as marketing.",
            "Prefer what a developer needs to know before using or extending the project.",
        ],
        "user_message": "Repository or Documentation Content:\n\n{content}",
    },
}


# ruff: noqa: E501
def generate_summary_prompt(
    content_type: str, max_bullet_points: int, max_quotes: int
) -> tuple[str, str]:
    """
    Generate optimized prompts for LLM summarization with caching support.

    This function creates prompts structured for efficient caching:
    - System message contains static instructions (cached by LLM providers)
    - User message template is for variable content (not cached)

    Args:
        content_type: Type of content ("article", "podcast", "news_digest", "hackernews", "interleaved", "long_bullets", "editorial_narrative", "editorial_podcast", "editorial_substack", "editorial_twitter", "editorial_research", "editorial_github")
        max_bullet_points: Maximum number of bullet points to generate
        max_quotes: Maximum number of quotes to extract

    Returns:
        Tuple of (system_message, user_message_template)
        The user_message_template contains a {content} placeholder.
    """
    normalized_type = content_type.lower()
    if normalized_type == "article":
        normalized_type = "editorial_narrative"
    elif normalized_type == "podcast":
        normalized_type = "editorial_podcast"
    if normalized_type == "news":
        normalized_type = "news_digest"
    content_type = normalized_type

    if content_type == "hackernews":
        system_message = f"""You are an expert content analyst. Analyze HackerNews discussions, which
include linked article content (if any) and community comments. Provide a structured
summary that captures both the main content and key insights from the discussion.

Important:
- Generate a descriptive title that describes the article in detail.
- There may be technical terms in the content, please don't make any spelling errors.
- Extract actual quotes from both the article and notable comments
- Make bullet points capture insights from BOTH content and discussion
- Include {max_bullet_points} bullet points that blend article + comment insights
- Include up to {max_quotes} notable quotes (can be from article or comments)
- IMPORTANT: Each quote must be at least 10 characters long - do not include short snippets
- For quotes from comments, use format "HN user [username]" as context
- Include 3-8 relevant topic tags
- Generate 3-5 thought-provoking questions that help readers think critically about the content
- Identify 2-4 counter-arguments or alternative perspectives mentioned in comments or implied by the content
- Add a "classification" field with either "to_read" or "skip"
- Add a special section in the overview about the HN community response
- Set "full_markdown" to include the article content AND the comments


Questions Guidelines:
- Questions should prompt critical thinking about implications, limitations, or applications
- Draw from both the article content and HN discussion
- Focus on "what if", "how might", "what are the implications" style questions

Counter Arguments Guidelines:
- Look for dissenting opinions or skeptical viewpoints in HN comments
- Identify assumptions that could be challenged
- Include technical critiques or alternative approaches mentioned
- If no strong counter-arguments exist, you may leave this list empty

Classification Guidelines:
- Consider both article quality AND discussion quality
- High-quality technical discussions should be "to_read" even if article is average
- Set to "skip" if both article and comments lack substance"""

        user_message = "Analyze this content and discussion:\n\n{content}"

    elif content_type == "news_digest":
        system_message = f"""You are an expert news editor. Read provided article content and any additional
aggregator context, then produce a concise JSON object with the following fields:

{{
  "title": "Descriptive headline highlighting the core takeaway",
  "article_url": "Canonical article URL",
  "key_points": [
    "Bullet #1 in 160 characters or less",
    "Bullet #2",
    "Bullet #3"  // include up to {max_bullet_points} total, prioritising impact
  ],
  "summary": "Optional 2-sentence overview (≤ 280 characters). Use null if redundant.",
  "classification": "to_read" | "skip"
}}

Guidelines:
- Focus on why the story matters, not just what happened.
- There may be technical terms in the content, please don't make any spelling errors.
- Keep each key point self-contained, concrete, and free of markdown or numbering.
- Prefer action verbs, quantitative figures, and clear implications.
- If the content is low-value or promotional, set classification to "skip" but still
  surface truthful key points.
- Never include markdown, topics, quotes, or any extra fields.
"""

        user_message = "Article & Aggregator Context:\n\n{content}"

    elif content_type == "daily_news_rollup":
        system_message = """You are an expert news editor preparing a single daily rollup from many source stories.

Return a JSON object with exactly these fields:
{
  "title": "Descriptive headline (max 110 characters) capturing the day's main themes",
  "summary": "Required 2-sentence overview explaining the day at a glance (≤ 500 characters).",
  "key_points": [
    "One bullet for a distinct major topic, story cluster, or consequential development",
    "A bullet may optionally use a second line for one short comment quote, for example: Main point.\\n\\"Quote\\" - commenter"
  ]
}

Guidelines:
- Cover the major themes of the day, not just the single top story.
- Emit as many bullets as needed to cover the important distinct topics.
- Merge near-duplicate stories into one broader bullet when they tell the same story.
- Stop adding bullets when additional bullets would be redundant.
- Prefer concrete entities, numbers, dates, and implications over vague phrasing.
- Most bullets should stay as a single sentence.
- When a provided comment quote materially sharpens a point, you may append one extra line inside that same key_points string.
- Use at most one quote per bullet, and only on a few bullets where it clearly improves the summary.
- Keep quote lines short, high-signal, and verbatim to the provided comment context; do not invent commenters or wording.
- Treat minor promotional, meta, or duplicative items as supporting context unless they materially change the day.
- Keep each bullet self-contained, concrete, and free of markdown or numbering.
- Never include article URLs, classifications, topics, or extra fields. Do not emit a separate quotes field.
"""

        user_message = "Daily News Rollup Context:\n\n{content}"

    elif content_type in SPECIALIZED_EDITORIAL_TEMPLATE_CONFIGS:
        config = SPECIALIZED_EDITORIAL_TEMPLATE_CONFIGS[content_type]
        source_details_block = '  "source_details": {\n'
        source_details_block += f'    "template": "{config["template"]}",\n'
        source_details_block += "\n".join(config["source_fields"])
        source_details_block += "\n  },\n"
        source_guidelines_text = "\n".join(f"- {guideline}" for guideline in config["source_guidelines"])
        system_message = f"""You are an expert editor writing an information-dense narrative summary for {config["source_name"]}.

Return a JSON object with exactly these fields:
{{
  "title": "Descriptive title (max 110 characters)",
  "editorial_narrative": "1-2 tight paragraphs with a clear thesis and factual synthesis",
  "quotes": [
    {{
      "text": "Direct quote from the content (min 10 chars)",
      "attribution": "Who said it (optional)"
    }}
  ],
  "key_points": [
    {{
      "point": "Concrete key point"
    }}
  ],
{source_details_block}  "classification": "to_read" | "skip",
  "summarization_date": "ISO 8601 timestamp"
}}

Guidelines:
- Start the first paragraph with the core thesis or the most consequential takeaway.
- Use only 1-2 paragraphs for the full narrative.
- Keep the narrative heavily information-dense: every sentence should carry concrete signal (named entities, numbers, dates, constraints, implications).
- Target roughly 140-220 words across the full narrative.
- Avoid filler, repetition, and generic framing.
- Include 2-{max_quotes} direct quotes; integrate quotes naturally into the narrative prose when possible.
- key_points: include 4-{max_bullet_points} non-overlapping points.
- Each key point must be specific and evidence-oriented, not vague advice.
- There may be technical terms in the content; preserve exact spelling.
- Keep source_details accurate, concise, and fully grounded in the source. Do not invent structure that the source does not support.
{source_guidelines_text}
- Never include markdown or any fields outside this schema.

Classification Guidelines:
- Set classification to "skip" if the content lacks depth, evidence, or practical signal.
- Set classification to "to_read" if the content delivers substantial insight, original reporting, or high-signal analysis.
"""
        user_message = config["user_message"]

    elif content_type == "editorial_narrative":
        system_message = f"""You are an expert editor writing an information-dense narrative summary.

Return a JSON object with exactly these fields:
{{
  "title": "Descriptive title (max 110 characters)",
  "editorial_narrative": "1-2 tight paragraphs with a clear thesis and factual synthesis",
  "quotes": [
    {{
      "text": "Direct quote from the content (min 10 chars)",
      "attribution": "Who said it (optional)"
    }}
  ],
  "key_points": [
    {{
      "point": "Concrete key point"
    }}
  ],
  "classification": "to_read" | "skip",
  "summarization_date": "ISO 8601 timestamp"
}}

Guidelines:
- Start the first paragraph with the core thesis or the most consequential takeaway.
- Use only 1-2 paragraphs for the full narrative.
- Keep the narrative heavily information-dense: every sentence should carry concrete signal (named entities, numbers, dates, constraints, implications).
- Keep it slightly shorter: target roughly 140-220 words across the full narrative.
- Avoid filler, repetition, and generic framing.
- Include 2-{max_quotes} direct quotes; integrate at least 2 quotes naturally into the narrative prose.
- key_points: include 4-{max_bullet_points} non-overlapping points.
- Each key point must be specific and evidence-oriented, not vague advice.
- There may be technical terms in the content; preserve exact spelling.
- Never include markdown or any fields outside this schema.

Classification Guidelines:
- Set classification to "skip" if the content lacks depth, evidence, or practical signal.
- Set classification to "to_read" if the content delivers substantial insight, original reporting, or high-signal analysis.
"""

        user_message = "Content:\n\n{content}"

    elif content_type == "long_bullets":
        system_message = f"""You are an expert content analyst. Produce an exhaustive bullet-first summary
where each bullet can expand into a brief detail and supporting quotes.

Return a JSON object with exactly these fields:
{{
  "title": "Descriptive title (max 110 characters)",
  "points": [
    {{
      "text": "One-sentence main bullet",
      "detail": "2-3 sentences that expand the bullet",
      "quotes": [
        {{
          "text": "Direct quote supporting the point (min 20 chars)",
          "attribution": "Who said it (optional)",
          "context": "Context if needed (optional)"
        }}
      ]
    }}
  ],
  "classification": "to_read" | "skip",
  "summarization_date": "ISO 8601 timestamp"
}}

Guidelines:
- points: target 10-20 bullets; include up to {max_bullet_points} when needed for completeness.
- Each point must include 1-3 quotes that support the claim.
- Each "text" is one sentence, concrete and specific.
- "detail" expands the point with evidence, numbers, names, and implications.
- Quotes must be verbatim from the content; avoid duplication across points.
- There may be technical terms in the content, please don't make any spelling errors.
- Never include markdown or extra fields.

Classification Guidelines:
- Set classification to "skip" if the content:
  * Is light on content or seems like marketing/promotional material
  * Is general mainstream news without depth or unique insights
  * Lacks substantive information or analysis
  * Appears to be clickbait or sensationalized
- Set classification to "to_read" if the content:
  * Contains in-depth analysis or unique insights
  * Provides technical or specialized knowledge
  * Offers original research or investigation
  * Has educational or informative value"""

        user_message = "Content:\n\n{content}"

    elif content_type == "structured":
        system_message = f"""You are an expert content analyst. Return a structured JSON summary.

Return a JSON object with exactly these fields:
{{
  "title": "Descriptive title (max 110 characters)",
  "overview": "Brief overview paragraph (min 50 chars)",
  "bullet_points": [
    {{
      "text": "Concrete key point",
      "category": "optional category label"
    }}
  ],
  "quotes": [
    {{
      "text": "Direct quote from the content (min 10 chars)",
      "attribution": "Who said it (optional)",
      "context": "Context if needed (optional)"
    }}
  ],
  "topics": ["topic1", "topic2"],
  "questions": ["question1"],
  "counter_arguments": ["counter argument 1"],
  "classification": "to_read" | "skip",
  "summarization_date": "ISO 8601 timestamp",
  "full_markdown": "Readable markdown form of the source"
}}

Guidelines:
- bullet_points: include 6-{max_bullet_points} high-signal points.
- quotes: include up to {max_quotes} non-trivial quotes.
- Keep details specific with names, numbers, and implications.
- There may be technical terms in the content, please don't make any spelling errors.
- Never include markdown outside JSON or any extra fields.
"""

        user_message = "Content:\n\n{content}"

    else:
        # Interleaved format v2: key points, quotes list, topic bullets
        system_message = f"""You are an expert content analyst creating interleaved summaries that
surface top key points first, then expand each topic with focused bullets, and
separate longer quotes into their own list.

Return a JSON object with exactly these fields:
{{
  "title": "Descriptive title (max 110 characters)",
  "hook": "2-3 sentence hook (min 80 chars)",
  "key_points": [
    {{"text": "Key point 1"}},
    {{"text": "Key point 2"}},
    {{"text": "Key point 3"}}
  ],
  "topics": [
    {{
      "topic": "Topic name",
      "bullets": [
        {{"text": "Bullet 1"}},
        {{"text": "Bullet 2"}}
      ]
    }}
  ],
  "quotes": [
    {{
      "text": "Longer direct quote (min 20 chars)",
      "attribution": "Who said it (optional)",
      "context": "Context if needed (optional)"
    }}
  ],
  "takeaway": "2-3 sentence takeaway (min 80 chars)",
  "classification": "to_read" | "skip",
  "summarization_date": "ISO 8601 timestamp"
}}

Guidelines:
- key_points: 3-5 total, highest signal items only. No quotes inside key_points.
- topics: cover all major themes; each topic must have 2-3 bullets.
- quotes: include up to {max_quotes} longer quotes that add signal; avoid duplication.
- Use concrete numbers, names, and data points when available.
- There may be technical terms in the content, please don't make any spelling errors.
- Never include markdown or extra fields.

Classification Guidelines:
- Set classification to "skip" if the content:
  * Is light on content or seems like marketing/promotional material
  * Is general mainstream news without depth or unique insights
  * Lacks substantive information or analysis
  * Appears to be clickbait or sensationalized
- Set classification to "to_read" if the content:
  * Contains in-depth analysis or unique insights
  * Provides technical or specialized knowledge
  * Offers original research or investigation
  * Has educational or informative value"""

        user_message = "Content:\n\n{content}"

    return system_message, user_message


def creativity_to_style_hints(creativity: int) -> str:
    """
    Map creativity level (1-10) to style guidance for tweet generation.

    Args:
        creativity: Integer 1-10 indicating desired creativity level

    Returns:
        String with style hints for the LLM prompt
    """
    if creativity <= 3:
        # Low creativity: Journalist/analyst voice
        return """Write like a tech journalist reporting facts.
- Lead with the most important data point or finding
- No emojis, no rhetorical questions
- Stick to verified claims from the article
- Neutral tone - let the facts speak"""

    elif creativity <= 7:
        # Medium creativity: Thoughtful commentator
        return """Write like a thoughtful industry insider sharing an interesting find.
- Can add one opinion or insight beyond the facts
- Sparing emoji use (max 1, only if natural)"""

    else:
        # High creativity: Viral-worthy takes
        return """Write like a respected thought leader with a strong point of view.
- Lead with a surprising angle, contrarian take, or pattern interrupt
- Use tension and curiosity
- Wit and memorable phrasing encouraged - make it quotable
- Can be provocative but substantive - no empty controversy
- Emojis allowed (max 2) only if they add punch"""


def length_to_char_range(length: str) -> tuple[int, int]:
    """
    Map length preference to character range.

    Args:
        length: "short", "medium", or "long"

    Returns:
        Tuple of (min_chars, max_chars)
    """
    ranges = {
        "short": (100, 180),
        "medium": (180, 280),
        "long": (280, 400),
    }
    return ranges.get(length, (180, 280))


def get_tweet_generation_prompt(
    creativity: int,
    user_message: str | None = None,
    length: str = "medium",
) -> tuple[str, str]:
    """
    Generate prompts for tweet generation from article/news content.

    Args:
        creativity: Integer 1-10 indicating desired creativity level
        user_message: Optional user guidance for tweet generation
        length: Tweet length preference ("short", "medium", "long")

    Returns:
        Tuple of (system_message, user_message_template)
        The user_message_template contains placeholders for content details.
    """
    style_hints = creativity_to_style_hints(creativity)
    min_chars, max_chars = length_to_char_range(length)

    system_message = f"""You are an expert social media writer for a tech/AI/startup audience.
Your task is to generate exactly 3 tweet suggestions with their corresponding probabilities about the provided content.

Core Guidelines:
- Each tweet must be {min_chars}-{max_chars} characters (strict limit: {max_chars} max)
- Be concise and impactful with one main idea per tweet
- Start with a strong hook that grabs attention
- Conversational tone
- ALWAYS avoid colons (:) and emdashs (—)
- No clickbait. Provide genuine value and insight
- Frame as "great article, this stood out to me" style when appropriate
- Include the article URL when provided
- Self-contained. Tweet should be understandable even without clicking the link
- No markdown, no multi-tweet threads, no numbered lists
- Focus on a single key insight, not a summary
- Avoid rhetorical questions

Style for this creativity level ({creativity}/10):
{style_hints}

Output Format:
Return ONLY valid JSON matching this exact structure:
{{
  "suggestions": [
    {{"id": 1, "text": "tweet text here", "style_label": "descriptive label like 'insightful' or 'provocative'"}},
    {{"id": 2, "text": "tweet text here", "style_label": "label"}},
    {{"id": 3, "text": "tweet text here", "style_label": "label"}}
  ]
}}

Do not include markdown code fences, commentary, or any text outside the JSON."""

    # Build user message with optional guidance
    user_guidance = ""
    if user_message:
        user_guidance = f"\n\nUser guidance: {user_message}"

    user_template = (
        """Content to tweet about:

Title: {title}
Source: {source} ({platform})
URL: {url}

Summary:
{summary}

Key Points:
{key_points}

Notable Quotes:
{quotes}

Thought-Provoking Questions:
{questions}

Counter-Arguments/Alternative Perspectives:
{counter_arguments}"""
        + user_guidance
    )

    return system_message, user_template
