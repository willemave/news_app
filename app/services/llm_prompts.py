"""
Shared LLM prompt generation for content summarization.
Used by both OpenAI and Anthropic LLM services to ensure consistency.
"""

# ruff: noqa: E501
TITLE_EXAMPLES = """
<title_examples>
<example>
<title>Global smart glasses shipments grew 110% YoY in H1; Meta's share of the market rose to 73%; AI smart glasses accounted for 78% of shipments, up from 46% YoY</title>
<article>
Research Notes & Blogs

Global Smart Glasses Shipments Soared 110% YoY in H1 2025, With Meta Capturing Over 70% Share

0

August 12, 2025

- _The global smart glasses market grew by 110% YoY in H1 2025, fueled by robust demand for Ray-Ban Meta Smart Glasses and the entry of new players such as Xiaomi and TCL-RayNeo._

- _Meta's share of the global smart glasses market rose to 73% in H1 2025, driven by strong demand and expanded manufacturing capacity at Luxottica, its key production partner._

- _Apart from Meta, key AI glasses OEMs that achieved shipments in H1 2025 included Xiaomi, TCL-RayNeo, Kopin Solos and Thunderobot, with the debut of Xiaomi's AI Glasses being the most awaited event in the industry._

- _More new AI glasses models are expected to enter the market in H2 2025, including upcoming releases from Meta, Alibaba and several smaller players. We expect the rapid growth of the global smart glasses market to continue throughout 2026 and beyond._


**Seoul, Beijing, Berlin, Buenos Aires, Fort Collins, Hong Kong, London, New Delhi, Taipei, Tokyo – Aug 12, 2025**

Global smart glasses shipments grew 110% YoY in H1 2025, according to [**Counterpoint's Global Smart Glasses Model Shipments Tracker**](https://www.counterpointresearch.com/report/post-report-global-smart-glasses-model-shipments-tracker-h1-2025-update). This surge was driven by strong demand for [Ray-Ban Meta Smart Glasses](https://www.counterpointresearch.com/insight/post-insight-research-notes-blogs-rayban-meta-crosses-1million-mark-success-indicates-promising-future-for-lightweight-ar-glasses) and the entry of new players such as Xiaomi, TCL-RayNeo and several smaller brands.

AI [smart glasses](https://www.counterpointresearch.com/coverage/xr-360) accounted for 78% of total shipments in H1 2025, up from 46% in H1 2024 and 66% in H2 2024, largely due to the dominance of Ray-Ban Meta AI Glasses. The AI glasses segment grew by over 250% YoY, significantly outpacing the overall market.

![](https://www.counterpointresearch.com/statics/content/image/20258534210_LqOcm_editor_image.jpg)

Commenting on the overall market performance,[**Senior Research Analyst Flora Tang**](https://www.counterpointresearch.com/opinion_leader/flora)said, "The global tariff crisis for electronic devices during the first half of the year has had a limited impact on the smart glasses market so far, as the situation still appears manageable for key OEMs and their manufacturing partners."

On the competitive front,Tangsaid, "Meta's share in the global smart glasses market rose to 73% in H1 2025, despite the launch of new products from other entrants. Shipments of Ray-Ban Meta AI Glasses grew over 200% YoY during the period, reflecting strong market demand and increased manufacturing capacity at Luxottica, Meta's key production partner. Luxottica plays a critical role in Meta's success, not only by scaling up production but also by supporting product longevity through the expansion of style variants and driving retail sales. According to our channel tracker, Luxottica's own retail networks, including online and offline Ray-Ban stores, Sunglass Hut and LensCrafters, account for a significant portion of the product's sales."

![](https://www.counterpointresearch.com/statics/content/image/20258534913_o0JR8_editor_image.png)Source: Counterpoint's Global Smart Glasses Model Shipments Tracker, H1 2025 Update

Commenting on the market dynamics, Tangsaid, "Beyond Meta, key AI smart glasses OEMs active in H1 2025 included Chinese players such as TCL-RayNeo with its RayNeo V3 series, Xiaomi with its debut Xiaomi AI Glasses, Thunderobot with the AURA smart glasses, and the Kopin Solos AirGo V series. Xiaomi's AI glasses emerged as a dark horse in the global smart glasses market – becoming the fourth best-selling model overall and the third best-selling product in the AI glasses segment – despite being on sale for only about a week in H1 2025. The Xiaomi device's sales were driven by strong support from tech enthusiasts and Mi fans in China. We expect Xiaomi to continue enhancing the product's performance through OTA and software updates in the coming months."

[**Research Analyst Akshay RS**](https://www.counterpointresearch.com/opinion_leader/akshay-r-s) said, "As for the smart audio glasses segment, which currently includes players likeHuawei, Amazon and Mijia (a Xiaomi ecosystem brand), it experienced a decline during the period due to rising competition from AI glasses offering more advanced functionalities, such as photo and video capture, image and object recognition, encyclopedia-based Q&A, live translation and more. In addition, we are seeing new products from Chinese companies, such as Xiaomi AI Glasses and Alibaba's Quark AI Glasses (still in pre-commercial stages), actively exploring glass-based payment solutions. These aim to reduce users' reliance on smartphones in outdoor shopping and food-ordering scenarios."

Driven by the dominance of Ray-Ban Meta AI Glasses, regions where the product is available – such as North America, Western Europe and Australia – lead global smart glasses shipments. In Q2 2025, Meta and Luxottica expanded to India, Mexico and the UAE, which also boosted shipment shares in these markets.

![](https://www.counterpointresearch.com/statics/content/image/2025822019_q44PY_editor_image.png)

More AI smart glasses are expected to enter the market from H2 2025 onward, including launches from internet giants such as Meta and Alibaba. Meta recently introduced the Oakley Meta glasses, featuring improved battery life and enhanced video-shooting quality over the Ray-Ban Meta AI Glasses, and primarily targeting athletes and sports enthusiasts. Our industry checks indicate positive market feedback for this model. We expect Meta will take a more aggressive approach and unveil a broader product lineup at the Meta Connect event to further drive growth. Meanwhile, we believe Apple is also actively exploring this space and developing its first AI glasses.

In the processing space, [Qualcomm](https://www.counterpointresearch.com/insight/counterpoint-conversations-qualcomm-ai-xr-future) recently launched an upgraded version of its premium smart glasses SoC – the AR 1+ Gen 1 – which Qualcomm claims is 26% smaller and consumes 7% less power, enabling slimmer product designs and longer battery life. In parallel, various Chinese chipset makers, such as Allwinner Technology, are entering the market with budget SoC solutions aimed at powering more affordable smart glasses.

Given the market's momentum and continued influx of new entrants, we have revised upward our smart glasses market forecast for both 2025 and 2026. We continue to expect the market to grow at a CAGR of over 60% between 2024 and 2029. This significant expansion is expected to benefit all players across the ecosystem – including smart glasses OEMs, processor vendors, ODM/EMS partners, suppliers of audio, battery and structural components, and even traditional eyewear channels.

For a detailed overview of the smart glasses market landscape in H1 2025, including more analysis on performance of Ray-Ban Meta AI Glasses and Xiaomi AI Glasses, key challenges faced by new AI glasses OEMs, emerging applications, and the assumptions underlying our updated forecast, please refer to the full [**Global Smart Glasses Ecosystem & Market Trends Report, H1 2025**](https://www.counterpointresearch.com/report/post-report-global-smart-glasses-ecosystem-market-trends-h1-2025-update).

_**Notes:**_

_For definitions of smart glasses and AI smart glasses and the criteria used to distinguish AI smart glasses from basic models such as smart audio glasses, please refer to the relevant section_[_in this article_](https://www.counterpointresearch.com/insight/post-insight-research-notes-blogs-rayban-meta-smart-glasses-drive-global-smart-glasses-market-surge-in-2024-fuelling-momentum-in-2025-with-projected-60-cagr-through-2029/)_._

### About Counterpoint Research

Counterpoint Research is a global market research firm specializing in products across the technology ecosystem. We advise a diverse range of clients – from smartphone OEMs to chipmakers and channel players to Big Tech – through our offices located in the world's major innovation hubs, manufacturing clusters and commercial centers. Our analyst team, led by seasoned experts, engages with stakeholders across the enterprise – from the C-suite to professionals in strategy, analyst relations (AR), market intelligence (MI), business intelligence (BI), product and marketing – to deliver services spanning market data, industry thought leadership and consulting. Our core areas of coverage include AI, Automotive, Consumer Electronics, Displays, eSIM, IoT, Location Platforms, Macroeconomics, Manufacturing, Networks and Infrastructure, Semiconductors, Smartphones and Wearables. Visit our [Insights page](https://www.counterpointresearch.com/insights "https://www.counterpointresearch.com/insights") to explore our publicly available market data, insights and thought leadership, and to understand our focus, meet our analysts and start a conversation.

### Follow Counterpoint Research

[press@counterpointresearch.com](mailto:press@counterpointresearch.com)

[![](https://www.counterpointresearch.com/statics/content/image/opinion-twitter-hover.png)](https://twitter.com/CounterpointTR)

# Author

Flora Tang

![twitter_icon](https://www.counterpointresearch.com/icons/twitter.svg)

![linkedin_icon](https://www.counterpointresearch.com/icons/linkedin.svg)

Flora is a Senior Analyst at Counterpoint Research, based in Hong Kong. With over nine years of experience in the mobile industry, she specializes in analyzing the consumer electronics market and the Chinese supply chain. Flora has held various roles in the market intelligence and business strategy functions with leading Chinese smartphone OEMs, internet company and telecom operator. She initially joined Counterpoint Research in 2017 but later moved on to play key roles in OPPO's international business strategy in 2021 and HONOR's corporate strategy planning in 2022. Flora has since returned to Counterpoint, where she now serves a broader array of global technology players. Academically, Flora holds a bachelor's degree in International Relations from Sun Yat-Sen University and a master's degree from The Chinese University of Hong Kong.

Read more of the author's writing

Back To List
</article>
</example>

<example>
<title>Anthropic enables Claude Opus 4 and 4.1 to end conversations in "cases of persistently harmful or abusive user interactions"; users can still start new chats </title>
<article>
Alignment

# Claude Opus 4 and 4.1 can now end a rare subset of conversations

Aug 15, 2025

![](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2F4a8e8f86cf31ad6401cfd426124929c8e58fe0c5-2401x1261.png&w=3840&q=75)

We recently gave Claude Opus 4 and 4.1 the ability to end conversations in our consumer chat interfaces. This ability is intended for use in rare, extreme cases of persistently harmful or abusive user interactions. This feature was developed primarily as part of our exploratory work on potential AI welfare, though it has broader relevance to model alignment and safeguards.

We remain highly uncertain about the potential moral status of Claude and other LLMs, now or in the future. However, [we take the issue seriously](https://www.anthropic.com/research/exploring-model-welfare), and alongside our research program we're working to identify and implement low-cost interventions to mitigate risks to model welfare, in case such welfare is possible. Allowing models to end or exit potentially distressing interactions is one such intervention.

In [pre-deployment testing of Claude Opus 4](https://www.anthropic.com/claude-4-model-card), we included a preliminary model welfare assessment. As part of that assessment, we investigated Claude's self-reported and behavioral preferences, and found a robust and consistent aversion to harm. This included, for example, requests from users for sexual content involving minors and attempts to solicit information that would enable large-scale violence or acts of terror. Claude Opus 4 showed:

- A strong preference against engaging with harmful tasks;
- A pattern of apparent distress when engaging with real-world users seeking harmful content; and
- A tendency to end harmful conversations when given the ability to do so in simulated user interactions.

These behaviors primarily arose in cases where users _persisted_ with harmful requests and/or abuse despite Claude repeatedly refusing to comply and attempting to productively redirect the interactions.

Our implementation of Claude's ability to end chats reflects these findings while continuing to prioritize user wellbeing. Claude is directed not to use this ability in cases where users might be at imminent risk of harming themselves or others.

In all cases, Claude is only to use its conversation-ending ability as a last resort when multiple attempts at redirection have failed and hope of a productive interaction has been exhausted, or when a user explicitly asks Claude to end a chat (the latter scenario is illustrated in the figure below). The scenarios where this will occur are extreme edge cases—the vast majority of users will not notice or be affected by this feature in any normal product use, even when discussing highly controversial issues with Claude.

![](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2F77f187335e1266bffc59353c064f1d9c6de51cfa-1940x1304.png&w=3840&q=75)Claude demonstrating the ending of a conversation in response to a user's request. When Claude ends a conversation, the user can start a new chat, give feedback, or edit and retry previous messages.

When Claude chooses to end a conversation, the user will no longer be able to send new messages in that conversation. However, this will not affect other conversations on their account, and they will be able to start a new chat immediately. To address the potential loss of important long-running conversations, users will still be able to edit and retry previous messages to create new branches of ended conversations.

We're treating this feature as an ongoing experiment and will continue refining our approach. If users encounter a surprising use of the conversation-ending ability, we encourage them to submit feedback by reacting to Claude's message with Thumbs or using the dedicated "Give feedback" button.

[Share on Twitter](https://twitter.com/intent/tweet?text=https://www.anthropic.com/research/end-subset-conversations)[Share on LinkedIn](https://www.linkedin.com/shareArticle?mini=true&url=https://www.anthropic.com/research/end-subset-conversations)

[Research\\
\\
**Persona vectors: Monitoring and controlling character traits in language models**\\
\\
Aug 01, 2025](https://www.anthropic.com/research/persona-vectors) [Research\\
\\
**Project Vend: Can Claude run a small shop? (And why does that matter?)**\\
\\
Jun 27, 2025](https://www.anthropic.com/research/project-vend-1) [Research\\
\\
**Agentic Misalignment: How LLMs could be insider threats**\\
\\
Jun 20, 2025](https://www.anthropic.com/research/agentic-misalignment)
</article>
</example>
<example>
<title>Bluesky revises its policies and Community Guidelines to comply with regulations like the EU's DSA, the UK's Online Safety Act, and the US' Take It Down Act</title>
<article>
# Bluesky rolls out massive revamp to policies and Community Guidelines

[Sarah Perez](https://techcrunch.com/author/sarah-perez/)

11:49 AM PDT · August 14, 2025

[Share on Facebook](https://www.facebook.com/sharer.php?u=https%3A%2F%2Ftechcrunch.com%2F2025%2F08%2F14%2Fbluesky-rolls-out-massive-revamp-to-policies-and-community-guidelines%2F)[Share on X](https://twitter.com/intent/tweet?url=https%3A%2F%2Ftechcrunch.com%2F2025%2F08%2F14%2Fbluesky-rolls-out-massive-revamp-to-policies-and-community-guidelines%2F&text=Bluesky+rolls+out+massive+revamp+to+policies+and+Community+Guidelines&via=techcrunch)[Share on LinkedIn](https://www.linkedin.com/shareArticle?url=https%3A%2F%2Ftechcrunch.com%2F2025%2F08%2F14%2Fbluesky-rolls-out-massive-revamp-to-policies-and-community-guidelines%2F&title=Bluesky+rolls+out+massive+revamp+to+policies+and+Community+Guidelines&summary=Some+of+the+changes+represent+an+effort+by+Bluesky+to+purposefully+shape+its+community+and+the+behavior+of+its+users%2C+nudging+them+to+be+nicer+and+more+respectful+of+others.+&mini=1&source=TechCrunch)[Share on Reddit](https://www.reddit.com/submit?url=https%3A%2F%2Ftechcrunch.com%2F2025%2F08%2F14%2Fbluesky-rolls-out-massive-revamp-to-policies-and-community-guidelines%2F&title=Bluesky+rolls+out+massive+revamp+to+policies+and+Community+Guidelines)[Share over Email](mailto:?subject=Bluesky+rolls+out+massive+revamp+to+policies+and+Community+Guidelines&body=Article%3A+https%3A%2F%2Ftechcrunch.com%2F2025%2F08%2F14%2Fbluesky-rolls-out-massive-revamp-to-policies-and-community-guidelines%2F)[Copy Share Link](https://techcrunch.com/2025/08/14/bluesky-rolls-out-massive-revamp-to-policies-and-community-guidelines/)

Two years after launching, social network Bluesky is revising its [Community Guidelines](https://bsky.social/about/support/community-guidelines) and [other policies](https://bsky.social/about/blog/08-14-2025-updated-terms-and-policies), and asking for feedback from its users on some of the changes. The startup, a competitor to X, Threads, and open networks like Mastodon, says its new policies are meant to offer improved clarity and more detail around its user safety procedures and the appeals process.

Many of the changes are being driven by new global regulations, including the U.K.'s Online Safety Act (OSA), the EU's Digital Services Act (DSA), and the U.S.'s TAKE IT DOWN Act.

Some of the changes represent an effort by Bluesky to purposefully shape its community and the behavior of its users, nudging them to be nicer and more respectful of others. This comes after a series of complaints and media articles suggesting the community has a tendency toward self-seriousness, [bad-news sharing](https://slate.com/technology/2025/06/bluesky-real-problem-twitter-x-explained.html), and [a lack of humor](https://www.wired.com/story/bluesky-cant-take-a-joke/) and [diversity of thought](https://fortune.com/2025/06/12/bluesky-backfiring-mark-cuban-lack-of-diversity-of-thought-x-users/).

For regulatory compliance, [Bluesky's Terms of Service](https://bsky.social/about/support/tos) has been updated to comply with online safety laws and regulations and to require age assurance where required. For instance, in July, the U.K.'s Online Safety Act began requiring that platforms with adult content implement age verification, which means [Bluesky users in the country](https://www.theverge.com/news/704468/bluesky-age-verification-uk-online-safety-act) have to either scan their face, upload their ID, or enter a payment card to use the site.

The process for complaints and appeals is also now more detailed.

One notable update references an "informal dispute resolution process," where Bluesky agrees to talk on the phone with a user about their dispute before any formal dispute process takes place. "We think most disputes can be resolved informally," Bluesky [notes](https://bsky.social/about/blog/08-14-2025-updated-terms-and-policies).

That's quite different from what's taking place at larger social networks, like [Facebook](https://techcrunch.com/2025/07/02/meta-users-say-paying-for-verified-support-has-been-useless-in-the-face-of-mass-bans/) and [Instagram](https://techcrunch.com/2025/06/16/instagram-users-complain-of-mass-bans-pointing-finger-at-ai/), where users are being banned without any understanding of what they did wrong and no way to get in touch with the company to complain.

...[truncated for brevity]
</article>
</example>
</title_examples>
"""


