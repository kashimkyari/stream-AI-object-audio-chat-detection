import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

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

  // Fetch notifications from the backend endpoint /api/logs.
  const fetchNotifications = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await axios.get('/api/logs', { timeout: 10000 });
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
      await axios.put(`/api/logs/${notificationId}/read`);
      setNotifications(prev => prev.map(n => n.id === notificationId ? { ...n, read: true } : n));
    } catch (err) {
      console.error('Error marking notification as read:', err);
    }
  }, []);

  const markAllAsRead = async () => {
    try {
      await axios.put('/api/logs/read-all');
      setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    } catch (err) {
      console.error('Error marking all notifications as read:', err);
    }
  };

  // Handler for deleting a single notification.
  const deleteNotification = useCallback(async (notificationId) => {
    try {
      await axios.delete(`/api/logs/${notificationId}`);
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
      await axios.delete('/api/logs/delete-all');
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
      <style jsx>{`
        .notifications-page {
          background: #1a1a1a;
          border-radius: 8px;
          overflow: hidden;
          height: calc(100vh - 160px);
          display: flex;
          flex-direction: column;
          animation: fadeIn 0.3s ease-out;
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        .notifications-controls {
          padding: 16px 20px;
          display: flex;
          flex-direction: column;
          gap: 8px;
          background: #252525;
          border-bottom: 1px solid #333;
        }
        .main-filter-controls {
          display: flex;
          gap: 8px;
        }
        .sub-filter-controls {
          display: flex;
          gap: 8px;
          margin-top: 4px;
        }
        .filter-btn,
        .sub-filter-btn,
        .mark-all-read,
        .delete-all,
        .refresh-notifications {
          padding: 8px 16px;
          border-radius: 6px;
          border: 1px solid #444;
          background: #2d2d2d;
          color: #e0e0e0;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .filter-btn:hover,
        .sub-filter-btn:hover,
        .mark-all-read:hover,
        .delete-all:hover,
        .refresh-notifications:hover {
          background: #333;
        }
        .filter-btn.active,
        .sub-filter-btn.active {
          background: #3a3a3a;
          border-color: #666;
        }
        .mark-all-read:disabled,
        .delete-all:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .delete-all {
          background: #3d1212;
          border-color: #541919;
        }
        .delete-all:hover {
          background: #4d1616;
        }
        .notifications-container {
          display: flex;
          flex: 1;
          overflow: hidden;
        }
        .notifications-list-container {
          width: 40%;
          border-right: 1px solid #333;
          display: flex;
          flex-direction: column;
        }
        .notifications-list-container h3 {
          padding: 16px 20px;
          margin: 0;
          border-bottom: 1px solid #333;
        }
        .notifications-list {
          overflow-y: auto;
          flex: 1;
        }
        .notification-item {
          display: flex;
          padding: 16px 20px;
          border-bottom: 1px solid #292929;
          cursor: pointer;
          transition: background-color 0.2s ease;
        }
        .notification-item:hover {
          background-color: #282828;
        }
        .notification-item.selected {
          background-color: #2d3748;
        }
        .notification-item.unread {
          background-color: #1e293b;
        }
        .notification-item.unread:hover {
          background-color: #233246;
        }
        .notification-item.unread.selected {
          background-color: #2c3e50;
        }
        .notification-indicator {
          width: 6px;
          min-width: 6px;
          border-radius: 3px;
          margin-right: 12px;
        }
        .notification-content {
          flex: 1;
        }
        .notification-message {
          font-size: 14px;
          margin-bottom: 4px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .notification-meta {
          display: flex;
          justify-content: space-between;
          font-size: 12px;
          color: #a0a0a0;
        }
        .notification-time {
          color: #888;
        }
        .notification-confidence {
          font-weight: 500;
          color: #f0f0f0;
        }
        .notification-detail-container {
          width: 60%;
          display: flex;
          flex-direction: column;
          overflow: hidden;
        }
        .notification-detail {
          padding: 20px;
          display: flex;
          flex-direction: column;
          height: 100%;
        }
        .detail-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
        }
        .detail-header h3 {
          margin: 0;
        }
        .detail-actions {
          display: flex;
          gap: 8px;
        }
        .mark-read-btn,
        .delete-btn {
          padding: 6px 12px;
          border-radius: 4px;
          border: none;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .mark-read-btn {
          background: #2d2d2d;
          color: #e0e0e0;
        }
        .mark-read-btn:hover {
          background: #333;
        }
        .delete-btn {
          background: #3d1212;
          color: #e0e0e0;
        }
        .delete-btn:hover {
          background: #4d1616;
        }
        .detail-timestamp {
          font-size: 14px;
          color: #888;
          margin-bottom: 20px;
        }
        .detection-content {
          display: flex;
          flex-direction: column;
          gap: 20px;
          flex: 1;
          overflow-y: auto;
        }
        .image-gallery {
          display: flex;
          gap: 20px;
          margin-bottom: 20px;
        }
        .image-card {
          background: #252525;
          border-radius: 8px;
          overflow: hidden;
          flex: 1;
          display: flex;
          flex-direction: column;
          align-items: center;
        }
        .detection-image {
          max-width: 100%;
          max-height: 300px;
          object-fit: contain;
        }
        .image-label {
          padding: 10px;
          background: #333;
          width: 100%;
          text-align: center;
          font-size: 14px;
          color: #e0e0e0;
        }
        .streamer-info-card {
          background: #252525;
          border-radius: 8px;
          padding: 16px;
          margin-bottom: 20px;
        }
        .streamer-info-card h4 {
          margin: 0 0 16px 0;
          font-size: 18px;
          color: #e0e0e0;
        }
        .info-item {
          display: flex;
          align-items: center;
          margin-bottom: 12px;
        }
        .info-label {
          width: 120px;
          font-weight: 500;
          color: #a0a0a0;
        }
        .info-value {
          flex: 1;
          color: #e0e0e0;
        }
        .detected-objects {
          background: #252525;
          border-radius: 8px;
          padding: 16px;
        }
        .detected-objects h4 {
          margin: 0 0 16px 0;
          font-size: 18px;
          color: #e0e0e0;
        }
        .detection-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }
        .detection-class {
          font-weight: 500;
          color: #e0e0e0;
        }
        .confidence-badge {
          padding: 4px 8px;
          border-radius: 12px;
          font-weight: 500;
          color: white;
        }
        .empty-detail,
        .empty-state,
        .loading-container,
        .error-message {
          height: 100%;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          color: #888;
          text-align: center;
          padding: 20px;
        }
        .empty-icon {
          font-size: 48px;
          margin-bottom: 16px;
          opacity: 0.5;
        }
        .loading-spinner {
          width: 40px;
          height: 40px;
          border: 4px solid rgba(255, 255, 255, 0.1);
          border-radius: 50%;
          border-top: 4px solid #007bff;
          animation: spin 1s linear infinite;
          margin-bottom: 16px;
        }
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        .error-message {
          color: #ff6b6b;
        }
        @media (max-width: 992px) {
          .notifications-container {
            flex-direction: column;
          }
          .notifications-list-container,
          .notification-detail-container {
            width: 100%;
            height: 50%;
          }
          .notifications-list-container {
            border-right: none;
            border-bottom: 1px solid #333;
          }
        }
        @media (max-width: 768px) {
          .notifications-controls {
            flex-direction: column;
            gap: 12px;
            align-items: stretch;
          }
          .main-filter-controls,
          .sub-filter-controls,
          .action-controls {
            justify-content: space-between;
          }
          .image-gallery {
            flex-direction: column;
          }
        }
      `}</style>
    </div>
  );
};

export default NotificationsPage;
