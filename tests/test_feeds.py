# e:\Dev\WakeUpAI\tests\test_feeds.py
import unittest
from unittest.mock import patch, MagicMock, ANY
import logging

from src.wakeupai.feeds import (
    generate_feed_content,
    _ask_openai, 
    _generate_daily_news_feed,
    _generate_topic_facts_feed,
    _generate_custom_prompt_feed,
    MAX_FEED_WORDS
)
# Temporarily set client to a MagicMock for all tests in this module if it was None
# This helps if feeds.py is imported and OPENAI_API_KEY isn't set during test discovery.
from src.wakeupai import feeds
if feeds.client is None:
    feeds.client = MagicMock()

class TestFeedsModule(unittest.TestCase):
    """Tests for the feeds.py module."""

    def setUp(self):
        # Suppress most logging output during tests unless specifically testing for it.
        # You can set this to logging.ERROR or logging.CRITICAL to see less.
        logging.disable(logging.DEBUG) 
        self.original_feeds_client = feeds.client # Store original

    def tearDown(self):
        logging.disable(logging.NOTSET) # Re-enable logging
        feeds.client = self.original_feeds_client # Restore original

    @patch('src.wakeupai.feeds.client.chat.completions.create')
    def test_ask_openai_success(self, mock_create_completion):
        """Test _ask_openai successfully returns content."""
        expected_response = "This is a test response from OpenAI."
        mock_choice = MagicMock()
        mock_choice.message.content = expected_response
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        mock_create_completion.return_value = mock_completion

        prompt = "Test prompt"
        response = _ask_openai(prompt)

        self.assertEqual(response, expected_response)
        mock_create_completion.assert_called_once_with(
            model=unittest.mock.ANY, # or specific model e.g. "gpt-3.5-turbo"
            messages=[
                {"role": "system", "content": unittest.mock.ANY},
                {"role": "user", "content": prompt}
            ],
            temperature=unittest.mock.ANY,
            # max_tokens=unittest.mock.ANY # if you add max_tokens
        )
        # Check if system prompt contains MAX_FEED_WORDS
        system_prompt_content = mock_create_completion.call_args[1]['messages'][0]['content']
        self.assertIn(str(MAX_FEED_WORDS), system_prompt_content)

    @patch('src.wakeupai.feeds.client.chat.completions.create')
    def test_ask_openai_api_error(self, mock_create_completion):
        """Test _ask_openai returns None on API error."""
        mock_create_completion.side_effect = Exception("API Error")
        response = _ask_openai("Test prompt on error")
        self.assertIsNone(response)

    def test_ask_openai_client_not_initialized(self):
        """Test _ask_openai returns None if client is None."""
        original_client = feeds.client
        feeds.client = None
        response = _ask_openai("Test prompt with no client")
        self.assertIsNone(response)
        feeds.client = original_client # Restore

    @patch('src.wakeupai.feeds._ask_openai')
    def test_generate_daily_news_feed(self, mock_ask_openai):
        """Test _generate_daily_news_feed constructs prompt and calls _ask_openai."""
        expected_news = "Today's news: ..."
        mock_ask_openai.return_value = expected_news

        country = "Wonderland"
        news = _generate_daily_news_feed(country=country)
        self.assertEqual(news, expected_news)
        mock_ask_openai.assert_called_once() # Check it was called
        # Check that the prompt passed to _ask_openai contained the country
        actual_prompt = mock_ask_openai.call_args[0][0]
        self.assertIn(country, actual_prompt)
        self.assertIn("news", actual_prompt.lower())

    @patch('src.wakeupai.feeds._ask_openai')
    def test_generate_topic_facts_feed(self, mock_ask_openai):
        """Test _generate_topic_facts_feed for success and missing topic."""
        expected_facts = "Facts about Llamas: ..."
        mock_ask_openai.return_value = expected_facts

        topic = "Llamas"
        facts = _generate_topic_facts_feed(topic=topic)
        self.assertEqual(facts, expected_facts)
        mock_ask_openai.assert_called_once() # Check it was called
        actual_prompt = mock_ask_openai.call_args[0][0]
        self.assertIn(topic, actual_prompt)
        self.assertIn("facts", actual_prompt.lower())

        # Test with no topic
        mock_ask_openai.reset_mock()
        facts_no_topic = _generate_topic_facts_feed(topic="")
        self.assertIsNone(facts_no_topic)
        mock_ask_openai.assert_not_called() # Should not call if topic is empty

    @patch('src.wakeupai.feeds._ask_openai')
    def test_generate_custom_prompt_feed(self, mock_ask_openai):
        """Test _generate_custom_prompt_feed."""
        expected_response = "Custom response."
        mock_ask_openai.return_value = expected_response

        user_prompt = "Tell me a story."
        response = _generate_custom_prompt_feed(user_prompt=user_prompt)
        self.assertEqual(response, expected_response)
        mock_ask_openai.assert_called_once_with(user_prompt, temperature=ANY)

        # Test with no user prompt
        mock_ask_openai.reset_mock()
        response_no_prompt = _generate_custom_prompt_feed(user_prompt="")
        self.assertIsNone(response_no_prompt)
        mock_ask_openai.assert_not_called()

    @patch('src.wakeupai.feeds._generate_daily_news_feed')
    def test_generate_feed_content_daily_news(self, mock_news_generator):
        """Test generate_feed_content for daily_news type."""
        expected_content = "Mocked News"
        mock_news_generator.return_value = expected_content
        options = {"country": "Testland"}
        content = generate_feed_content("daily_news", options)
        self.assertEqual(content, expected_content)
        mock_news_generator.assert_called_once_with(country="Testland")

    @patch('src.wakeupai.feeds._generate_topic_facts_feed')
    def test_generate_feed_content_topic_facts(self, mock_topic_generator):
        """Test generate_feed_content for topic_facts type."""
        expected_content = "Mocked Facts"
        mock_topic_generator.return_value = expected_content
        options = {"topic": "Pytest"}
        content = generate_feed_content("topic_facts", options)
        self.assertEqual(content, expected_content)
        mock_topic_generator.assert_called_once_with(topic="Pytest")

        # Test missing topic
        mock_topic_generator.reset_mock()
        content_no_topic = generate_feed_content("topic_facts", options={})
        self.assertIsNone(content_no_topic)
        mock_topic_generator.assert_not_called()

    @patch('src.wakeupai.feeds._generate_custom_prompt_feed')
    def test_generate_feed_content_custom_prompt(self, mock_custom_generator):
        """Test generate_feed_content for custom_prompt type."""
        expected_content = "Mocked Custom Response"
        mock_custom_generator.return_value = expected_content
        options = {"prompt": "Hello AI"}
        content = generate_feed_content("custom_prompt", options)
        self.assertEqual(content, expected_content)
        mock_custom_generator.assert_called_once_with(user_prompt="Hello AI")

        # Test missing prompt
        mock_custom_generator.reset_mock()
        content_no_prompt = generate_feed_content("custom_prompt", options={})
        self.assertIsNone(content_no_prompt)
        mock_custom_generator.assert_not_called()

    def test_generate_feed_content_invalid_type(self):
        """Test generate_feed_content with an invalid feed type."""
        content = generate_feed_content("non_existent_feed_type", {})
        self.assertIsNone(content)
    
    @patch('src.wakeupai.feeds._ask_openai')
    def test_generate_feed_content_length_warning(self, mock_ask_openai):
        """Test that a warning is logged for excessively long content."""
        # MAX_FEED_WORDS is 400. Warning threshold is MAX_FEED_WORDS * 7 = 2800 chars
        long_content = "a" * 3000 
        mock_ask_openai.return_value = long_content
        
        # We need to capture log messages for this test
        with self.assertLogs(logger='src.wakeupai.feeds', level='WARNING') as cm:
            content = generate_feed_content("daily_news", {"country": "longtextland"})
            self.assertEqual(content, long_content)
        
        self.assertIn("Generated content for 'daily_news' is quite long", cm.output[0])
        self.assertIn("(3000 chars)", cm.output[0])

if __name__ == '__main__':
    unittest.main()
