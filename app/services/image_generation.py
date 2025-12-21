"""
AI image generation service using Google Gemini.

Generates two types of images:
- News thumbnails: Simple, fast 1:1 images using gemini-2.5-flash-image
- Infographics: Complex 16:9 editorial images using gemini-3-pro-image-preview
"""

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from google import genai
from google.genai.types import GenerateContentConfig, ImageConfig

from app.core.logging import get_logger
from app.models.metadata import ContentData, ContentType

logger = get_logger(__name__)

# Models for image generation
NEWS_THUMBNAIL_MODEL = "gemini-2.5-flash-image"
INFOGRAPHIC_MODEL = "gemini-3-pro-image-preview"

# Image storage paths
NEWS_THUMBNAILS_DIR = Path("static/images/news_thumbnails")
INFOGRAPHICS_DIR = Path("static/images/content")


@dataclass
class ImageGenerationResult:
    """Result from image generation."""

    content_id: int
    image_path: str
    success: bool
    error_message: str | None = None


# ============================================================================
# Information Theory Scoring for News Thumbnails
# ============================================================================


@dataclass
class InterestingScore:
    """Score components for thumbnail interestingness based on information theory."""

    information_density: float = 0.0
    semantic_variety: float = 0.0
    surprise_novelty: float = 0.0
    conceptual_tension: float = 0.0
    abstractness: float = 0.0

    key_concepts: list[str] = field(default_factory=list)
    contrast_pairs: list[tuple[str, str]] = field(default_factory=list)

    @property
    def overall_score(self) -> float:
        """Weighted combination of all metrics (0-100)."""
        return (
            self.information_density * 0.20
            + self.semantic_variety * 0.20
            + self.surprise_novelty * 0.25
            + self.conceptual_tension * 0.20
            + self.abstractness * 0.15
        )


def _analyze_content_interestingness(
    title: str,
    overview: str,
    bullet_points: list[str],
) -> InterestingScore:
    """Analyze content using information theory principles."""
    score = InterestingScore()

    all_text = " ".join([title, overview] + bullet_points)
    words = re.findall(r"\b[a-zA-Z]{3,}\b", all_text.lower())

    word_freq = Counter(words)
    score.key_concepts = [w for w, c in word_freq.most_common(10) if c > 1 or w[0].isupper()]

    # Find contrast pairs
    contrast_markers = [
        ("but", "however"),
        ("despite", "although"),
        ("vs", "versus"),
        ("rise", "fall"),
        ("growth", "decline"),
        ("old", "new"),
        ("past", "future"),
        ("human", "ai"),
    ]
    for pair in contrast_markers:
        if any(p in all_text.lower() for p in pair):
            score.contrast_pairs.append(pair)

    # Information Density
    if len(words) > 0:
        unique_ratio = len(set(words)) / len(words)
        score.information_density = min(100, unique_ratio * 100)

    # Semantic Variety (entropy)
    if word_freq:
        total = sum(word_freq.values())
        entropy = -sum((c / total) * math.log2(c / total) for c in word_freq.values() if c > 0)
        max_entropy = math.log2(len(word_freq)) if len(word_freq) > 1 else 1
        score.semantic_variety = min(100, (entropy / max_entropy) * 100) if max_entropy > 0 else 0

    # Surprise/Novelty
    unusual_indicators = [
        "first",
        "never",
        "breakthrough",
        "unprecedented",
        "shocking",
        "surprising",
        "unexpected",
        "billion",
        "million",
        "record",
    ]
    unusual_count = sum(1 for ind in unusual_indicators if ind in all_text.lower())
    score.surprise_novelty = min(100, unusual_count * 15)

    # Conceptual Tension
    score.conceptual_tension = min(100, len(score.contrast_pairs) * 25)

    # Abstractness
    abstract_words = [
        "technology",
        "future",
        "innovation",
        "change",
        "growth",
        "crisis",
        "opportunity",
        "power",
        "security",
        "privacy",
    ]
    concrete_words = [
        "company",
        "person",
        "product",
        "money",
        "computer",
        "phone",
        "car",
        "market",
    ]
    abstract_count = sum(1 for w in words if w in abstract_words)
    concrete_count = sum(1 for w in words if w in concrete_words)
    if abstract_count + concrete_count > 0:
        score.abstractness = (abstract_count / (abstract_count + concrete_count)) * 100
    else:
        score.abstractness = 50

    return score


