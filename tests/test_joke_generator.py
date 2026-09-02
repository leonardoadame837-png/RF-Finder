"""Tests for the joke generator module."""

import pytest
from unittest.mock import patch, MagicMock
from app.utils.joke_generator import JokeGenerator, JokeType, Joke, format_joke


class TestJokeGenerator:
    """Test suite for JokeGenerator."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.generator = JokeGenerator(timeout=5)
    
    @patch('app.utils.joke_generator.requests.get')
    def test_get_random_joke_single_part(self, mock_get):
        """Test fetching a single-part joke from JokeAPI."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "type": "single",
            "joke": "Why don't scientists trust atoms? Because they make up everything!",
            "category": "General"
        }
        mock_get.return_value = mock_response
        
        joke = self.generator.get_random_joke(JokeType.GENERAL)
        
        assert joke is not None
        assert "atoms" in joke.content
        assert joke.joke_type == "General"
        assert joke.source == "JokeAPI"
    
    @patch('app.utils.joke_generator.requests.get')
    def test_get_random_joke_two_part(self, mock_get):
        """Test fetching a two-part joke from JokeAPI."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "type": "twopart",
            "setup": "Why did the programmer quit his job?",
            "delivery": "Because he didn't get arrays!",
            "category": "Programming"
        }
        mock_get.return_value = mock_response
        
        joke = self.generator.get_random_joke(JokeType.PROGRAMMING)
        
        assert joke is not None
        assert "quit" in joke.content
        assert "arrays" in joke.content
        assert joke.joke_type == "Programming"
    
    @patch('app.utils.joke_generator.requests.get')
    def test_get_random_joke_fallback_api(self, mock_get):
        """Test fallback to Official Joke API when primary fails."""
        # First call (primary API) fails
        mock_response_fail = MagicMock()
        mock_response_fail.raise_for_status.side_effect = Exception("Connection error")
        
        # Second call (fallback API) succeeds
        mock_response_success = MagicMock()
        mock_response_success.json.return_value = {
            "setup": "Why did the chicken cross the road?",
            "delivery": "To get to the other side!"
        }
        
        # Configure mock to return different responses
        mock_get.side_effect = [
            MagicMock(json=MagicMock(return_value={"error": True})),
            mock_response_success
        ]
        
        joke = self.generator.get_random_joke(JokeType.GENERAL)
        
        assert joke is not None
        assert "chicken" in joke.content
        assert joke.source == "Official-Joke-API"
    
    @patch('app.utils.joke_generator.requests.get')
    def test_get_multiple_jokes(self, mock_get):
        """Test fetching multiple jokes."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "type": "single",
            "joke": "Test joke",
            "category": "General"
        }
        mock_get.return_value = mock_response
        
        jokes = self.generator.get_multiple_jokes(count=3)
        
        assert len(jokes) == 3
        assert all(isinstance(j, Joke) for j in jokes)
    
    @patch('app.utils.joke_generator.requests.get')
    def test_get_joke_api_error(self, mock_get):
        """Test handling of JokeAPI errors."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "error": True,
            "message": "No jokes found"
        }
        mock_get.return_value = mock_response
        
        joke = self.generator.get_random_joke(JokeType.GENERAL)
        
        # Should fail and return None
        assert joke is None
    
    @patch('app.utils.joke_generator.requests.get')
    def test_get_joke_network_error(self, mock_get):
        """Test handling of network errors."""
        mock_get.side_effect = ConnectionError("Network unreachable")
        
        joke = self.generator.get_random_joke(JokeType.GENERAL)
        
        assert joke is None
    
    @patch('app.utils.joke_generator.requests.get')
    def test_get_joke_timeout(self, mock_get):
        """Test handling of request timeout."""
        import requests
        mock_get.side_effect = requests.Timeout("Request timed out")
        
        joke = self.generator.get_random_joke(JokeType.GENERAL)
        
        assert joke is None
    
    def test_format_joke(self):
        """Test joke formatting."""
        joke = Joke(
            content="Why did the chicken cross the road?\nTo get to the other side!",
            joke_type="General",
            source="TestAPI"
        )
        
        formatted = format_joke(joke)
        
        assert "[General - TestAPI]" in formatted
        assert "chicken" in formatted
        assert "road" in formatted
    
    @patch('app.utils.joke_generator.requests.get')
    def test_knock_knock_joke(self, mock_get):
        """Test fetching a knock-knock joke."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "type": "twopart",
            "setup": "Knock knock",
            "delivery": "Who's there? Boo. Boo who? Don't cry!",
            "category": "Knock-Knock"
        }
        mock_get.return_value = mock_response
        
        joke = self.generator.get_random_joke(JokeType.KNOCK_KNOCK)
        
        assert joke is not None
        assert "Knock" in joke.content
        assert joke.joke_type == "Knock-Knock"


class TestJokeDataclass:
    """Test suite for Joke dataclass."""
    
    def test_joke_creation(self):
        """Test creating a Joke object."""
        joke = Joke(
            content="A test joke",
            joke_type="Test",
            source="TestAPI"
        )
        
        assert joke.content == "A test joke"
        assert joke.joke_type == "Test"
        assert joke.source == "TestAPI"
    
    def test_joke_default_source(self):
        """Test Joke with default source."""
        joke = Joke(
            content="A test joke",
            joke_type="Test"
        )
        
        assert joke.source == "JokeAPI"
