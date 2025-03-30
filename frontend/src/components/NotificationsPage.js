import React, { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import io from 'socket.io-client';
import './NotificationsPage.css';

axios.defaults.withCredentials = true;
const SOCKET_SERVER_URL = 'http://54.86.99.85:5000';

const NotificationsPage = ({ user, ongoingStreams = [] }) => {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [mainFilter, setMainFilter] = useState('All');
  const [detectionSubFilter, setDetectionSubFilter] = useState('Visual');
  const [selectedNotification, setSelectedNotification] = useState(null);
  const [agents, setAgents] = useState([]);
  const [dashboardStreams, setDashboardStreams] = useState([]);
  const [showAgentDropdown, setShowAgentDropdown] = useState(false);
  const socketRef = useRef();

  const extractStreamInfo = useCallback((streamUrl) => {
    let platform = 'Chaturbate';
    let streamer = '';
    if (streamUrl && streamUrl.includes('edge-hls.doppiocdn.live')) {
      platform = 'Stripchat';
    }
    if (streamUrl) {
      const parts = streamUrl.split('/');
      streamer = parts[parts.length - 1].split('?')[0];
    }
    return { platform, streamer };
  }, []);

  const formatImage = useCallback((image) => {
    if (image && !image.startsWith("data:")) {
      return "data:image/png;base64," + image;
    }
    return image;
  }, []);

  const processNotifications = useCallback((data) => {
    return data.map(notification => {
      const assignedAgent = notification.details?.assigned_agent || notification.assigned_agent || "Unassigned";
      const baseNotification = {
        id: notification.id,
        event_type: notification.event_type,
        timestamp: notification.timestamp,
        read: notification.read,
        details: {
          ...notification.details,
          detections: (notification.details?.detections || []).map(d => ({
            class: d.class,
            confidence: d.confidence || d.score || 0,
            bbox: d.bbox || []
          })),
          images: notification.details?.images || {
            annotated: notification.details?.annotated_image,
            original: notification.details?.captured_image
          },
          stream: notification.details?.stream || {
            platform: notification.details?.platform,
            streamer: notification.details?.streamer_name,
            url: notification.room_url
          },
          agent: assignedAgent
        },
        assigned_agent: assignedAgent
      };

      return {
        ...baseNotification,
        displayType: notification.event_type === 'object_detection' ? 'object' : notification.event_type,
        previewText: notification.event_type === 'object_detection'
          ? `${notification.details.detections.length} objects detected`
          : notification.details.message,
        timestamp: notification.timestamp,
        confidence: notification.event_type === 'object_detection'
          ? Math.max(...(notification.details.detections.map(d => d.confidence))) || 0
          : 0
      };
    });
  }, []);

  // Fetch dashboard streams when a visual detection notification is selected.
  useEffect(() => {
    const fetchDashboardStreams = async () => {
      try {
        const res = await axios.get('/api/dashboard');
        if (res.status === 200 && res.data && res.data.streams) {
          setDashboardStreams(res.data.streams);
        }
      } catch (err) {
        console.error('Error fetching dashboard streams:', err);
      }
    };
    if (selectedNotification && selectedNotification.event_type === 'object_detection') {
      fetchDashboardStreams();
    }
  }, [selectedNotification]);

  // Lookup the assigned agent using dashboard stream data and agents list.
  const getAssignedAgentForStream = useCallback(() => {
    if (dashboardStreams && dashboardStreams.length > 0 && selectedNotification && selectedNotification.details) {
      const { platform, streamer } = selectedNotification.details.stream;
      const matchedStream = dashboardStreams.find(s =>
        s.platform.toLowerCase() === platform.toLowerCase() &&
        s.streamer_username.toLowerCase() === streamer.toLowerCase()
      );
      if (matchedStream && matchedStream.assignments && matchedStream.assignments.length > 0 && matchedStream.assignments[0].agent) {
        const agentId = matchedStream.assignments[0].agent.id;
        const foundAgent = agents.find(a => a.id === agentId);
        if (foundAgent) return foundAgent.username;
        return matchedStream.assignments[0].agent.username || "Unassigned";
      }
    }
    return "Unassigned";
  }, [dashboardStreams, selectedNotification, agents]);

  const fetchNotifications = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await axios.get('/api/notifications', { timeout: 10000 });
      if (res.status === 200 && Array.isArray(res.data)) {
        let processed = processNotifications(res.data);
        if (user && user.role === 'agent') {
          processed = processed.filter(n =>
            (n.assigned_agent || "").toLowerCase() === user.username.toLowerCase()
          );
        }
        if (mainFilter === 'Unread') {
          processed = processed.filter(n => !n.read);
        } else if (mainFilter === 'Detections') {
          const typeMap = {
            Visual: 'object_detection',
            Audio: 'audio_detection',
            Chat: 'chat_detection',
          };
          processed = processed.filter(n => n.event_type === typeMap[detectionSubFilter]);
        }
        setNotifications(processed);
      } else {
        setError('Unexpected response from server.');
      }
    } catch (err) {
      console.error('Error fetching notifications:', err);
      setError('Failed to load notifications.');
    } finally {
      setLoading(false);
    }
  }, [processNotifications, user, mainFilter, detectionSubFilter]);

  useEffect(() => {
    const fetchAgents = async () => {
      if (user?.role === 'admin') {
        try {
          const res = await axios.get('/api/agents');
          setAgents(res.data);
        } catch (err) {
          console.error('Error fetching agents:', err);
        }
      }
    };

    socketRef.current = io(SOCKET_SERVER_URL, { withCredentials: true });
    socketRef.current.on('notification_forwarded', fetchNotifications);

    fetchAgents();
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 60000);
    return () => {
      clearInterval(interval);
      socketRef.current.disconnect();
    };
  }, [fetchNotifications, user]);

  useEffect(() => {
    const listContainer = document.querySelector('.notifications-list');
    if (listContainer && !loading && !error) {
      listContainer.scrollTop = 0;
    }
  }, [notifications.length, loading, error]);

  const markAsRead = useCallback(async (notificationId) => {
    try {
      await axios.put(`/api/notifications/${notificationId}/read`);
      setNotifications(prev => prev.map(n => n.id === notificationId ? { ...n, read: true } : n));
    } catch (err) {
      console.error('Error marking notification as read:', err);
    }
  }, []);

  const markAllAsRead = async () => {
    try {
      await axios.put('/api/notifications/read-all');
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    } catch (err) {
      console.error('Error marking all notifications as read:', err);
    }
  };

  const deleteNotification = useCallback(async (notificationId) => {
    try {
      await axios.delete(`/api/notifications/${notificationId}`);
      setNotifications(prev => prev.filter(n => n.id !== notificationId));
      if (selectedNotification?.id === notificationId) {
        setSelectedNotification(null);
      }
    } catch (err) {
      console.error('Error deleting notification:', err);
    }
  }, [selectedNotification]);

  const deleteAllNotifications = async () => {
    try {
      await axios.delete('/api/notifications/delete-all');
      setNotifications([]);
      setSelectedNotification(null);
    } catch (err) {
      console.error('Error deleting all notifications:', err);
    }
  };

