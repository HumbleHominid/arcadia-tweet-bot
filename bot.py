#!/usr/arcadia_tweet_bot/venv/bin/python4.11
# ---------------------
# Arcadia Twitter Bot
#
# Author: HumbleHominid
# ---------------------
import os
import json
from google.oauth2 import service_account
import googleapiclient.discovery
import tweepy
import requests
import xml.etree.ElementTree as ET
import isodate
from datetime import datetime, timezone

# Twitter API credentials
from twitter_creds import *

# Arcadia members info
from arcadia_members import ARCADIA_MEMBERS

DIR_PATH = os.getcwd()

# Token Test
TOKEN_TEST = True

# YouTube API setup
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
SERVICE_ACCOUNT_FILE = os.path.join(DIR_PATH, "service_account.json")

# Cached latest videos
LATEST_VIDEOS_FILE = os.path.join(DIR_PATH, "latest_videos.json")

# Ignore short for twitter
SHOULD_EXCLUDE_SHORTS = True

# If tweets should be posted
SHOULD_POST_TWEET = False

# Logfile
LOG_FILE = os.path.join(DIR_PATH, datetime.now().strftime("%Y-%m-%d")+".log")

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
        with (open(LATEST_VIDEOS_FILE, 'r') as videos_file):
            try:
                latest_vids = json.load(videos_file)
            except: pass

    return latest_vids

# Creates an Oauth1 twitter client
def create_twitter_client():
    client = tweepy.Client(
        consumer_key=TWITTER_API_KEY,
        consumer_secret=TWITTER_API_SECRET_KEY,
        access_token=TWITTER_ACCESS_TOKEN,
        access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
    )
    return client

# Posts a tweet given a video title, links to the video, and tags the member on twitter
def post_tweet(client, video_title, video_id, member_twitter_handle=None):
    tweet_text = f"{video_title} https://www.youtube.com/watch?v={video_id}"

    ## Only tag the member if the twitter handle is not empty
    if member_twitter_handle: tweet_text += f" @{member_twitter_handle}"

    if SHOULD_POST_TWEET:
        try:
            client.create_tweet(text=tweet_text)
            append_log(f"Sent Tweet: \"{tweet_text}\"")
            return True
        except:
            append_log(f"Failed to send tweet: \"{tweet_text}\"")
            return False
    else:
        append_log(f"Demo Tweet: \"{tweet_text}\"")
        return True

def main():
    append_log("Running bot: " + datetime.now(timezone.utc).strftime("%H:%M"))

    latest_vids = load_latest_videos()
    twitter_client = create_twitter_client()
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

            # Only post tweet if it's a new video we don't know about
            if channel_id in latest_vids and latest_vids[channel_id] == video_id: break

            # This is a flag 1) to make it easier to turn off but 2) because this hits the youtube api through oauth whereas the xml request does not
            if SHOULD_EXCLUDE_SHORTS and youtube_api:
                # No way to query if a video is a short so we have to just guess it's a short if it's less than 60s. Which is probably true for our content anyways
                video = get_video(youtube_api, video_id)
                duration_iso = video['items'][0]['contentDetails']['duration']
                duration_seconds = isodate.parse_duration(duration_iso).seconds

                if duration_seconds <= 60: continue

            video_title = entry.find(".//{http://www.w3.org/2005/Atom}title").text
            # Send tweet
            success = post_tweet(twitter_client, video_title, video_id, arcadia_member[1])

            # Only update list if the twitter post succeeds
            if success: latest_vids[channel_id] = video_id

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
