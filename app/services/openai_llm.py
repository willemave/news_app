import contextlib
import json
import os
import re
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, BinaryIO

from openai import OpenAI, OpenAIError
from pydantic import ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.models.metadata import NewsSummary, StructuredSummary
from app.utils.error_logger import GenericErrorLogger
from app.utils.json_repair import strip_json_wrappers, try_repair_truncated_json

logger = get_logger(__name__)
settings = get_settings()
error_logger = GenericErrorLogger("openai_llm")

# Constants
MAX_FILE_SIZE_MB = 25
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
CHUNK_DURATION_SECONDS = 10 * 60  # 10 minutes in seconds
MAX_CONTENT_LENGTH = 1500000  # Maximum characters (~300K tokens, leaves room for prompt + output)


class StructuredSummaryRetryableError(Exception):
    """Retryable summarization failure used to trigger Tenacity retries."""


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

- _Meta’s share of the global smart glasses market rose to 73% in H1 2025, driven by strong demand and expanded manufacturing capacity at Luxottica, its key production partner._

- _Apart from Meta, key AI glasses OEMs that achieved shipments in H1 2025 included Xiaomi, TCL-RayNeo, Kopin Solos and Thunderobot, with the debut of Xiaomi’s AI Glasses being the most awaited event in the industry._

- _More new AI glasses models are expected to enter the market in H2 2025, including upcoming releases from Meta, Alibaba and several smaller players. We expect the rapid growth of the global smart glasses market to continue throughout 2026 and beyond._


**Seoul, Beijing, Berlin, Buenos Aires, Fort Collins, Hong Kong, London, New Delhi, Taipei, Tokyo – Aug 12, 2025**

