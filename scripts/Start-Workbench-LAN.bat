@echo off
rem SuperBrain Workbench LAN launcher (ASCII only, CRLF)
rem Phone must join the SAME Wi-Fi as this PC.
rem No auth: trusted home network only. Close when done.
cd /d "%~dp0"
python sb_workbench.py --host 0.0.0.0
pause
