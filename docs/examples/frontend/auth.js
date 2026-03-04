/**
 * Frontend Integration Example for Vibe Authentication Service
 * 
 * This example shows how to integrate the authentication service
 * into a Telegram Mini-App frontend.
 */

// Configuration
const API_BASE_URL = 'https://your-api-gateway-url.execute-api.il-central-1.amazonaws.com/dev';

/**
 * Authentication Service Class
 */
class VibeAuthService {
    constructor() {
        this.token = localStorage.getItem('vibe_auth_token');
        this.userId = localStorage.getItem('user_id');
        this.isAuthenticated = !!this.token;
    }

    /**
     * Initialize Telegram WebApp and authenticate user
     */
    async initialize() {
        try {
            // Check if Telegram WebApp is available
            if (!window.Telegram || !window.Telegram.WebApp) {
                throw new Error('Telegram WebApp is not available');
            }

            const tg = window.Telegram.WebApp;
            
            // Initialize Telegram WebApp
            tg.ready();
            tg.expand();

            // Get Telegram authentication data
            const initData = tg.initData;
            const initDataUnsafe = tg.initDataUnsafe;

            if (!initData || !initDataUnsafe.user) {
                throw new Error('Telegram authentication data not available');
            }

            // Authenticate with backend
            const authResult = await this.authenticateWithTelegram(initData, initDataUnsafe.user);
            
            return authResult;

        } catch (error) {
            console.error('Authentication initialization failed:', error);
            throw error;
        }
    }

    /**
     * Authenticate with Telegram data
     */
    async authenticateWithTelegram(initData, telegramUser) {
        try {
            const response = await fetch(`${API_BASE_URL}/auth/telegram`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    platform: 'telegram',
                    platformToken: initData,
                    platformMetadata: telegramUser
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Authentication failed');
            }

            const authData = await response.json();
            
            // Store authentication data
            this.token = authData.token;
            this.userId = authData.userId;
            this.isAuthenticated = true;
            
            localStorage.setItem('vibe_auth_token', this.token);
            localStorage.setItem('user_id', this.userId);

            return authData;

        } catch (error) {
            console.error('Telegram authentication failed:', error);
            throw error;
        }
    }

    /**
     * Make authenticated API request
     */
    async apiRequest(endpoint, options = {}) {
        if (!this.isAuthenticated) {
            throw new Error('User not authenticated');
        }

        const config = {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.token}`,
                ...options.headers,
            },
        };

        const response = await fetch(`${API_BASE_URL}${endpoint}`, config);

        // Handle token expiration
        if (response.status === 401) {
            this.logout();
            throw new Error('Authentication expired. Please re-authenticate.');
        }

        return response;
    }

    /**
     * Logout user
     */
    logout() {
        this.token = null;
        this.userId = null;
        this.isAuthenticated = false;
        
        localStorage.removeItem('vibe_auth_token');
        localStorage.removeItem('user_id');
    }

    /**
     * Check if user is authenticated
     */
    getAuthStatus() {
        return {
            isAuthenticated: this.isAuthenticated,
            userId: this.userId,
            hasToken: !!this.token
        };
    }
}

/**
 * API Client for Vibe Dating App
 * 
 * Note: These endpoints are examples and may not be implemented yet.
 * The actual endpoints will depend on the user, media, and other services.
 */
class VibeApiClient {
    constructor(authService) {
        this.auth = authService;
    }

    /**
     * Get current user information
     */
    async getCurrentUser() {
        const response = await this.auth.apiRequest('/users/me');
        return response.json();
    }

    /**
     * Get a specific profile by ID
     */
    async getProfile(profileId) {
        const response = await this.auth.apiRequest(`/profile/${profileId}`);
        return response.json();
    }

    /**
     * Create or update a profile
     */
    async upsertProfile(profileId, profileData) {
        const response = await this.auth.apiRequest(`/profile/${profileId}`, {
            method: 'PUT',
            body: JSON.stringify(profileData)
        });
        return response.json();
    }

    /**
     * Delete profile
     */
    async deleteProfile(profileId) {
        const response = await this.auth.apiRequest(`/profile/${profileId}`, {
            method: 'DELETE'
        });
        return response.json();
    }

    /**
     * Upload media to profile
     */
    async uploadProfileMedia(profileId, mediaFile) {
        const formData = new FormData();
        formData.append('media', mediaFile);

        const response = await this.auth.apiRequest(`/profile/${profileId}/media`, {
            method: 'POST',
            headers: {
                // Remove Content-Type to let browser set it with boundary
            },
            body: formData
        });
        return response.json();
    }

    /**
     * Update profile location
     */
    async updateLocation(profileId, location) {
        const response = await this.auth.apiRequest(`/profile/${profileId}/location`, {
            method: 'PUT',
            body: JSON.stringify(location)
        });
        return response.json();
    }

    /**
     * Discover nearby profiles
     */
    async discoverProfiles(location, radius = 10) {
        const params = new URLSearchParams({
            latitude: location.latitude,
            longitude: location.longitude,
            radius: radius
        });

        const response = await this.auth.apiRequest(`/discover?${params}`);
        return response.json();
    }
}

/**
 * Usage Example
 */
async function initializeVibeApp() {
    try {
        // Initialize authentication service
        const authService = new VibeAuthService();
        
        // Initialize Telegram authentication
        const authResult = await authService.initialize();
        console.log('Authentication successful:', authResult);

        // Create API client
        const apiClient = new VibeApiClient(authService);

        // Example: Get a specific profile
        const profileId = 'example_profile_id';
        const profile = await apiClient.getProfile(profileId);
        console.log('Profile:', profile);

        // Example: Create or update a profile
        const newProfile = await apiClient.upsertProfile(profileId, {
            name: 'My Dating Profile',
            age: 25,
            bio: 'Looking for meaningful connections',
            interests: ['music', 'travel', 'sports'],
            lookingFor: ['friendship', 'relationship']
        });
        console.log('Created/Updated profile:', newProfile);

        // Example: Update location
        const location = {
            latitude: 40.7128,
            longitude: -74.0060,
            precision: 5
        };
        await apiClient.updateLocation(profileId, location);

        // Example: Discover nearby profiles
        const nearbyProfiles = await apiClient.discoverProfiles(location, 5);
        console.log('Nearby profiles:', nearbyProfiles);

    } catch (error) {
        console.error('Failed to initialize Vibe app:', error);
        
        // Show error to user
        if (window.Telegram && window.Telegram.WebApp) {
            window.Telegram.WebApp.showAlert('Failed to initialize app: ' + error.message);
        }
    }
}

/**
 * React Hook Example (if using React)
 */
function useVibeAuth() {
    const [authService, setAuthService] = useState(null);
    const [apiClient, setApiClient] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        async function setupAuth() {
            try {
                setIsLoading(true);
                setError(null);

                const auth = new VibeAuthService();
                await auth.initialize();
                
                const api = new VibeApiClient(auth);
                
                setAuthService(auth);
                setApiClient(api);
                
            } catch (err) {
                setError(err.message);
            } finally {
                setIsLoading(false);
            }
        }

        setupAuth();
    }, []);

    return { authService, apiClient, isLoading, error };
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        VibeAuthService,
        VibeApiClient,
        initializeVibeApp,
        useVibeAuth
    };
} 