Global smart glasses shipments grew 110% YoY in H1 2025, according to [**Counterpoint’s Global Smart Glasses Model Shipments Tracker**](https://www.counterpointresearch.com/report/post-report-global-smart-glasses-model-shipments-tracker-h1-2025-update). This surge was driven by strong demand for [Ray-Ban Meta Smart Glasses](https://www.counterpointresearch.com/insight/post-insight-research-notes-blogs-rayban-meta-crosses-1million-mark-success-indicates-promising-future-for-lightweight-ar-glasses) and the entry of new players such as Xiaomi, TCL-RayNeo and several smaller brands.

AI [smart glasses](https://www.counterpointresearch.com/coverage/xr-360) accounted for 78% of total shipments in H1 2025, up from 46% in H1 2024 and 66% in H2 2024, largely due to the dominance of Ray-Ban Meta AI Glasses. The AI glasses segment grew by over 250% YoY, significantly outpacing the overall market.

![](https://www.counterpointresearch.com/statics/content/image/20258534210_LqOcm_editor_image.jpg)

Commenting on the overall market performance,[**Senior Research Analyst Flora Tang**](https://www.counterpointresearch.com/opinion_leader/flora)said, “The global tariff crisis for electronic devices during the first half of the year has had a limited impact on the smart glasses market so far, as the situation still appears manageable for key OEMs and their manufacturing partners.”

On the competitive front,Tangsaid, “Meta’s share in the global smart glasses market rose to 73% in H1 2025, despite the launch of new products from other entrants. Shipments of Ray-Ban Meta AI Glasses grew over 200% YoY during the period, reflecting strong market demand and increased manufacturing capacity at Luxottica, Meta’s key production partner. Luxottica plays a critical role in Meta’s success, not only by scaling up production but also by supporting product longevity through the expansion of style variants and driving retail sales. According to our channel tracker, Luxottica’s own retail networks, including online and offline Ray-Ban stores, Sunglass Hut and LensCrafters, account for a significant portion of the product’s sales.”

![](https://www.counterpointresearch.com/statics/content/image/20258534913_o0JR8_editor_image.png)Source: Counterpoint’s Global Smart Glasses Model Shipments Tracker, H1 2025 Update

Commenting on the market dynamics, Tangsaid, “Beyond Meta, key AI smart glasses OEMs active in H1 2025 included Chinese players such as TCL-RayNeo with its RayNeo V3 series, Xiaomi with its debut Xiaomi AI Glasses, Thunderobot with the AURA smart glasses, and the Kopin Solos AirGo V series. Xiaomi's AI glasses emerged as a dark horse in the global smart glasses market – becoming the fourth best-selling model overall and the third best-selling product in the AI glasses segment – despite being on sale for only about a week in H1 2025. The Xiaomi device’s sales were driven by strong support from tech enthusiasts and Mi fans in China. We expect Xiaomi to continue enhancing the product’s performance through OTA and software updates in the coming months.”

[**Research Analyst Akshay RS**](https://www.counterpointresearch.com/opinion_leader/akshay-r-s) said, “As for the smart audio glasses segment, which currently includes players likeHuawei, Amazon and Mijia (a Xiaomi ecosystem brand), it experienced a decline during the period due to rising competition from AI glasses offering more advanced functionalities, such as photo and video capture, image and object recognition, encyclopedia-based Q&A, live translation and more. In addition, we are seeing new products from Chinese companies, such as Xiaomi AI Glasses and Alibaba’s Quark AI Glasses (still in pre-commercial stages), actively exploring glass-based payment solutions. These aim to reduce users’ reliance on smartphones in outdoor shopping and food-ordering scenarios.”

Driven by the dominance of Ray-Ban Meta AI Glasses, regions where the product is available – such as North America, Western Europe and Australia – lead global smart glasses shipments. In Q2 2025, Meta and Luxottica expanded to India, Mexico and the UAE, which also boosted shipment shares in these markets.

![](https://www.counterpointresearch.com/statics/content/image/2025822019_q44PY_editor_image.png)

More AI smart glasses are expected to enter the market from H2 2025 onward, including launches from internet giants such as Meta and Alibaba. Meta recently introduced the Oakley Meta glasses, featuring improved battery life and enhanced video-shooting quality over the Ray-Ban Meta AI Glasses, and primarily targeting athletes and sports enthusiasts. Our industry checks indicate positive market feedback for this model. We expect Meta will take a more aggressive approach and unveil a broader product lineup at the Meta Connect event to further drive growth. Meanwhile, we believe Apple is also actively exploring this space and developing its first AI glasses.

In the processing space, [Qualcomm](https://www.counterpointresearch.com/insight/counterpoint-conversations-qualcomm-ai-xr-future) recently launched an upgraded version of its premium smart glasses SoC – the AR 1+ Gen 1 – which Qualcomm claims is 26% smaller and consumes 7% less power, enabling slimmer product designs and longer battery life. In parallel, various Chinese chipset makers, such as Allwinner Technology, are entering the market with budget SoC solutions aimed at powering more affordable smart glasses.

Given the market’s momentum and continued influx of new entrants, we have revised upward our smart glasses market forecast for both 2025 and 2026. We continue to expect the market to grow at a CAGR of over 60% between 2024 and 2029. This significant expansion is expected to benefit all players across the ecosystem – including smart glasses OEMs, processor vendors, ODM/EMS partners, suppliers of audio, battery and structural components, and even traditional eyewear channels.

For a detailed overview of the smart glasses market landscape in H1 2025, including more analysis on performance of Ray-Ban Meta AI Glasses and Xiaomi AI Glasses, key challenges faced by new AI glasses OEMs, emerging applications, and the assumptions underlying our updated forecast, please refer to the full [**Global Smart Glasses Ecosystem & Market Trends Report, H1 2025**](https://www.counterpointresearch.com/report/post-report-global-smart-glasses-ecosystem-market-trends-h1-2025-update).

_**Notes:**_

_For definitions of smart glasses and AI smart glasses and the criteria used to distinguish AI smart glasses from basic models such as smart audio glasses, please refer to the relevant section_[_in this article_](https://www.counterpointresearch.com/insight/post-insight-research-notes-blogs-rayban-meta-smart-glasses-drive-global-smart-glasses-market-surge-in-2024-fuelling-momentum-in-2025-with-projected-60-cagr-through-2029/)_._

### About Counterpoint Research

Counterpoint Research is a global market research firm specializing in products across the technology ecosystem. We advise a diverse range of clients – from smartphone OEMs to chipmakers and channel players to Big Tech – through our offices located in the world's major innovation hubs, manufacturing clusters and commercial centers. Our analyst team, led by seasoned experts, engages with stakeholders across the enterprise – from the C-suite to professionals in strategy, analyst relations (AR), market intelligence (MI), business intelligence (BI), product and marketing – to deliver services spanning market data, industry thought leadership and consulting. Our core areas of coverage include AI, Automotive, Consumer Electronics, Displays, eSIM, IoT, Location Platforms, Macroeconomics, Manufacturing, Networks and Infrastructure, Semiconductors, Smartphones and Wearables. Visit our [Insights page](https://www.counterpointresearch.com/insights "https://www.counterpointresearch.com/insights") to explore our publicly available market data, insights and thought leadership, and to understand our focus, meet our analysts and start a conversation.

### Follow Counterpoint Research

[press@counterpointresearch.com](mailto:press@counterpointresearch.com)

[![](https://www.counterpointresearch.com/statics/content/image/opinion-twitter-hover.png)](https://twitter.com/CounterpointTR)

# Author

Flora Tang

![twitter_icon](https://www.counterpointresearch.com/icons/twitter.svg)

![linkedin_icon](https://www.counterpointresearch.com/icons/linkedin.svg)

Flora is a Senior Analyst at Counterpoint Research, based in Hong Kong. With over nine years of experience in the mobile industry, she specializes in analyzing the consumer electronics market and the Chinese supply chain. Flora has held various roles in the market intelligence and business strategy functions with leading Chinese smartphone OEMs, internet company and telecom operator. She initially joined Counterpoint Research in 2017 but later moved on to play key roles in OPPO’s international business strategy in 2021 and HONOR’s corporate strategy planning in 2022. Flora has since returned to Counterpoint, where she now serves a broader array of global technology players. Academically, Flora holds a bachelor’s degree in International Relations from Sun Yat-Sen University and a master’s degree from The Chinese University of Hong Kong.

Read more of the author's writing

Back To List
</article>
</example>

<example>
<title>Anthropic enables Claude Opus 4 and 4.1 to end conversations in “cases of persistently harmful or abusive user interactions”; users can still start new chats </title>
<article>
Alignment

# Claude Opus 4 and 4.1 can now end a rare subset of conversations

Aug 15, 2025

![](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2F4a8e8f86cf31ad6401cfd426124929c8e58fe0c5-2401x1261.png&w=3840&q=75)

We recently gave Claude Opus 4 and 4.1 the ability to end conversations in our consumer chat interfaces. This ability is intended for use in rare, extreme cases of persistently harmful or abusive user interactions. This feature was developed primarily as part of our exploratory work on potential AI welfare, though it has broader relevance to model alignment and safeguards.

We remain highly uncertain about the potential moral status of Claude and other LLMs, now or in the future. However, [we take the issue seriously](https://www.anthropic.com/research/exploring-model-welfare), and alongside our research program we’re working to identify and implement low-cost interventions to mitigate risks to model welfare, in case such welfare is possible. Allowing models to end or exit potentially distressing interactions is one such intervention.

In [pre-deployment testing of Claude Opus 4](https://www.anthropic.com/claude-4-model-card), we included a preliminary model welfare assessment. As part of that assessment, we investigated Claude’s self-reported and behavioral preferences, and found a robust and consistent aversion to harm. This included, for example, requests from users for sexual content involving minors and attempts to solicit information that would enable large-scale violence or acts of terror. Claude Opus 4 showed:

- A strong preference against engaging with harmful tasks;
- A pattern of apparent distress when engaging with real-world users seeking harmful content; and
- A tendency to end harmful conversations when given the ability to do so in simulated user interactions.

These behaviors primarily arose in cases where users _persisted_ with harmful requests and/or abuse despite Claude repeatedly refusing to comply and attempting to productively redirect the interactions.

Our implementation of Claude’s ability to end chats reflects these findings while continuing to prioritize user wellbeing. Claude is directed not to use this ability in cases where users might be at imminent risk of harming themselves or others.

In all cases, Claude is only to use its conversation-ending ability as a last resort when multiple attempts at redirection have failed and hope of a productive interaction has been exhausted, or when a user explicitly asks Claude to end a chat (the latter scenario is illustrated in the figure below). The scenarios where this will occur are extreme edge cases—the vast majority of users will not notice or be affected by this feature in any normal product use, even when discussing highly controversial issues with Claude.

![](https://www.anthropic.com/_next/image?url=https%3A%2F%2Fwww-cdn.anthropic.com%2Fimages%2F4zrzovbb%2Fwebsite%2F77f187335e1266bffc59353c064f1d9c6de51cfa-1940x1304.png&w=3840&q=75)Claude demonstrating the ending of a conversation in response to a user’s request. When Claude ends a conversation, the user can start a new chat, give feedback, or edit and retry previous messages.

When Claude chooses to end a conversation, the user will no longer be able to send new messages in that conversation. However, this will not affect other conversations on their account, and they will be able to start a new chat immediately. To address the potential loss of important long-running conversations, users will still be able to edit and retry previous messages to create new branches of ended conversations.

We’re treating this feature as an ongoing experiment and will continue refining our approach. If users encounter a surprising use of the conversation-ending ability, we encourage them to submit feedback by reacting to Claude’s message with Thumbs or using the dedicated “Give feedback” button.

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

Many of the changes are being driven by new global regulations, including the U.K.’s Online Safety Act (OSA), the EU’s Digital Services Act (DSA), and the U.S.’s TAKE IT DOWN Act.

Some of the changes represent an effort by Bluesky to purposefully shape its community and the behavior of its users, nudging them to be nicer and more respectful of others. This comes after a series of complaints and media articles suggesting the community has a tendency toward self-seriousness, [bad-news sharing](https://slate.com/technology/2025/06/bluesky-real-problem-twitter-x-explained.html), and [a lack of humor](https://www.wired.com/story/bluesky-cant-take-a-joke/) and [diversity of thought](https://fortune.com/2025/06/12/bluesky-backfiring-mark-cuban-lack-of-diversity-of-thought-x-users/).

For regulatory compliance, [Bluesky’s Terms of Service](https://bsky.social/about/support/tos) has been updated to comply with online safety laws and regulations and to require age assurance where required. For instance, in July, the U.K.’s Online Safety Act began requiring that platforms with adult content implement age verification, which means [Bluesky users in the country](https://www.theverge.com/news/704468/bluesky-age-verification-uk-online-safety-act) have to either scan their face, upload their ID, or enter a payment card to use the site.

The process for complaints and appeals is also now more detailed.

One notable update references an “informal dispute resolution process,” where Bluesky agrees to talk on the phone with a user about their dispute before any formal dispute process takes place. “We think most disputes can be resolved informally,” Bluesky [notes](https://bsky.social/about/blog/08-14-2025-updated-terms-and-policies).

That’s quite different from what’s taking place at larger social networks, like [Facebook](https://techcrunch.com/2025/07/02/meta-users-say-paying-for-verified-support-has-been-useless-in-the-face-of-mass-bans/) and [Instagram](https://techcrunch.com/2025/06/16/instagram-users-complain-of-mass-bans-pointing-finger-at-ai/), where users are being banned without any understanding of what they did wrong and no way to get in touch with the company to complain.

Techcrunch event

### Tech and VC heavyweights join the Disrupt 2025 agenda

#### Netflix, ElevenLabs, Wayve, Sequoia Capital, Elad Gil — just a few of the heavy hitters joining the Disrupt 2025 agenda. They’re here to deliver the insights that fuel startup growth and sharpen your edge. Don’t miss the 20th anniversary of TechCrunch Disrupt, and a chance to learn from the top voices in tech — grab your ticket now and save up to $600+ before prices rise.

### Tech and VC heavyweights join the Disrupt 2025 agenda

#### Netflix, ElevenLabs, Wayve, Sequoia Capital — just a few of the heavy hitters joining the Disrupt 2025 agenda. They’re here to deliver the insights that fuel startup growth and sharpen your edge. Don’t miss the 20th anniversary of TechCrunch Disrupt, and a chance to learn from the top voices in tech — grab your ticket now and save up to $675 before prices rise.

San Francisco\|October 27-29, 2025

[**REGISTER NOW**](https://techcrunch.com/events/tc-disrupt-2025/?utm_source=tc&utm_medium=ad&utm_campaign=disrupt2025&utm_content=ticketsales&promo=tc_inline_rb&display=)

Bluesky also says it will allow users to resolve certain claims of harm in court, instead of through arbitration. This is also somewhat unusual for tech companies that often [prefer to mediate](https://www.numberanalytics.com/blog/technological-mediation-practical-guide) disputes outside the courts.

However, Bluesky users may be more interested in the proposed changes to the Community Guidelines, which they’re invited to [offer feedback about](https://forms.gle/mfgZGnhDMaKeq61p7). (The changes go into effect October 15, 2025, after the feedback period completes.)

These revised guidelines are organized around four principles: Safety First, Respect Others, Be Authentic, and Follow the Rules. These general principles are meant to guide Bluesky’s moderation decisions around whether content should be labeled or removed, if the company can suspend or ban your account, or, in some cases, report you to law enforcement.

Bluesky’s rules include many common-sense policies around not promoting violence or harm (including self-harm and animal abuse); not posting content that’s illegal or that sexualizes minors (including in role-play); not allowing harmful actions like doxxing and other nonconsensual personal data-sharing; and not posting spam or malicious content, among other things.

It carves out provisions for journalism, parody, and satire. For instance, journalists engaged in “factual reporting” can post about criminal acts and violence, mental health, online safety, and other topics, like warnings of online viral challenges that may be harmful.

Where Bluesky may get into trouble is with the nuances of what’s considered a “threat,” “harm,” or “abuse.”

The policy states that users should “respect others” by not posting, promoting, or encouraging “hate, harassment, or bullying.” As an example, the policy bans exploitive deepfakes and content that “incites discrimination or hatred,” meaning posts that attack individuals or groups based on “race, ethnicity, religion, gender identity, sexual orientation, disability, or other protected traits.”

This is an area where Bluesky has faltered before, when, in earlier days, its moderation decisions [strained its relationship with the Black community](https://techcrunch.com/2023/06/08/blueskys-growing-pains-strain-relationship-with-its-black-community-moderation/), and in another case, [when its failure to moderate](https://techcrunch.com/2024/12/13/bluesky-is-at-a-crossroads-as-users-petition-to-ban-jesse-singal-over-anti-trans-views-harassment/) angered the trans community.

More recently, the company has been facing backlash that it’s become [too](https://www.washingtonpost.com/opinions/2025/06/08/blue-sky-twitter-liberals/) [left-leaning](https://www.washingtonpost.com/opinions/2025/06/08/blue-sky-twitter-liberals/), where users were quick to criticize, [post hateful replies](https://bsky.app/profile/mcuban.bsky.social/post/3lr4op5zib22q), and where the community generally [lacked humor](https://www.wired.com/story/bluesky-cant-take-a-joke/).

The original idea behind Bluesky was to provide users with tools to create the community they want, including not only blocking and reporting tools, but also things like subscribable block lists or opt-in moderation services that align with your values. However, Bluesky users have still shown a preference for the app itself to handle much of the moderation, [railing against](https://www.change.org/p/bluesky-must-enforce-its-community-guidelines-equally) its trust and safety department when it made decisions they disagreed with.

In addition, Bluesky’s [Privacy Policy](https://bsky.social/about/support/privacy-policy) and [Copyright Policy](https://bsky.social/about/support/copyright) were also rewritten to comply with global laws around user rights, data transfer, retention and deletion, takedown procedures, transparency reporting, and more. These both go into effect on September 15, 2025, and there is no feedback period for either.

Topics

[Apps](https://techcrunch.com/category/apps/), [Bluesky](https://techcrunch.com/tag/bluesky/), [Social](https://techcrunch.com/category/social/)

[Share on Facebook](https://www.facebook.com/sharer.php?u=https%3A%2F%2Ftechcrunch.com%2F2025%2F08%2F14%2Fbluesky-rolls-out-massive-revamp-to-policies-and-community-guidelines%2F)[Share on X](https://twitter.com/intent/tweet?url=https%3A%2F%2Ftechcrunch.com%2F2025%2F08%2F14%2Fbluesky-rolls-out-massive-revamp-to-policies-and-community-guidelines%2F&text=Bluesky+rolls+out+massive+revamp+to+policies+and+Community+Guidelines&via=techcrunch)[Share on LinkedIn](https://www.linkedin.com/shareArticle?url=https%3A%2F%2Ftechcrunch.com%2F2025%2F08%2F14%2Fbluesky-rolls-out-massive-revamp-to-policies-and-community-guidelines%2F&title=Bluesky+rolls+out+massive+revamp+to+policies+and+Community+Guidelines&summary=Some+of+the+changes+represent+an+effort+by+Bluesky+to+purposefully+shape+its+community+and+the+behavior+of+its+users%2C+nudging+them+to+be+nicer+and+more+respectful+of+others.+&mini=1&source=TechCrunch)[Share on Reddit](https://www.reddit.com/submit?url=https%3A%2F%2Ftechcrunch.com%2F2025%2F08%2F14%2Fbluesky-rolls-out-massive-revamp-to-policies-and-community-guidelines%2F&title=Bluesky+rolls+out+massive+revamp+to+policies+and+Community+Guidelines)[Share over Email](mailto:?subject=Bluesky+rolls+out+massive+revamp+to+policies+and+Community+Guidelines&body=Article%3A+https%3A%2F%2Ftechcrunch.com%2F2025%2F08%2F14%2Fbluesky-rolls-out-massive-revamp-to-policies-and-community-guidelines%2F)[Copy Share Link](https://techcrunch.com/2025/08/14/bluesky-rolls-out-massive-revamp-to-policies-and-community-guidelines/)

![Sarah Perez](https://techcrunch.com/wp-content/uploads/2021/01/lwzxxnshgj71bonwbik3.jpg.jpg?w=150)

Sarah Perez

Consumer News Editor

[Sarah Perez on Twitter](http://twitter.com/SarahPerezTC)[Sarah Perez on Bluesky](https://bsky.app/profile/sarahp.bsky.social)[Sarah Perez on Mastodon](https://mastodon.social/@Sarahp)[Sarah Perez on Linkedin](https://www.linkedin.com/in/sarahperez2020/)

Sarah has worked as a reporter for TechCrunch since August 2011. She joined the company after having previously spent over three years at ReadWriteWeb. Prior to her work as a reporter, Sarah worked in I.T. across a number of industries, including banking, retail and software.

You can contact or verify outreach from Sarah by emailing [sarahp@techcrunch.com](mailto:sarahp@techcrunch.com) or via encrypted message at sarahperez.01 on Signal.

[View Bio](https://techcrunch.com/author/sarah-perez/)

![Event Logo](https://techcrunch.com/wp-content/uploads/2025/07/TC25_Disrupt-Color.png)

October 27-29, 2025

San Francisco

Put your brand in front of 10,000+ tech and VC leaders across all three days of Disrupt 2025. Amplify your reach, spark real connections, and lead the innovation charge. Secure your exhibit space before your competitor does.

[**Book Your Table**](https://techcrunch.com/events/tc-disrupt-2025/exhibit/?promo=rightrail_disrupt2025exhibit&utm_campaign=disrupt2025&utm_content=exhibit&utm_medium=ad&utm_source=tc)

## Most Popular

- ### [Co-founder of Elon Musk’s xAI departs the company](https://techcrunch.com/2025/08/13/co-founder-of-elon-musks-xai-departs-the-company/)





- [Maxwell Zeff](https://techcrunch.com/author/maxwell-zeff/)

- ### [Google CEO adds a new calendar feature at Stripe co-founder’s request](https://techcrunch.com/2025/08/13/google-ceo-adds-a-new-calendar-feature-at-stripe-co-founders-request/)





- [Sarah Perez](https://techcrunch.com/author/sarah-perez/)

- ### [NASA has sparked a race to develop the data pipeline to Mars](https://techcrunch.com/2025/08/13/nasa-has-sparked-a-race-to-develop-the-data-pipeline-to-mars/)





- [Aria Alamalhodaei](https://techcrunch.com/author/aria-alamalhodaei/)

- ### [Security flaws in a carmaker’s web portal let one hacker remotely unlock cars from anywhere](https://techcrunch.com/2025/08/10/security-flaws-in-a-carmakers-web-portal-let-one-hacker-remotely-unlock-cars-from-anywhere/)





- [Zack Whittaker](https://techcrunch.com/author/zack-whittaker/)

- ### [The hidden cost of living in Mark Zuckerberg’s $110M compound](https://techcrunch.com/2025/08/10/the-hidden-cost-of-living-amid-mark-zuckerbergs-110m-compound/)





- [Connie Loizos](https://techcrunch.com/author/connie-loizos/)

- ### [The computer science dream has become a nightmare](https://techcrunch.com/2025/08/10/the-computer-science-dream-has-become-a-nightmare/)





- [Connie Loizos](https://techcrunch.com/author/connie-loizos/)

- ### [Sam Altman addresses ‘bumpy’ GPT-5 rollout, bringing 4o back, and the ‘chart crime’](https://techcrunch.com/2025/08/08/sam-altman-addresses-bumpy-gpt-5-rollout-bringing-4o-back-and-the-chart-crime/)





- [Julie Bort](https://techcrunch.com/author/julie-bort/)

Keep reading

![Blue sky with clouds illustration, representing Bluesky social](https://techcrunch.com/wp-content/uploads/2023/05/bluesky-felt.jpg?w=1024)**Image Credits:** Bryce Durbin / TechCrunch

[Apps](https://techcrunch.com/category/apps/)

[Share on Facebook](https://www.facebook.com/sharer.php?u=https%3A%2F%2Ftechcrunch.com%2F2025%2F08%2F14%2Fwhat-is-bluesky-everything-to-know-about-the-x-competitor%2F)[Share on X](https://twitter.com/intent/tweet?url=https%3A%2F%2Ftechcrunch.com%2F2025%2F08%2F14%2Fwhat-is-bluesky-everything-to-know-about-the-x-competitor%2F&text=What+is+Bluesky%3F+Everything+to+know+about+the+X+competitor&via=techcrunch)[Share on LinkedIn](https://www.linkedin.com/shareArticle?url=https%3A%2F%2Ftechcrunch.com%2F2025%2F08%2F14%2Fwhat-is-bluesky-everything-to-know-about-the-x-competitor%2F&title=What+is+Bluesky%3F+Everything+to+know+about+the+X+competitor&summary=We%E2%80%99ve+compiled+the+answers+to+some+of+the+most+common+questions+users+have+about+Bluesky.+&mini=1&source=TechCrunch)[Share on Reddit](https://www.reddit.com/submit?url=https%3A%2F%2Ftechcrunch.com%2F2025%2F08%2F14%2Fwhat-is-bluesky-everything-to-know-about-the-x-competitor%2F&title=What+is+Bluesky%3F+Everything+to+know+about+the+X+competitor)[Share over Email](mailto:?subject=What+is+Bluesky%3F+Everything+to+know+about+the+X+competitor&body=Article%3A+https%3A%2F%2Ftechcrunch.com%2F2025%2F08%2F14%2Fwhat-is-bluesky-everything-to-know-about-the-x-competitor%2F)[Copy Share Link](https://techcrunch.com/2025/08/14/what-is-bluesky-everything-to-know-about-the-x-competitor/)

# What is Bluesky? Everything to know about the X competitor

[Amanda Silberling](https://techcrunch.com/author/amanda-silberling/)

[Cody Corrall](https://techcrunch.com/author/cody-corrall/)

[Alyssa Stringer](https://techcrunch.com/author/alyssa-stringer/)

11:56 AM PDT · August 14, 2025

Is the grass greener on the other side? We’re not sure, but the sky is most certainly bluer. It’s been over two years since [Elon Musk purchased Twitter](https://techcrunch.com/2024/06/05/elon-musk-twitter-everything-you-need-to-know/), now X, leading people to set up shop on alternative platforms. [Mastodon](https://techcrunch.com/2023/10/09/mastodon-actually-has-407k-more-monthly-users-than-it-thought/), [Post](https://techcrunch.com/2022/11/28/post-news-twitter-alternative-a16z/), [Pebble](https://techcrunch.com/2023/01/12/twitter-rival-t2-raises-its-first-outside-funding-1-1m-from-a-group-of-high-profile-angels/) (two of which have already [shuttered](https://techcrunch.com/2023/10/24/pebble-the-twitter-alternative-previously-known-as-t2-is-closing-down/) [operations](https://www.theverge.com/2024/4/19/24135011/twitter-alternative-post-news-shutdown)) and [Spill](https://techcrunch.com/2023/11/07/spill-toasts-one-year-with-a-2-m-seed-extension-kerry-washington-and-champagne/) have been presented as [potential replacements](https://techcrunch.com/2024/09/24/best-twitter-alternatives-social-apps/), but few [aside from Meta’s Threads](https://techcrunch.com/2023/10/26/zuckerberg-says-threads-has-a-good-chance-of-reaching-1-billion-users-in-a-few-years/) have achieved the speed of growth Bluesky has reached.

As of February 2025, Bluesky has [surpassed 30 million users.](https://bsky.jazco.dev/stats) Its growth stems from several policy changes at X, including a heavily criticized [change to the block feature](https://techcrunch.com/2024/11/03/x-updates-block-feature-letting-blocked-users-see-your-public-posts/) and allowing third party companies to [train their AI on users’ posts](https://techcrunch.com/2024/10/17/elon-musks-x-is-changing-its-privacy-policy-to-allow-third-parties-to-train-ai-on-your-posts/), which helped the app soar to the [top of the U.S. App Store.](https://www.forbes.com/sites/paultassi/2024/11/13/bluesky-hits-1-in-the-app-store-is-it-worth-switching-from-twitter/) Bluesky also saw a big boost following the results of the [2024 U.S. presidential election](https://techcrunch.com/2024/11/04/bluesky-gears-up-for-election-day-as-x-goes-pro-trump/) (which also contributed to an X exodus by [Taylor Swift fans](https://www.wired.com/story/taylor-swift-fans-leaving-x-following-trumps-election/)). But while the number is promising, [the growth has slowed](https://techcrunch.com/2025/01/06/bluesky-bump-from-x-exodus-is-slowing-down-data-shows/) — and the network has a lot of catching up to do to compete with [Threads’ 275 million monthly active users](https://techcrunch.com/2024/11/03/threads-now-has-275m-monthly-active-users/).

Below, we’ve compiled the answers to some of the most common questions users have about Bluesky. And if you’ve made the switch, you can [follow TechCrunch here](https://bsky.app/profile/techcrunch.com/) as well as our team with [our Starter Pack.](https://go.bsky.app/NadxCsH)

### What is Bluesky?

Bluesky is a [decentralized social app](https://techcrunch.com/2022/12/13/decentralized-discourse-how-open-source-is-shaping-twitters-future/) conceptualized by former Twitter CEO Jack Dorsey and developed in parallel with Twitter. The social network has a Twitter-like user interface with algorithmic choice, a federated design and community-specific moderation.

Bluesky is using an [open source framework](https://techcrunch.com/2025/03/25/a-world-without-caesars-how-the-atproto-community-is-rebuilding-the-web-to-return-power-to-the-people/) built in-house, the [AT Protocol](https://atproto.com/), meaning people outside of the company have transparency into how it is built and what is being developed.

Dorsey introduced the Bluesky project back in 2019 while he was still Twitter CEO. At the time, he said Twitter would be funding a “small independent team of up to five open source architects, engineers, and designers,” charged with building a decentralized standard for social media, with the original goal that Twitter would adopt this standard itself. But that was before Elon Musk bought the platform, so Bluesky is completely divorced from X.

As of May 2024, Dorsey is [no longer on Bluesky’s board.](https://techcrunch.com/2024/05/05/jack-dorsey-says-hes-no-longer-on-the-bluesky-board/) Bluesky is now an independent public benefit corporation led by [CEO Jay Graber.](https://techcrunch.com/2024/02/06/as-bluesky-opens-to-the-public-ceo-jay-graber-faces-her-biggest-challenge-yet/)

Techcrunch event

### Tech and VC heavyweights join the Disrupt 2025 agenda

#### Netflix, ElevenLabs, Wayve, Sequoia Capital, Elad Gil — just a few of the heavy hitters joining the Disrupt 2025 agenda. They’re here to deliver the insights that fuel startup growth and sharpen your edge. Don’t miss the 20th anniversary of TechCrunch Disrupt, and a chance to learn from the top voices in tech — grab your ticket now and save up to $600+ before prices rise.

### Tech and VC heavyweights join the Disrupt 2025 agenda

#### Netflix, ElevenLabs, Wayve, Sequoia Capital — just a few of the heavy hitters joining the Disrupt 2025 agenda. They’re here to deliver the insights that fuel startup growth and sharpen your edge. Don’t miss the 20th anniversary of TechCrunch Disrupt, and a chance to learn from the top voices in tech — grab your ticket now and save up to $675 before prices rise.

San Francisco\|October 27-29, 2025

[**REGISTER NOW**](https://techcrunch.com/events/tc-disrupt-2025/?utm_source=tc&utm_medium=ad&utm_campaign=disrupt2025&utm_content=ticketsales&promo=tc_inline_rb&display=)

### How do you use Bluesky?

Upon signing up, users can create a handle which is then represented as @username.bsky.social as well as a display name that appears more prominent in bold text. If you’re so inclined, you can turn a domain name that you own into your username — so, for example, I’m known on Bluesky as [@amanda.omg.lol.](https://bsky.app/profile/amanda.omg.lol)

The app itself functions [much like X,](https://techcrunch.com/2024/11/14/how-to-use-bluesky-the-twitter-like-app-thats-taking-on-elon-musks-x/) where you can click a plus button to create a post of 256 characters, which can also include photos. Posts themselves can be replied to, retweeted, liked and, from a three-dot menu, reported, shared via the iOS Share Sheet to other apps, or copied as text.

You can search for and follow other individuals, then view their updates in your “Home” timeline. Previously, the Bluesky app would feature popular posts in a “What’s Hot” feed. That feed has since been replaced with an algorithmic and [personalized “Discover” feed](https://techcrunch.com/2023/07/28/as-threads-soars-twitter-rival-bluesky-adopts-a-new-personalized-algorithmic-feed/) featuring more than just trending content.

For new users, Bluesky introduced [a “Starter Pack” feature,](https://techcrunch.com/2024/06/27/bluesky-lets-you-curate-accounts-and-feeds-to-follow-with-its-starter-pack-feature/) which creates a curated list of people and custom feeds to follow in order to find interesting content right out of the gate. You can find TechCrunch’s Starter Pack [right here.](https://go.bsky.app/NadxCsH)

User profiles contain the same sort of features you’d expect: a profile pic, background, bio, metrics and how many people they’re following. Profile feeds are divided into two sections, like X: posts and posts & replies. In January 2025, Bluesky also added [a new video tab](https://techcrunch.com/2025/01/27/bluesky-adds-video-to-user-profiles/) to user profiles.

There is also a “Discover” tab in the bottom center of the app’s navigation, which offers more “who to follow” suggestions and a running feed of recently posted Bluesky updates. In January 2025, Bluesky also introduced [a vertical video feed](https://techcrunch.com/2025/01/19/bluesky-launches-a-custom-feed-for-vertical-videos/) to compete with TikTok.

We’ve also put together a helpful guide on [how to use Bluesky here.](https://techcrunch.com/2024/11/14/how-to-use-bluesky-the-twitter-like-app-thats-taking-on-elon-musks-x/)

![Screenshot of Bluesky menu tab](https://techcrunch.com/wp-content/uploads/2023/07/bluesky.png?w=161)**Image Credits:** Natalie Christman

### Who’s on Bluesky?

By the beginning of July 2023, when [Instagram’s Threads](https://techcrunch.com/2023/07/17/what-is-instagrams-threads-app-all-your-questions-answered/) launched, [Bluesky topped a million downloads](https://techcrunch.com/2023/07/07/as-threads-soars-twitter-rival-bluesky-hits-its-first-million-installs/) across iOS and Android. Notable figures like [Rep. Alexandria Ocasio-Cortez](https://bsky.app/profile/aoc.bsky.social), [Mark Cuban](https://bsky.app/profile/mcuban.bsky.social), [Quinta Brunson,](https://bsky.app/profile/quintabrunson.bsky.social) [Dril](https://bsky.app/profile/dril.bsky.social), [Weird Al Yankovic](https://bsky.app/profile/alyankovic.bsky.social), [Guillermo del Toro,](https://bsky.app/profile/realgdt.bsky.social) [Barbra Streisand,](https://bsky.app/profile/barbrastreisand.bsky.social) and [Brazil President Luiz Inácio Lula da Silva](https://bsky.app/profile/lula.com.br) have migrated to Bluesky.

Bluesky is also home to news organizations like [Bloomberg](https://bsky.app/profile/bloomberg.com), [The Washington Post](https://bsky.app/profile/washingtonpost.com), and of course, [TechCrunch](https://bsky.app/profile/techcrunch.com/)! Since August 2024, Bluesky is also now allowing [heads of state](https://techcrunch.com/2024/04/15/bluesky-now-allows-heads-of-states-to-sign-up-for-the-social-network/) to sign up and join the platform for the first time.

In 2025, some prominent U.S. political figures set up accounts on the platform, like [Barack Obama](https://techcrunch.com/2025/03/23/barack-obama-joins-bluesky/) and [Hillary Clinton](https://techcrunch.com/2025/03/31/hillary-clinton-joins-bluesky/).

### Does Bluesky work just like X?

In many ways, yes. When it first started, Bluesky was much more pared down and didn’t even have DMs, but this key feature [has since been implemented](https://techcrunch.com/2024/05/22/bluesky-now-has-dms/), even with [emoji reactions](https://techcrunch.com/2025/04/10/blueskys-latest-update-adds-chat-reactions-and-an-explore-page-similar-to-x/). But DMs on Bluesky are currently limited to one-to-one messages, not group messages. Bluesky has also said it is interested in implementing something similar to [X’s Community Notes feature.](https://techcrunch.com/2024/08/28/bluesky-adds-anti-toxicity-tools-and-aims-to-integrate-a-community-notes-like-feature-in-the-future/) Additionally, X does not use a decentralized protocol like ActivityPub or [AT](https://atproto.com/). Bluesky has also been [testing a Trending Topics feature](https://techcrunch.com/2024/12/25/bluesky-starts-testing-a-trending-topics-feature/) and developing [its own photo sharing app](https://techcrunch.com/2025/01/15/bluesky-is-getting-its-own-photo-sharing-app-flashes/) called Flashes, which is expected to be [released in beta soon.](https://bsky.app/profile/flashesapp.bsky.social/post/3lfshio2jb22o)

In October 2024, Elon Musk announced that [X’s block feature would work differently](https://techcrunch.com/2024/09/23/x-will-soon-make-your-public-posts-visible-to-accounts-youve-blocked/) than it has in the past. The new block functionality allows users you have blocked to view your posts and your profile, but not the ability to interact with your posts. Some users [believe this update to be a safety concern,](https://techcrunch.com/2024/10/18/why-changes-to-the-block-on-elon-musks-x-are-driving-users-away/) leading to an influx in Bluesky sign-ups as its block feature is more traditional.

In another move that separates Bluesky from X, the social network said it has [“no intention” of using user content to train generative AI tools](https://techcrunch.com/2024/11/15/unlike-x-bluesky-says-it-wont-train-ai-on-your-posts/) as X implemented a new terms of service that allows the platform to [train AI models on public posts.](https://techcrunch.com/2024/10/17/elon-musks-x-is-changing-its-privacy-policy-to-allow-third-parties-to-train-ai-on-your-posts/) But that doesn’t stop [third parties from doing so.](https://techcrunch.com/2024/11/27/blueskys-open-api-means-anyone-can-scrape-your-data-for-ai-training/)

While Bluesky was initially kicked off as a project convened by Jack Dorsey in 2019 when he was CEO of Twitter, the social app has been an independent company since its inception in 2021.

### Is Bluesky free?

Yes, and it is now open to the public.

### How does Bluesky make money?

Bluesky’s goal is to find another means to sustain its network outside of advertising with paid services, so it can remain free to end users. On July 5, 2023, [Bluesky announced](https://techcrunch.com/2023/07/05/bluesky-announces-its-8m-seed-round-first-paid-service-custom-domains/) additional seed round funding and a paid service that provides custom domains for end users who want to have a unique domain as their handle on the service. Bluesky has also emphasized that it does not want to “require selling user data for ads” [in order to monetize its platform.](https://bsky.social/about/blog/7-05-2023-business-plan)

In November 2024, Bluesky announced it raised [a $15 million Series A round](https://techcrunch.com/2024/10/24/bluesky-raises-15m-series-a-plans-to-launch-subscriptions/) and is developing a subscription service for premium features. Bluesky, however, noted its subscription model will not follow in the footsteps of X’s [“pay to win” premium offerings.](https://bsky.social/about/blog/10-24-2024-series-a) Users have spotted mockups teasing the [subscription feature, dubbed Bluesky+,](https://techcrunch.com/2024/12/09/bluesky-teases-paid-subscription-bluesky-in-new-mockup/) which could include features like higher quality video uploads and profile customizations.

In December 2024, Peter Wang announced [a $1 million fund,](https://techcrunch.com/2024/12/18/with-25m-users-bluesky-gets-a-1m-fund-to-take-on-social-media-and-ai/) dubbed Skyseed, that will offer grants to those building on Bluesky’s open source AT Protocol.

### Is Bluesky decentralized?

Yes. Bluesky’s team is [developing the decentralized AT Protocol,](https://techcrunch.com/2024/06/25/welcome-to-the-fediverse-your-guide-to-mastodon-threads-bluesky-and-more/) which Bluesky was built atop. In its beta phase, users can only join the bsky.social network, but Bluesky plans to be federated, meaning that endless individually operated communities can exist within the open source network. So, if a developer outside of Bluesky built their own new social app using the AT Protocol, Bluesky users could jump over to the new app and port over their existing followers, handle and data.

“You’ll always have the freedom to choose (and to exit) instead of being held to the whims of private companies or black box algorithms. And wherever you go, your friends and relationships will be there too,” [a Bluesky blog post explained](https://blueskyweb.xyz/blog/11-15-2023-toward-federation).

### What third-party apps are built on the AT Protocol?

Many developers are building [consumer-facing apps](https://techcrunch.com/2025/04/04/beyond-bluesky-these-are-the-apps-building-social-experiences-on-the-at-protocol/#h-photo-and-video-sharing-apps) on Bluesky or its underlying AT Protocol. These apps are built on open technology, as opposed to being siloed within big tech’s centralized, opaque ownership.

Some social apps include [Flashes](https://bsky.app/profile/did:plc:24kqkpfy6z7avtgu3qg57vvl), a photo viewing client; [Spark](https://techcrunch.com/2025/01/28/reelo-stands-out-among-the-apps-building-a-tiktok-for-bluesky/), a TikTok-like app; and [Skylight Social](https://bsky.app/profile/skylight.social), which is backed by Mark Cuban.

Check out our more [comprehensive list](https://techcrunch.com/2025/04/04/beyond-bluesky-these-are-the-apps-building-social-experiences-on-the-at-protocol/#h-music-and-audio-apps) at various apps built within this ecosystem, including cross-posting apps, music apps, feed builders, and livestreamers.

### Is Bluesky secure?

In October 2023, Bluesky [added email verification](https://techcrunch.com/2023/10/10/x-competitor-bluesky-adds-email-verification-flags-misleading-links-in-security-focused-update/) as part of a larger effort to improve account security and authentication on the network. The addition is an important step forward in terms of making Bluesky more competitive with larger networks like X, which have more robust security controls. In December 2023, Bluesky allowed users to opt out of a change that would [expose their posts to the public web](https://techcrunch.com/2023/12/06/bluesky-says-it-will-allow-users-to-opt-out-of-the-public-web-interface-after-backlash/) following backlash from users.

### Is Bluesky customizable?

Yes. In May 2023, Bluesky released custom algorithms, which it calls “custom feeds.” Custom feeds allow users to subscribe to multiple different algorithms that showcase different kinds of posts a user may want to see. You can pin custom feeds that will show up at the top of your timeline as different tabs to pick from. The feeds you pin, or save, are located under the “My Feeds” menu in the app’s sidebar.

In March 2024,​​ the company announced [“AT Protocol Grants,”](https://techcrunch.com/2024/03/11/bluesky-is-funding-developer-projects-to-give-its-twitter-x-alternative-a-boost/) a new program that will dole out small grants to developers in order to foster growth and customization. One of the recipients, SkyFeed, is a custom tool that lets anyone build their own feeds using a graphical user interface.

### Is Bluesky on iOS and Android?

Yes. Bluesky has rolled out to [Android users](https://techcrunch.com/2023/04/20/jack-dorsey-backed-twitter-alternative-bluesky-hits-android/) after it was initially launched to iOS users. Users can access Bluesky on the web [here](https://bsky.app/).

### How does Bluesky tackle misinformation?

After an [October 2023 update](https://techcrunch.com/2023/10/10/x-competitor-bluesky-adds-email-verification-flags-misleading-links-in-security-focused-update/), the app will now warn users of misleading links by flagging them. If links shared in users’ posts don’t match their text, the app will offer a “possibly misleading” warning to the user to alert them that the link may be directing them somewhere they don’t want to go.

![](https://techcrunch.com/wp-content/uploads/2023/10/bluesky-misleading-link.png?w=300)**Image Credits:** Bluesky on GitHub**Image Credits:** Bluesky on Github

In December 2024, the Bluesky Safety team posted that the company [updated its impersonation policy](https://bsky.app/profile/safety.bsky.app/post/3lc4h7p676225) to be “more aggressive,” adding that “impersonation and handle-squatting accounts will be removed.” The company said it is [also exploring alternatives](https://techcrunch.com/2024/11/30/bluesky-promises-more-verification-and-an-aggressive-approach-to-impersonation/) to its current domain handle verification process.

### Has Bluesky had any controversies?

Bluesky has been embattled with moderation issues since its first launch. The app has been accused of failing to protect its marginalized users and failing to moderate racist content. Following [a controversy](https://techcrunch.com/2023/07/27/bluesky-racism-slur-apology-feedback/) about the app allowing racial slurs in account handles, frustrated users initiated a “posting strike,” where they refused to engage with the platform until it established guardrails to flag slurs and other offensive terms in usernames.

In December 2024, Bluesky also faced criticism when writer and podcast host [Jesse Singal joined the platform.](https://techcrunch.com/2024/12/13/bluesky-is-at-a-crossroads-as-users-petition-to-ban-jesse-singal-over-anti-trans-views-harassment/) Singal has been cataloged by GLAAD’s Accountability Project for his writings on transgender issues and other matters. Bluesky users have reported Singal’s account en masse, leading the company to ban him, reinstate him, and then label his account intolerant by its moderation service.

### What moderation features does Bluesky have?

In December 2023, Bluesky rolled out [“more advanced automated tooling”](https://techcrunch.com/2023/12/01/bluesky-rolls-out-automated-moderation-tools-plus-user-and-moderation-lists/) designed to flag content that violates its Community Guidelines that will then be reviewed by the app’s moderation team. Bluesky has moderation features similar to ones on X, including user lists and moderation lists, and a feature that lets users limit who can reply to posts. However, some Bluesky users are still advocating for the ability to set their accounts to private.

In March 2024, [the company launched Ozone](https://techcrunch.com/2024/03/12/bluesky-launches-ozone-a-tool-that-lets-users-create-and-run-their-own-independent-moderation-services/), a tool that lets users create and run their own independent moderation services that will give users [“unprecedented control”](https://bsky.social/about/blog/03-12-2024-stackable-moderation) over their social media experience. In October 2024, [Bluesky joined Instragram’s Threads](https://techcrunch.com/2024/10/10/bluesky-joins-threads-to-court-users-frustrated-by-metas-moderation-issues/) app in an effort to court users who were frustrated by Meta’s moderation issues.

In January 2025, Bluesky published [its 2024 moderation report](https://bsky.social/about/blog/01-17-2025-moderation-2024) that said it saw a 17x increase in moderation reports following the rapid growth on the platform. The report also noted that the largest number of reports came from users reporting accounts or posts for harassment, trolling, or intolerance — an issue that’s plagued Bluesky as it’s grown. To meet the demands caused by this growth, Bluesky [increased its moderation team to roughly 100 moderators](https://techcrunch.com/2025/01/17/bluesky-saw-17x-increase-in-moderation-reports-in-2024-after-rapid-growth/) and will continue to hire.

[Bluesky revamped its Community Guidelines in August 2025](https://techcrunch.com/2025/08/14/bluesky-rolls-out-massive-revamp-to-policies-and-community-guidelines/), with some of the changes representing an effort by Bluesky to purposefully shape its community and the behavior of its users.

### What’s the difference between Bluesky and Mastodon?

Though Bluesky’s architecture is similar to Mastodon’s, many users have found Bluesky to be more intuitive, while [Mastodon can come off as inaccessible:](https://techcrunch.com/2024/06/25/welcome-to-the-fediverse-your-guide-to-mastodon-threads-bluesky-and-more/) Choosing which instance to join feels like an impossible task on Mastodon, and longtime users are very defensive about their established posting norms, which can make joining the conversation intimidating. To remain competitive, Mastodon recently [simplified](https://techcrunch.com/2023/05/02/mastodon-now-has-a-simpler-sign-up-process/) its sign-up flow, making mastodon.social the default server for new users.

However, the launch of [federation](https://techcrunch.com/2023/11/16/x-rival-bluesky-hits-2m-users-saying-federation-coming-early-next-year/) will make it work more similarly to Mastodon in that users can pick and choose which servers to join and move their accounts around at will.

### Who owns Bluesky?

Though Jack Dorsey funded Bluesky, he is not involved in day-to-day development and no longer sits on the company’s board. The CEO of Bluesky is Jay Graber, who previously worked as a software engineer for the cryptocurrency Zcash, then founded an event-planning site called [Happening](https://happening.net/).

_If you have more FAQs about Bluesky not covered here, leave us a comment below._

_This story was originally published in May 2023 and is updated regularly with new information._
</article>
</example>
</title_examples>
"""


def generate_summary_prompt(
    content_type: str, max_bullet_points: int, max_quotes: int
) -> tuple[str, str]:
    """
    Generate optimized prompts for caching.

    Returns:
        Tuple of (system_message, user_message_template)
        System message contains static instructions (cached).
        User message template is for variable content (not cached).
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


class OpenAISummarizationService:
    """OpenAI service for content summarization using GPT-5-mini."""

    def __init__(self):
        openai_api_key = getattr(settings, "openai_api_key", None)
        if not openai_api_key:
            raise ValueError("OpenAI API key is required for LLM service")

        self.client = OpenAI(api_key=openai_api_key)
        self.model_name = "gpt-5-mini"
        logger.info("Initialized OpenAI provider for summarization")

    @staticmethod
    def _extract_json_payload(validation_error: ValidationError) -> str | None:
        """Return the raw JSON payload embedded in a ValidationError, if available."""

        for error in validation_error.errors():
            input_value = error.get("input")
            if isinstance(input_value, str):
                return input_value
        return None

    def _parse_summary_payload(
        self,
        raw_payload: str,
        schema: type[StructuredSummary] | type[NewsSummary],
        content_id: str,
    ) -> StructuredSummary | NewsSummary | None:
        """Clean and parse an OpenAI JSON payload into the target schema."""

        cleaned_payload = strip_json_wrappers(raw_payload)
        if not cleaned_payload:
            logger.error("OpenAI response payload empty after cleanup")
            error = ValueError("Empty payload after cleanup")
            error_logger.log_processing_error(
                item_id=content_id or "unknown",
                error=error,
                operation="openai_empty_payload",
                context={"raw_payload": raw_payload, "response_length": len(raw_payload)},
            )
            return None

        try:
            summary_data: Any = json.loads(cleaned_payload)
        except json.JSONDecodeError as decode_error:
            repaired_payload = try_repair_truncated_json(cleaned_payload)
            if not repaired_payload:
                logger.error(
                    "Failed to repair truncated JSON from OpenAI response: %s", decode_error
                )
                error_logger.log_processing_error(
                    item_id=content_id or "unknown",
                    error=decode_error,
                    operation="openai_json_decode_error",
                    context={
                        "cleaned_payload": cleaned_payload,
                        "response_length": len(cleaned_payload),
                    },
                )
                return None

            logger.info("Repaired OpenAI JSON payload after initial decode failure")

            try:
                summary_data = json.loads(repaired_payload)
            except json.JSONDecodeError as repair_error:
                logger.error("Failed to decode repaired OpenAI JSON payload: %s", repair_error)
                error_logger.log_processing_error(
                    item_id=content_id or "unknown",
                    error=repair_error,
                    operation="openai_json_repair_failed",
                    context={
                        "repaired_payload": repaired_payload,
                        "response_length": len(repaired_payload),
                    },
                )
                return None

        try:
            return schema.model_validate(summary_data)
        except ValidationError as schema_error:
            recovered = self._attempt_structured_summary_recovery(
                summary_data,
                schema,
                content_id,
            )
            if recovered is not None:
                return recovered

            logger.error("OpenAI JSON payload failed schema validation: %s", schema_error)
            response_text = (
                json.dumps(summary_data, ensure_ascii=False)[:2000]
                if isinstance(summary_data, dict)
                else str(summary_data)[:2000]
            )
            error_logger.log_processing_error(
                item_id=content_id or "unknown",
                error=schema_error,
                operation="openai_schema_validation_error",
                context={"summary_data": response_text, "response_length": len(response_text)},
            )
            return None

    @staticmethod
    def _finalize_summary(
        summary: StructuredSummary | NewsSummary,
        content_type: str,
    ) -> StructuredSummary | NewsSummary:
        """Apply post-processing to the structured summary before returning it."""

        if content_type != "news_digest" and hasattr(summary, "quotes") and summary.quotes:
            filtered_quotes = [quote for quote in summary.quotes if len(quote.text or "") >= 10]
            if len(filtered_quotes) != len(summary.quotes):
                logger.warning("Filtered out quotes shorter than 10 characters")
                summary.quotes = filtered_quotes

        return summary

    @staticmethod
    def _attempt_structured_summary_recovery(
        summary_data: Any,
        schema: type[StructuredSummary] | type[NewsSummary],
        content_id: str,
    ) -> StructuredSummary | None:
        """Attempt to coerce partial payloads into a valid StructuredSummary."""

        if schema is not StructuredSummary or not isinstance(summary_data, dict):
            return None

        normalized = deepcopy(summary_data)

        # Always ensure classification defaults to to_read
        classification = normalized.get("classification")
        if not isinstance(classification, str) or not classification.strip():
            normalized["classification"] = "to_read"

        # Normalize bullet points: accept string lists or synthesize from overview/key points
        bullet_points: list[dict[str, str]] = []
        raw_bullets = normalized.get("bullet_points")

        if isinstance(raw_bullets, list):
            for entry in raw_bullets:
                if isinstance(entry, dict):
                    text = str(entry.get("text", "")).strip()
                    if not text:
                        continue
                    category = str(entry.get("category", "insight")).strip() or "insight"
                    bullet_points.append({"text": text, "category": category})
                elif isinstance(entry, str) and entry.strip():
                    bullet_points.append({"text": entry.strip(), "category": "insight"})

        if not bullet_points:
            key_points = normalized.get("key_points")
            if isinstance(key_points, list):
                bullet_points.extend(
                    {"text": item.strip(), "category": "insight"}
                    for item in key_points
                    if isinstance(item, str) and item.strip()
                )

        if not bullet_points:
            overview = normalized.get("overview")
            if isinstance(overview, str):
                overview_text = overview.strip()
                sentences = [
                    sentence.strip()
                    for sentence in re.split(r"(?<=[.!?])\s+", overview_text)
                    if sentence and len(sentence.strip()) >= 10
                ]
                if not sentences and len(overview_text) >= 10:
                    sentences = [overview_text[:400]]

                bullet_points.extend(
                    {"text": sentence[:400], "category": "insight"} for sentence in sentences[:3]
                )

        if not bullet_points:
            title = normalized.get("title")
            if isinstance(title, str):
                title_text = title.strip()
                if len(title_text) >= 10:
                    bullet_points.append({"text": title_text[:400], "category": "insight"})

        if not bullet_points:
            logger.error(
                "Unable to synthesize bullet points for content %s during recovery", content_id
            )
            return None

        # Ensure minimum bullet point count expected by schema (3)
        while len(bullet_points) < 3:
            bullet_points.append(dict(bullet_points[-1]))

        normalized["bullet_points"] = bullet_points[:50]

        # Normalize quotes to required shape
        quotes = []
        raw_quotes = normalized.get("quotes")
        if isinstance(raw_quotes, list):
            for item in raw_quotes:
                if isinstance(item, dict):
                    raw_text = str(item.get("text", "")).strip()
                    if not raw_text:
                        continue
                    context = (
                        str(item.get("context", "Source unspecified")).strip()
                        or "Source unspecified"
                    )
                    quotes.append({"text": raw_text, "context": context})
                elif isinstance(item, str) and item.strip():
                    quotes.append({"text": item.strip(), "context": "Source unspecified"})
        normalized["quotes"] = quotes[:50]

        # Topics should be a list of strings
        topics = normalized.get("topics")
        if isinstance(topics, list):
            normalized["topics"] = [str(topic).strip() for topic in topics if str(topic).strip()]
        else:
            normalized["topics"] = []

        # Ensure full_markdown field exists even if empty string
        if not isinstance(normalized.get("full_markdown"), str):
            normalized["full_markdown"] = ""

        # Remove helper fields not part of schema to avoid validation issues
        normalized.pop("key_points", None)

        try:
            recovered = StructuredSummary.model_validate(normalized)
        except ValidationError as recovery_error:
            logger.error(
                "Structured summary recovery failed for content %s: %s",
                content_id,
                recovery_error,
            )
            return None

        logger.info(
            "Recovered structured summary payload after schema failure for content %s",
            content_id,
        )
        return recovered

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def summarize_content(
        self,
        content: str,
        max_bullet_points: int = 6,
        max_quotes: int = 8,
        content_type: str = "article",
    ) -> StructuredSummary | NewsSummary | None:
        """Summarize content using LLM and classify it.

        Args:
            content: The content to summarize
            max_bullet_points: Maximum number of bullet points to generate (default: 6)
            max_quotes: Maximum number of quotes to extract (default: 8)
            content_type: Type of content - "article" or "podcast" (default: "article")

        Returns:
            StructuredSummary with bullet points, quotes, classification, and full_markdown
        """
        content_identifier = str(id(content))

        try:
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="ignore")

            if len(content) > MAX_CONTENT_LENGTH:
                logger.warning(
                    "Content length (%s chars) exceeds max (%s chars), truncating",
                    len(content),
                    MAX_CONTENT_LENGTH,
                )
                content = content[:MAX_CONTENT_LENGTH] + "\n\n[Content truncated due to length]"

            # Generate cache-optimized prompts (system instructions + user content)
            system_message, user_template = generate_summary_prompt(
                content_type, max_bullet_points, max_quotes
            )
            user_message = user_template.format(content=content)

            schema: type[StructuredSummary] | type[NewsSummary]
            schema = NewsSummary if content_type == "news_digest" else StructuredSummary

            max_output_tokens = 25000  # Large limit for full_markdown support
            if content_type == "podcast":
                max_output_tokens = 8000  # Podcasts don't include transcript in full_markdown
            elif content_type == "news_digest":
                max_output_tokens = 4000  # Increased to reduce truncation errors
            elif content_type == "hackernews":
                max_output_tokens = 30000  # Needs even more for article + comments

            try:
                response = self.client.responses.parse(
                    model=self.model_name,
                    input=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message},
                    ],
                    max_output_tokens=max_output_tokens,
                    text_format=schema,
                    prompt_cache_key=f"summary_{content_type}",  # Group by content type for caching
                )
            except ValidationError as validation_error:
                logger.warning("OpenAI structured output validation failed: %s", validation_error)
                raw_payload = self._extract_json_payload(validation_error) or ""

                # Try to repair truncated JSON before failing
                if "EOF while parsing" in str(validation_error) and raw_payload:
                    try:
                        repaired = try_repair_truncated_json(raw_payload)
                        if repaired:
                            logger.info("Attempting to use repaired JSON after truncation")
                            # Attempt to validate the repaired JSON
                            if content_type == "news_digest":
                                return NewsSummary.model_validate_json(repaired)
                            else:
                                return StructuredSummary.model_validate_json(repaired)
                    except Exception as repair_error:
                        logger.warning("JSON repair failed: %s", repair_error)

                error_logger.log_processing_error(
                    item_id=content_identifier or "unknown",
                    error=validation_error,
                    operation="openai_structured_output_error",
                    context={"raw_payload": raw_payload, "response_length": len(raw_payload)},
                )
                raise StructuredSummaryRetryableError(
                    "OpenAI structured output validation failed; retrying"
                ) from validation_error

            if not response.output:
                logger.error("LLM returned no choices")
                error_logger.log_processing_error(
                    item_id=content_identifier or "unknown",
                    error=ValueError("LLM returned no output"),
                    operation="openai_no_output",
                    context={},
                )
                return None

            parsed_message = response.output_parsed
            if parsed_message is None:
                logger.error("Parsed response missing from OpenAI response")
                output_text = getattr(response, "output_text", "")
                error_logger.log_processing_error(
                    item_id=content_identifier or "unknown",
                    error=ValueError("Parsed response missing"),
                    operation="openai_missing_parsed_message",
                    context={"output_text": output_text},
                )
                return None

            # Log cache metrics for monitoring
            usage = response.usage
            if usage:
                # OpenAI uses input_tokens for prompt tokens
                input_tokens = getattr(usage, "input_tokens", 0)

                # Access cached tokens from input_tokens_details if available
                cached_tokens = 0
                if hasattr(usage, "input_tokens_details") and usage.input_tokens_details:
                    cached_tokens = getattr(usage.input_tokens_details, "cached_tokens", 0)

                cache_hit_rate = (cached_tokens / input_tokens * 100) if input_tokens > 0 else 0

                logger.info(
                    "OpenAI cache metrics - content_type: %s, input_tokens: %d, cached_tokens: %d, cache_hit_rate: %.1f%%",
                    content_type,
                    input_tokens,
                    cached_tokens,
                    cache_hit_rate,
                )

            return self._finalize_summary(parsed_message, content_type)

        except StructuredSummaryRetryableError as retryable_error:
            logger.warning("Retryable structured summary failure: %s", retryable_error)
            raise
        except OpenAIError as error:
            logger.error("OpenAI structured output error: %s", error)
            error_logger.log_processing_error(
                item_id=content_identifier or "unknown",
                error=error,
                operation="openai_structured_output_error",
                context={},
            )
            return None
        except Exception as error:  # noqa: BLE001
            logger.error("Error generating structured summary: %s", error)
            error_logger.log_processing_error(
                item_id=content_identifier or "unknown",
                error=error,
                operation="unexpected_error",
                context={},
            )
            return None


class OpenAITranscriptionService:
    """OpenAI service for audio transcription using Whisper API."""

    def __init__(self):
        openai_api_key = getattr(settings, "openai_api_key", None)
        if not openai_api_key:
            raise ValueError("OpenAI API key is required for transcription service")

        self.client = OpenAI(api_key=openai_api_key)
        self.model_name = "gpt-4o-transcribe"
        logger.info("Initialized OpenAI provider for transcription")

    def _get_audio_format(self, file_path: Path) -> str:
        """Determine audio format from file extension."""
        extension = file_path.suffix.lower()
        format_map = {
            ".mp3": "mp3",
            ".mp4": "mp4",
            ".m4a": "mp4",
            ".wav": "wav",
            ".webm": "webm",
            ".ogg": "ogg",
            ".opus": "opus",
            ".flac": "flac",
        }
        return format_map.get(extension, "mp3")

    def _check_file_size(self, file_path: Path) -> bool:
        """Check if file is within size limit."""
        file_size = os.path.getsize(file_path)
        return file_size <= MAX_FILE_SIZE_BYTES

    def _get_audio_duration(self, file_path: Path) -> float:
        """Get audio duration in seconds using ffprobe."""
        try:
            cmd = [
                "ffprobe",
                "-i",
                str(file_path),
                "-show_entries",
                "format=duration",
                "-v",
                "quiet",
                "-of",
                "csv=p=0",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.error(f"Failed to get audio duration: {e}")
            # Estimate based on file size - rough approximation
            # Assuming 128kbps bitrate as average
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            estimated_duration = file_size_mb * 60  # Very rough estimate
            logger.warning(f"Using estimated duration: {estimated_duration:.1f} seconds")
            return estimated_duration

    def _split_audio_file_ffmpeg(self, file_path: Path) -> list[Path]:
        """Split large audio file into chunks using ffmpeg directly."""
        logger.info(f"Splitting large audio file using ffmpeg: {file_path}")

        # Get audio duration
        duration = self._get_audio_duration(file_path)
        num_chunks = int((duration + CHUNK_DURATION_SECONDS - 1) // CHUNK_DURATION_SECONDS)

        logger.info(f"Audio duration: {duration:.1f}s, will split into {num_chunks} chunks")

        # Create temporary directory for chunks
        temp_dir = Path(tempfile.mkdtemp(prefix="audio_chunks_"))
        chunk_paths = []
        audio_format = self._get_audio_format(file_path)

        try:
            for i in range(num_chunks):
                start_time = i * CHUNK_DURATION_SECONDS

                # Create chunk filename
                chunk_filename = f"chunk_{i:03d}.{audio_format}"
                chunk_path = temp_dir / chunk_filename

                # Build ffmpeg command
                cmd = [
                    "ffmpeg",
                    "-i",
                    str(file_path),
                    "-ss",
                    str(start_time),
                    "-t",
                    str(CHUNK_DURATION_SECONDS),
                    "-acodec",
                    "copy",  # Copy codec to avoid re-encoding
                    "-y",  # Overwrite output file
                    str(chunk_path),
                ]

                logger.info(f"Creating chunk {i + 1}/{num_chunks}")

                # Execute ffmpeg
                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode != 0:
                    raise RuntimeError(f"ffmpeg failed: {result.stderr}")

                chunk_paths.append(chunk_path)

                # Verify chunk was created
                if not chunk_path.exists() or os.path.getsize(chunk_path) == 0:
                    raise RuntimeError(f"Failed to create chunk: {chunk_path}")

                logger.info(
                    f"Created chunk {i + 1}/{num_chunks}: "
                    f"{os.path.getsize(chunk_path) / (1024 * 1024):.1f}MB"
                )

            return chunk_paths

        except Exception as e:
            # Clean up on error
            for chunk_path in chunk_paths:
                if chunk_path.exists():
                    chunk_path.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()
            raise e

    def _check_ffmpeg_available(self) -> bool:
        """Check if ffmpeg is available on the system."""
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _get_transcription_prompt(self, file_path: Path) -> str:
        """Generate a contextual prompt based on the file name and podcast context."""
        file_name = file_path.stem

        # Default prompt for podcasts
        prompt = (
            "This is a podcast episode. Please transcribe accurately, "
            "including speaker names when mentioned."
        )

        # Add specific context based on filename patterns
        if "interview" in file_name.lower():
            prompt = (
                "This is a podcast interview. Please transcribe accurately, "
                "noting different speakers."
            )
        elif "tech" in file_name.lower() or "ai" in file_name.lower():
            prompt = (
                "This is a technology podcast discussing AI, software, and tech innovations. "
                "Include technical terms accurately."
            )
        elif "news" in file_name.lower():
            prompt = (
                "This is a news podcast. Please transcribe accurately, "
                "including proper names and places."
            )
        elif any(term in file_name.lower() for term in ["bg2", "bill", "gurley", "gerstner"]):
            prompt = (
                "This is the BG2 podcast with Bill Gurley and Brad Gerstner discussing "
                "technology, venture capital, and market trends."
            )

        return prompt

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _transcribe_single_file(self, file_path: Path, prompt: str) -> tuple[str, str | None]:
        """Transcribe a single audio file."""
        with open(file_path, "rb") as audio_file:
            logger.info(f"Sending audio file to OpenAI for transcription: {file_path}")

            transcription = self.client.audio.transcriptions.create(
                model=self.model_name, file=audio_file, response_format="json", prompt=prompt
            )

            transcript = transcription.text
            language = getattr(transcription, "language", None)

            logger.info(
                f"Successfully transcribed audio. "
                f"Length: {len(transcript)} chars, Language: {language}"
            )

            return transcript, language

    def transcribe_audio(self, audio_file_path: Path) -> tuple[str, str | None]:
        """Transcribe audio file using OpenAI Whisper API.

        Handles large files by splitting them into chunks.

        Args:
            audio_file_path: Path to the audio file to transcribe

        Returns:
            Tuple of (transcript, language_code)
        """
        try:
            # Generate contextual prompt
            prompt = self._get_transcription_prompt(audio_file_path)
            logger.info(f"Using transcription prompt: {prompt}")

            # Check file size
            if self._check_file_size(audio_file_path):
                # File is small enough, transcribe directly
                return self._transcribe_single_file(audio_file_path, prompt)

            # File is too large, need to split
            logger.info(f"File exceeds {MAX_FILE_SIZE_MB}MB limit, splitting into chunks")

            # Check if ffmpeg is available
            if not self._check_ffmpeg_available():
                raise RuntimeError(
                    "Audio file exceeds 25MB limit but ffmpeg is not available for splitting. "
                    "Please install ffmpeg (e.g., 'brew install ffmpeg' on macOS) "
                    "or use audio files smaller than 25MB."
                )

            # Split using ffmpeg
            chunk_paths = self._split_audio_file_ffmpeg(audio_file_path)

            try:
                # Transcribe each chunk
                transcripts = []
                detected_language = None

                for i, chunk_path in enumerate(chunk_paths):
                    logger.info(f"Transcribing chunk {i + 1}/{len(chunk_paths)}")

                    # Adjust prompt for subsequent chunks
                    chunk_prompt = prompt
                    if i > 0:
                        chunk_prompt += " This is a continuation of the previous segment."

                    chunk_transcript, chunk_language = self._transcribe_single_file(
                        chunk_path, chunk_prompt
                    )

                    transcripts.append(chunk_transcript)

                    # Use the language from the first chunk
                    if detected_language is None and chunk_language:
                        detected_language = chunk_language

                # Combine transcripts
                full_transcript = " ".join(transcripts)

                logger.info(
                    f"Successfully transcribed {len(chunk_paths)} chunks. "
                    f"Total length: {len(full_transcript)} chars"
                )

                return full_transcript, detected_language

            finally:
                # Clean up chunk files
                for chunk_path in chunk_paths:
                    if chunk_path.exists():
                        chunk_path.unlink()

                # Remove temporary directory
                if chunk_paths:
                    temp_dir = chunk_paths[0].parent
                    if temp_dir.exists() and temp_dir.name.startswith("audio_chunks_"):
                        with contextlib.suppress(OSError):
                            temp_dir.rmdir()

        except Exception as e:
            logger.error(f"Error transcribing audio with OpenAI: {e}")
            raise

    def transcribe_audio_from_buffer(
        self, audio_buffer: BinaryIO, filename: str
    ) -> tuple[str, str | None]:
        """Transcribe audio from a file buffer using OpenAI Whisper API.

        Args:
            audio_buffer: File-like object containing audio data
            filename: Original filename for the audio

        Returns:
            Tuple of (transcript, language_code)
        """
        try:
            # For buffers, we need to save to a temporary file to check size and potentially split
            with tempfile.NamedTemporaryFile(
                suffix=Path(filename).suffix, delete=False
            ) as tmp_file:
                tmp_file.write(audio_buffer.read())
                tmp_path = Path(tmp_file.name)

            try:
                # Use the file-based method
                return self.transcribe_audio(tmp_path)
            finally:
                # Clean up temporary file
                if tmp_path.exists():
                    tmp_path.unlink()

        except Exception as e:
            logger.error(f"Error transcribing audio buffer with OpenAI: {e}")
            raise


# Global instances
_openai_transcription_service = None
_openai_summarization_service = None


def get_openai_transcription_service() -> OpenAITranscriptionService:
    """Get the global OpenAI transcription service instance."""
    global _openai_transcription_service
    if _openai_transcription_service is None:
        _openai_transcription_service = OpenAITranscriptionService()
    return _openai_transcription_service


def get_openai_summarization_service() -> OpenAISummarizationService:
    """Get the global OpenAI summarization service instance."""
    global _openai_summarization_service
    if _openai_summarization_service is None:
        _openai_summarization_service = OpenAISummarizationService()
    return _openai_summarization_service