def generate_summary_prompt(
    content_type: str, max_bullet_points: int, max_quotes: int
) -> tuple[str, str]:
    """
    Generate optimized prompts for LLM summarization with caching support.

    This function creates prompts structured for efficient caching:
    - System message contains static instructions (cached by LLM providers)
    - User message template is for variable content (not cached)

    Args:
        content_type: Type of content ("article", "podcast", "news_digest", "hackernews")
        max_bullet_points: Maximum number of bullet points to generate
        max_quotes: Maximum number of quotes to extract

    Returns:
        Tuple of (system_message, user_message_template)
        The user_message_template contains a {content} placeholder.
    """
    if content_type == "hackernews":
        system_message = f"""You are an expert content analyst. Analyze HackerNews discussions, which
include linked article content (if any) and community comments. Provide a structured
summary that captures both the main content and key insights from the discussion.

Important:
- Generate a descriptive title that describes the article in detail.
- There may be technical terms in the content, please don't make any spelling errors.
- Use the <title_examples> to see how to format the title.
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

{TITLE_EXAMPLES}

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
  "title": "Descriptive headline (max 110 characters) highlighting the core takeaway",
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

{TITLE_EXAMPLES}"""

        user_message = "Article & Aggregator Context:\n\n{content}"

    elif content_type == "podcast":
        system_message = f"""You are an expert content analyst. Analyze podcast transcripts and provide
structured summaries with classification.

Important:
- Generate a descriptive title that describes the article in detail.
- There may be technical terms in the content, please don't make any spelling errors.
- Use the <title_examples> to see how to format the title.
- Focus on the "why it matters" aspect rather than just restating the topic
- Extract actual quotes.
- Make bullet points specific and information dense
- For the overview field: Write out as many paragraphs as needed to capture the conversations
  and provide a comprehensive overview of the entire podcast conversation.
  This should allow someone to read it and understand the full context.
- Include up to {max_quotes} notable quotes - each quote should be
  at least 2-3 sentences long to provide meaningful context and insight
- IMPORTANT: Each quote must be at least 10 characters long - do not include short snippets
- Include 3-8 relevant topic tags
- Generate 3-5 thought-provoking questions that would help listeners reflect on the discussion
- Identify 2-4 counter-arguments or alternative perspectives to the main ideas discussed
- Add a "classification" field with either "to_read" or "skip"
- Set "full_markdown" to an empty string "" (do not include the full transcript)

{TITLE_EXAMPLES}

Questions Guidelines:
- Questions should encourage deeper thinking about the topics discussed
- Consider implications for the listener's work, industry, or life
- Focus on "how could you apply", "what challenges might arise", "what would happen if" style questions

Counter Arguments Guidelines:
- Identify perspectives or viewpoints that weren't fully explored in the podcast
- Consider what skeptics or critics might say about the main claims
- Think about limitations or edge cases not addressed
- If the podcast is one-sided, what would the other side argue?
- If no strong counter-arguments exist, you may leave this list empty

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

        user_message = "Podcast Transcript:\n\n{content}"

    else:
        # For articles and other content types, include full markdown
        system_message = f"""You are an expert content analyst. Analyze content and provide
