import os
from datetime import datetime, timedelta

import google.oauth2.credentials
import google_auth_oauthlib.flow
import pytz
import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi

# allows for full read/write access to the authenticated user's account
# and requires requests to use an SSL connection.
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

# When running locally, disable OAuthlib's HTTPs verification.
# When running in production * do not * leave this option enabled.
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"


class YoutubeData:
    def __init__(self, youtube_api_key, youtube_client_secret_file):
        self.youtube_api_key = youtube_api_key
        self.youtube_client_secret_file = youtube_client_secret_file
        self.client = self.get_authenticated_service()
        self.subscriptions = None

    def get_authenticated_service(self):
        flow = InstalledAppFlow.from_client_secrets_file(
            self.youtube_client_secret_file, SCOPES
        )
        credentials = flow.run_local_server(host="localhost", port=54344)
        return build(API_SERVICE_NAME, API_VERSION, credentials=credentials)

    def get_subscriptions(self):
        self.subscriptions = (
            self.client.subscriptions()
            .list(**{"part": "snippet, contentDetails", "mine": True, "maxResults": 10})
            .execute()
        )

    def get_metadata(self):
        if self.subscriptions is None:
            self.get_subscriptions()
        title = self.subscriptions["items"][0]["snippet"]["title"]
        description = self.subscriptions["items"][0]["snippet"]["description"]
        channelId = self.subscriptions["items"][0]["snippet"]["resourceId"]["channelId"]
        return title, description, channelId

    def get_items(self):
        if self.subscriptions is None:
            self.get_subscriptions()
        items = self.subscriptions["items"]
        return items

    def get_channel_description(self):
        """Retrieve list of subscribed channel description."""
        if self.subscriptions is None:
            self.get_subscriptions()
        return {
            item["snippet"]["channelId"]: item["snippet"]["description"]
            for item in self.subscriptions["items"]
        }

    def get_channel_titles(self):
        """Retrieve list of subscribed channel titles."""
        if self.subscriptions is None:
            self.get_subscriptions()
        items = self.subscriptions["items"]
        return [item["snippet"]["title"] for item in items]

    def get_channel_ids(self):
        """Retrieve list of subscribed channel IDs."""
        if self.subscriptions is None:
            self.get_subscriptions()
        return [
            item["snippet"]["resourceId"]["channelId"]
            for item in self.subscriptions["items"]
        ]

    def get_videos_published_in_last_days(self, days: int):
        channelIds = self.get_channel_ids()
        all_videos_simple = {}
        for channelId in channelIds:
            date_x_days_ago = datetime.utcnow() - timedelta(days=days)
            formatted_date = date_x_days_ago.isoformat("T") + "Z"  # Format as RFC 3339
            url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={channelId}&publishedAfter={formatted_date}&maxResults=25&order=date&type=video&key={self.youtube_api_key}"
            response = requests.get(url)
            if response.status_code == 200:
                response_data = response.json()
                video_summaries = []
                for item in response_data.get("items", []):
                    video_summary = {
                        "videoId": item["id"]["videoId"],
                        "title": item["snippet"]["title"],
                        "description": item["snippet"]["description"],
                        "publishedAt": item["snippet"]["publishedAt"],
                    }
                    video_summaries.append(video_summary)
                all_videos_simple[channelId] = video_summaries
            else:
                all_videos_simple[
                    channelId
                ] = f"Failed to retrieve videos, status code: {response.status_code}"
        return all_videos_simple

    def get_video_transcript(self, videoId: str, maxLength: int = None):
        srt = YouTubeTranscriptApi.get_transcript(videoId)
        transcript = " ".join([e["text"] for e in srt])
        if maxLength:
            transcript = transcript[:maxLength]
        return transcript

    def get_all_video_descrition(self, channelId: str) -> dict:
        """Fetch and return all video descriptions for a given channel."""
        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={channelId}&maxResults=50&order=date&type=video&key={self.youtube_api_key}"
        response = requests.get(url)
        video_descriptions = {}

        if response.status_code == 200:
            response_data = response.json()
            for item in response_data.get("items", []):
                videoId = item["id"]["videoId"]
                description = item["snippet"]["description"]
                video_descriptions[videoId] = description
        else:
            print(f"Failed to retrieve videos, status code: {response.status_code}")

        return video_descriptions

    def get_video_comments(self, video_id: str):
        url = f"https://www.googleapis.com/youtube/v3/commentThreads?part=snippet&videoId={video_id}&key={self.youtube_api_key}&maxResults=100"
        response = requests.get(url)
        comments = []
        if response.status_code == 200:
            response_data = response.json()
            for item in response_data.get("items", []):
                comment = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                comments.append(comment)
        return comments

    def get_video_likes_dislikes(self, video_id: str):
        url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics&id={video_id}&key={self.youtube_api_key}"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()["items"][0]["statistics"]
            return {
                "likes": data.get("likeCount"),
                "dislikes": data.get("dislikeCount"),
            }
        else:
            return {"likes": "unknown", "dislikes": "unknown"}


if __name__ == "__main__":
    youtube_api_key = os.environ["YOUTUBE_API_KEY"]
    youtube_client_secret_file = "client_secret.json"

    YTD = YoutubeData(
        youtube_api_key=youtube_api_key,
        youtube_client_secret_file=youtube_client_secret_file,
    )
    title, description, channelId = YTD.get_metadata()
    print("Video IDs: ")
    video_metadata = YTD.get_videos_published_in_last_days(days=13)
    print(video_metadata)
    print("Video Metadata:", video_metadata)
    videoId = video_metadata[list(video_metadata.keys())[0]][0]["videoId"]
    print(videoId)
    video_title = video_metadata[list(video_metadata.keys())[0]][0]["title"]
    print(video_title)
    transcript = YTD.get_video_transcript(videoId=videoId)
    print("transcript")
    video_description = YTD.get_all_video_descrition(
        channelId="UCHNRIjq2A7x5_rF8LtkXdsg"
    )
    print("video_description")
    print(video_description)
