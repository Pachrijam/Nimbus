# Nimbus

An interactive game prototype where you draw a drone route and compare it against Gemini's planned flight.

## How to play

- Visit the app in a browser and choose the camera input.
- Draw a route from the drone with one finger; lift your hand to launch.
- Hold up two or more fingers to start a new route or trigger autopilot.
- The browser keeps the route in memory while the mission is active.

## Free Draw

Press **P** or the pencil button for Free Draw. One raised index finger draws;
two or more raised fingers lift the pen and cycle its color once per gesture.
Use the browser's palette and Fine/Medium/Bold sizes to choose a pen, **U / Undo**
to remove the last stroke, or **C / Clear** to erase the canvas. **Esc**, **P**, or
**Back to game** resumes the paused mission. Ink stays when switching modes
and is cleared on reload. Game shortcuts R, N, and V are disabled in Free Draw.
Desktop Free Draw supports the same drawing/color gestures, C to clear, and
P or Esc to return to the game.

Hand tracking loads MediaPipe and its model from the internet and requires
HTTPS when deployed (localhost is allowed for development).

## Controls

- Start with the drone icon and then draw on the map.
- `R` retries the level.
- `N` continues to the next level.
- `V` toggles autopilot.
- `C` clears the current free-draw canvas.
- `P` toggles free draw.

## Development

This project includes a Python server, browser game logic, and browser tests.
