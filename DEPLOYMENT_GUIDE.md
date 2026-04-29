# Docker Deployment Guide for NAS

This guide explains how to build the application as a Docker image locally, export it, and import it into your NAS Container Manager.

## 1. Build the Docker Image Locally
Open your terminal, navigate to the project directory containing the `Dockerfile`, and run:
```bash
docker build -t ta-update-web .
```

## 2. Export the Image to a .tar File
Once the build finishes, export the image into an archive file that you can transfer to your NAS:
```bash
docker save -o ta-update-web.tar ta-update-web
```

## 3. Import into NAS Container Manager
1. Transfer the `ta-update-web.tar` file to your NAS (via SMB, AFP, or File Station).
2. Open **Container Manager** (or Docker UI) on your NAS.
3. Go to the **Image** section.
4. Click **Action** -> **Import** (or **Add** -> **Add from file**).
5. Select the `ta-update-web.tar` file you uploaded.
6. Once imported, select the image and click **Run** to create a container.
7. **Important Settings during setup:**
   - **Port Settings:** Map the container port `8000` to a local port on your NAS (e.g., `8000`).
   - **Environment Variables:** You can optionally configure the auto-update schedule by modifying `CRON_DAY`, `CRON_HOUR`, and `CRON_MINUTE` (defaults are `1`, `9`, `0` for the 1st of the month at 9:00 AM).
8. Start the container and access the application via `http://<NAS_IP>:<MAPPED_PORT>`.
