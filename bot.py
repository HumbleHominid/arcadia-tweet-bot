#!/usr/arcadia_tweet_bot/venv/bin/python4.11
# ---------------------
# Arcadia Twitter Bot
#
# Author: HumbleHominid
# ---------------------
import os
import json
import httpx
from google.oauth2 import service_account
import googleapiclient.discovery
import tweepy
import atproto
from atproto import client_utils, IdResolver, models
import requests
import xml.etree.ElementTree as ET
import isodate
from datetime import datetime, timezone
from enum import Enum

# Twitter API credentials
from social_secrets import *

# Arcadia members info
from arcadia_members import ARCADIA_MEMBERS

class Platforms(Enum):
    Twitter = 'twitter'
    BlueSky = 'bsky'

DIR_PATH = os.getcwd()

# YouTube API setup
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
SERVICE_ACCOUNT_FILE = os.path.join(DIR_PATH, "service_account.json")

# Cached latest videos
LATEST_VIDEOS_FILE = os.path.join(DIR_PATH, "latest_videos.json")

# Cached DIDs of members for bsky
DID_FILE = os.path.join(DIR_PATH, "did_cache.json")

# Ignore short for twitter
SHOULD_EXCLUDE_SHORTS = True

# If posts should be posted
SHOULD_POST_TWEET = False
SHOULD_POST_BSKY = False

# Logfile
LOG_FILE = os.path.join(DIR_PATH, "logs", datetime.now().strftime("%Y-%m-%d")+".log")

class ClientCache:
    twitter_client = None
    bsky_client = None

    def get_twitter(self):
        if not self.twitter_client:
            append_log("Creating Twitter Client")
            self.twitter_client = tweepy.Client(consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_KEY_SECRET, access_token=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET)
        return self.twitter_client

    def get_bsky(self):
        if not self.bsky_client:
            client = atproto.Client()
            try:
                client.login(BLUESKY_USERNAME, BLUESKY_PASSWORD)
                self.bsky_client = client
            except Exception as e:
                append_log(e)

        return self.bsky_client

CLIENT_CACHE = ClientCache()

# Writes to log file
def append_log(text):
    with open(LOG_FILE, 'a') as log_file:
        log_file.write(f"{text}\n")

# Authenticates YouTube and returns an api object
def authenticate_youtube():
    # Use a service account for authentication
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    if creds:
        return googleapiclient.discovery.build(API_SERVICE_NAME, API_VERSION, credentials=creds)
    else:
        return None

# Gets the latest video for a specific channel
def get_video(api, video_id):
    request = api.videos().list(
        part ="snippet,contentDetails,statistics",
        id=video_id
    )
    append_log(f"Calling videos.list for {video_id}")
    return request.execute()

# Loads the latest videos members have posted from the saved video file into memory
def load_latest_videos():
    latest_vids = {}

    if os.path.exists(LATEST_VIDEOS_FILE):
        with(open(LATEST_VIDEOS_FILE, 'r') as videos_file):
            try:
                latest_vids = json.load(videos_file)
            except: pass

    return latest_vids

def load_dids():
    dids = {}

    if os.path.exists(DID_FILE):
        with(open(DID_FILE, 'r') as did_file):
            try:
                dids = json.load(did_file)
            except: pass

    return dids

# Create text for a post given video title, links to the video, and tags the member on twitter
def create_post_contents(platform: Platforms, video_data, member_handle: str = ""):
    text = video_data["title"]
    video_link = f"https://www.youtube.com/watch?v={video_data['id']}"

    if platform == Platforms.Twitter:
        if member_handle:
            text += f" - @{member_handle}"
        text += f" {video_link}"
    elif platform == Platforms.BlueSky:
        text = client_utils.TextBuilder().text(f"{text}")
        if member_handle:
            # First check if we have the did cached
            dids = load_dids()
            if member_handle in dids:
                did = dids[member_handle]
            else:
                resolver = IdResolver()
                did = resolver.handle.resolve(member_handle)

                if did:
                    dids[member_handle] = did

                    # Write the newly acquired did to the cache file so we don't have to fetch it again.
                    with (open(DID_FILE, 'w') as did_file):
                        json.dump(dids, did_file)
            if did:
                text.text(" ").mention(f"@{member_handle}", did)

    return text

def post_tweet(video_data, member_handle):
    # Make the text for the tweet
    text = create_post_contents(Platforms.Twitter, video_data, member_handle)
    if SHOULD_POST_TWEET:
        client = CLIENT_CACHE.get_twitter()
        try:
            client.create_tweet(text=text)
            append_log(f"Sent Tweet: \"{text}\"")
            return True
        except Exception as e:
            append_log(f"Failed to send tweet: \"{text}\"")
            return False
    else:
        append_log(f"Demo Tweet: \"{text}\"")
        return False