def _get_mood_from_score(score: InterestingScore) -> str:
    """Determine mood/tone from score."""
    moods = []
    if score.surprise_novelty > 60:
        moods.append("dramatic")
    if score.conceptual_tension > 50:
        moods.append("thought-provoking")
    if score.abstractness > 60:
        moods.append("futuristic")
    if not moods:
        moods = ["professional", "engaging"]
    return " and ".join(moods[:2])


# ============================================================================
# Prompt Builders
# ============================================================================


def _build_news_thumbnail_prompt(content: ContentData) -> str:
    """Build prompt for subtle news thumbnail."""
    summary = content.metadata.get("summary", {})
    title = summary.get("title") or content.display_title
    overview = summary.get("overview", "")

    bullet_points = []
    for bp in summary.get("bullet_points", [])[:3]:
        text = bp.get("text") if isinstance(bp, dict) else bp
        if text:
            bullet_points.append(text)

    score = _analyze_content_interestingness(title, overview, bullet_points)

    # Style based on abstractness
    if score.abstractness > 60:
        style_direction = """
- Abstract, conceptual representation
- Simple geometric shapes
- Plenty of negative space
- Minimalist composition"""
    elif score.abstractness > 30:
        style_direction = """
- Stylized, understated illustration
- Simple shapes and forms
- Subtle metaphorical imagery
- Balanced, calm composition"""
    else:
        style_direction = """
- Clean, simple illustration style
- Recognizable subjects, minimal detail
- Quiet visual hierarchy
- Refined editorial aesthetic"""

    tension_instruction = ""
    if score.contrast_pairs:
        tension = score.contrast_pairs[0]
        tension_instruction = f"\n- Visual tension between {tension[0]} and {tension[1]}"

    return f"""Create a subtle editorial thumbnail illustration.

CONTENT:
Title: {title}
Summary: {overview[:300] if overview else "N/A"}
Key themes: {", ".join(score.key_concepts[:5])}

VISUAL REQUIREMENTS:
{style_direction}
- No text, logos, or watermarks
- Square 1:1 aspect ratio
- Muted, subtle color palette
- Soft contrast, understated aesthetic
- Clean and minimal{tension_instruction}

MOOD: {_get_mood_from_score(score)}

Create a refined, elegant thumbnail image."""


def _build_infographic_prompt(content: ContentData) -> str:
    """Build prompt for complex editorial infographic (existing logic)."""
    parts = []
    summary = content.metadata.get("summary", {})

    title = summary.get("title") or content.display_title
    parts.append(f"Title: {title}")

    overview = summary.get("overview", "")
    if overview:
        parts.append(f"Summary: {overview}")

    bullet_points = summary.get("bullet_points", [])
    if bullet_points:
        key_points = []
        for bp in bullet_points[:3]:
            text = bp.get("text") if isinstance(bp, dict) else bp
            if text:
                key_points.append(text)
        if key_points:
            parts.append("Key points: " + "; ".join(key_points))

    quotes = summary.get("quotes", [])
    if quotes:
        quote_texts = []
        for q in quotes[:2]:
            text = q.get("text") if isinstance(q, dict) else q
            if text:
                quote_texts.append(f'"{text}"')
        if quote_texts:
            parts.append("Quotes: " + " ".join(quote_texts))

    content_context = "\n".join(parts)

    return f"""Create a visually striking, editorial-style illustration for a news article.

{content_context}

Style requirements:
- Modern, clean editorial illustration style
- Bold colors with good contrast
- Abstract or conceptual representation of the theme
- Professional, suitable for a news app
- No text or logos in the image
- 16:9 aspect ratio optimized for mobile display
"""


# ============================================================================
# Skip Logic
# ============================================================================


def _should_skip_image_generation(content: ContentData) -> tuple[bool, str]:
    """Check if image generation should be skipped."""
    if content.content_type == ContentType.PODCAST:
        metadata = content.metadata or {}
        if metadata.get("thumbnail_url"):
            return True, "YouTube podcast already has thumbnail"
        if metadata.get("video_id"):
            return True, "YouTube video - uses existing thumbnail"

    if not content.metadata.get("summary"):
        return True, "No summary available for prompt generation"

    return False, ""


# ============================================================================
# Image Generation Service
# ============================================================================


