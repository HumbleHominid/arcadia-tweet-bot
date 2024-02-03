import os
import json
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import tweepy

# YouTube API setup
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
CHANNEL_IDS = ["CHANNEL_ID_1", "CHANNEL_ID_2"]  # Replace with the actual channel IDs

# Twitter API setup
TWITTER_API_KEY = "YOUR_TWITTER_API_KEY"
TWITTER_API_SECRET_KEY = "YOUR_TWITTER_API_SECRET_KEY"
TWITTER_ACCESS_TOKEN = "YOUR_TWITTER_ACCESS_TOKEN"
TWITTER_ACCESS_TOKEN_SECRET = "YOUR_TWITTER_ACCESS_TOKEN_SECRET"

def authenticate_youtube():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json')

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build(API_SERVICE_NAME, API_VERSION, credentials=creds)

def authenticate_twitter():
    auth = tweepy.OAuthHandler(TWITTER_API_KEY, TWITTER_API_SECRET_KEY)
    auth.set_access_token(TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    return api

def get_latest_video_id(api, channel_id):
    response = api.search(q=f"from:{channel_id} filter:videos", count=1, result_type="recent")
    if response:
        return response[0].id_str
    return None

def post_tweet(api, channel_id, video_id):
    tweet_text = f"New video alert! Check out the latest video from {channel_id} - https://www.youtube.com/watch?v={video_id}"
    api.update_status(status=tweet_text)

def main():
    youtube_api = authenticate_youtube()
    twitter_api = authenticate_twitter()

    for channel_id in CHANNEL_IDS:
        latest_video_id = get_latest_video_id(twitter_api, channel_id)
        request = youtube_api.search().list(
            part="snippet",
            channelId=channel_id,
            order="date",
            type="video",
            maxResults=1
        )
        response = request.execute()
        new_video_id = response['items'][0]['id']['videoId']

        if new_video_id != latest_video_id:
            post_tweet(twitter_api, channel_id, new_video_id)

if __name__ == "__main__":
    main()
