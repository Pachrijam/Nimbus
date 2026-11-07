# Nimbus: Flight Path (HackRPI 2026)

**Sketch a drone's route in the air with one finger. A physics simulation instantly shows whether the drone can actually fly it through the wind and around the storms.**

## Run
```
python -m pip install -r requirements.txt
python main.py
```
For hand tracking, put `hand_landmarker.task` in this folder. If it is missing or MediaPipe Tasks is unavailable, the app starts in mouse mode: move the cursor and hold the left mouse button to draw.

Keys: `q` quit · `p` Free Draw/Game · `m` mouse mode · `f` fullscreen · `r` retry · `n` next level · `v` autopilot view · `c` clear · `d` debug

## Browser version
The browser game is in `web/` and runs without a Python backend. To try it locally:
```
python -m http.server 8000 --directory web
```
Open `http://localhost:8000`. Mouse controls work immediately. Hand tracking asks permission to use the webcam and loads MediaPipe and its model in the browser; it requires `https` when deployed (localhost is allowed for development). Camera frames are processed locally and are not uploaded.

To serve it from the Vultr VPS, from the repository directory on the server:
```
sudo apt update
sudo apt install -y nginx
sudo cp -r web/. /var/www/html/
sudo systemctl enable --now nginx
```
Open `http://YOUR_SERVER_IP` for mouse play. Webcam access requires HTTPS: point a domain's DNS A record at the server, then install a certificate (for example, `sudo apt install -y certbot python3-certbot-nginx` followed by `sudo certbot --nginx -d your-domain.example`). After pushing updates, run `git pull` in the repository and repeat the copy command. The Python/OpenCV desktop app remains separate from this static browser version.

## Docs
- **[OVERVIEW.md](OVERVIEW.md):** the full project: problem, solution, tech, architecture, interfaces, demo
- **[STEPS.md](STEPS.md):** exactly what each person does, in order, with checkpoints

## Credits
Hand tracking: Google MediaPipe HandLandmarker. Built at HackRPI 2026 by Avyay, Paul and Person 3.
