@echo off
REM Run as Administrator. Opens the receiver port on private networks.
set PORT=8765
netsh advfirewall firewall add rule name="BarScan Receiver" dir=in action=allow protocol=TCP localport=%PORT% profile=private
pause
