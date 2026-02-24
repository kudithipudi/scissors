# Rock Paper Scissors - Real-time Multiplayer Game

A real-time multiplayer Rock Paper Scissors web application with phone shake detection using gyroscope. Players can host games, share QR codes, and compete in best-of-1, best-of-3, or best-of-5 matches.

## Features

- 🎮 **Real-time Multiplayer**: Instant game synchronization between players
- 📱 **Shake Detection**: Use your phone's accelerometer to make choices by shaking (with user-gesture-triggered permission flow)
- 🔗 **QR Code Joining**: Easy game joining via QR code scanning
- 🏆 **Multiple Game Modes**: Best of 1, 3, or 5 rounds
- 📊 **Admin Dashboard**: Monitor active games, statistics, and game history
- 🎨 **Responsive Design**: Mobile-first design that works on all devices
- ⚡ **High Performance**: Built with Flask, Supabase, and Alpine.js for optimal speed

## Technology Stack

- **Backend**: Flask 3.0+
- **Database**: Supabase (PostgreSQL + Real-time)
- **Frontend**: Alpine.js, Vanilla JavaScript
- **Real-time**: Supabase Realtime subscriptions
- **Server**: Gunicorn with gevent workers
- **QR Codes**: qrcode + Pillow
- **Styling**: Custom CSS with CSS variables

## Architecture

```
/var/www/scissors/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── config.py            # Configuration management
│   ├── models.py            # Database models/queries
│   ├── routes/
│   │   ├── game.py          # Game endpoints
│   │   ├── admin.py         # Admin endpoints
│   │   └── api.py           # API endpoints
│   ├── services/
│   │   ├── game_service.py  # Game logic
│   │   ├── qr_service.py    # QR code generation
│   │   └── supabase_service.py  # Supabase client
│   ├── static/
│   │   ├── css/styles.css
│   │   └── js/
│   │       ├── shake.js     # Gyroscope detection
│   │       ├── admin.js     # Admin dashboard
│   └── templates/
│       ├── base.html
│       ├── index.html       # Landing page
│       ├── game.html        # Game view
│       └── admin.html       # Admin dashboard
├── migrations/              # Database migrations
├── logs/                    # Application logs
├── requirements.txt
├── gunicorn_config.py
├── run.py
└── README.md
```

## Prerequisites

- Python 3.8+
- Supabase account and project
- pip and virtualenv

## Installation

### 1. Clone or navigate to the project directory

```bash
cd /var/www/scissors
```

### 2. Create and activate virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up Supabase

1. Create a Supabase project at https://supabase.com
2. Run the database migration SQL from `migrations/001_initial_schema.sql`
3. Get your Supabase URL and anon key

### 5. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and add your configuration:

```env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
SECRET_KEY=your_random_secret_key
ADMIN_PASSWORD=your_admin_password
FLASK_ENV=production
```

### 6. Create logs directory

```bash
mkdir -p logs
```

### 7. Run the application

**Development mode:**

```bash
python run.py
```

**Production mode with Gunicorn:**

```bash
gunicorn -c gunicorn_config.py run:app
```

## Database Schema

All tables use the `vs_` prefix for namespace isolation in shared Supabase projects.

### Games Table (vs_games)

```sql
CREATE TABLE vs_games (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    game_code VARCHAR(8) UNIQUE NOT NULL,
    status VARCHAR(20) NOT NULL,
    best_of INTEGER NOT NULL,
    host_session_id VARCHAR(255) NOT NULL,
    guest_session_id VARCHAR(255),
    winner VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);
```

### Rounds Table (vs_rounds)

