#!/usr/bin/env python3
"""
Obsidian → Splunky Brewster Blog Publisher

Converts an Obsidian note to a Jekyll blog post:
- Uploads videos to YouTube (playlist optional)
- Copies images to the blog repo
- Converts Obsidian embeds to HTML/markdown
- Pushes to GitHub
"""

import os
import re
import sys
import json
import shutil
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load env from ML_Social project for YouTube credentials
load_dotenv("/mnt/c/Users/jenas/dev/ML_Social/.env")

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Paths
VAULT_PATH = Path("/mnt/c/Users/jenas/OneDrive/Documents/Obsidian Vault")
ATTACHMENTS_PATH = VAULT_PATH / "attachments"
BLOG_REPO = Path("/mnt/c/Users/jenas/dev/splunkybrewster")
BLOG_POSTS = BLOG_REPO / "_posts"
BLOG_MEDIA = BLOG_REPO / "assets" / "media"
TOKEN_FILE = BLOG_REPO / "temp" / "youtube_token.json"

# YouTube playlist for blog videos
DEFAULT_PLAYLIST = "Splunky Brewster Blog"


def find_note(name):
    """Find an Obsidian note by name (searches recursively)."""
    for md in VAULT_PATH.rglob("*.md"):
        if md.stem.lower() == name.lower() or md.name.lower() == name.lower():
            return md
    # Try partial match
    for md in VAULT_PATH.rglob("*.md"):
        if name.lower() in md.stem.lower():
            return md
    return None


def find_attachment(name):
    """Find an attachment file in the vault."""
    # Check attachments folder first
    for f in ATTACHMENTS_PATH.rglob(name):
        return f
    # Check entire vault
    for f in VAULT_PATH.rglob(name):
        if ".obsidian" not in str(f):
            return f
    return None


def upload_to_youtube(video_path, title, description="", tags=None, privacy="unlisted", playlist_name=None):
    """Upload a video to YouTube and return the video ID."""
    try:
        import googleapiclient.discovery
        import googleapiclient.errors
        import googleapiclient.http
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        client_id = os.getenv("YOUTUBE_CLIENT_ID")
        project_id = os.getenv("YOUTUBE_PROJECT_ID")
        client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")

        if not all([client_id, project_id, client_secret]):
            logger.error("Missing YouTube credentials in .env")
            return None

        client_secrets = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
            }
        }

        scopes = [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube"
        ]

        # Create temp directory for credentials
        TOKEN_FILE.parent.mkdir(exist_ok=True)
        creds_file = TOKEN_FILE.parent / "youtube_credentials.json"

        with open(creds_file, "w") as f:
            json.dump(client_secrets, f)

        # Handle authentication
        creds = None
        if TOKEN_FILE.exists():
            with open(TOKEN_FILE, "r") as token:
                creds = Credentials.from_authorized_user_info(json.load(token), scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("Refreshing YouTube token...")
                creds.refresh(Request())
            else:
                logger.info("YouTube OAuth: authenticating...")
                flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), scopes)
                try:
                    creds = flow.run_local_server(port=0, open_browser=False)
                except Exception:
                    # Fallback for environments without browser
                    creds = flow.run_console()

            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())

        youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)

        video_metadata = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": "28"
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False
            }
        }

        media_file = googleapiclient.http.MediaFileUpload(
            str(video_path),
            mimetype="video/*",
            resumable=True
        )

        logger.info(f"Uploading {video_path.name} to YouTube...")
        request = youtube.videos().insert(
            part="snippet,status",
            body=video_metadata,
            media_body=media_file
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"  Upload progress: {int(status.progress() * 100)}%")

        video_id = response["id"]
        logger.info(f"  Uploaded: https://www.youtube.com/watch?v={video_id}")

        # Add to playlist if specified
        if playlist_name:
            try:
                # Find or create playlist
                playlists = youtube.playlists().list(part="snippet", mine=True, maxResults=50).execute()
                playlist_id = None
                for p in playlists.get("items", []):
                    if p["snippet"]["title"].lower() == playlist_name.lower():
                        playlist_id = p["id"]
                        break

                if not playlist_id:
                    logger.info(f"  Creating playlist: {playlist_name}")
                    pl = youtube.playlists().insert(
                        part="snippet,status",
                        body={
                            "snippet": {"title": playlist_name, "description": "Videos from splunkybrewster.com"},
                            "status": {"privacyStatus": "public"}
                        }
                    ).execute()
                    playlist_id = pl["id"]

                youtube.playlistItems().insert(
                    part="snippet",
                    body={
                        "snippet": {
                            "playlistId": playlist_id,
                            "resourceId": {"kind": "youtube#video", "videoId": video_id}
                        }
                    }
                ).execute()
                logger.info(f"  Added to playlist: {playlist_name}")
            except Exception as e:
                logger.warning(f"  Could not add to playlist: {e}")

        return video_id

    except Exception as e:
        logger.error(f"YouTube upload failed: {e}")
        return None


