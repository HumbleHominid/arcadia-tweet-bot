# ---------------------
# Arcadia Twitter Bot
#
# Author: HumbleHominid
# ---------------------
import os
import json
import googleapiclient.discovery
import google_auth_oauthlib.flow
import google.oauth2
import google.auth.transport.requests
import tweepy

# Twitter API credentials
from twitter_creds import *

# YouTube API setup
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
SECRETS_FILE = "secrets.json"
TOKEN_FILE = "token.json"

# List of members YouTube channels and twitter IDs
ARCADIA_MEMBERS = [
    # [YouTube Channel ID, Twitter Handle]
]

# Cached latest videos
LATEST_VIDEOS_FILE = "latest_videos.json"

# Authenticates YouTube and returns an api object
def authenticate_youtube():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = google.oauth2.credentials.Credentials.from_authorized_user_file(TOKEN_FILE)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(google.auth.transport.requests.Request())
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'w') as token_file:
            token_file.write(creds.to_json())

    return googleapiclient.discovery.build(API_SERVICE_NAME, API_VERSION, credentials=creds)

# Loads the latest videos members have posted from the saved video file into memory
def load_latest_videos():
    latest_vids = {}

    if os.path.exists(LATEST_VIDEOS_FILE):
        with (open(LATEST_VIDEOS_FILE, 'r') as videos_file):
            try:
                latest_vids = json.load(videos_file)
            except: None

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
    if member_twitter_handle:
        tweet_text += f" @{member_twitter_handle}"

    try:
        client.create_tweet(text=tweet_text)
    except: None

def main():
    youtube_api = authenticate_youtube()
    twitter_client = create_twitter_client()
    latest_vids = load_latest_videos()

    for arcadia_member in ARCADIA_MEMBERS:
        channel_id = arcadia_member[0]
        request = youtube_api.search().list(
            part ="snippet",
            channelId=channel_id,
            order="date",
            type="video",
            maxResults=1
        )
        response = request.execute()

        if response['items']:
            video_id = response['items'][0]['id']['videoId']

            # Only post tweet if it's a new video we don't know about
            if not channel_id in latest_vids or latest_vids[channel_id] != video_id:
                video_title = response['items'][0]['snippet']['title']
                latest_vids[channel_id] = video_id

                # Send tweet
                post_tweet(twitter_client, video_title, video_id, arcadia_member[1])

    # Write the latest videos to a file for reading in later
    with (open(LATEST_VIDEOS_FILE, 'w') as videos_file):
        json.dump(latest_vids, videos_file)

if __name__ == "__main__":
    main()