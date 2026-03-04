"""
Prompt builders for Claude draft generation.
"""

PROMPT_VERSION = "1.2"

_FORMAT_INSTRUCTIONS = {
    "text_post": (
        "\n\nFORMAT: Write a single tweet (text post).\n"
        "- Maximum 280 characters (aim for under 220)\n"
        "- Direct and opinionated — no hedging\n"
        "- Leaves something to argue about\n"
        "- Return ONLY the tweet text, nothing else"
    ),
    "thread": (
        "\n\nFORMAT: Write a Twitter thread (5-8 tweets).\n"
        "- Number each tweet: '1/', '2/', etc.\n"
        "- Each tweet max 280 characters\n"
        "- Hook hard in tweet 1\n"
        "- Build an argument across the thread\n"
        "- Land with a sharp conclusion in the final tweet\n"
        "- Return ONLY the numbered tweets separated by newlines, nothing else"
    ),
    "caption": (
        "\n\nFORMAT: Write a one-line caption.\n"
        "- One line only, dry and sharp\n"
        "- Like captioning something obvious that everyone is pretending not to notice\n"
        "- Return ONLY the caption text, nothing else"
    ),
}


def build_system_prompt(niche_config: dict) -> str:
    return niche_config.get("personality_prompt", "You are a sports content writer.")


def build_user_message(story, fmt: str) -> str:
    title = story.title or ""
    source = story.source or ""
    body = (story.full_text or story.summary or "")[:3000]
    format_instruction = _FORMAT_INSTRUCTIONS.get(fmt, "")

    return (
        f"STORY TITLE: {title}\n"
        f"SOURCE: {source}\n\n"
        f"ARTICLE TEXT:\n{body}\n"
        f"---{format_instruction}"
    )
