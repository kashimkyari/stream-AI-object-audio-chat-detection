import React, { useState, useEffect } from 'react';
import axios from 'axios';

// Directly import components (no lazy loading for speed)
import Login from './components/Login';
import AdminPanel from './components/AdminPanel';
import AgentDashboard from './components/AgentDashboard';
import NotificationsPage from './components/NotificationsPage';
import MessageComponent from './components/MessageComponent'; // Import the messaging component
import { ToastProvider, useToast } from './ToastContext';

function AppContent() {
  const [user, setUser] = useState(null); // Store full user object
  const [activeTab, setActiveTab] = useState('dashboard');
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState([]);
  const [dashboardData, setDashboardData] = useState({ streams: [] });
  const [isMobile, setIsMobile] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  
  // States for stream URL, online status, poster image, etc.
  const [m3u8Url, setM3u8Url] = useState(null);
  const [isOnline, setIsOnline] = useState(true);
  const [posterUrl, setPosterUrl] = useState(null);
  const [loading, setLoading] = useState(true);

  const { showToast } = useToast();

  // Check if device is mobile
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Check session on mount
  useEffect(() => {
    const checkSession = async () => {
      try {
        const res = await axios.get('/api/session');
        if (res.data.logged_in) {
          setUser(res.data.user);
          if (res.data.user.role === 'admin') {
            const dashboardRes = await axios.get('/api/dashboard');
            setDashboardData(dashboardRes.data);
          }
        }
      } catch (error) {
        console.log("No active session.");
      }
    };
    checkSession();
  }, []);

  const handleLogin = (loggedInUser) => {
    setUser(loggedInUser);
    if (loggedInUser.role === 'admin') {
      axios.get('/api/dashboard').then(res => setDashboardData(res.data));
    }
    showToast("Login successful", "success");
  };

  const handleLogout = async () => {
    try {
      await axios.post('/api/logout');
      setUser(null);
      setMenuOpen(false);
      showToast("Logged out successfully", "info");
    } catch (err) {
      console.error("Logout error", err);
      showToast("Logout failed", "error");
    }
  };

  const handleNotificationClick = () => {
    setActiveTab('notifications');
    setUnreadCount(0);
    if (isMobile) setMenuOpen(false);
  };

  const handleTabClick = (tab) => {
    setActiveTab(tab);
    if (isMobile) setMenuOpen(false);
  };

  const toggleMenu = () => {
    setMenuOpen(!menuOpen);
  };

  // Example function to handle successful agent creation
  const handleAgentCreated = (newAgent) => {
    showToast("Agent created successfully", "success");
  };

  // -------------
  // Fetch m3u8 URL using provided snippet.
  // For an agent, assume the assigned stream URL is stored in user.assignedStreamUrl.
  // For admin, you may select a stream from dashboardData; here we assume a staticThumbnail is irrelevant.
  // Adjust the source of platform and streamerName as needed.
  const platform = user?.role === 'agent' ? user.assignedStreamPlatform || '' : 'chaturbate';
  const streamerName = user?.role === 'agent' ? user.assignedStreamStreamerName || '' : dashboardData.streams[0]?.streamer_username || '';

  useEffect(() => {
    // Only run if we have a valid platform and streamerName.
    if (!platform || !streamerName) {
      setLoading(false);
      return;
    }

    if (platform.toLowerCase() === 'chaturbate') {
      const fetchM3u8Url = async () => {
        try {
          const response = await fetch(`/api/streams?platform=chaturbate&streamer=${streamerName}`);
          if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
          }
          const data = await response.json();
          if (data.length > 0 && data[0].chaturbate_m3u8_url) {
            setM3u8Url(data[0].chaturbate_m3u8_url);
          } else {
            throw new Error("No m3u8 URL found for the stream");
          }
        } catch (error) {
          console.error("Error fetching m3u8 URL for Chaturbate:", error);
          setIsOnline(false);
          const fallbackPosterUrl = `https://jpeg.live.mmcdn.com/stream?room=${streamerName}&f=${Math.random()}`;
          setPosterUrl(fallbackPosterUrl);
        } finally {
          setLoading(false);
        }
      };
      fetchM3u8Url();
    } else if (platform.toLowerCase() === 'stripchat') {
      const fetchM3u8Url = async () => {
        try {
          const response = await fetch(`/api/streams?platform=stripchat&streamer=${streamerName}`);
          if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
          }
          const data = await response.json();
          if (data.length > 0 && data[0].stripchat_m3u8_url) {
            setM3u8Url(data[0].stripchat_m3u8_url);
          } else {
            throw new Error("No m3u8 URL found for the stream");
          }
        } catch (error) {
          console.error("Error fetching m3u8 URL for Stripchat:", error);
          setIsOnline(false);
        } finally {
          setLoading(false);
        }
      };
      fetchM3u8Url();
    } else {
      setLoading(false);
    }
  }, [platform, streamerName]);

  // -------------
  // Use Page Visibility API to trigger/stop detection
  useEffect(() => {
    const triggerDetection = () => {
      if (m3u8Url) {
        axios.post('/api/trigger-detection', {
          stream_url: m3u8Url,
          timestamp: new Date().toISOString(),
          platform: platform,
          streamer_name: streamerName
        })
        .then(res => console.log("Detection started:", res.data))
        .catch(err => console.error("Error triggering detection:", err));
      }
    };

    const stopDetection = () => {
      if (m3u8Url) {
        axios.post('/api/stop-detection', { stream_url: m3u8Url })
          .then(res => console.log("Detection stopped:", res.data))
          .catch(err => console.error("Error stopping detection:", err));
      }
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        stopDetection();
      } else if (document.visibilityState === 'visible') {
        triggerDetection();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    if (m3u8Url && document.visibilityState === 'visible') {
      triggerDetection();
    }

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      if (m3u8Url) {
        stopDetection();
      }
    };
  }, [m3u8Url, platform, streamerName]);

  return (
    <div className="app-container">
      {user && (
        <header className="app-header">
          <div className="nav-container">
            {isMobile && user.role === 'admin' && (
              <button className="menu-toggle" onClick={toggleMenu}>
                {menuOpen ? '✕' : '☰'}
                {unreadCount > 0 && !menuOpen && (
                  <span className="mobile-notification-badge">{unreadCount}</span>
                )}
              </button>
            )}
            {user && (!isMobile || (isMobile && menuOpen)) && (
              <nav className={`admin-nav ${isMobile ? 'mobile-nav' : ''}`}>
                <button onClick={() => handleTabClick('dashboard')} className={activeTab === 'dashboard' ? 'active' : ''}>
                  Dashboard
                </button>
                {user.role === 'admin' && (
                  <>
                    <button onClick={() => handleTabClick('streams')} className={activeTab === 'streams' ? 'active' : ''}>
                      Management
                    </button>
                    <button onClick={() => handleTabClick('flag')} className={activeTab === 'flag' ? 'active' : ''}>
                      Settings
                    </button>
                  </>
                )}
                <button onClick={() => handleTabClick('messaging')} className={activeTab === 'messaging' ? 'active' : ''}>
                  Messaging
                </button>
                <button onClick={() => handleTabClick('notifications')} className={activeTab === 'notifications' ? 'active' : ''}>
                  Notifications {unreadCount > 0 && <span className="notification-badge">{unreadCount}</span>}
                </button>
                {isMobile && (
                  <button className="mobile-logout-button" onClick={handleLogout}>
                    Logout
                  </button>
                )}
              </nav>
            )}
            {(!isMobile || user.role !== 'admin') && (
              <button className="logout-button" onClick={handleLogout}>
                Logout
              </button>
            )}
          </div>
        </header>
      )}

      <div className="main-content">
        {!user && <Login onLogin={handleLogin} />}
        {user && activeTab === 'dashboard' && user.role === 'admin' && (
          <AdminPanel 
            activeTab={activeTab} 
            isMobile={isMobile}
            onAgentCreated={handleAgentCreated}
          />
        )}
        {user && activeTab === 'streams' && user.role === 'admin' && (
          <AdminPanel activeTab={activeTab} isMobile={isMobile} />
        )}
        {user && activeTab === 'flag' && user.role === 'admin' && (
          <AdminPanel activeTab={activeTab} isMobile={isMobile} />
        )}
        {user && activeTab === 'messaging' && (
          <MessageComponent user={user} isAdmin={user.role === 'admin'} />
        )}
        {user && activeTab === 'notifications' && (
          <NotificationsPage user={currentUser} ongoingStreams={ongoingStreams}
            notifications={notifications} 
            onNotificationClick={() => setActiveTab('notifications')} 
          />
        )}
        {user && user.role === 'agent' && activeTab !== 'messaging' && activeTab !== 'notifications' && (
          <AgentDashboard isMobile={isMobile} />
        )}
      </div>

      <style jsx global>{`
        * { box-sizing: border-box; }
        body {
          background: #121212;
          margin: 0;
          font-family: 'Inter', sans-serif;
          color: #e0e0e0;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
          overflow-x: hidden;
        }
      `}</style>

      <style jsx>{`
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .app-container {
          min-height: 100vh;
          animation: slideUp 0.6s cubic-bezier(0.22, 1, 0.36, 1);
        }
        .app-header {
          position: sticky;
          top: 0;
          z-index: 1000;
          padding: ${isMobile ? '12px 16px' : '20px 40px'};
          background: #1a1a1a;
          border-bottom: 1px solid #2d2d2d;
        }
        .nav-container {
          display: flex;
          justify-content: space-between;
          align-items: center;
          max-width: 1200px;
          margin: 0 auto;
          position: relative;
        }
        .menu-toggle {
          padding: 8px;
          background: #2d2d2d;
          border: none;
          border-radius: 6px;
          color: #e0e0e0;
          font-size: 1.2rem;
          cursor: pointer;
          position: relative;
          z-index: 1010;
        }
        .mobile-notification-badge {
          position: absolute;
          top: -5px;
          right: -5px;
          background: #ff4444;
          color: white;
          width: 18px;
          height: 18px;
          border-radius: 50%;
          font-size: 0.7em;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .admin-nav {
          display: flex;
          gap: ${isMobile ? '8px' : '12px'};
          flex-wrap: ${isMobile ? 'nowrap' : 'wrap'};
          position: relative;
        }
        .mobile-nav {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: #1a1a1a;
          z-index: 1000;
          padding: 60px 16px 16px;
          display: flex;
          flex-direction: column;
          overflow-y: auto;
          animation: fadeIn 0.3s ease;
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        .admin-nav button {
          padding: ${isMobile ? '14px 12px' : '12px 24px'};
          border: none;
          background: #2d2d2d;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          color: #a0a0a0;
          font-weight: 500;
          position: relative;
          overflow: hidden;
          width: ${isMobile ? '100%' : 'auto'};
          margin-bottom: ${isMobile ? '8px' : '0'};
          text-align: ${isMobile ? 'left' : 'center'};
        }
        .admin-nav button::before {
          content: '';
          position: absolute;
          bottom: 0;
          left: 0;
          width: 100%;
          height: 3px;
          background: #007bff;
          transform: scaleX(0);
          transition: transform 0.3s ease;
        }
        .admin-nav button.active, 
        .admin-nav button:hover {
          background: #333;
          color: #fff;
          transform: ${isMobile ? 'none' : 'translateY(-2px)'};
        }
        .admin-nav button.active::before {
          transform: scaleX(1);
        }
        .logout-button {
          padding: 12px 24px;
          background: linear-gradient(135deg, #007bff, #0056b3);
          color: white;
          border: none;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.3s ease;
          font-weight: 500;
        }
        .logout-button:hover {
          transform: translateY(-2px);
          box-shadow: 0 5px 15px rgba(0,123,255,0.3);
        }
        .main-content {
          max-width: 1200px;
          margin: ${isMobile ? '20px auto' : '40px auto'};
          padding: 0 ${isMobile ? '12px' : '20px'};
        }
        .notification-badge {
          background: #ff4444;
          color: white;
          border-radius: 50%;
          padding: 2px 6px;
          font-size: 0.8rem;
          margin-left: 4px;
        }
      `}</style>
    </div>
  );
}

function AppContentWrapper() {
  return <AppContent />;
}

function App() {
  return (
    <ToastProvider>
      <AppContentWrapper />
    </ToastProvider>
  );
}

export default App;
