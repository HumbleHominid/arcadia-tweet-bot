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
import flask

# Twitter API credentials
from twitter_creds import *

# Arcadia members info
from arcadia_members import ARCADIA_MEMBERS

# YouTube API setup
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
SECRETS_FILE = "secrets.json"
TOKEN_FILE = "token.json"

# Cached latest videos
LATEST_VIDEOS_FILE = "latest_videos.json"

# If tweets should be posted
SHOULD_POST_TWEET = True

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

def check_subscription(api, channel_id):
    request = api.subscriptions().list(
        part="snippet,contentDetails",
        forChannelId=channel_id,
        mine=True
    )
    return request.execute()

# Subscribe to notifications for certain channels
def subscribe_to_youtube_notifications(api, channel_id):
    request = api.subscriptions().insert(
        part="snippet",
        body={
            "snippet": {
                "resourceId": {
                    "kind": "youtube#channel",
                    "channelId": channel_id
                },
                "types": ["video"]
            }
        }
    )

    response = request.execute()
    return response

# Gets the latest video for a specific channel
def get_latest_video(api, channel_id):
    request = api.search().list(
        part ="snippet",
        channelId=channel_id,
        order="date",
        type="video",
        maxResults=1
    )
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
    if member_twitter_handle:
        tweet_text += f" @{member_twitter_handle}"

    if SHOULD_POST_TWEET:
        try:
            client.create_tweet(text=tweet_text)
            print(f"Sent Tweet: \"{tweet_text}\"")
        except: pass
    else:
        print(f"Demo Tweet: \"{tweet_text}\"")

def main():
    youtube_api = authenticate_youtube()
    # twitter_client = create_twitter_client()
    latest_vids = load_latest_videos()

    # Check if we need to subscribe to any Arcadians
    for arcadia_member in ARCADIA_MEMBERS:
        response = check_subscription(youtube_api, arcadia_member[0])

        # Subscribe to Arcadians if we need to
        if not response['items']:
            response = subscribe_to_youtube_notifications(youtube_api, arcadia_member[0])

            if response:
                print(f"Added subscription to {response['snippet']['title']}!")
        else:
                print(f"Already subscribed to {response['items'][0]['snippet']['title']}!")

    # Check for latest videos the first time we start up in case we missed something
    # for arcadia_member in ARCADIA_MEMBERS:
    #     channel_id = arcadia_member[0]
    #     response = get_latest_video(youtube_api, channel_id)

    #     if response['items']:
    #         video_id = response['items'][0]['id']['videoId']

    #         # Only post tweet if it's a new video we don't know about
    #         if not channel_id in latest_vids or latest_vids[channel_id] != video_id:
    #             video_title = response['items'][0]['snippet']['title']
    #             latest_vids[channel_id] = video_id

    #             # Send tweet
    #             post_tweet(twitter_client, video_title, video_id, arcadia_member[1])

    # # Write the latest videos to a file for reading in later
    # with (open(LATEST_VIDEOS_FILE, 'w') as videos_file):
    #     json.dump(latest_vids, videos_file)

if __name__ == "__main__":
    main()