```sql
CREATE TABLE vs_rounds (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    game_id UUID REFERENCES vs_games(id) ON DELETE CASCADE,
    round_number INTEGER NOT NULL,
    host_choice VARCHAR(10),
    guest_choice VARCHAR(10),
    host_shakes INTEGER DEFAULT 0,
    guest_shakes INTEGER DEFAULT 0,
    winner VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

## API Endpoints

### Public Routes

- `GET /` - Landing page
- `POST /game/create` - Create new game
- `GET /game/<game_code>` - View game page
- `POST /game/<game_code>/cancel` - Cancel game

### API Routes

- `GET /api/stats` - Public statistics
- `GET /api/game/<game_code>/state` - Get game state
- `POST /api/game/<game_code>/shake` - Record shake count
- `POST /api/game/<game_code>/choice` - Submit player choice
- `POST /api/game/<game_code>/play-again` - Start new game

### Admin Routes (Protected)

- `GET /admin` - Admin dashboard
- `GET /admin/games` - List games (with filters)
- `GET /admin/game/<game_id>` - Game details
- `GET /admin/stats` - Statistics

## Game Flow

1. **Host creates a game**
   - Selects game mode (best of 1, 3, or 5)
   - Receives unique game code and QR code
   - Waits for guest to join

2. **Guest joins via QR code or game code**
   - Scans QR code or enters game code
   - Automatically joins the game
   - Game status changes to "active"

3. **Gameplay**
   - Tap "Enable & Start" to grant motion sensor access (first round only)
   - 3-2-1 countdown
   - Both players shake their phones 3 times (or use manual buttons as fallback)
   - Choices are randomly generated after 3 shakes
   - Simultaneous reveal
   - Round winner announced, scores updated from server state
   - Continue to next round or show final results

4. **Game completion**
   - Final winner announced
   - Statistics displayed
   - Option to play again (host only)

## Device Detection & Motion Sensors

The app automatically detects device capabilities and adapts the user interface accordingly.

### Device Detection

The app detects mobile devices using:
- **User Agent Detection**: Checks for mobile device strings (iPhone, iPad, Android, etc.)
- **Touch Points Detection**: Validates `navigator.maxTouchPoints > 1` for tablets/phones

### Motion Sensor Support

For shake detection to work, all of these requirements must be met:
1. **Mobile Device**: Smartphone or tablet
2. **DeviceMotionEvent Support**: Browser supports motion sensors
3. **HTTPS**: Secure connection (required by modern browsers)
4. **Permission**: User permission granted (iOS 13+ only)

### Platform-Specific Behavior

#### iOS (13+)
- **Permission Required**: iOS requires explicit user permission for motion sensor access
- **User Gesture**: Permission must be requested from a user interaction (button tap)
- **Permission Flow**:
  1. App detects mobile device at the start of each game
  2. Shows "Tap to Enable & Start" button before the first round
  3. User taps button (satisfying user-gesture requirement)
  4. Browser shows system permission dialog (iOS) or auto-grants (Android)
  5. If granted, shake detection is enabled for all subsequent rounds
  6. If denied or unavailable, manual choice buttons are shown as fallback

#### Android
- **User Gesture Flow**: Android also goes through the "Tap to Enable & Start" step to ensure consistent behavior
- **Auto-Grant**: Permission is typically auto-granted after the user tap
- **Immediate Access**: Shake detection works immediately after the enable step

### Manual Choice Fallback

If shake detection is unavailable (desktop, permission denied, or unsupported device), the app automatically shows manual choice buttons:
- **Rock** ✊
- **Paper** ✋
- **Scissors** ✌️

This ensures the game is playable on all devices and serves as an accessibility feature.

### Shake Detection Algorithm

When motion sensors are available:
- **Threshold**: 15 m/s² acceleration
- **Required Shakes**: 3 distinct shakes
- **Timeout**: 1 second between shakes
- **Automatic Choice**: Random selection after 3rd shake
- **Haptic Feedback**: Vibration on each detected shake (if supported)

### Testing Device Capabilities

Visit `/device-simple-test` to check your device's capabilities:
- Device type detection (mobile/desktop)
- Motion sensor availability
- HTTPS status
- Permission status (iOS)
- DeviceCapabilities API functionality

This test page works on all devices and provides detailed diagnostics.

## Admin Dashboard

Access the admin dashboard at `/admin` using the password configured in `.env`.

Features:
- Real-time statistics
- Active and historical games
- Game details with round-by-round breakdown
- Filter by game status
- Auto-refresh options

## Configuration

Key configuration options in `app/config.py`:

- `GAME_TIMEOUT_MINUTES`: Time before waiting games expire (default: 2)
- `MAX_GAMES_PER_IP_PER_HOUR`: Rate limiting (default: 10)
- `SHAKE_THRESHOLD`: Acceleration threshold for shake detection (default: 15)
- `REQUIRED_SHAKES`: Number of shakes needed (default: 3)

## Deployment

### Systemd Service

Create `/etc/systemd/system/scissors.service`:

```ini
[Unit]
Description=Rock Paper Scissors Gunicorn Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/scissors
Environment="PATH=/var/www/scissors/venv/bin"
ExecStart=/var/www/scissors/venv/bin/gunicorn -c gunicorn_config.py run:app

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable scissors
sudo systemctl start scissors
```

### Nginx Configuration

```nginx
upstream scissors_app {
    server unix:/var/www/scissors/scissors.sock fail_timeout=0;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://scissors_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /var/www/scissors/app/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

## Background Jobs

The app includes a background scheduler that:
- Cleans up expired games every minute
- Sets waiting games past their `expires_at` to cancelled status

## Troubleshooting

### Shake Detection Issues

**iOS Permission Denied:**
- iOS requires explicit permission for motion sensors
- If denied, the app shows manual choice buttons (rock/paper/scissors)
- To re-enable: Safari > Settings > Motion & Orientation Access
- Clear site data and revisit to trigger new permission prompt

**Motion Sensors Not Detected:**
- Visit `/device-simple-test` to diagnose the issue
- Ensure you're accessing via HTTPS (HTTP blocks motion sensors)
- Check browser console for specific error messages
- Verify you're on a mobile device (desktop browsers don't have motion sensors)

