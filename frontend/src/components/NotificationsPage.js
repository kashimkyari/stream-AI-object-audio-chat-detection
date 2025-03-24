import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import './NotificationsPage.css';

axios.defaults.withCredentials = true;

const NotificationsPage = ({ user, ongoingStreams = [] }) => {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [mainFilter, setMainFilter] = useState('All');
  const [detectionSubFilter, setDetectionSubFilter] = useState('Visual');
  const [selectedNotification, setSelectedNotification] = useState(null);

  // Extract platform and streamer info from a stream URL.
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

  // Process and format notifications.
  const processNotifications = useCallback((data) => {
    return data.map(notification => {
      const fromUrl = extractStreamInfo(notification.room_url);
      const details = {
        annotated_image: notification.details?.annotated_image || null,
        captured_image: notification.details?.captured_image || null,
        streamer_name: notification.details?.streamer_name ||
          (notification.event_type === 'object_detection' ? fromUrl.streamer : ''),
        assigned_agent: notification.details?.assigned_agent || '',
        platform: notification.details?.platform ||
          (notification.event_type === 'object_detection' ? fromUrl.platform : ''),
        detections: (notification.details?.detections || []).map(det => ({
          ...det,
          confidence: det.score || det.confidence || 0,
        })),
        keyword: notification.details?.keyword || '',
        message: notification.details?.message || '',
      };
      return { ...notification, details, event_type: notification.event_type };
    });
  }, [extractStreamInfo]);

  // Fetch notifications from the backend notifications endpoint.
  const fetchNotifications = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      // Updated endpoint to /api/notifications
      const res = await axios.get('/api/notifications', { timeout: 10000 });
      if (res.status === 200 && Array.isArray(res.data)) {
        let processed = processNotifications(res.data);
        // If user is an agent, filter notifications to show only those where the assigned agent matches the agent's username.
        if (user && user.role === 'agent') {
          processed = processed.filter(n =>
            n.details?.assigned_agent &&
            n.details.assigned_agent.toLowerCase() === user.username.toLowerCase()
          );
        }
        // Further filter by main and sub filters if needed.
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

  // Poll notifications every 60 seconds.
  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 60000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  // Auto-scroll notifications list to top when notifications update.
  useEffect(() => {
    const listContainer = document.querySelector('.notifications-list');
    if (listContainer && !loading && !error) {
      listContainer.scrollTop = 0;
    }
  }, [notifications.length, loading, error]);

  // Handlers for marking notifications as read.
  const markAsRead = useCallback(async (notificationId) => {
    try {
      // Updated endpoint to /api/notifications/{id}/read
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

  // Handler for deleting a single notification.
  const deleteNotification = useCallback(async (notificationId) => {
    try {
      // Updated endpoint to /api/notifications/{id}
      await axios.delete(`/api/notifications/${notificationId}`);
      setNotifications(prev => prev.filter(n => n.id !== notificationId));
      if (selectedNotification?.id === notificationId) {
        setSelectedNotification(null);
      }
    } catch (err) {
      console.error('Error deleting notification:', err);
    }
  }, [selectedNotification]);

  // Handler for deleting all notifications.
  const deleteAllNotifications = async () => {
    try {
      await axios.delete('/api/notifications/delete-all');
      setNotifications([]);
      setSelectedNotification(null);
    } catch (err) {
      console.error('Error deleting all notifications:', err);
    }
  };

  const handleNotificationClick = (notification) => {
    if (!notification.read) markAsRead(notification.id);
    setSelectedNotification(notification);
  };

  // Format confidence value.
  const formatConfidence = (confidence) => {
    return (typeof confidence === 'number' && confidence > 0)
      ? `${(confidence * 100).toFixed(1)}%`
      : '';
  };

  // Determine a background color based on confidence.
  const getConfidenceColor = (confidence) => {
    const conf = typeof confidence === 'number' ? confidence : 0;
    if (conf >= 0.9) return '#ff4444';
    if (conf >= 0.75) return '#ff8c00';
    if (conf >= 0.5) return '#ffcc00';
    return '#28a745';
  };

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
            : selectedNotification.event_type === 'video_notification'
            ? 'Video Notification Details'
            : 'Notification Details'}
        </h3>
        <div className="detail-actions">
          {!selectedNotification.read && (
            <button className="mark-read-btn" onClick={() => markAsRead(selectedNotification.id)}>
              Mark as Read
            </button>
          )}
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
              <p>Detected keyword: <strong>{selectedNotification.details?.keyword}</strong></p>
              <p>Transcript: {selectedNotification.details?.transcript}</p>
            </div>
          </div>
        );
      case 'object_detection':
        return (
          <div className="notification-detail">
            {commonHeader}
            {commonTimestamp}
            <div className="detection-content">
              <div className="image-gallery">
                {selectedNotification.details?.annotated_image && (
                  <div className="image-card">
                    <img
                      src={selectedNotification.details.annotated_image}
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
                  <span className="info-value">{selectedNotification.details?.assigned_agent}</span>
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
      case 'video_notification':
        return (
          <div className="notification-detail">
            {commonHeader}
            {commonTimestamp}
            <div className="video-notification-content">
              <p>{selectedNotification.details?.message || 'Video event occurred'}</p>
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
            <button key={tab}
                    className={`filter-btn ${mainFilter === tab ? 'active' : ''}`}
                    onClick={() => {
                      setMainFilter(tab);
                      if (tab === 'Detections') setDetectionSubFilter('Visual');
                    }}>
              {tab}
            </button>
          ))}
        </div>
        {mainFilter === 'Detections' && (
          <div className="sub-filter-controls">
            {['Visual', 'Audio', 'Chat'].map(subTab => (
              <button key={subTab}
                      className={`sub-filter-btn ${detectionSubFilter === subTab ? 'active' : ''}`}
                      onClick={() => setDetectionSubFilter(subTab)}>
                {subTab}
              </button>
            ))}
          </div>
        )}
        <div className="action-controls">
          <button className="mark-all-read"
                  onClick={markAllAsRead}
                  disabled={notifications.filter(n => !n.read).length === 0}>
            Mark All as Read
          </button>
          <button className="delete-all"
                  onClick={deleteAllNotifications}
                  disabled={notifications.length === 0}>
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
                <div key={notification.id}
                     className={`notification-item ${notification.read ? 'read' : 'unread'} ${selectedNotification?.id === notification.id ? 'selected' : ''}`}
                     onClick={() => handleNotificationClick(notification)}>
                  <div className="notification-indicator"
                       style={{
                         backgroundColor: notification.event_type === 'object_detection'
                           ? getConfidenceColor(notification.details?.detections?.[0]?.confidence)
                           : notification.event_type === 'audio_detection'
                           ? '#007bff'
                           : notification.event_type === 'chat_detection'
                           ? '#8a2be2'
                           : notification.event_type === 'video_notification'
                           ? '#dc3545'
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
                        : notification.event_type === 'video_notification'
                        ? notification.details?.message || 'Video event occurred'
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
