"""Test utility helper functions."""
import pytest
from app.utils.helpers import (
    generate_game_code,
    is_valid_choice,
    determine_winner,
    calculate_game_winner,
    get_choice_emoji,
    format_timestamp
)


class TestGameCodeGeneration:
    """Test game code generation."""

    def test_generate_game_code_default_length(self):
        """Test default game code length is 6."""
        code = generate_game_code()
        assert len(code) == 6

    def test_generate_game_code_custom_length(self):
        """Test custom game code length."""
        code = generate_game_code(8)
        assert len(code) == 8

    def test_generate_game_code_uppercase(self):
        """Test game code is uppercase."""
        code = generate_game_code()
        assert code.isupper()

    def test_generate_game_code_no_ambiguous_chars(self):
        """Test game code doesn't contain ambiguous characters."""
        for _ in range(100):
            code = generate_game_code()
            assert '0' not in code
            assert 'O' not in code
            assert 'I' not in code
            assert '1' not in code

    def test_generate_game_code_uniqueness(self):
        """Test multiple codes are different (probabilistic)."""
        codes = [generate_game_code() for _ in range(10)]
        assert len(set(codes)) == 10


class TestChoiceValidation:
    """Test choice validation."""

    def test_valid_choices(self):
        """Test valid choices are accepted."""
        assert is_valid_choice('rock') is True
        assert is_valid_choice('paper') is True
        assert is_valid_choice('scissors') is True

    def test_invalid_choices(self):
        """Test invalid choices are rejected."""
        assert is_valid_choice('stone') is False
        assert is_valid_choice('') is False
        assert is_valid_choice('ROCK') is False
        assert is_valid_choice('lizard') is False


class TestWinnerDetermination:
    """Test winner determination logic."""

    def test_rock_beats_scissors(self):
        """Test rock beats scissors."""
        assert determine_winner('rock', 'scissors') == 'host'
        assert determine_winner('scissors', 'rock') == 'guest'

    def test_scissors_beats_paper(self):
        """Test scissors beats paper."""
        assert determine_winner('scissors', 'paper') == 'host'
        assert determine_winner('paper', 'scissors') == 'guest'

    def test_paper_beats_rock(self):
        """Test paper beats rock."""
        assert determine_winner('paper', 'rock') == 'host'
        assert determine_winner('rock', 'paper') == 'guest'

    def test_ties(self):
        """Test tie scenarios."""
        assert determine_winner('rock', 'rock') == 'tie'
        assert determine_winner('paper', 'paper') == 'tie'
        assert determine_winner('scissors', 'scissors') == 'tie'


class TestGameWinnerCalculation:
    """Test overall game winner calculation."""

    def test_best_of_one_host_wins(self):
        """Test best of 1 with host winning."""
        rounds = [{'winner': 'host'}]
        assert calculate_game_winner(rounds, 1) == 'host'

    def test_best_of_one_guest_wins(self):
        """Test best of 1 with guest winning."""
        rounds = [{'winner': 'guest'}]
        assert calculate_game_winner(rounds, 1) == 'guest'

    def test_best_of_three_host_wins(self):
        """Test best of 3 with host winning 2-1."""
        rounds = [
            {'winner': 'host'},
            {'winner': 'guest'},
            {'winner': 'host'}
        ]
        assert calculate_game_winner(rounds, 3) == 'host'

    def test_best_of_three_guest_wins(self):
        """Test best of 3 with guest winning 2-0."""
        rounds = [
            {'winner': 'guest'},
            {'winner': 'guest'}
        ]
        assert calculate_game_winner(rounds, 3) == 'guest'

    def test_best_of_three_incomplete(self):
        """Test best of 3 incomplete (1-1)."""
        rounds = [
            {'winner': 'host'},
            {'winner': 'guest'}
        ]
        assert calculate_game_winner(rounds, 3) is None

    def test_best_of_five_host_wins(self):
        """Test best of 5 with host winning 3-2."""
        rounds = [
            {'winner': 'host'},
            {'winner': 'guest'},
            {'winner': 'host'},
            {'winner': 'guest'},
            {'winner': 'host'}
        ]
        assert calculate_game_winner(rounds, 5) == 'host'

    def test_ties_dont_count(self):
        """Test that ties don't count toward winning."""
        rounds = [
            {'winner': 'tie'},
            {'winner': 'host'},
            {'winner': 'tie'},
            {'winner': 'host'}
        ]
        assert calculate_game_winner(rounds, 3) == 'host'


class TestChoiceEmoji:
    """Test choice emoji mapping."""

    def test_valid_emojis(self):
        """Test correct emojis are returned."""
        assert get_choice_emoji('rock') == '✊'
        assert get_choice_emoji('paper') == '✋'
        assert get_choice_emoji('scissors') == '✌️'

    def test_invalid_choice_emoji(self):
        """Test invalid choice returns question mark."""
        assert get_choice_emoji('invalid') == '❓'
        assert get_choice_emoji('') == '❓'


class TestTimestampFormatting:
    """Test timestamp formatting."""

    def test_valid_timestamp(self):
        """Test valid ISO timestamp formatting."""
        result = format_timestamp('2026-02-13T10:00:00Z')
        assert '2026' in result
        assert '02' in result
        assert '13' in result

    def test_invalid_timestamp(self):
        """Test invalid timestamp returns original."""
        invalid = 'not-a-timestamp'
        assert format_timestamp(invalid) == invalid

    def test_none_timestamp(self):
        """Test None returns None unchanged."""
        assert format_timestamp(None) is None

    def test_non_string_timestamp(self):
        """Test non-string input returns unchanged."""
        assert format_timestamp(12345) == 12345
