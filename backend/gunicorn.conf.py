[Unit]
Description=Gunicorn instance to serve my Flask app with SSL
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/stream-AI-object-audio-chat-detection/backend

# Use the gunicorn executable from the specified virtual environment
# Added --certfile and --keyfile options to enable SSL.
ExecStart=/opt/pytorch/bin/gunicorn --workers 12 --bind 0.0.0.0:5000 --certfile /home/ec2-user/certs/fullchain2.pem --keyfile /home/ec2-user/certs/privkey2.pem main:app

Restart=always
RestartSec=3
KillMode=process
TimeoutStartSec=30
LimitNOFILE=4096

# Set environment variables:
# - VIRTUAL_ENV points to the root of your virtual environment.
# - PATH is updated to prioritize the virtual environment's binaries.
Environment=VIRTUAL_ENV=/source/opt/pytorch
Environment=PATH=/source/opt/pytorch/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

[Install]
WantedBy=multi-user.target
