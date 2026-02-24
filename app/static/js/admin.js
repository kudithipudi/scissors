/**
 * Admin Dashboard JavaScript
 */

function adminDashboard() {
    return {
        // Data
        stats: {
            total_games: 0,
            active_games: 0,
            completed_games: 0,
            cancelled_games: 0,
            game_modes: { 1: 0, 3: 0, 5: 0 }
        },
        games: [],
        selectedGame: null,
        gameRounds: [],

        // UI State
        loading: false,
        filter: '',
        refreshInterval: '0',
        refreshTimer: null,

        // Initialization
        async init() {
            await this.loadStats();
            await this.loadGames();
        },

        // Load statistics
        async loadStats() {
            try {
                const response = await fetch(window.ADMIN_API_URLS.stats, {
                    headers: this.getAuthHeaders()
                });

                if (response.ok) {
                    const data = await response.json();
                    if (data.stats) {
                        this.stats = {
                            ...data.stats,
                            cancelled_games: data.stats.total_games - data.stats.completed_games - data.stats.active_games
                        };
                    }
                }
            } catch (error) {
                console.error('Failed to load stats:', error);
            }
        },

        // Load games
        async loadGames() {
            this.loading = true;

            try {
                let url = window.ADMIN_API_URLS.games;
                if (this.filter) {
                    url += '?status=' + encodeURIComponent(this.filter);
                }

                const response = await fetch(url, {
                    headers: this.getAuthHeaders()
                });

                if (response.ok) {
                    const data = await response.json();
                    this.games = data.games || [];
                } else if (response.status === 401) {
                    this.promptAuth();
                }
            } catch (error) {
                console.error('Failed to load games:', error);
                handleError('Failed to load games');
            } finally {
                this.loading = false;
            }
        },

        // View game details
        async viewGame(game) {
            this.selectedGame = game;
            this.gameRounds = [];

            try {
                const url = window.ADMIN_API_URLS.gameDetail.replace('PLACEHOLDER', game.id);
                const response = await fetch(url, {
                    headers: this.getAuthHeaders()
                });

                if (response.ok) {
                    const data = await response.json();
                    this.selectedGame = data.game;
                    this.gameRounds = data.rounds || [];
                }
            } catch (error) {
                console.error('Failed to load game details:', error);
                handleError('Failed to load game details');
            }
        },

        // Update refresh interval
        updateRefreshInterval() {
            // Clear existing timer
            if (this.refreshTimer) {
                clearInterval(this.refreshTimer);
                this.refreshTimer = null;
            }

            // Set new timer if interval > 0
            const interval = parseInt(this.refreshInterval);
            if (interval > 0) {
                this.refreshTimer = setInterval(() => {
                    this.loadStats();
                    this.loadGames();
                }, interval);
            }
        },

        // Get auth headers (basic auth)
        getAuthHeaders() {
            const password = localStorage.getItem('admin_password');
            if (password) {
                const credentials = btoa(':' + password);
                return {
                    'Authorization': 'Basic ' + credentials
                };
            }
            return {};
        },

        // Prompt for authentication
        promptAuth() {
            const password = prompt('Enter admin password:');
            if (password) {
                localStorage.setItem('admin_password', password);
                this.loadStats();
                this.loadGames();
            } else {
                window.location.href = window.ADMIN_API_URLS.home;
            }
        },

        // Helper: Get status color
        getStatusColor(status) {
            const colors = {
                'waiting': 'background: var(--color-warning); color: var(--color-bg);',
                'active': 'background: var(--color-success); color: white;',
                'completed': 'background: var(--color-info); color: white;',
                'cancelled': 'background: var(--color-danger); color: white;'
            };
            return colors[status] || '';
        },

        // Helper: Format date
        formatDate(dateString) {
            if (!dateString) return 'N/A';

            try {
                const date = new Date(dateString);
                return date.toLocaleString();
            } catch {
                return dateString;
            }
        },

        // Helper: Get choice emoji
        getChoiceEmoji(choice) {
            const emojis = {
                'rock': '✊',
                'paper': '✋',
                'scissors': '✌️'
            };
            return emojis[choice] || '❓';
        }
    }
}

// Auto-prompt for auth on page load
document.addEventListener('DOMContentLoaded', () => {
    if (!localStorage.getItem('admin_password')) {
        const password = prompt('Enter admin password:');
        if (password) {
            localStorage.setItem('admin_password', password);
        } else {
            window.location.href = window.ADMIN_API_URLS.home;
        }
    }
});
