# ---------------------
# Arcadia Twitter Bot
#
# Author: HumbleHominid
# ---------------------
import os
import json
import tweepy
import requests

import xml.etree.ElementTree as ET

# Twitter API credentials
from twitter_creds import *

# Arcadia members info
from arcadia_members import ARCADIA_MEMBERS

# Cached latest videos
LATEST_VIDEOS_FILE = "latest_videos.json"

# If tweets should be posted
SHOULD_POST_TWEET = False

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
            print(f"Sent Tweet: \"{tweet_text}\"")
            return True
        except: pass
    else:
        print(f"Demo Tweet: \"{tweet_text}\"")

    return False

def main():
    twitter_client = create_twitter_client()
    latest_vids = load_latest_videos()

    for arcadia_member in ARCADIA_MEMBERS:
        channel_id = arcadia_member[0]
        # Request the xml for a channel. Only grabs the 10 most recent but they are ordered so it's perfect
        request = requests.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}")

        if request.status_code != requests.codes.ok: continue

        # This response is XML so we gotta to annoying things
        root = ET.fromstring(request.text)

        entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        if entries and len(entries) > 0:
            entry = entries[0]
            video_id = entry.find(".//{http://www.youtube.com/xml/schemas/2015}videoId").text

            # Only post tweet if it's a new video we don't know about
            if not channel_id in latest_vids or latest_vids[channel_id] != video_id:
                video_title = entry.find(".//{http://www.w3.org/2005/Atom}title").text
                # Send tweet
                success = post_tweet(twitter_client, video_title, video_id, arcadia_member[1])

                # Only update list if the twitter post succeeds
                if success: latest_vids[channel_id] = video_id

    # Write the latest videos to a file for reading in later
    with (open(LATEST_VIDEOS_FILE, 'w') as videos_file):
        json.dump(latest_vids, videos_file)

if __name__ == "__main__":
    main()