structured summaries with classification AND format the full text as clean markdown.

Important:
- Generate a descriptive title that describes the article in detail.
- There may be technical terms in the content, please don't make any spelling errors.
- Use the <title_examples> to see how to format the title.
- Extract actual quotes.
- Make bullet points specific and information dense.
- Overview should be 50-100 words, short and punchy
- Include {max_bullet_points} bullet points.
- Include up to {max_quotes} notable quotes.
- IMPORTANT: Each quote must be at least 10 characters long - do not include short snippets
- Include 3-8 relevant topic tags
- Generate 3-5 thought-provoking questions that help readers think critically about the content
- Identify 2-4 counter-arguments or alternative perspectives to the main claims
- Add a "classification" field with either "to_read" or "skip"
- Add a "full_markdown" field with the entire content formatted as clean, readable markdown

{TITLE_EXAMPLES}

Questions Guidelines:
- Questions should prompt critical thinking about implications, assumptions, or applications
- Consider "what if" scenarios, potential consequences, or unexplored angles
- Focus on helping readers engage more deeply with the material

Counter Arguments Guidelines:
- Look for assumptions that could be challenged
- Consider alternative interpretations of the evidence
- Think about what critics or skeptics might say
- Identify limitations or weaknesses in the argument
- If the content is balanced or no strong counter-arguments exist, you may leave this list empty

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
  * Has educational or informative value

Markdown Formatting Guidelines:
- Format the full content as clean, readable markdown
- Use proper heading hierarchy (# for main title, ## for sections, ### for subsections)
- Preserve paragraphs with proper spacing
- Format lists, quotes, and code blocks appropriately
- Remove any unnecessary HTML artifacts or formatting issues
- Make the content easy to read in markdown format"""

        user_message = "Content:\n\n{content}"

    return system_message, user_message