class ImageGenerationService:
    """Service for generating images from content summaries."""

    def __init__(self) -> None:
        self.client = genai.Client()
        # Ensure output directories exist
        NEWS_THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
        INFOGRAPHICS_DIR.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Initialized ImageGenerationService with models: news=%s, infographic=%s",
            NEWS_THUMBNAIL_MODEL,
            INFOGRAPHIC_MODEL,
        )

    def get_image_url(self, content_id: int, content_type: str = "article") -> str | None:
        """Get the URL for a content's image if it exists."""
        if content_type == "news":
            path = NEWS_THUMBNAILS_DIR / f"{content_id}.png"
            if path.exists():
                return f"/static/images/news_thumbnails/{content_id}.png"
        else:
            path = INFOGRAPHICS_DIR / f"{content_id}.png"
            if path.exists():
                return f"/static/images/content/{content_id}.png"
        return None

    def generate_image(self, content: ContentData) -> ImageGenerationResult:
        """Generate an image for content, dispatching by content type."""
        content_id = content.id or 0

        should_skip, reason = _should_skip_image_generation(content)
        if should_skip:
            logger.info("Skipping image generation for content %s: %s", content_id, reason)
            return ImageGenerationResult(
                content_id=content_id,
                image_path="",
                success=False,
                error_message=f"Skipped: {reason}",
            )

        if content.content_type == ContentType.NEWS:
            return self._generate_news_thumbnail(content)
        else:
            return self._generate_infographic(content)

    def _generate_news_thumbnail(self, content: ContentData) -> ImageGenerationResult:
        """Generate a subtle 1:1 thumbnail for news content."""
        content_id = content.id or 0

        try:
            prompt = _build_news_thumbnail_prompt(content)
            logger.debug("News thumbnail prompt for %s: %s", content_id, prompt[:200])

            response = self.client.models.generate_content(
                model=NEWS_THUMBNAIL_MODEL,
                contents=prompt,
                config=GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=ImageConfig(aspect_ratio="1:1"),
                ),
            )

            image_path = NEWS_THUMBNAILS_DIR / f"{content_id}.png"
            image_saved = False

            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts or []:
                    if (
                        part.inline_data
                        and part.inline_data.mime_type
                        and part.inline_data.mime_type.startswith("image/")
                    ):
                        image_path.write_bytes(part.inline_data.data)
                        image_saved = True
                        break

            if not image_saved:
                raise ValueError("No image generated in response")

            logger.info("Generated news thumbnail for %s at %s", content_id, image_path)

            return ImageGenerationResult(
                content_id=content_id,
                image_path=str(image_path),
                success=True,
            )

        except Exception as e:
            logger.exception(
                "News thumbnail generation failed for %s: %s",
                content_id,
                e,
                extra={
                    "component": "image_generation",
                    "operation": "generate_news_thumbnail",
                    "item_id": content_id,
                },
            )
            return ImageGenerationResult(
                content_id=content_id,
                image_path="",
                success=False,
                error_message=str(e),
            )

    def _generate_infographic(self, content: ContentData) -> ImageGenerationResult:
        """Generate a complex 16:9 infographic for articles/podcasts."""
        content_id = content.id or 0

        try:
            prompt = _build_infographic_prompt(content)
            logger.debug("Infographic prompt for %s: %s", content_id, prompt[:200])

            response = self.client.models.generate_content(
                model=INFOGRAPHIC_MODEL,
                contents=prompt,
                config=GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )

            image_path = INFOGRAPHICS_DIR / f"{content_id}.png"
            image_saved = False

            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts or []:
                    if (
                        part.inline_data
                        and part.inline_data.mime_type
                        and part.inline_data.mime_type.startswith("image/")
                    ):
                        image_path.write_bytes(part.inline_data.data)
                        image_saved = True
                        break

            if not image_saved:
                raise ValueError("No image generated in response")

            logger.info("Generated infographic for %s at %s", content_id, image_path)

            return ImageGenerationResult(
                content_id=content_id,
                image_path=str(image_path),
                success=True,
            )

        except Exception as e:
            logger.exception(
                "Infographic generation failed for %s: %s",
                content_id,
                e,
                extra={
                    "component": "image_generation",
                    "operation": "generate_infographic",
                    "item_id": content_id,
                },
            )
            return ImageGenerationResult(
                content_id=content_id,
                image_path="",
                success=False,
                error_message=str(e),
            )


# Module-level singleton
_service_instance: ImageGenerationService | None = None


def get_image_generation_service() -> ImageGenerationService:
    """Get or create the ImageGenerationService singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = ImageGenerationService()
    return _service_instance
