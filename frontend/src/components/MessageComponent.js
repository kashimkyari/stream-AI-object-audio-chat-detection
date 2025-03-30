import React, { useState, useEffect, useRef, useCallback } from 'react';
import io from 'socket.io-client';
import { formatDistanceToNow } from 'date-fns';
import './MessageComponent.css';

const MessageComponent = ({ user }) => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [onlineUsers, setOnlineUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [isTyping, setIsTyping] = useState(false);
  const [unreadCounts, setUnreadCounts] = useState({});
  const [notificationDetails, setNotificationDetails] = useState(null);
  const [connectionError, setConnectionError] = useState(false);
  const messagesEndRef = useRef(null);
  const socketRef = useRef(null);
  const typingTimeout = useRef(null);

  // Configure WebSocket connection
  const configureSocket = useCallback(() => {
    if (!user) return;

    const socketUrl = 'http://54.86.99.85:5000';
    
    socketRef.current = io(socketUrl, {
      withCredentials: true,
      transports: ['websocket', 'polling'],
      reconnectionAttempts: 5,
      query: { 
        userId: user.id,
        role: user.role 
      }
    });

    // Connection handlers
    socketRef.current.on('connect', () => {
      console.log('WebSocket connected');
      setConnectionError(false);
    });

    socketRef.current.on('connect_error', (err) => {
      console.error('WebSocket connection error:', err);
      setConnectionError(true);
    });

    socketRef.current.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason);
      if (reason === 'io server disconnect') {
        socketRef.current.connect();
      }
    });

    // Event listeners
    socketRef.current.on('online_users', handleOnlineUsers);
    socketRef.current.on('receive_message', handleReceiveMessage);
    socketRef.current.on('typing', handleTypingIndicator);
    socketRef.current.on('notification_forwarded', handleForwardedNotification);

    return () => {
      socketRef.current.off('connect');
      socketRef.current.off('connect_error');
      socketRef.current.off('disconnect');
      socketRef.current.disconnect();
    };
  }, [user]);

  useEffect(() => {
    configureSocket();
  }, [configureSocket]);

  const handleOnlineUsers = (users) => {
    setOnlineUsers(users.filter(u => u.id !== user.id));
  };

  // Add to MessageComponent.js
