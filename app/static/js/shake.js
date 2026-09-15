/**
 * Shake Detection using Device Motion API
 * Detects phone shakes using accelerometer data
 * Version: 2.1 - Fixed iOS permission handling
 */

console.log('shake.js v2.1 loading...');

/**
 * Device capability detection utilities
 */
window.DeviceCapabilities = {
    /**
     * Check if device is mobile
     */
    isMobile() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
               (navigator.maxTouchPoints && navigator.maxTouchPoints > 1);
    },

    /**
     * Check if device supports motion sensors
     */
    hasMotionSensors() {
        return 'DeviceMotionEvent' in window;
    },

    /**
     * Check if device supports orientation sensors
     */
    hasOrientationSensors() {
        return 'DeviceOrientationEvent' in window;
    },

    /**
     * Check if HTTPS (required for sensor access)
     */
    isSecureContext() {
        return window.isSecureContext || location.protocol === 'https:';
    },

    /**
     * Check if permission is required (iOS 13+)
     */
    needsPermission() {
        return typeof DeviceMotionEvent !== 'undefined' &&
               typeof DeviceMotionEvent.requestPermission === 'function';
    },

    /**
     * Request motion sensor permission (must be called from user gesture)
     */
    async requestPermission() {
        if (this.needsPermission()) {
            try {
                const permission = await DeviceMotionEvent.requestPermission();
                return permission === 'granted';
            } catch (error) {
                console.error('Permission request failed:', error);
                return false;
            }
        }
        // Non-iOS devices don't need permission
        return true;
    },

    /**
     * Comprehensive capability check (does NOT request permission)
     */
    async checkCapabilities() {
        const result = {
            isMobile: this.isMobile(),
            hasMotionSensors: this.hasMotionSensors(),
            hasOrientationSensors: this.hasOrientationSensors(),
            isSecureContext: this.isSecureContext(),
            needsPermission: this.needsPermission(),
            permissionGranted: false,
            errors: []
        };

        // Check if mobile
        if (!result.isMobile) {
            result.errors.push('This game requires a mobile device with motion sensors');
        }

        // Check if motion sensors available
        if (!result.hasMotionSensors) {
            result.errors.push('Your device does not support motion sensors');
        }

        // Check if HTTPS
        if (!result.isSecureContext) {
            result.errors.push('Motion sensors require HTTPS connection');
        }

        // On iOS, permission must be requested via user gesture
        // We don't request it here, just note if it's needed
        if (result.needsPermission) {
            result.permissionGranted = false;
            result.errors.push('Tap "Request Permission" button to enable shake detection');
        } else {
            // Non-iOS devices don't need permission
            result.permissionGranted = true;
        }

        result.ready = result.isMobile &&
                       result.hasMotionSensors &&
                       result.isSecureContext &&
                       result.permissionGranted;

        return result;
    }
};

console.log('✓ DeviceCapabilities loaded successfully');
console.log('  - isMobile:', window.DeviceCapabilities.isMobile());
console.log('  - hasMotionSensors:', window.DeviceCapabilities.hasMotionSensors());
console.log('  - isSecureContext:', window.DeviceCapabilities.isSecureContext());

class ShakeDetector {
    /**
     * @param {function(number)} onShakeCallback  called with the running shake count
     * @param {function(string[])} onErrorCallback called with a list of reasons
     * @param {{threshold?: number, timeoutMs?: number, requiredShakes?: number}} [options]
     *        Server-provided tuning (see SHAKE_THRESHOLD / SHAKE_TIMEOUT_MS /
     *        REQUIRED_SHAKES in .env). Omitted or partial options fall back to
     *        the historical hardcoded defaults, so callers that don't pass
     *        anything (e.g. the /device-test page) behave exactly as before.
     */
    constructor(onShakeCallback, onErrorCallback, options) {
        this.onShake = onShakeCallback;
        this.onError = onErrorCallback;
        this.shakeCount = 0;
        this.lastShakeTime = 0;
        this.isListening = false;

        // Configuration (defaults are the original hardcoded values)
        const opts = options || {};
        const num = (value, fallback) =>
            (typeof value === 'number' && isFinite(value) && value > 0) ? value : fallback;

        this.SHAKE_THRESHOLD = num(opts.threshold, 15);      // m/s² - acceleration threshold
        this.SHAKE_TIMEOUT = num(opts.timeoutMs, 1000);      // min ms between counted shakes
        this.REQUIRED_SHAKES = num(opts.requiredShakes, 3);

        // Bind the handler
        this.handleMotion = this.handleMotion.bind(this);
    }

    async start() {
        // Request permission if needed (iOS) - must be from user gesture
        if (DeviceCapabilities.needsPermission()) {
            const granted = await DeviceCapabilities.requestPermission();
            if (!granted) {
                const error = ['Motion sensor permission was denied. Please allow sensor access to use shake detection.'];
                console.error('Permission denied');
                if (this.onError) {
                    this.onError(error);
                }
                return false;
            }
        }

        // Check other capabilities
        const isMobile = DeviceCapabilities.isMobile();
        const hasMotion = DeviceCapabilities.hasMotionSensors();
        const isSecure = DeviceCapabilities.isSecureContext();

        if (!isMobile || !hasMotion || !isSecure) {
            const errors = [];
            if (!isMobile) errors.push('Mobile device required');
            if (!hasMotion) errors.push('Motion sensors not available');
            if (!isSecure) errors.push('HTTPS required');

            console.error('Device not ready:', errors);
            if (this.onError) {
                this.onError(errors);
            }
            return false;
        }

        // Reset state
        this.shakeCount = 0;
        this.lastShakeTime = 0;
        this.isListening = true;

        // Add event listener
        window.addEventListener('devicemotion', this.handleMotion);

        console.log('Shake detection started successfully');
        return true;
    }

    stop() {
        this.isListening = false;
        window.removeEventListener('devicemotion', this.handleMotion);
        console.log('Shake detection stopped');
    }

    handleMotion(event) {
        if (!this.isListening) return;

        const acceleration = event.accelerationIncludingGravity;

        if (!acceleration) {
            console.warn('No acceleration data available');
            return;
        }

        // Calculate total acceleration (magnitude)
        const x = acceleration.x || 0;
        const y = acceleration.y || 0;
        const z = acceleration.z || 0;

        const magnitude = Math.sqrt(x * x + y * y + z * z);

        // Detect shake
        const now = Date.now();

        if (magnitude > this.SHAKE_THRESHOLD) {
            // Check if enough time has passed since last shake
            if (now - this.lastShakeTime > this.SHAKE_TIMEOUT) {
                this.shakeCount++;
                this.lastShakeTime = now;

                console.log(`Shake detected! Count: ${this.shakeCount}/${this.REQUIRED_SHAKES}`);

                // Haptic feedback if available
                if (navigator.vibrate) {
                    navigator.vibrate(50);
                }

                // Call callback
                if (this.onShake) {
                    this.onShake(this.shakeCount);
                }

                // Stop if reached required shakes
                if (this.shakeCount >= this.REQUIRED_SHAKES) {
                    this.stop();
                }
            }
        }
    }

    reset() {
        this.shakeCount = 0;
        this.lastShakeTime = 0;
    }
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ShakeDetector;
}
