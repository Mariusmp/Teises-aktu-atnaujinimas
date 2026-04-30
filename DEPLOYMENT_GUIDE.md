# Docker Deployment Guide (GHCR to NAS)

This guide explains how to connect your NAS to the GitHub Container Registry (GHCR) to pull and run the automated application directly.

## 1. Create a Personal Access Token (PAT)
Since GitHub Packages (GHCR) images are private by default, your NAS needs a token to pull the image:
1. Go to your GitHub account **Settings** -> **Developer settings** -> **Personal access tokens (Classic)**.
2. Click **Generate new token (classic)**.
3. Give it a descriptive name (e.g., "NAS GHCR Pull").
4. Under **Select scopes**, check the box for `read:packages`.
5. Click **Generate token** and **copy it immediately** (you won't see it again).

## 2. Connect NAS to GHCR
1. Open **Container Manager** (or Docker) on your NAS.
2. Go to the **Registry** section and click **Settings**.
3. Click **Add** to add a new registry:
   - **Registry Name:** GHCR
   - **Registry URL:** `https://ghcr.io`
   - Check **Enable authentication**.
   - **Username:** Your GitHub username.
   - **Password:** Paste the PAT you generated in Step 1.
4. Click **Apply** or **OK** to save.

## 3. Pull and Run the Image
1. Still in the **Registry** section, search for your image using your repository name (e.g., `<your-github-username>/<repo-name>`).
2. Right-click the image and select **Download** (choose the `main` or `latest` tag).
3. Once downloaded, go to the **Image** tab, select the image, and click **Run** to create a container.
4. **Important Settings during setup:**
   - **Port Settings:** Map the container port `8000` to a local port on your NAS (e.g., `8000`).
   - **Environment Variables:** You can optionally configure the auto-update schedule by modifying `CRON_DAY`, `CRON_HOUR`, and `CRON_MINUTE` (defaults are `1`, `9`, `0` for the 1st of the month at 9:00 AM).
5. Start the container and access the application via `http://<NAS_IP>:<MAPPED_PORT>`.
