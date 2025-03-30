import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { formatDistanceToNow } from 'date-fns';
import './MessageComponent.css';

const Sidebar = ({ user, onlineUsers, selectedUser, setSelectedUser, unreadCounts }) => {
  return (
    <div className="user-list-container">
      <h2 className="section-title">Online Users</h2>
      <div className="user-list">
        {onlineUsers.map(u => (
          <div 
            key={u.id} 
            className={`user-card ${selectedUser?.id === u.id ? 'active' : ''}`}
            onClick={() => {
              setSelectedUser(u);
              if (unreadCounts[u.id]) {
                unreadCounts[u.id] = 0;
              }
            }}
          >
            <div className="user-avatar">
              <span>{u.username[0]}</span>
              <div className={`online-status ${u.online ? 'online' : 'offline'}`} />
            </div>
            <div className="user-info">
              <h3>{u.username}</h3>
              <p>{u.role}</p>
              {unreadCounts[u.id] > 0 && (
                <span className="unread-count">{unreadCounts[u.id]}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const MessageBubble = ({ message, isUserMessage, onlineUsers, setNotificationDetails }) => {
  const renderDetailsButton = () => {
    if (!message.details) return null;
    
    return (
      <button 
        className="details-btn"
        onClick={() => setNotificationDetails(message.details)}
      >
        View Alert Details
      </button>
    );
  };

  return (
    <div className={`message ${isUserMessage ? 'sent' : 'received'} ${message.is_system ? 'system' : ''}`}>
      {message.is_system ? (
        <div className="system-message">
          <div className="message-content">
            {message.message}
            {renderDetailsButton()}
          </div>
          <span className="message-time">
            {formatDistanceToNow(new Date(message.timestamp), { addSuffix: true })}
          </span>
        </div>
      ) : (
        <>
          <div className="message-header">
            {!isUserMessage && (
              <span className="sender-name">
                {onlineUsers.find(u => u.id === message.sender_id)?.username}
              </span>
            )}
            <span className="message-time">
              {formatDistanceToNow(new Date(message.timestamp), { addSuffix: true })}
            </span>
          </div>
          <div className="message-content">
            {message.message}
          </div>
          {isUserMessage && (
            <div className="message-status">
              {message.read ? '✓✓' : '✓'}
            </div>
          )}
        </>
      )}
    </div>
  );
};

const MessageInput = ({ inputMessage, sendMessage, handleInputChange }) => {
  return (
    <div className="message-input-container">
      <textarea
        value={inputMessage}
        onChange={handleInputChange}
        placeholder="Type your message..."
        onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
      />
      <button onClick={sendMessage} disabled={!inputMessage.trim()}>
        Send
      </button>
    </div>
  );
};

const NotificationModal = ({ notificationDetails, closeModal }) => {
  if (!notificationDetails) return null;

  const renderContent = () => {
    if (!notificationDetails) return null;

    switch(notificationDetails.event_type) {
      case 'object_detection':
        return (
          <>
            <div className="image-preview">
              {notificationDetails.annotated_image && (
                <img 
                  src={`data:image/jpeg;base64,${notificationDetails.annotated_image}`} 
                  alt="Annotated detection"
                />
              )}
            </div>
            <div className="detection-list">
              {notificationDetails.detections?.map((det, i) => (
                <div key={i} className="detection-item">
                  <span>{det.class}</span>
                  <span className="confidence">
                    {(det.confidence * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          </>
        );
      case 'chat_detection':
        return (
          <>
            <div className="keywords-list">
              {notificationDetails.keywords?.map((kw, i) => (
                <span key={i} className="keyword-tag">{kw}</span>
              ))}
            </div>
            <div className="chat-messages">
              {notificationDetails.messages?.map((msg, i) => (
                <div key={i} className="chat-message">
                  <span className="sender">{msg.sender}:</span>
                  <span className="content">{msg.message}</span>
                </div>
              ))}
            </div>
          </>
        );
      case 'audio_detection':
        return (
          <>
            <div className="keyword">{notificationDetails.keyword}</div>
            <div className="transcript">{notificationDetails.transcript}</div>
          </>
        );
      default:
        return <div>{JSON.stringify(notificationDetails)}</div>;
    }
  };

  return (
    <div className="notification-modal">
      <div className="modal-content">
        <button className="close-btn" onClick={closeModal}>×</button>
        <h3>Alert Details</h3>
        <div className="meta-info">
          <div>Platform: {notificationDetails.platform}</div>
          <div>Streamer: {notificationDetails.streamer}</div>
          <div>Time: {new Date(notificationDetails.timestamp).toLocaleString()}</div>
        </div>
        <div className="alert-content">
          {renderContent()}
        </div>
      </div>
    </div>
  );
};

const MessageComponent = ({ user }) => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [onlineUsers, setOnlineUsers] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [unreadCounts, setUnreadCounts] = useState({});
  const [notificationDetails, setNotificationDetails] = useState(null);
  const pollingInterval = useRef();

  const fetchMessages = async (receiverId) => {
    try {
      const res = await axios.get(`/api/messages/${receiverId}`);
      if (res.data) {
        setMessages(res.data);
      }
    } catch (error) {
      console.error('Error fetching messages:', error);
    }
  };

  const fetchOnlineUsers = async () => {
    try {
      const res = await axios.get('/api/online-users');
      setOnlineUsers(res.data);
    } catch (error) {
      console.error('Error fetching online users:', error);
    }
  };

  const sendMessage = async () => {
    const content = inputMessage.trim();
    if (!content || !selectedUser) return;

    try {
      await axios.post('/api/messages', {
        receiver_id: selectedUser.id,
        message: content
      });
      setInputMessage('');
      fetchMessages(selectedUser.id);
    } catch (error) {
      console.error('Message send error:', error);
    }
  };

  const markMessagesAsRead = async (messageIds) => {
    try {
      await axios.put('/api/messages/mark-read', { messageIds });
    } catch (error) {
      console.error('Error marking messages as read:', error);
    }
  };

  useEffect(() => {
    const startPolling = () => {
      fetchOnlineUsers();
      if (selectedUser) fetchMessages(selectedUser.id);
      pollingInterval.current = setInterval(() => {
        fetchOnlineUsers();
        if (selectedUser) fetchMessages(selectedUser.id);
      }, 10000); // Poll every 10 seconds
    };

    startPolling();
    return () => clearInterval(pollingInterval.current);
  }, [selectedUser]);

  useEffect(() => {
    const calculateUnreads = () => {
      const counts = {};
      messages.forEach(msg => {
        if (!msg.read && msg.sender_id !== user.id) {
          counts[msg.sender_id] = (counts[msg.sender_id] || 0) + 1;
        }
      });
      setUnreadCounts(counts);
    };
    calculateUnreads();
  }, [messages, user.id]);

  useEffect(() => {
    const markAsRead = async () => {
      const unreadIds = messages
        .filter(msg => !msg.read && msg.sender_id === selectedUser?.id)
        .map(msg => msg.id);

      if (unreadIds.length > 0) {
        await markMessagesAsRead(unreadIds);
        fetchMessages(selectedUser.id);
      }
    };

    if (selectedUser) markAsRead();
  }, [messages, selectedUser]);

  return (
    <div className="messaging-container">
      <Sidebar 
        user={user}
        onlineUsers={onlineUsers}
        selectedUser={selectedUser}
        setSelectedUser={setSelectedUser}
        unreadCounts={unreadCounts}
      />

      <div className="chat-container">
        {selectedUser ? (
          <>
            <div className="chat-header">
              <div className="user-info">
                <div className="avatar">{selectedUser.username[0]}</div>
                <div>
                  <h2>{selectedUser.username}</h2>
                  <p className="status">
                    {onlineUsers.find(u => u.id === selectedUser.id)?.online ? 'Online' : 'Offline'}
                  </p>
                </div>
              </div>
            </div>
            
            <div className="messages-window">
              {messages.map(message => (
                <MessageBubble 
                  key={message.id}
                  message={message}
                  isUserMessage={message.sender_id === user.id}
                  onlineUsers={onlineUsers}
                  setNotificationDetails={setNotificationDetails}
                />
              ))}
            </div>

            <MessageInput 
              inputMessage={inputMessage}
              sendMessage={sendMessage}
              handleInputChange={(e) => setInputMessage(e.target.value)}
            />
          </>
        ) : (
          <div className="no-selection">
            <div className="welcome-message">
              <h1>Secure Messaging Platform</h1>
              <p>Select a user to start communicating</p>
            </div>
          </div>
        )}
      </div>

      <NotificationModal 
        notificationDetails={notificationDetails}
        closeModal={() => setNotificationDetails(null)}
      />
    </div>
  );
};

export default MessageComponent;