useEffect(() => {
  const activityTimer = setInterval(() => {
    socketRef.current.emit('user_activity');
  }, 300000); // 5 minutes

  const activityEvents = ['mousemove', 'keydown', 'scroll'];
  const handleActivity = () => {
    socketRef.current.emit('user_activity');
  };

  activityEvents.forEach(event => {
    window.addEventListener(event, handleActivity);
  });

  return () => {
    clearInterval(activityTimer);
    activityEvents.forEach(event => {
      window.removeEventListener(event, handleActivity);
    });
  };
}, []);

  const handleReceiveMessage = (message) => {
    setMessages(prev => [...prev, message]);
    if (message.senderId !== selectedUser?.id) {
      setUnreadCounts(prev => ({
        ...prev,
        [message.senderId]: (prev[message.senderId] || 0) + 1
      }));
    }
    scrollToBottom();
  };

  const handleTypingIndicator = ({ senderId, typing }) => {
    if (senderId === selectedUser?.id) setIsTyping(typing);
  };

  const handleForwardedNotification = (notification) => {
    const systemMessage = {
      id: `notif-${notification.id}`,
      content: `🚨 Forwarded Alert: ${notification.details.message}`,
      senderId: 'system',
      receiverId: user.id,
      timestamp: new Date().toISOString(),
      type: 'notification',
      meta: notification.details
    };
    setMessages(prev => [...prev, systemMessage]);
    scrollToBottom();
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const sendMessage = useCallback(async () => {
    const content = inputMessage.trim();
    if (!content || !selectedUser) return;

    const message = {
      content,
      receiverId: selectedUser.id,
      senderId: user.id,
      timestamp: new Date().toISOString(),
      read: false
    };

    try {
      socketRef.current.emit('send_message', message);
      setInputMessage('');
    } catch (error) {
      console.error('Message send error:', error);
    }
  }, [inputMessage, selectedUser, user]);

  const handleTyping = (e) => {
    setInputMessage(e.target.value);
    
    // Typing indicator with debounce
    if (typingTimeout.current) clearTimeout(typingTimeout.current);
    socketRef.current.emit('typing', {
      receiverId: selectedUser?.id,
      typing: true
    });

    typingTimeout.current = setTimeout(() => {
      socketRef.current.emit('typing', {
        receiverId: selectedUser?.id,
        typing: false
      });
    }, 1000);
  };

  const renderMessage = (message) => {
    const isUserMessage = message.senderId === user.id;
    const isNotification = message.type === 'notification';

    return (
      <div key={message.id} className={`message ${isUserMessage ? 'sent' : 'received'} ${isNotification ? 'notification' : ''}`}>
        <div className="message-header">
          {!isUserMessage && !isNotification && (
            <span className="sender-name">
              {onlineUsers.find(u => u.id === message.senderId)?.name}
            </span>
          )}
          <span className="message-time">
            {formatDistanceToNow(new Date(message.timestamp), { addSuffix: true })}
          </span>
        </div>
        <div className="message-content">
          {message.content}
          {isNotification && (
            <button 
              className="details-btn"
              onClick={() => setNotificationDetails(message.meta)}
            >
              View Details
            </button>
          )}
        </div>
        {isUserMessage && (
          <div className="message-status">
            {message.read ? '✓✓' : '✓'}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="messaging-container">
      {connectionError && (
        <div className="connection-error">
          Connection lost. Trying to reconnect...
        </div>
      )}

      <div className="user-list-container">
        <h2 className="section-title">Online Agents</h2>
        <div className="user-list">
          {onlineUsers.map(user => (
            <div 
              key={user.id} 
              className={`user-card ${selectedUser?.id === user.id ? 'active' : ''}`}
              onClick={() => {
                setSelectedUser(user);
                setUnreadCounts(prev => ({ ...prev, [user.id]: 0 }));
              }}
            >
              <div className="user-avatar">
                <span>{user.name[0]}</span>
                <div className={`online-status ${user.online ? 'online' : 'offline'}`} />
              </div>
              <div className="user-info">
                <h3>{user.name}</h3>
                <p>{user.role}</p>
                {unreadCounts[user.id] > 0 && (
                  <span className="unread-count">{unreadCounts[user.id]}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="chat-container">
        {selectedUser ? (
          <>
            <div className="chat-header">
              <div className="user-info">
                <div className="avatar">{selectedUser.name[0]}</div>
                <div>
                  <h2>{selectedUser.name}</h2>
                  <p className="status">{isTyping ? 'Typing...' : 'Online'}</p>
                </div>
              </div>
            </div>

            <div className="messages-window">
              {messages.filter(m => 
                (m.senderId === selectedUser.id || m.receiverId === selectedUser.id) ||
                m.type === 'notification'
              ).map(renderMessage)}
              <div ref={messagesEndRef} />
            </div>

            <div className="message-input-container">
              <textarea
                value={inputMessage}
                onChange={handleTyping}
                placeholder="Type your message..."
                onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                disabled={connectionError}
              />
              <button 
                onClick={sendMessage} 
                disabled={!inputMessage.trim() || connectionError}
              >
                <span className="send-icon">➤</span>
              </button>
            </div>
          </>
        ) : (
          <div className="no-selection">
            <div className="welcome-message">
              <h1>Secure Messaging Platform</h1>
              <p>Select an agent to start communicating</p>
            </div>
          </div>
        )}
      </div>

      {notificationDetails && (
        <div className="notification-modal">
          <div className="modal-content">
            <button className="close-btn" onClick={() => setNotificationDetails(null)}>×</button>
            <h3>Alert Details</h3>
            <div className="detail-item">
              <label>Streamer:</label>
              <span>{notificationDetails.streamer_name || 'N/A'}</span>
            </div>
            <div className="detail-item">
              <label>Platform:</label>
              <span>{notificationDetails.platform || 'N/A'}</span>
            </div>
            <div className="detail-item">
              <label>Detections:</label>
              <div className="detection-list">
                {notificationDetails.detections?.map((det, i) => (
                  <span key={i} className="detection-tag">
                    {det.class} ({(det.confidence * 100).toFixed(1)}%)
                  </span>
                ))}
              </div>
            </div>
            {user.role === 'admin' && (
              <div className="detail-item">
                <label>Assigned Agent:</label>
                <span>{notificationDetails.assigned_agent || 'Unassigned'}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default MessageComponent;