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
        lastFocused: null,

        // UI State
        loading: false,
        filter: '',
        refreshInterval: '0',
        refreshTimer: null,

        // Initialization
        async init() {
            // Restore the status filter from the URL so refresh/deep-links keep it
            const params = new URLSearchParams(window.location.search);
            const status = params.get('status');
            if (status) {
                this.filter = status;
            }
            await this.loadStats();
            await this.loadGames();
        },

        // Load statistics
        async loadStats() {
            try {
                const response = await fetch(window.ADMIN_API_URLS.stats);

                if (response.ok) {
                    const data = await response.json();
                    if (data.stats) {
                        this.stats = {
                            ...data.stats,
                            cancelled_games: data.stats.total_games - data.stats.completed_games - data.stats.active_games
                        };
                    }
                } else if (response.status === 401) {
                    window.location.href = window.ADMIN_API_URLS.login;
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

                const response = await fetch(url);

                if (response.ok) {
                    const data = await response.json();
                    this.games = data.games || [];
                } else if (response.status === 401) {
                    window.location.href = window.ADMIN_API_URLS.login;
                }
            } catch (error) {
                console.error('Failed to load games:', error);
                handleError('Failed to load games');
            } finally {
                this.loading = false;
            }
        },

        // Sync the status filter to the URL so it survives refresh/deep-links
        applyFilter() {
            const params = new URLSearchParams(window.location.search);
            if (this.filter) {
                params.set('status', this.filter);
            } else {
                params.delete('status');
            }
            const query = params.toString();
            window.history.replaceState({}, '', query ? '?' + query : window.location.pathname);
            this.loadGames();
        },

        // View game details
        async viewGame(game) {
            this.lastFocused = document.activeElement;
            this.selectedGame = game;
            this.gameRounds = [];

            try {
                const url = window.ADMIN_API_URLS.gameDetail.replace('PLACEHOLDER', game.id);
                const response = await fetch(url);

                if (response.ok) {
                    const data = await response.json();
                    this.selectedGame = data.game;
                    this.gameRounds = data.rounds || [];
                } else if (response.status === 401) {
                    window.location.href = window.ADMIN_API_URLS.login;
                }
            } catch (error) {
                console.error('Failed to load game details:', error);
                handleError('Failed to load game details');
            }

            // Move focus into the dialog once it is shown
            this.$nextTick(() => {
                const modal = this.$refs.gameModal;
                const closeBtn = modal && modal.querySelector('[aria-label="Close"]');
                if (closeBtn) {
                    closeBtn.focus();
                }
            });
        },

        // Close the modal and restore focus to the trigger
        closeModal() {
            if (!this.selectedGame) return;
            this.selectedGame = null;
            if (this.lastFocused && this.lastFocused.focus) {
                this.lastFocused.focus();
            }
        },

        // Trap Tab focus inside the modal
        trapFocus(event) {
            if (event.key !== 'Tab' || !this.selectedGame) return;

            const modal = this.$refs.gameModal;
            if (!modal) return;

            const focusable = modal.querySelectorAll(
                'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
            );
            if (focusable.length === 0) return;

            const first = focusable[0];
            const last = focusable[focusable.length - 1];

            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault();
                last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault();
                first.focus();
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