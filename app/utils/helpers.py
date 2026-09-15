"""Utility helper functions."""
import random
import string
from datetime import datetime, timedelta


def generate_game_code(length: int = 6) -> str:
    """Generate a random game code."""
    chars = string.ascii_uppercase + string.digits
    # Exclude ambiguous characters: 0, O, I, 1
    chars = chars.replace('0', '').replace('O', '').replace('I', '').replace('1', '')
    return ''.join(random.choice(chars) for _ in range(length))


def is_valid_choice(choice: str) -> bool:
    """Validate rock, paper, scissors choice."""
    return choice in ['rock', 'paper', 'scissors']


def random_choice() -> str:
    """Pick a random rock/paper/scissors move (used for the computer opponent)."""
    return random.choice(['rock', 'paper', 'scissors'])


def determine_winner(host_choice: str, guest_choice: str) -> str:
    """Determine winner of a round."""
    if host_choice == guest_choice:
        return 'tie'

    winning_combos = {
        'rock': 'scissors',
        'scissors': 'paper',
        'paper': 'rock'
    }

    if winning_combos[host_choice] == guest_choice:
        return 'host'
    else:
        return 'guest'


def calculate_game_winner(rounds: list, best_of: int) -> str:
    """Calculate overall game winner from rounds."""
    wins_needed = (best_of // 2) + 1
    host_wins = sum(1 for r in rounds if r.get('winner') == 'host')
    guest_wins = sum(1 for r in rounds if r.get('winner') == 'guest')

    if host_wins >= wins_needed:
        return 'host'
    elif guest_wins >= wins_needed:
        return 'guest'
    else:
        return None  # Game not finished


def get_choice_emoji(choice: str) -> str:
    """Get emoji for choice."""
    emojis = {
        'rock': '✊',
        'paper': '✋',
        'scissors': '✌️'
    }
    return emojis.get(choice, '❓')


def format_timestamp(timestamp: str) -> str:
    """Format ISO timestamp to readable format."""
    if not isinstance(timestamp, str):
        return timestamp
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        return timestamp