// NotificationsPage.js
const forwardNotification = useCallback(async (agentId) => {
  if (!selectedNotification) return;
  try {
    await axios.post(`/api/notifications/${selectedNotification.id}/forward`, { 
      agent_id: agentId 
    });
    setShowAgentDropdown(false);
    fetchNotifications();
  } catch (err) {
    console.error('Forward error:', err);
  }
}, [selectedNotification, fetchNotifications]);

  const handleNotificationClick = (notification) => {
    if (!notification.read) markAsRead(notification.id);
    setSelectedNotification(notification);
  };

  const formatConfidence = (confidence) => {
    return (typeof confidence === 'number' && confidence > 0)
      ? `${(confidence * 100).toFixed(1)}%`
      : '';
  };

  const getConfidenceColor = (confidence) => {
    const conf = typeof confidence === 'number' ? confidence : 0;
    if (conf >= 0.9) return '#ff4444';
    if (conf >= 0.75) return '#ff8c00';
    if (conf >= 0.5) return '#ffcc00';
    return '#28a745';
  };

  // Render agent forwarding dropdown
  const renderForwardSection = () => (
    <div className="forward-section">
      <button 
        className="forward-btn"
        onClick={() => setShowAgentDropdown(true)}
      >
        Forward to Agent
      </button>
      
      {showAgentDropdown && (
        <div className="forward-modal-overlay" onClick={() => setShowAgentDropdown(false)}>
          <div className="forward-modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Select Agent</h3>
              <button 
                className="modal-close-btn"
                onClick={() => setShowAgentDropdown(false)}
              >
                &times;
              </button>
            </div>
            <div className="agent-list">
              {agents.map(agent => (
                <div 
                  key={agent.id} 
                  className="agent-option"
                  onClick={() => {
                    forwardNotification(agent.id);
                    setShowAgentDropdown(false);
                  }}
                >
                  <div className={`agent-status-indicator ${agent.online ? 'online' : 'offline'}`} />
                  <div className="agent-info">
                    <div className="agent-name">{agent.username}</div>
                    <div className="agent-email">{agent.email}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );

  const renderNotificationDetails = () => {
    if (!selectedNotification) {
      return (
        <div className="empty-detail">
          <div className="empty-icon">📋</div>
          <p>Select a notification to view details</p>
        </div>
      );
    }

    const commonHeader = (
      <div className="detail-header">
        <h3>
          {selectedNotification.event_type === 'audio_detection'
            ? 'Audio Detection Details'
            : selectedNotification.event_type === 'object_detection'
            ? 'Visual Detection Details'
            : selectedNotification.event_type === 'chat_detection'
            ? 'Chat Detection Details'
            : selectedNotification.event_type === 'stream_created'
            ? 'New Stream Created'
            : 'Notification Details'}
        </h3>
        <div className="detail-actions">
          {!selectedNotification.read && (
            <button className="mark-read-btn" onClick={() => markAsRead(selectedNotification.id)}>
              Mark as Read
            </button>
          )}
          {user?.role === 'admin' && renderForwardSection()}
          <button className="delete-btn" onClick={() => deleteNotification(selectedNotification.id)}>
            Delete
          </button>
        </div>
      </div>
    );

    const commonTimestamp = (
      <div className="detail-timestamp">
        Detected at: {new Date(selectedNotification.timestamp).toLocaleString()}
      </div>
    );

    switch (selectedNotification.event_type) {
      case 'audio_detection':
  return (
    <div className="notification-detail">
      {commonHeader}
      {commonTimestamp}
      <div className="audio-detection-content">
        <p>Detected keywords: <strong>{selectedNotification.details?.keywords?.join(', ')}</strong></p>
        <p>Transcript: {selectedNotification.details?.transcript}</p>
      </div>
    </div>
  );
      case 'object_detection': {
        // For visual detections, fetch assigned agent from dashboard and then look up agent username from agents.
        const assignedAgent = getAssignedAgentForStream();
        return (
          <div className="notification-detail">
            {commonHeader}
            {commonTimestamp}
            <div className="detection-content">
              <div className="image-gallery">
                {selectedNotification.details?.annotated_image && (
                  <div className="image-card">
                    <img
                      src={formatImage(selectedNotification.details.annotated_image)}
                      alt="Annotated Detection"
                      className="detection-image"
                    />
                    <div className="image-label">Annotated Image</div>
                  </div>
                )}
                {selectedNotification.details?.captured_image && (
                  <div className="image-card">
                    <img
                      src={selectedNotification.details.captured_image}
                      alt="Captured Image"
                      className="detection-image"
                    />
                    <div className="image-label">Captured Image</div>
                  </div>
                )}
              </div>
              <div className="streamer-info-card">
                <h4>Streamer Info</h4>
                <div className="info-item">
                  <span className="info-label">Streamer:</span>
                  <span className="info-value">{selectedNotification.details?.streamer_name}</span>
                </div>
                <div className="info-item">
                  <span className="info-label">Assigned Agent:</span>
                  <span className="info-value">
                    {assignedAgent !== "Unassigned"
                      ? assignedAgent
                      : <span className="unassigned-badge">⚠️ UNASSIGNED</span>}
                  </span>
                </div>
                <div className="info-item">
                  <span className="info-label">Platform:</span>
                  <span className="info-value">{selectedNotification.details?.platform}</span>
                </div>
              </div>
              <div className="detected-objects">
                <h4>Detected Objects</h4>
                {selectedNotification.details?.detections?.map((detection, index) => (
                  <div key={index} className="detection-item">
                    <span className="detection-class">{detection.class}</span>
                    <span className="confidence-badge"
                          style={{ backgroundColor: getConfidenceColor(detection.confidence) }}>
                      {formatConfidence(detection.confidence)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        );
      }
      case 'chat_detection':
        return (
          <div className="notification-detail">
            {commonHeader}
            {commonTimestamp}
            <div className="chat-detection-content">
              <p>Detected chat keyword: <strong>{selectedNotification.details?.keyword}</strong></p>
              <p className="chat-excerpt">{selectedNotification.details?.ocr_text}</p>
            </div>
          </div>
        );
      case 'stream_created':
        return (
          <div className="notification-detail">
            {commonHeader}
            {commonTimestamp}
            <div className="stream-created-content">
              <p>A new stream has been created by <strong>{selectedNotification.details?.streamer_name || 'Unknown'}</strong>.</p>
              {selectedNotification.details?.stream_url && (
                <p>
                  Stream URL: <a href={selectedNotification.details.stream_url} target="_blank" rel="noopener noreferrer">
                    {selectedNotification.details.stream_url}
                  </a>
                </p>
              )}
            </div>
          </div>
        );
      default:
        return (
          <div className="notification-detail">
            {commonHeader}
            {commonTimestamp}
            <p>{selectedNotification.message}</p>
          </div>
        );
    }
  };

  return (
    <div className="notifications-page">
      <div className="notifications-controls">
        <div className="main-filter-controls">
          {['All', 'Unread', 'Detections'].map(tab => (
            <button 
              key={tab}
              className={`filter-btn ${mainFilter === tab ? 'active' : ''}`}
              onClick={() => {
                setMainFilter(tab);
                if (tab === 'Detections') setDetectionSubFilter('Visual');
              }}
            >
              {tab}
            </button>
          ))}
        </div>
        {mainFilter === 'Detections' && (
          <div className="sub-filter-controls">
            {['Visual', 'Audio', 'Chat'].map(subTab => (
              <button 
                key={subTab}
                className={`sub-filter-btn ${detectionSubFilter === subTab ? 'active' : ''}`}
                onClick={() => setDetectionSubFilter(subTab)}
              >
                {subTab}
              </button>
            ))}
          </div>
        )}
        <div className="action-controls">
          <button 
            className="mark-all-read"
            onClick={markAllAsRead}
            disabled={notifications.filter(n => !n.read).length === 0}
          >
            Mark All as Read
          </button>
          <button 
            className="delete-all"
            onClick={deleteAllNotifications}
            disabled={notifications.length === 0}
          >
            Delete All
          </button>
          <button className="refresh-notifications" onClick={fetchNotifications}>
            Refresh Notifications
          </button>
        </div>
      </div>
      <div className="notifications-container">
        <div className="notifications-list-container">
          <h3>Notifications ({notifications.length})</h3>
          {loading ? (
            <div className="loading-container">
              <div className="loading-spinner"></div>
              <p>Loading notifications...</p>
            </div>
          ) : error ? (
            <div className="error-message">{error}</div>
          ) : notifications.length === 0 ? (
            <div className="empty-state">
              <div className="empty-icon">🔔</div>
              <p>No notifications to display</p>
            </div>
          ) : (
            <div className="notifications-list">
              {notifications.map(notification => (
                <div 
                  key={notification.id}
                  className={`notification-item ${notification.read ? 'read' : 'unread'} ${selectedNotification?.id === notification.id ? 'selected' : ''}`}
                  onClick={() => handleNotificationClick(notification)}
                >
                  <div className="notification-indicator"
                       style={{
                         backgroundColor: notification.event_type === 'object_detection'
                           ? getConfidenceColor(notification.details?.detections?.[0]?.confidence)
                           : notification.event_type === 'audio_detection'
                           ? '#007bff'
                           : notification.event_type === 'chat_detection'
                           ? '#8a2be2'
                           : notification.event_type === 'stream_created'
                           ? '#28a745'
                           : '#28a745'
                       }}></div>
                  <div className="notification-content">
                    <div className="notification-message">
                      {notification.event_type === 'object_detection'
                        ? `Detected ${notification.details?.detections?.length || 0} objects`
                        : notification.event_type === 'audio_detection'
                        ? `Detected keyword: ${notification.details?.keyword}`
                        : notification.event_type === 'chat_detection'
                        ? `Chat event: ${notification.details?.keyword}`
                        : notification.event_type === 'stream_created'
                        ? `New stream created by ${notification.details?.streamer_name || 'Unknown'}`
                        : notification.message}
                    </div>
                    <div className="notification-meta">
                      <span className="notification-time">
                        {new Date(notification.timestamp).toLocaleString()}
                      </span>
                      {notification.event_type === 'object_detection' && (
                        <span className="notification-confidence">
                          {formatConfidence(notification.details?.detections?.[0]?.confidence)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="notification-detail-container">
          {renderNotificationDetails()}
        </div>
      </div>
    </div>
  );
};

export default NotificationsPage;
