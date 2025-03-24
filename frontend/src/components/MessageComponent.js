import React, { useState, useEffect, useRef } from 'react';
import io from 'socket.io-client';
import { FiSend, FiSmile, FiPaperclip } from 'react-icons/fi';

const SOCKET_SERVER_URL = 'http://localhost:5000';

const MessageComponent = ({ user }) => {
  const [onlineUsers, setOnlineUsers] = useState([]);
  const [messages, setMessages] = useState([]);
  const [currentMessage, setCurrentMessage] = useState('');
  const [typingStatus, setTypingStatus] = useState({});
  const messagesEndRef = useRef(null);
  const socketRef = useRef();

  useEffect(() => {
    socketRef.current = io(SOCKET_SERVER_URL, {
      withCredentials: true,
      transports: ['websocket'],
    });

    // Socket event listeners
    socketRef.current.on('online_users', setOnlineUsers);
    socketRef.current.on('receive_message', (message) => {
      setMessages(prev => [...prev, message]);
    });
    socketRef.current.on('typing', (data) => {
      setTypingStatus(prev => ({ ...prev, [data.sender_id]: data.typing }));
      setTimeout(() => {
        setTypingStatus(prev => ({ ...prev, [data.sender_id]: false }));
      }, 3000);
    });

    return () => socketRef.current.disconnect();
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(scrollToBottom, [messages]);

  const sendMessage = () => {
    if (!currentMessage.trim()) return;
    socketRef.current.emit('send_message', {
      receiver_id: 0, // Replace with dynamic receiver
      message: currentMessage,
    });
    setCurrentMessage('');
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex h-screen bg-gray-900 text-gray-100">
      {/* Online Users Sidebar */}
      <div className="w-64 bg-gray-800 p-4 border-r border-gray-700">
        <h2 className="text-xl font-bold mb-6 text-purple-400">Active Users</h2>
        <div className="space-y-3">
          {onlineUsers.map(uid => (
            <div key={uid} className="flex items-center space-x-3 hover:bg-gray-700 p-2 rounded-lg">
              <div className="relative">
                <div className="w-10 h-10 bg-gray-600 rounded-full flex items-center justify-center">
                  <span className="text-sm">U{uid.slice(-2)}</span>
                </div>
                <div className="absolute bottom-0 right-0 w-3 h-3 bg-green-500 rounded-full border-2 border-gray-800"></div>
              </div>
              <div>
                <p className="font-medium">User {uid}</p>
                <p className="text-xs text-gray-400">Online</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-gradient-to-b from-gray-900 to-gray-800">
          {messages.map((msg, index) => (
            <div key={index} className={`flex ${msg.sender_id === user.id ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-md p-4 rounded-2xl ${
                msg.sender_id === user.id 
                  ? 'bg-purple-600 rounded-br-none'
                  : 'bg-gray-700 rounded-bl-none'
              }`}>
                {msg.system ? (
                  <div className="text-sm text-gray-300 italic">
                    🔔 System: {msg.details?.message}
                  </div>
                ) : (
                  <p className="text-gray-100">{msg.message}</p>
                )}
                <div className="mt-2 text-xs text-gray-300 opacity-70">
                  {new Date(msg.timestamp).toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Typing Indicator */}
        {Object.values(typingStatus).some(Boolean) && (
          <div className="px-6 py-2 text-sm text-gray-400 italic">
            {Object.keys(typingStatus).filter(k => typingStatus[k]).join(', ')} is typing...
          </div>
        )}

        {/* Message Input */}
        <div className="p-6 border-t border-gray-700">
          <div className="flex items-center space-x-4 bg-gray-800 rounded-xl p-4">
            <button className="text-gray-400 hover:text-purple-400 p-2">
              <FiSmile size={24} />
            </button>
            <button className="text-gray-400 hover:text-purple-400 p-2">
              <FiPaperclip size={24} />
            </button>
            <textarea
              value={currentMessage}
              onChange={(e) => setCurrentMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Write your message..."
              className="flex-1 bg-transparent resize-none outline-none text-gray-100 placeholder-gray-500"
              rows="1"
            />
            <button 
              onClick={sendMessage}
              className="bg-purple-600 hover:bg-purple-700 p-3 rounded-xl text-white transition-colors"
            >
              <FiSend size={20} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MessageComponent;