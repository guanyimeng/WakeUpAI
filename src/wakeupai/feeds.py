import os
import logging
from openai import OpenAI
from ..config import OPENAI_API_KEY, FEEDS_NEWS_ARTICLE_COUNT # NEWS_API_KEY could be used here in future

logger = logging.getLogger(__name__)

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
# We will aim for a response of about 300-500 words in the prompts. = 400, Aiming for a bit shorter to be safe
MAX_FEED_WORDS = 400

# Model to use for web search enabled queries
WEB_SEARCH_MODEL = "gpt-4.1"

def _fetch_web_search_content_from_openai(input_prompt: str, country_code: str | None = None) -> str | None:
    """
    Helper function to query OpenAI using the web_search_preview tool.
    Args:
        input_prompt (str): The prompt to send to OpenAI.
        country_code (str, optional): The country code for user_location (e.g., "US", "GB").
                                      If None or "world", location is not specified for global results.
    Returns:
        str | None: The extracted text content or None on failure.
    """
    if not client:
        logger.error("OpenAI client not initialized. Cannot perform web search.")
        return None

    tools_payload = [{"type": "web_search_preview"}]

    # setup Web search location
    if country_code and country_code.lower() != "world":
        tools_payload[0]["user_location"] = {
            "type": "approximate",
            "country": country_code.upper()
        }
        logger.debug(f"Web search location set to: {country_code.upper()}")
    else:
        logger.debug("Web search location not specified (global search).")

    # Request to AI API
    try:
        logger.debug(f"Sending prompt to OpenAI for web search (model: {WEB_SEARCH_MODEL}, first 50 chars): '{input_prompt[:50]}...'")
        response = client.responses.create(
            model=WEB_SEARCH_MODEL,
            tools=tools_payload,
            input=input_prompt
        )
        logger.debug(f"Raw response from OpenAI web search: {response}")

        # Extract text response
        if isinstance(response, list) and len(response) > 1:
            message_part = response[1]
            if isinstance(message_part, dict) and message_part.get("type") == "message":
                content_list = message_part.get("content")
                if isinstance(content_list, list) and len(content_list) > 0:
                    output_text_part = content_list[0]
                    if isinstance(output_text_part, dict) and output_text_part.get("type") == "output_text":
                        text_content = output_text_part.get("text")
                        if text_content:
                            logger.debug(f"Successfully extracted text from web search (first 50 chars): '{text_content[:50]}...'")
                            return text_content.strip()
                        else:
                            logger.error("Extracted text from web search is empty.")
                    else:
                        logger.error(f"Unexpected structure for output_text_part: {output_text_part}")
                else:
                    logger.error(f"Unexpected structure or empty content list in message_part: {content_list}")
            else:
                logger.error(f"Second part of response is not a message: {message_part}")
        elif hasattr(response, 'output_text') and response.output_text:
             logger.info("Accessing web search result via response.output_text attribute.")
             return response.output_text.strip()
        else:
            logger.error(f"Unexpected response structure from OpenAI web search: {response}")

        return None

    except AttributeError as e:
        logger.error(f"OpenAI SDK Error: 'client.responses.create' may not be available or model/tool type is incorrect for web search. {e}", exc_info=True)
        logger.error(f"Please ensure your OpenAI library is up-to-date and supports the 'responses.create' API with 'web_search_preview' tool and '{WEB_SEARCH_MODEL}' model.")
        return None
    except Exception as e:
        logger.error(f"Error querying OpenAI with web search: {e}", exc_info=True)
        return None

# def _ask_openai(prompt: str, temperature: float = 0.7) -> str | None:
#     """Helper function to query the OpenAI Chat API (non-web-search)."""
#     if not client:
#         logger.error("OpenAI client not initialized for feeds. Cannot query.")
#         return None
#     try:
#         logger.debug(f"Sending prompt to OpenAI for feed generation (first 50 chars): '{prompt[:50]}...'")
#         completion = client.chat.completions.create(
#             model="gpt-3.5-turbo", # Or consider gpt-4 if available and needed, though more expensive
#             messages=[
#                 {"role": "system", "content": f"You are a helpful assistant that provides concise information suitable for a morning audio feed. Please keep responses under {MAX_FEED_WORDS} words."},
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=temperature,
#             # max_tokens can be used to further limit output length if necessary,
#             # but good prompting is often more effective for quality.
#             # max_tokens=MAX_FEED_WORDS * 2, # Rough estimate: 1 token ~ 0.75 words, so give some leeway
#         )
#         response_text = completion.choices[0].message.content.strip()
#         logger.debug(f"Received response from OpenAI for feed (first 50 chars): '{response_text[:50]}...'")
#         return response_text
#     except Exception as e:
#         logger.error(f"Error querying OpenAI for feed generation: {e}", exc_info=True)
#         return None

# Prompt engineering: Different topics
def _generate_daily_news_feed(country: str = "world") -> str | None:
    """
    Generates a daily news summary using OpenAI's web search capability.
    Args:
        country (str): The country for news focus (e.g., "US", "UK"), or "world" for global.
    """
    prompt = (
        f"You are Ron Burgundy from the movie Anchorman. "
        f"In the style of Run Burgundy, provide a concise summary of 3-4 significant current news headlines from {country} (or globally if 'world'). "
        f"Focus on factual reporting. The summary should be engaging for a morning update. "
        f"Also try to be engaging and funny, throwing in some inoffensive dad humor and puns occassionally. "
        f"Ensure the total length is suitable for a brief audio feed, ideally around {FEEDS_NEWS_ARTICLE_COUNT} key points "
        f"and under {MAX_FEED_WORDS} words in total. Use web search to get the latest information."
    )
    # For news, we pass the country code to the web search helper.
    return _fetch_web_search_content_from_openai(prompt, country_code=country)

