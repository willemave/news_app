#!/usr/bin/env python3
"""
Diagnostic script for YouTube extraction issues.
Run this to test if a YouTube URL can be extracted successfully.

Usage:
    python scripts/diagnose_youtube.py <youtube_url>
"""

import sys

import yt_dlp


def diagnose_youtube_url(url: str) -> None:
    """Test YouTube URL extraction with detailed output."""
    print(f"Testing YouTube URL: {url}")
    print(f"yt-dlp version: {yt_dlp.version.__version__}")
    print("-" * 80)

    ydl_opts = {
        "quiet": False,
        "verbose": True,
        "no_warnings": False,
        "extract_flat": False,
        "ignoreerrors": False,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en"],
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            print("\nExtracting video information...")
            info = ydl.extract_info(url, download=False)

            if info is None:
                print("❌ FAILED: yt-dlp returned None")
                print("\nPossible reasons:")
                print("  - Video is private or deleted")
                print("  - Video is geo-blocked")
                print("  - Video requires age verification")
                print("  - Rate limiting by YouTube")
                print("  - Outdated yt-dlp version")
                sys.exit(1)

            # Success - print summary
            print("\n✅ SUCCESS: Video information extracted")
            print(f"\nTitle: {info.get('title')}")
            print(f"Channel: {info.get('uploader')}")
            print(f"Duration: {info.get('duration')}s")
            print(f"Age-restricted: {info.get('age_limit', 0) > 0}")
            print(f"View count: {info.get('view_count', 0):,}")

            # Check for subtitles
            subtitles = info.get("subtitles", {})
            auto_captions = info.get("automatic_captions", {})
            has_en_subs = "en" in subtitles or "en" in auto_captions

            print(f"\nSubtitles available: {has_en_subs}")
            if subtitles:
                print(f"  Manual subtitles: {list(subtitles.keys())}")
            if auto_captions:
                print(f"  Auto captions: {list(auto_captions.keys())}")

        except yt_dlp.utils.DownloadError as e:
            print("\n❌ FAILED: DownloadError")
            print(f"\nError: {e}")
            print("\nPossible reasons:")
            print("  - Video is geo-blocked in your region")
            print("  - Video requires sign-in (age-restriction)")
            print("  - YouTube is rate-limiting your IP")
            print("  - Video was removed/made private")
            print("\nRecommended actions:")
            print("  1. Update yt-dlp: uv add --upgrade yt-dlp")
            print("  2. Check if video is accessible in browser")
            print("  3. Consider using cookies for age-restricted videos")
            sys.exit(1)

        except Exception as e:
            print(f"\n❌ FAILED: {type(e).__name__}")
            print(f"\nError: {e}")
            sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/diagnose_youtube.py <youtube_url>")
        print("\nExample:")
        print("  python scripts/diagnose_youtube.py 'https://youtu.be/2jtJnfth6Bw'")
        sys.exit(1)

    diagnose_youtube_url(sys.argv[1])