**DeviceCapabilities Not Loaded:**
- Check browser console for JavaScript errors
- Try hard refresh (Ctrl+Shift+R or Cmd+Shift+R)
- Clear browser cache and reload
- Verify `shake.js` loads successfully in Network tab

**Android Motion Sensors:**
- Android should work automatically without permission prompts
- If not working, ensure HTTPS and check browser console
- Try Chrome or Firefox (better motion API support)

### Database Connection Errors

**Supabase Connection Failed:**
- Verify `SUPABASE_URL` and `SUPABASE_KEY` in `.env`
- Check Supabase project is active (not paused)
- Ensure database tables are created with `vs_` prefix
- Test connection: visit `/api/stats` (should return JSON)

**Table Not Found Errors:**
- Run migration: `migrations/001_initial_schema.sql` in Supabase SQL editor
- Verify tables exist: `vs_games` and `vs_rounds`
- Check table permissions in Supabase dashboard

### Deployment Issues

**Gunicorn Socket Permission Errors:**
- Check file ownership: `chown www-data:www-data /var/www/scissors/scissors.sock`
- Verify nginx user has access to socket
- Check Gunicorn logs: `tail -f logs/error.log`

**Subpath Hosting (e.g., /scissors):**
- Ensure nginx sets `X-Forwarded-Prefix` header
- Verify ProxyFix middleware is enabled in `app/__init__.py`
- All internal links use `url_for()` (not hardcoded paths)
- Static files should be served from correct subpath

## Performance Optimization

- **Caching**: Game state cached for 120 seconds
- **Connection Pooling**: Supabase client reuses connections
- **Static Assets**: Aggressive caching with 30-day expiry
- **Gevent Workers**: Async support for concurrent connections
- **Indexed Queries**: Database indexes on frequently queried fields

## Security

- Session-based authentication with secure cookies
- CSRF protection (Flask default)
- Admin routes protected with password
- Input validation on all endpoints
- Rate limiting on game creation
- SQL injection prevention (parameterized queries)
- Race condition guards on concurrent round submissions (prevents duplicate rounds)

## Browser Compatibility

### Desktop Browsers
- Chrome 80+
- Safari 13+
- Firefox 75+
- Edge 80+

**Note**: Desktop browsers don't have motion sensors. Manual choice buttons will be shown.

### Mobile Browsers
- **iOS Safari 13+**: Motion sensors available (permission required)
- **iOS Chrome 13+**: Motion sensors available (permission required)
- **Android Chrome 80+**: Motion sensors available (auto-granted)
- **Android Firefox 75+**: Motion sensors available (auto-granted)

### Testing Your Device
Visit `/device-simple-test` to check:
- Device type (mobile/desktop)
- Motion sensor support
- HTTPS status
- Permission requirements
- DeviceCapabilities API status

## Changelog

### v2.2 - Bug Fixes (2026-02-24)

- **Fixed: Motion sensor permission not prompting on mobile** - `DeviceMotionEvent.requestPermission()` was being called from a timer callback instead of a user gesture, causing it to silently fail on iOS and modern Android browsers. Added a "Tap to Enable & Start" button that triggers permission from a proper user gesture.
- **Fixed: Scores not updating correctly** - Scores were tracked with local increments (`yourWins++`) that could drift out of sync. Now calculated from server-provided round data on every round result.
- **Fixed: Games exceeding round limit** - A race condition in `submit_choice()` allowed concurrent requests from both players to each complete the same round and create duplicate next rounds. Added guards to check for already-completed rounds, already-completed games, and already-existing pending rounds before creating new ones.

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues and questions:
- Check the troubleshooting section
- Review browser console for errors
- Verify Supabase configuration
- Check application logs in `logs/`

## Author

Built for real-time multiplayer gaming with modern web technologies.
