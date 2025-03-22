import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';

// URL for your Socket.IO backend (adjust as needed)
const SOCKET_SERVER_URL = 'http://localhost:5000';

const MessageComponent = ({ user, isAdmin }) => {
  const [onlineUsers, setOnlineUsers] = useState([]);
  const [messages, setMessages] = useState([]); // All chat messages
  const [currentMessage, setCurrentMessage] = useState('');
  const [typingStatus, setTypingStatus] = useState({});
  // State to store forwarding alert details (for admin)
  const [forwardAlertData, setForwardAlertData] = useState({ alertId: '', agentId: '' });
  const socketRef = useRef();

  useEffect(() => {
    // Establish connection to the Socket.IO backend.
    socketRef.current = io(SOCKET_SERVER_URL, {
      withCredentials: true,
    });

    // Listen for updated online users list.
    socketRef.current.on('online_users', (users) => {
      setOnlineUsers(users);
    });

    // Listen for incoming messages.
    socketRef.current.on('receive_message', (message) => {
      setMessages((prev) => [...prev, message]);
    });

    // Listen for typing events.
    socketRef.current.on('typing', (data) => {
      setTypingStatus((prev) => ({ ...prev, [data.sender_id]: data.typing }));
      // Auto-clear typing indicator after 3 seconds.
      setTimeout(() => {
        setTypingStatus((prev) => ({ ...prev, [data.sender_id]: false }));
      }, 3000);
    });

    // Listen for forwarded alert confirmation (admin feedback).
    socketRef.current.on('forward_confirmation', (data) => {
      alert(data.message);
    });

    // Listen for forwarded alert notifications (agent receives forwarded alert).
    socketRef.current.on('forwarded_alert', (data) => {
      setMessages((prev) => [
        ...prev,
        {
          system: true,
          event_type: data.event_type,
          details: data.details,
          room_url: data.room_url,
        },
      ]);
    });

    return () => {
      socketRef.current.disconnect();
    };
  }, []);

  // Send a message to the specified receiver.
  const sendMessage = (receiverId) => {
    if (!currentMessage.trim()) return;
    socketRef.current.emit('send_message', {
      receiver_id: receiverId,
      message: currentMessage,
    });
    setCurrentMessage('');
  };

  // Notify the backend that the user is typing.
  const handleTyping = (receiverId) => {
    socketRef.current.emit('typing', { receiver_id: receiverId, typing: true });
  };

  // Admin event: forward a detection alert and assign an agent.
  const forwardAlert = () => {
    const { alertId, agentId } = forwardAlertData;
    if (!alertId || !agentId) {
      alert('Please provide both Alert ID and Agent ID');
      return;
    }
    socketRef.current.emit('forward_alert', { alert_id: alertId, agent_id: agentId });
  };

  return (
    <div style={styles.container}>
      <h2 style={styles.heading}>Realtime Messaging</h2>
      <div style={styles.contentContainer}>
        {/* Sidebar with online users and alert forwarding (admin only) */}
        <div style={styles.sidebar}>
          <h3 style={styles.subHeading}>Online Users</h3>
          <ul style={styles.userList}>
            {onlineUsers.map((uid) => (
              <li key={uid} style={styles.userListItem}>
                User ID: {uid}
              </li>
            ))}
          </ul>
          {isAdmin && (
            <div style={styles.forwardContainer}>
              <h3 style={styles.subHeading}>Forward Alert</h3>
              <div style={styles.formGroup}>
                <input
                  type="number"
                  placeholder="Alert ID"
                  value={forwardAlertData.alertId}
                  onChange={(e) =>
                    setForwardAlertData({ ...forwardAlertData, alertId: e.target.value })
                  }
                  style={styles.input}
                />
              </div>
              <div style={styles.formGroup}>
                <input
                  type="number"
                  placeholder="Agent ID"
                  value={forwardAlertData.agentId}
                  onChange={(e) =>
                    setForwardAlertData({ ...forwardAlertData, agentId: e.target.value })
                  }
                  style={styles.input}
                />
              </div>
              <button onClick={forwardAlert} style={styles.button}>
                Forward
              </button>
            </div>
          )}
        </div>

        {/* Main Chat Area */}
        <div style={styles.chatArea}>
          <div style={styles.messages}>
            {messages.map((msg, index) => (
              <div
                key={index}
                style={
                  msg.system
                    ? styles.systemMessage
                    : msg.sender_id === user.id
                    ? styles.sentMessage
                    : styles.receivedMessage
                }
              >
                {msg.system ? (
                  <em>
                    Alert: {msg.event_type} -{' '}
                    {msg.details ? JSON.stringify(msg.details) : ''}
                  </em>
                ) : (
                  <p>
                    <strong>
                      {msg.sender_id === user.id ? 'You' : `User ${msg.sender_id}`}:{' '}
                    </strong>
                    {msg.message}
                  </p>
                )}
              </div>
            ))}
          </div>
          <div style={styles.typingIndicator}>
            {Object.entries(typingStatus).map(
              ([sender, typing]) =>
                typing &&
                sender !== String(user.id) && (
                  <p key={sender} style={styles.typingText}>
                    User {sender} is typing...
                  </p>
                )
            )}
          </div>
          <div style={styles.inputContainer}>
            <input
              type="text"
              placeholder="Type a message..."
              value={currentMessage}
              onChange={(e) => setCurrentMessage(e.target.value)}
              onKeyPress={() => handleTyping(0)} // Replace with dynamic receiver if needed
              style={styles.input}
            />
            <button onClick={() => sendMessage(0)} style={styles.button}>
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// Inline styles that follow the app's dark theme and design.
const styles = {
  container: {
    background: '#121212',
    color: '#e0e0e0',
    padding: '20px',
    fontFamily: 'Inter, sans-serif',
    borderRadius: '8px',
    maxWidth: '1000px',
    margin: '20px auto',
  },
  heading: {
    textAlign: 'center',
    marginBottom: '20px',
  },
  contentContainer: {
    display: 'flex',
    gap: '20px',
    flexWrap: 'wrap',
  },
  sidebar: {
    flex: '1 1 250px',
    background: '#1a1a1a',
    padding: '15px',
    borderRadius: '8px',
    border: '1px solid #2d2d2d',
  },
  subHeading: {
    marginBottom: '10px',
    fontSize: '1.1rem',
  },
  userList: {
    listStyleType: 'none',
    padding: 0,
    margin: 0,
  },
  userListItem: {
    padding: '5px 0',
    borderBottom: '1px solid #2d2d2d',
  },
  forwardContainer: {
    marginTop: '20px',
    paddingTop: '10px',
    borderTop: '1px solid #2d2d2d',
  },
  formGroup: {
    marginBottom: '10px',
  },
  chatArea: {
    flex: '2 1 500px',
    display: 'flex',
    flexDirection: 'column',
    background: '#1a1a1a',
    padding: '15px',
    borderRadius: '8px',
    border: '1px solid #2d2d2d',
  },
  messages: {
    flex: 1,
    overflowY: 'auto',
    padding: '10px',
    background: '#121212',
    borderRadius: '4px',
    border: '1px solid #2d2d2d',
    marginBottom: '10px',
    maxHeight: '400px',
  },
  sentMessage: {
    background: '#2d2d2d',
    padding: '8px',
    margin: '5px 0',
    borderRadius: '8px',
    alignSelf: 'flex-end',
    maxWidth: '80%',
  },
  receivedMessage: {
    background: '#333',
    padding: '8px',
    margin: '5px 0',
    borderRadius: '8px',
    alignSelf: 'flex-start',
    maxWidth: '80%',
  },
  systemMessage: {
    textAlign: 'center',
    fontStyle: 'italic',
    margin: '5px 0',
    color: '#a0a0a0',
  },
  typingIndicator: {
    minHeight: '20px',
    marginBottom: '10px',
  },
  typingText: {
    fontSize: '0.9rem',
    color: '#888',
  },
  inputContainer: {
    display: 'flex',
    gap: '10px',
  },
  input: {
    flex: 1,
    padding: '10px',
    borderRadius: '4px',
    border: '1px solid #2d2d2d',
    background: '#121212',
    color: '#e0e0e0',
  },
  button: {
    padding: '10px 15px',
    background: '#007bff',
    color: '#fff',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontWeight: '500',
  },
};

export default MessageComponent;
