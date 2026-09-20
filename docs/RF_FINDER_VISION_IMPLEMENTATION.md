# RF Finder Vision implementation

This milestone adds the server-side foundation for the Camera & Audio workspace without pretending that hardware is connected.

## Implemented now

- Authenticated camera registry backed by the existing RF Finder SQLite database.
- Camera metadata supports RTSP, RTSPS, and ONVIF configuration.
- Camera passwords are not stored in SQLite, returned to the browser, or embedded in URLs.
- Local deployments use the environment variable RF_FINDER_CAMERA_<ID>_PASSWORD for the camera password.
- Timestamp-only RF/audio/video correlation is implemented as a separate event model.
- Correlation preserves event provenance and explicitly states that temporal correlation is not causal attribution.
- The existing Spectrum Analyzer remains the only source of RF measurements. Camera video/audio can never create an RF detection.
- Static GitHub Pages remains a UI/documentation surface; private RTSP credentials and camera streams must be brokered by the authenticated local/backend service.

## Camera setup

1. Connect the IP camera and Windows PC to the same LAN.
2. Give the camera a stable LAN address or DHCP reservation.
3. Enable RTSP/ONVIF on the camera if supported.
4. Register the camera through the authenticated RF Finder API.
5. Store its password only in the local backend environment using the generated camera ID.
6. A deployment-specific video broker is then required to convert the private camera stream to a browser-compatible transport such as WebRTC or HLS.

The current milestone intentionally stops before claiming a live camera feed. The camera model and stream format determine the correct broker/adapter.

## RF provenance

SIMULATED remains demo/test data. IMPORTED_MEASUREMENT and LIVE_MEASUREMENT are measurement provenance states. Camera connection state never changes an RF record's provenance.

## Example camera registration

POST /api/cameras
Authorization: Bearer <session-token>
Content-Type: application/json

{
  "name": "Field Camera 01",
  "host": "192.168.1.50",
  "port": 554,
  "protocol": "rtsp",
  "username": "operator",
  "audio_enabled": true
}

The API response intentionally omits a password and credentialed RTSP URL.