def post_bsky(video_data, member_handle):
    # Make the text for the tweet
    text = create_post_contents(Platforms.BlueSky, video_data, member_handle)
    if SHOULD_POST_BSKY:
        client = CLIENT_CACHE.get_bsky()
        try:
            # We have to manually embed the video cause BlueSky is dumb and doesn't do it on their end.
            thumb_data = httpx.get(video_data['thumbnail']).content
            thumb_blob = client.upload_blob(thumb_data).blob
            video_embed = models.AppBskyEmbedExternal.Main(
                external=models.AppBskyEmbedExternal.External(
                    title=video_data["title"],
                    description=video_data["description"],
                    uri=f"https://www.youtube.com/watch?v={video_data['id']}",
                    thumb=thumb_blob
                )
            )

            client.send_post(text=text, embed=video_embed)
            append_log(f"Sent Bsky: \"{text.build_text()}\"")
            return True
        except:
            append_log(f"Failed to send bsky: \"{text.build_text()}\"")
            return False
    else:
        append_log(f"Demo Bsky: \"{text.build_text()}\"")
        return False

def do_post(platform: Platforms, video_data, member_handle):
    if platform == Platforms.Twitter:
        return post_tweet(video_data, member_handle)
    elif platform == Platforms.BlueSky:
        return post_bsky(video_data, member_handle)

def main():
    append_log("Running bot: " + datetime.now(timezone.utc).strftime("%H:%M"))

    latest_vids = load_latest_videos()
    if SHOULD_EXCLUDE_SHORTS: youtube_api = authenticate_youtube()

    append_log(f"Polling for new videos...")
    # Check members for new videos
    for arcadia_member in ARCADIA_MEMBERS:
        channel_id = arcadia_member[0]

        # Request the xml for a channel. Only grabs the 10 most recent but they are ordered so it's perfect
        request = requests.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")

        if request.status_code != requests.codes.ok: continue

        # This response is XML so we gotta to annoying things
        root = ET.fromstring(request.text)
        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")

        for entry in entries:
            video_id = entry.find(".//{http://www.youtube.com/xml/schemas/2015}videoId").text
            socials = [
                {
                    "platform": Platforms.Twitter,
                    "member_handle": arcadia_member[1],
                },
                {
                    "platform": Platforms.BlueSky,
                    "member_handle": arcadia_member[2],
                }
            ]

            # list of socials to post to
            socials_to_post = []

            # Make sure we haven't seen this video on at least one of the social platforms
            if channel_id in latest_vids:
                latest = latest_vids[channel_id]
                for social in socials:
                    platform = social['platform'].value
                    if platform not in latest or latest[platform] != video_id:
                        socials_to_post.append(social)
            else:
                latest_vids[channel_id] = {}
                socials_to_post = list(socials)

            if not socials_to_post:
                break

            # This is a flag 1) to make it easier to turn off but 2) because this hits the youtube api through oauth whereas the xml request does not
            if SHOULD_EXCLUDE_SHORTS and youtube_api:
                # No way to query if a video is a short so we have to just guess it's a short if it's less than 60s. Which is probably true for our content anyways
                video = get_video(youtube_api, video_id)
                duration_iso = video['items'][0]['contentDetails']['duration']
                duration_seconds = isodate.parse_duration(duration_iso).seconds

                if duration_seconds <= 60: continue

            video_title = entry.find(".//{http://www.w3.org/2005/Atom}title").text
            video_thumbnail = entry.find(".//{http://search.yahoo.com/mrss/}thumbnail").attrib.get('url')
            video_description = entry.find(".//{http://search.yahoo.com/mrss/}description").text
            # Do social posts
            video_data = {
                "title": video_title,
                "id": video_id,
                "thumbnail": video_thumbnail,
                "description": video_description
            }

            for social in socials_to_post:
                # post to social
                success = do_post(social['platform'], video_data, social['member_handle'])
                # Only update list if the twitter post succeeds
                if success:
                    latest_vids[channel_id][social['platform'].value] = video_id

            break

        # if we get through all the entries either the whole list is shorts, or the final video is the most recent one. we can just update to the most recent one to avoid further api requests
        last_video_entry = entries[-1].find(".//{http://www.youtube.com/xml/schemas/2015}videoId").text
        if not channel_id in latest_vids or latest_vids[channel_id] == last_video_entry:
            first_video_entry = entries[0].find(".//{http://www.youtube.com/xml/schemas/2015}videoId").text
            latest_vids[channel_id] = first_video_entry

    append_log(f"Polling Ended")
    # Write the latest videos to a file for reading in later
    with (open(LATEST_VIDEOS_FILE, 'w') as videos_file):
        json.dump(latest_vids, videos_file)
        append_log(f"{LATEST_VIDEOS_FILE} written")

if __name__ == "__main__":
    main()
