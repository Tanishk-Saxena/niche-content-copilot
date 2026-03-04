"""
Prompt builders for Claude draft generation.
"""

PROMPT_VERSION = "1.2"

# Twitter shortens all URLs to 23 chars. When a link is appended, effective text budget is 257.
_TEXT_POST_LIMIT_NO_LINK = 280
_TEXT_POST_LIMIT_WITH_LINK = 256  # 280 - 23 (URL) - 1 (space)

_FORMAT_INSTRUCTIONS = {
    "text_post_no_link": (
        "\n\nFORMAT: Write a single tweet (text post).\n"
        "- Maximum {limit} characters\n"
        "- Direct and opinionated — no hedging\n"
        "- Leaves something to argue about\n"
        "- Return ONLY the tweet text, nothing else"
    ),
    "text_post_with_link": (
        "\n\nFORMAT: Write a single tweet (text post).\n"
        "- Maximum {limit} characters (a link to the article will be appended automatically — do NOT include it yourself)\n"
        "- Direct and opinionated — no hedging\n"
        "- Leaves something to argue about\n"
        "- Return ONLY the tweet text, nothing else"
    ),
    "thread_no_link": (
        "\n\nFORMAT: Write a Twitter thread (5-8 tweets).\n"
        "- Number each tweet: '1/', '2/', etc.\n"
        "- Each tweet max 280 characters\n"
        "- Start straight with the point — no meta-openers like 'A thread:' or 'This is not a drill'\n"
        "- End wherever it naturally ends — do not add a summary or moral conclusion\n"
        "- Return ONLY the numbered tweets separated by newlines, nothing else"
    ),
    "thread_with_link": (
        "\n\nFORMAT: Write a Twitter thread (5-8 tweets).\n"
        "- Number each tweet: '1/', '2/', etc.\n"
        "- Tweet 1 max 256 characters (a link will be appended to it — do NOT include it yourself)\n"
        "- All other tweets max 280 characters\n"
        "- Start straight with the point — no meta-openers like 'A thread:' or 'This is not a drill'\n"
        "- End wherever it naturally ends — do not add a summary or moral conclusion\n"
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


def build_user_message(story, fmt: str, include_link: bool = False) -> str:
    title = story.title or ""
    source = story.source or ""
    body = (story.full_text or story.summary or "")[:3000]

    if fmt == "text_post":
        if include_link:
            limit = _TEXT_POST_LIMIT_WITH_LINK
            instruction = _FORMAT_INSTRUCTIONS["text_post_with_link"].format(limit=limit)
        else:
            limit = _TEXT_POST_LIMIT_NO_LINK
            instruction = _FORMAT_INSTRUCTIONS["text_post_no_link"].format(limit=limit)
    elif fmt == "thread":
        instruction = _FORMAT_INSTRUCTIONS["thread_with_link" if include_link else "thread_no_link"]
    else:
        instruction = _FORMAT_INSTRUCTIONS.get("caption", "")

    return (
        f"STORY TITLE: {title}\n"
        f"SOURCE: {source}\n\n"
        f"ARTICLE TEXT:\n{body}\n"
        f"---{instruction}"
    )