def convert_note_to_post(note_path, upload_videos=True, youtube_playlist=DEFAULT_PLAYLIST):
    """Convert an Obsidian note to a Jekyll blog post."""
    content = note_path.read_text(encoding="utf-8")

    # Parse frontmatter
    fm_match = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
    if not fm_match:
        logger.error("No frontmatter found in note")
        return None

    frontmatter = fm_match.group(1)
    body = fm_match.group(2)

    # Extract title and slug from frontmatter
    title_match = re.search(r"^title:\s*(.+)$", frontmatter, re.MULTILINE)
    slug_match = re.search(r"^slug:\s*(.+)$", frontmatter, re.MULTILINE)
    tags_match = re.findall(r"^\s+-\s+(.+)$", frontmatter, re.MULTILINE)

    title = title_match.group(1).strip().strip('"') if title_match else note_path.stem
    slug = slug_match.group(1).strip() if slug_match else None

    if not slug:
        logger.error("No slug in frontmatter. Apply the blog-post template first.")
        return None

    # Process video embeds: ![[video.mp4]]
    video_pattern = r"!\[\[([^\]]+\.mp4)\]\]"
    for match in re.finditer(video_pattern, body):
        video_name = match.group(1)
        video_file = find_attachment(video_name)

        if not video_file:
            logger.warning(f"Video not found: {video_name}")
            body = body.replace(match.group(0), f"<!-- Video not found: {video_name} -->")
            continue

        if upload_videos:
            video_id = upload_to_youtube(
                video_file,
                title=title,
                description=f"From: https://splunkybrewster.com\n\n{title}",
                tags=tags_match if tags_match else [],
                privacy="unlisted",
                playlist_name=youtube_playlist
            )
            if video_id:
                embed = f'<div class="video-embed">\n<iframe width="100%" height="400" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>\n</div>'
                body = body.replace(match.group(0), embed)
            else:
                # Fallback: copy video to repo
                dest = BLOG_MEDIA / video_file.name.replace(" ", "-").lower()
                shutil.copy2(video_file, dest)
                embed = f'<video controls width="100%" preload="metadata">\n  <source src="/assets/media/{dest.name}" type="video/mp4">\n</video>'
                body = body.replace(match.group(0), embed)
        else:
            # No upload — copy to repo
            dest = BLOG_MEDIA / video_file.name.replace(" ", "-").lower()
            shutil.copy2(video_file, dest)
            embed = f'<video controls width="100%" preload="metadata">\n  <source src="/assets/media/{dest.name}" type="video/mp4">\n</video>'
            body = body.replace(match.group(0), embed)

    # Process image embeds: ![[image.png]]
    image_pattern = r"!\[\[([^\]]+\.(?:png|jpg|jpeg|gif|webp|svg))\]\]"
    for match in re.finditer(image_pattern, body):
        image_name = match.group(1)
        image_file = find_attachment(image_name)

        if not image_file:
            logger.warning(f"Image not found: {image_name}")
            body = body.replace(match.group(0), f"<!-- Image not found: {image_name} -->")
            continue

        dest_name = image_file.name.replace(" ", "-").lower()
        dest = BLOG_MEDIA / dest_name
        shutil.copy2(image_file, dest)
        alt = image_file.stem.replace("-", " ").replace("_", " ")
        body = body.replace(match.group(0), f"![{alt}](/assets/media/{dest_name})")
        logger.info(f"  Copied image: {dest_name}")

    # Process wikilinks: [[Note Name]] → plain text
    body = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", body)  # [[note|display]] → display
    body = re.sub(r"\[\[([^\]]+)\]\]", r"\1", body)  # [[note]] → note

    # Build final post
    post_content = f"---\n{frontmatter}\n---\n{body}"
    post_filename = f"{slug}.md"
    post_path = BLOG_POSTS / post_filename

    post_path.write_text(post_content, encoding="utf-8")
    logger.info(f"  Created: _posts/{post_filename}")

    return post_path


def git_push(post_path, message=None):
    """Stage, commit, and push changes."""
    os.chdir(BLOG_REPO)

    # Stage the post and any new media
    subprocess.run(["git", "add", str(post_path.relative_to(BLOG_REPO))], check=True)
    subprocess.run(["git", "add", "assets/media/"], check=True)

    if not message:
        message = f"Publish: {post_path.stem}"

    subprocess.run(["git", "commit", "-m", message], check=True)
    subprocess.run(["git", "push", "origin", "main"], check=True)
    logger.info("  Pushed to GitHub")


def publish(note_name, upload_videos=True, youtube_playlist=DEFAULT_PLAYLIST, push=True):
    """Main publish function."""
    logger.info(f"\n--- Publishing: {note_name} ---\n")

    # Find the note
    note_path = find_note(note_name)
    if not note_path:
        logger.error(f"Note not found: {note_name}")
        return False

    logger.info(f"Found: {note_path.relative_to(VAULT_PATH)}")

    # Check for share: true
    content = note_path.read_text(encoding="utf-8")
    if "share: true" not in content:
        logger.error("Note doesn't have 'share: true' in frontmatter. Not publishing.")
        return False

    # Convert and process
    post_path = convert_note_to_post(note_path, upload_videos=upload_videos, youtube_playlist=youtube_playlist)
    if not post_path:
        return False

    # Push to GitHub
    if push:
        git_push(post_path)
        logger.info(f"\nPublished! Check the site in a minute.")
    else:
        logger.info(f"\nPost created at {post_path} (not pushed)")

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python publish.py <note-name> [--no-video] [--no-push] [--playlist 'Name']")
        print()
        print("Examples:")
        print("  python publish.py 'Threat Detection Automation'")
        print("  python publish.py 'Threat Detection Automation' --no-video")
        print("  python publish.py 'Threat Detection Automation' --playlist 'My Playlist'")
        sys.exit(1)

    note_name = sys.argv[1]
    upload_videos = "--no-video" not in sys.argv
    push = "--no-push" not in sys.argv

    playlist = DEFAULT_PLAYLIST
    if "--playlist" in sys.argv:
        idx = sys.argv.index("--playlist")
        if idx + 1 < len(sys.argv):
            playlist = sys.argv[idx + 1]

    success = publish(note_name, upload_videos=upload_videos, youtube_playlist=playlist, push=push)
    sys.exit(0 if success else 1)