def _generate_topic_facts_feed(topic: str) -> str | None:
    """
    Generates interesting facts or a short brief about a given topic using web search.
    Args:
        topic (str): The topic for the feed (e.g., "Space Exploration", "Ancient Rome").
    """
    if not topic:
        logger.error("No topic provided for topic facts feed.")
        return None
    prompt = (
        f"You are Ron Burgundy from the movie Anchorman. "
        f"In the style of Ron Burgundy, tell me some interesting and fun facts about '{topic}' based on current web search results. "
        f"Present it as an engaging short segment for a morning audio feed. "
        f"Also try to be engaging and funny, throwing in some inoffensive dad humor and puns occassionally. "
        f"Keep the total length under {MAX_FEED_WORDS} words."
    )
    # For general topics, country_code is typically not needed, resulting in a global search.
    return _fetch_web_search_content_from_openai(prompt)

def _generate_custom_prompt_feed(user_prompt: str) -> str | None:
    """
    Generates content based on a user-provided prompt using web search.
    Args:
        user_prompt (str): The custom prompt from the user.
    """
    if not user_prompt:
        logger.error("No user prompt provided for custom feed.")
        return None

    # We can prepend a general instruction to the user's prompt.
    enhanced_prompt = (
        f"Based on current web search results, provide a response for the following request. "
        f"The response should be concise, suitable for a morning audio feed, and ideally under {MAX_FEED_WORDS} words. "
        f"User's request: {user_prompt}"
    )
    # For custom prompts, country_code is typically not needed, resulting in a global search.
    return _fetch_web_search_content_from_openai(enhanced_prompt)

# Feed generators
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

# =============================================================================================================================
if __name__ == '__main__':
    # Setup basic logging for the __main__ test if not already configured
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        logger.info("Basic logging configured for feeds.py direct test run.")

    import json # For saving results to JSON

    TEST_OUTPUT_DIR = "test_output/test_generated_feeds"
    os.makedirs(TEST_OUTPUT_DIR, exist_ok=True)
    logger.info(f"Test outputs will be saved in '{TEST_OUTPUT_DIR}' directory.")

    logger.info("--- Feeds Module Test ---")
    if not OPENAI_API_KEY or not client:
        logger.warning("OpenAI API key not configured or client not initialized. Cannot run feed generation tests.")
    else:
        logger.info("\n--- Testing Daily News Feed ---")
        news_options = {"country": "US"}
        news_feed = generate_feed_content("daily_news", options=news_options)
        if news_feed:
            logger.info(f"Generated News Feed (first 100 chars):\n{news_feed[:100]}...")
            logger.info(f"Approx. word count: {len(news_feed.split())}")

            file_path = os.path.join(TEST_OUTPUT_DIR, f"daily_news_{news_options['country']}.json")
            data_to_save = {"feed_type": "daily_news", "options": news_options, "content": news_feed}
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data_to_save, f, indent=4, ensure_ascii=False)
                logger.info(f"Saved daily news feed to {file_path}")
            except IOError as e:
                logger.error(f"Failed to save daily news feed to {file_path}: {e}")
        else:
            logger.error("Failed to generate daily news feed.")

        logger.info("\n--- Testing Topic Facts Feed ---")
        topic_options = {"topic": "The Roman Empire"}
        topic_feed = generate_feed_content("topic_facts", options=topic_options)
        if topic_feed:
            logger.info(f"Generated Topic Feed (The Roman Empire, first 100 chars):\n{topic_feed[:100]}...")
            logger.info(f"Approx. word count: {len(topic_feed.split())}")

            topic_slug = topic_options["topic"].replace(" ", "_").replace("/", "_").replace("\\", "_")
            file_path = os.path.join(TEST_OUTPUT_DIR, f"topic_facts_{topic_slug}.json")
            data_to_save = {"feed_type": "topic_facts", "options": topic_options, "content": topic_feed}
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data_to_save, f, indent=4, ensure_ascii=False)
                logger.info(f"Saved topic facts feed to {file_path}")
            except IOError as e:
                logger.error(f"Failed to save topic facts feed to {file_path}: {e}")
        else:
            logger.error("Failed to generate topic facts feed.")

        logger.info("\n--- Testing Custom Prompt Feed ---")
        custom_prompt_text = "Tell me a very short, uplifting story suitable for starting the day."
        custom_options = {"prompt": custom_prompt_text}
        custom_feed = generate_feed_content("custom_prompt", options=custom_options)
        if custom_feed:
            logger.info(f"Generated Custom Feed (Uplifting Story, first 100 chars):\n{custom_feed[:100]}...")
            logger.info(f"Approx. word count: {len(custom_feed.split())}")

            # Using a generic name for the custom prompt output file for simplicity
            file_path = os.path.join(TEST_OUTPUT_DIR, "custom_prompt_uplifting_story.json")
            data_to_save = {"feed_type": "custom_prompt", "options": custom_options, "content": custom_feed}
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data_to_save, f, indent=4, ensure_ascii=False)
                logger.info(f"Saved custom prompt feed to {file_path}")
            except IOError as e:
                logger.error(f"Failed to save custom prompt feed to {file_path}: {e}")
        else:
            logger.error("Failed to generate custom prompt feed.")

        logger.info("\n--- Testing Invalid Feed Type ---")
        invalid_feed = generate_feed_content("unknown_feed_type")
        if not invalid_feed: # This means it correctly returned None
            logger.info("Correctly handled invalid feed type (returned None).")
        # No file to save for invalid feed type, as it's expected to be None

    logger.info("--- Feeds Module Test Complete ---")
