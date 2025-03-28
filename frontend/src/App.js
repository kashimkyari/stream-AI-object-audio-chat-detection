import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

// Directly import components (no lazy loading for speed)
import Login from './components/Login';
import AdminPanel from './components/AdminPanel';
import AgentDashboard from './components/AgentDashboard';
import MessageComponent from './components/MessageComponent';
import NotificationsPage from './components/NotificationsPage';

function AppContent() {
  const [user, setUser] = useState(null); // Store full user object
  const [appLoading, setAppLoading] = useState(true); // Overall app loading flag
  const [initialRedirectDone, setInitialRedirectDone] = useState(false); // Delay before redirect on first login
  const [activeTab, setActiveTab] = useState(null);
  const [dashboardData, setDashboardData] = useState({ streams: [] });
  const [isMobile, setIsMobile] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  // States for stream URL, online status, poster image, etc.
  const [m3u8Url, setM3u8Url] = useState(null);
  const [isOnline, setIsOnline] = useState(true);
  const [posterUrl, setPosterUrl] = useState(null);
  const [loading, setLoading] = useState(true);

  // Notification-related states
  const [unreadCount, setUnreadCount] = useState(0);
  const [notificationStack, setNotificationStack] = useState([]);
  const [prevUnreadCount, setPrevUnreadCount] = useState(0);
  const [showNotificationStack, setShowNotificationStack] = useState(false);

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
            setActiveTab('dashboard');
            const dashboardRes = await axios.get('/api/dashboard');
            setDashboardData(dashboardRes.data);
          } else if (res.data.user.role === 'agent') {
            setActiveTab('agentdashboard');
          }
          // For logged-in users, wait briefly before marking initial redirect as done.
          setTimeout(() => setInitialRedirectDone(true), 1000);
        } else {
          // If not logged in, mark initial redirect as done to allow login screen to show.
          setInitialRedirectDone(true);
        }
      } catch (error) {
        console.log("No active session.");
        setInitialRedirectDone(true);
      } finally {
        setAppLoading(false);
      }
    };
    checkSession();
  }, []);

  const handleLogin = (loggedInUser) => {
    setUser(loggedInUser);
    if (loggedInUser.role === 'admin') {
      setActiveTab('dashboard');
      axios.get('/api/dashboard').then(res => setDashboardData(res.data));
    } else if (loggedInUser.role === 'agent') {
      setActiveTab('agentdashboard');
    }
    console.log("Login successful");
    setInitialRedirectDone(true);
  };

  const handleLogout = async () => {
    try {
      await axios.post('/api/logout');
      setUser(null);
      setMenuOpen(false);
      console.log("Logged out successfully");
      setActiveTab(null);
    } catch (err) {
      console.error("Logout error", err);
      console.log("Logout failed");
    }
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
    console.log("Agent created successfully");
  };

  // -------------
  // Fetch m3u8 URL using provided snippet.
  const platform = user?.role === 'agent' ? user.assignedStreamPlatform || '' : 'chaturbate';
  const streamerName = user?.role === 'agent'
    ? user.assignedStreamStreamerName || ''
    : dashboardData.streams[0]?.streamer_username || '';

  useEffect(() => {
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

  // -------------
  // Fetch notifications count and list for badge and floating stack.
  useEffect(() => {
    const fetchNotificationsData = async () => {
      try {
        const res = await axios.get('/api/notifications', { timeout: 10000 });
        let notifications = res.data;
        if (user && user.role === 'agent') {
          // For agents, filter notifications by assigned_agent
          notifications = notifications.filter(n =>
            (n.assigned_agent || "").toLowerCase() === user.username.toLowerCase()
          );
        }
        const unread = notifications.filter(n => !n.read);
        const sortedUnread = unread.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
        setUnreadCount(sortedUnread.length);
        setNotificationStack(sortedUnread);
        if (sortedUnread.length > prevUnreadCount) {
          setShowNotificationStack(true);
          setTimeout(() => setShowNotificationStack(false), 5000);
        }
        setPrevUnreadCount(sortedUnread.length);
      } catch (err) {
        console.error('Error fetching notifications count:', err);
      }
    };

    fetchNotificationsData();
    const interval = setInterval(fetchNotificationsData, 60000);
    return () => clearInterval(interval);
  }, [user, prevUnreadCount]);

  // Helper function to get a proper thumbnail image from a notification.
  const getThumbnail = (notif) => {
    if (notif.event_type === 'object_detection') {
      let image = notif.details?.annotated_image;
      if (image) {
        if (!image.startsWith("data:")) {
          image = "data:image/png;base64," + image;
        }
        return image;
      }
    }
    return null;
  };

  // While app is still loading or initial redirect is not complete, show a full-page loader.
  if (appLoading || !initialRedirectDone) {
    return (
      <div className="app-loading">
        <div className="spinner"></div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {user && (
        <header className="app-header">
          <div className="nav-container">
            {isMobile && user.role === 'admin' && (
              <button className="menu-toggle" onClick={toggleMenu}>
                {menuOpen ? '✕' : '☰'}
              </button>
            )}
            {user && (!isMobile || (isMobile && menuOpen)) && (
              <nav className={`admin-nav ${isMobile ? 'mobile-nav' : ''}`}>
                {user.role === 'admin' ? (
                  <>
                    <button onClick={() => handleTabClick('dashboard')} className={activeTab === 'dashboard' ? 'active' : ''}>
                      Dashboard
                    </button>
                    <button onClick={() => handleTabClick('streams')} className={activeTab === 'streams' ? 'active' : ''}>
                      Management
                    </button>
                    <button onClick={() => handleTabClick('flag')} className={activeTab === 'flag' ? 'active' : ''}>
                      Settings
                    </button>
                  </>
                ) : (
                  <button onClick={() => handleTabClick('agentdashboard')} className={activeTab === 'agentdashboard' ? 'active' : ''}>
                    Dashboard
                  </button>
                )}
                <button onClick={() => handleTabClick('messaging')} className={activeTab === 'messaging' ? 'active' : ''}>
                  Messaging
                </button>
                <button onClick={() => handleTabClick('notifications')} className={activeTab === 'notifications' ? 'active' : ''}>
                  Notifications {unreadCount > 0 && <span className="badge">{unreadCount}</span>}
                </button>
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
        {user && user.role === 'admin' && activeTab === 'dashboard' && (
          <AdminPanel 
            activeTab={activeTab} 
            isMobile={isMobile}
            onAgentCreated={handleAgentCreated}
          />
        )}
        {user && user.role === 'admin' && (activeTab === 'streams' || activeTab === 'flag') && (
          <AdminPanel activeTab={activeTab} isMobile={isMobile} />
        )}
        {user && activeTab === 'messaging' && (
          <MessageComponent user={user} isAdmin={user.role === 'admin'} />
        )}
        {user && activeTab === 'notifications' && (
          <NotificationsPage user={user} ongoingStreams={dashboardData.streams} />
        )}
        {user && user.role === 'agent' && activeTab === 'agentdashboard' && (
          <AgentDashboard isMobile={isMobile} />
        )}
      </div>

      {showNotificationStack && notificationStack.length > 0 && (
        <div className="notification-stack">
          {notificationStack.slice(0, 5).map((notif) => (
            <div 
              key={notif.id} 
              className="notification-card"
              onClick={() => setActiveTab('notifications')}
            >
              <div className="card-thumbnail">
                {getThumbnail(notif) ? (
                  <img src={getThumbnail(notif)} alt="Detection Thumbnail" />
                ) : (
                  <span className="default-thumb">🔔</span>
                )}
              </div>
              <div className="card-details">
                <strong>{notif.details?.streamer_name || 'Unknown'}</strong>
                <p>Agent: {notif.assigned_agent || notif.details?.assigned_agent || 'N/A'}</p>
                <p>{new Date(notif.timestamp).toLocaleTimeString()}</p>
              </div>
              {notif.event_type === 'object_detection' && (
                <div 
                  className="card-confidence" 
                  style={{ backgroundColor: notif.details?.detections?.[0] ? 
                    (notif.details.detections[0].confidence >= 0.9 ? '#ff4444' : notif.details.detections[0].confidence >= 0.75 ? '#ff8c00' : notif.details.detections[0].confidence >= 0.5 ? '#ffcc00' : '#28a745') : '#28a745'
                  }}>
                  {notif.details?.detections?.[0] ? `${(notif.details.detections[0].confidence * 100).toFixed(1)}%` : ''}
                </div>
              )}
            </div>
          ))}
          {notificationStack.length > 5 && (
            <div className="notification-card more">
              +{notificationStack.length - 5} more
            </div>
          )}
        </div>
      )}

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
        .badge {
          background: #dc3545;
          color: white;
          border-radius: 50%;
          padding: 2px 8px;
          margin-left: 6px;
          font-size: 0.8rem;
        }
        .notification-stack {
          position: fixed;
          bottom: 20px;
          right: 20px;
          display: flex;
          flex-direction: column;
          gap: 10px;
          z-index: 1000;
        }
        .notification-card {
          background: #1a1a1a;
          padding: 10px 15px;
          border-radius: 6px;
          box-shadow: 0 2px 6px rgba(0,0,0,0.3);
          cursor: pointer;
          display: flex;
          align-items: center;
          transition: transform 0.2s ease;
        }
        .notification-card:hover {
          transform: translateY(-3px);
        }
        .notification-card.more {
          text-align: center;
          background: #333;
          font-weight: bold;
        }
        .card-thumbnail img {
          width: 40px;
          height: 40px;
          object-fit: cover;
          border-radius: 4px;
          margin-right: 8px;
        }
        .default-thumb {
          font-size: 1.5rem;
          margin-right: 8px;
        }
        .card-details {
          flex-grow: 1;
        }
        .card-confidence {
          padding: 4px 8px;
          border-radius: 4px;
          color: #fff;
          font-weight: bold;
          font-size: 0.8rem;
        }
        .app-loading {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100vh;
          width: 100vw;
          background: #121212;
          position: fixed;
          top: 0;
          left: 0;
          z-index: 2000;
        }
        .spinner {
          border: 8px solid #f3f3f3;
          border-top: 8px solid #007bff;
          border-radius: 50%;
          width: 60px;
          height: 60px;
          animation: spin 1s linear infinite;
        }
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
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
          box-shadow: 0 2px 6px rgba(0, 0, 0, 0.5);
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
          padding: 10px;
          background: #2d2d2d;
          border: none;
          border-radius: 6px;
          color: #e0e0e0;
          font-size: 1.4rem;
          cursor: pointer;
          transition: background 0.3s ease;
        }
        .menu-toggle:hover {
          background: #3a3a3a;
        }
        .admin-nav {
          display: flex;
          gap: ${isMobile ? '10px' : '16px'};
          flex-wrap: ${isMobile ? 'nowrap' : 'wrap'};
          position: relative;
          transition: all 0.3s ease;
        }
        .mobile-nav {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: #1a1a1a;
          z-index: 1000;
          padding: 70px 16px 16px;
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
          transition: transform 0.3s ease, background 0.3s ease;
          color: #a0a0a0;
          font-weight: 500;
          position: relative;
          overflow: hidden;
          width: ${isMobile ? '100%' : 'auto'};
          margin-bottom: ${isMobile ? '8px' : '0'};
        }
        .admin-nav button:hover {
          background: #333;
          transform: translateY(-3px);
          color: #fff;
        }
        .admin-nav button.active {
          background: #007bff;
          color: #fff;
          transform: translateY(-3px);
        }
        .logout-button {
          padding: 12px 24px;
          background: linear-gradient(135deg, #007bff, #0056b3);
          color: white;
          border: none;
          border-radius: 8px;
          cursor: pointer;
          transition: transform 0.3s ease, box-shadow 0.3s ease;
          font-weight: 500;
        }
        .logout-button:hover {
          transform: translateY(-3px);
          box-shadow: 0 5px 15px rgba(0,123,255,0.4);
        }
        .main-content {
          max-width: 1200px;
          margin: ${isMobile ? '20px auto' : '40px auto'};
          padding: 0 ${isMobile ? '12px' : '20px'};
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
    <AppContentWrapper />
  );
}

export default App;
