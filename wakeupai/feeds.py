import os
import logging # Added
from openai import OpenAI
from wakeupai.config import OPENAI_API_KEY, FEEDS_NEWS_ARTICLE_COUNT # NEWS_API_KEY could be used here in future

logger = logging.getLogger(__name__) # Added

# Initialize OpenAI client
if not OPENAI_API_KEY:
    logger.critical("OPENAI_API_KEY not configured. Feed generation functionality will not work.")
    client = None
else:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        logger.debug("OpenAI client initialized successfully for feeds module.")
    except Exception as e:
        logger.critical(f"Failed to initialize OpenAI client for feeds: {e}", exc_info=True)
        client = None

# Target character count for feeds to stay under 5 mins of speech (approx 700-800 words, ~4000 chars)
# OpenAI recommends max_tokens for completion, but for chat models, prompt engineering is key.
# We will aim for a response of about 300-500 words in the prompts.
MAX_FEED_WORDS = 400 # Aiming for a bit shorter to be safe

def _ask_openai(prompt: str, temperature: float = 0.7) -> str | None:
    """Helper function to query the OpenAI Chat API."""
    if not client:
        logger.error("OpenAI client not initialized for feeds. Cannot query.")
        return None
    try:
        logger.debug(f"Sending prompt to OpenAI for feed generation (first 50 chars): '{prompt[:50]}...'")
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo", # Or consider gpt-4 if available and needed, though more expensive
            messages=[
                {"role": "system", "content": f"You are a helpful assistant that provides concise information suitable for a morning audio feed. Please keep responses under {MAX_FEED_WORDS} words."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            # max_tokens can be used to further limit output length if necessary,
            # but good prompting is often more effective for quality.
            # max_tokens=MAX_FEED_WORDS * 2, # Rough estimate: 1 token ~ 0.75 words, so give some leeway
        )
        response_text = completion.choices[0].message.content.strip()
        logger.debug(f"Received response from OpenAI for feed (first 50 chars): '{response_text[:50]}...'")
        return response_text
    except Exception as e:
        logger.error(f"Error querying OpenAI for feed generation: {e}", exc_info=True)
        return None

def _generate_daily_news_feed(country: str = "world") -> str | None:
    """
    Generates a daily news summary using OpenAI.
    Placeholder: In a real scenario, this might use a dedicated News API first,
    and then OpenAI for summarization if needed.
    Args:
        country (str): The country for news focus (e.g., "US", "UK"), or "world" for global.
    """
    # For now, we ask OpenAI to generate a general news summary.
    # Prompt can be improved significantly.
    prompt = (
        f"Provide a concise summary of 3-4 significant current news headlines from {country} (or globally if 'world'). "
        f"Focus on factual reporting. The summary should be engaging for a morning update. "
        f"Ensure the total length is suitable for a brief audio feed, ideally around {FEEDS_NEWS_ARTICLE_COUNT} key points "
        f"and under {MAX_FEED_WORDS} words in total."
    )
    return _ask_openai(prompt, temperature=0.5) # News is better with lower temperature

def _generate_topic_facts_feed(topic: str) -> str | None:
    """
    Generates interesting facts or a short brief about a given topic.
    Args:
        topic (str): The topic for the feed (e.g., "Space Exploration", "Ancient Rome").
    """
    if not topic:
        logger.error("No topic provided for topic facts feed.")
        return None
    prompt = (
        f"Tell me some interesting and fun facts about '{topic}'. "
        f"Present it as an engaging short segment for a morning audio feed. "
        f"Keep the total length under {MAX_FEED_WORDS} words."
    )
    return _ask_openai(prompt, temperature=0.7)

def _generate_custom_prompt_feed(user_prompt: str) -> str | None:
    """
    Generates content based on a user-provided prompt.
    Args:
        user_prompt (str): The custom prompt from the user.
    """
    if not user_prompt:
        logger.error("No user prompt provided for custom feed.")
        return None
    
    # The system message in _ask_openai already guides for conciseness.
    # We pass the user_prompt directly.
    # We could add more system context here if needed, e.g. "The user wants a morning feed based on this: ..."
    return _ask_openai(user_prompt, temperature=0.7)


FEED_GENERATORS = {
    "daily_news": _generate_daily_news_feed,
    "topic_facts": _generate_topic_facts_feed,
    "custom_prompt": _generate_custom_prompt_feed,
}

def generate_feed_content(feed_type: str, options: dict = None) -> str | None:
    """
    Main function to generate feed content based on type.

    Args:
        feed_type (str): Type of feed. Supported: "daily_news", "topic_facts", "custom_prompt".
        options (dict, optional): Additional options for the feed type.
            For "daily_news": {"country": "US"} (optional, defaults to "world")
            For "topic_facts": {"topic": "your topic here"} (required)
            For "custom_prompt": {"prompt": "your prompt here"} (required)

    Returns:
        str | None: The generated text content for the feed, or None on failure.
    """
    options = options or {}
    logger.info(f"Generating feed content for type: '{feed_type}' with options: {options}")

    generator = FEED_GENERATORS.get(feed_type)

    if not generator:
        logger.error(f"Unknown feed type '{feed_type}'. Cannot generate content.")
        return None

    content = None
    try:
        if feed_type == "daily_news":
            country = options.get("country", "world")
            content = generator(country=country)
        elif feed_type == "topic_facts":
            topic = options.get("topic")
            if not topic:
                logger.error("'topic' is required in options for feed_type 'topic_facts'.")
                return None
            content = generator(topic=topic)
        elif feed_type == "custom_prompt":
            user_prompt = options.get("prompt")
            if not user_prompt:
                logger.error("'prompt' is required in options for feed_type 'custom_prompt'.")
                return None
            content = generator(user_prompt=user_prompt)
    except Exception as e_gen:
        logger.error(f"Exception during '{feed_type}' generation with options {options}: {e_gen}", exc_info=True)
        return None
    
    if content:
        logger.debug(f"Successfully generated content for '{feed_type}'. Length: {len(content)} chars.")
        # Basic length check (OpenAI should mostly respect the prompt, but good to have a fallback)
        if len(content) > (MAX_FEED_WORDS * 7): # Approx 7 chars per word as a loose upper bound check
            logger.warning(f"Generated content for '{feed_type}' is quite long ({len(content)} chars). May exceed 5 minutes of speech.")
        return content
    else:
        logger.warning(f"Failed to generate content for feed type '{feed_type}' (generator returned None).")
        return None

if __name__ == '__main__':
    # Setup basic logging for the __main__ test if not already configured
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.DEBUG, 
            format="%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        logger.info("Basic logging configured for feeds.py direct test run.")

    logger.info("--- Feeds Module Test ---")
    if not OPENAI_API_KEY or not client:
        logger.warning("OpenAI API key not configured or client not initialized. Cannot run feed generation tests.")
    else:
        logger.info("\n--- Testing Daily News Feed ---")
        news_feed = generate_feed_content("daily_news", options={"country": "US"})
        if news_feed:
            logger.info(f"Generated News Feed (first 100 chars):\n{news_feed[:100]}...")
            logger.info(f"Approx. word count: {len(news_feed.split())}")
        else:
            logger.error("Failed to generate daily news feed.")

        logger.info("\n--- Testing Topic Facts Feed ---")
        topic_feed = generate_feed_content("topic_facts", options={"topic": "The Roman Empire"})
        if topic_feed:
            logger.info(f"Generated Topic Feed (The Roman Empire, first 100 chars):\n{topic_feed[:100]}...")
            logger.info(f"Approx. word count: {len(topic_feed.split())}")
        else:
            logger.error("Failed to generate topic facts feed.")

        logger.info("\n--- Testing Custom Prompt Feed ---")
        custom_prompt_text = "Tell me a very short, uplifting story suitable for starting the day."
        custom_feed = generate_feed_content("custom_prompt", options={"prompt": custom_prompt_text})
        if custom_feed:
            logger.info(f"Generated Custom Feed (Uplifting Story, first 100 chars):\n{custom_feed[:100]}...")
            logger.info(f"Approx. word count: {len(custom_feed.split())}")
        else:
            logger.error("Failed to generate custom prompt feed.")
        
        logger.info("\n--- Testing Invalid Feed Type ---")
        invalid_feed = generate_feed_content("unknown_feed_type")
        if not invalid_feed:
            logger.info("Correctly handled invalid feed type (returned None).")

    logger.info("--- Feeds Module Test Complete ---")
