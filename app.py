import argparse
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api.proxies import GenericProxyConfig
import re
import os
from datetime import datetime

def get_video_id(url):
    """
    Extracts the YouTube video ID from a URL.
    Handles standard, short, and embed URLs.
    """
    patterns = [
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([^&]+)',
        r'(?:https?:\/\/)?youtu\.be\/([^?]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([^?]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def fetch_transcript_with_fallback(video_id):
    """
    Tries to fetch transcript first with proxy, then direct if proxy fails.
    Returns transcript_list if successful, None if both fail.
    """
    # Proxy configuration from environment variables
    PROXY_USERNAME = os.getenv("PROXY_USERNAME")
    PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")
    PROXY_URL = os.getenv("PROXY_URL")
    
    # Check if all proxy environment variables are set
    if not all([PROXY_USERNAME, PROXY_PASSWORD, PROXY_URL]):
        print("Warning: Proxy environment variables not fully configured. Skipping proxy attempt.")
        print("Required env vars: PROXY_USERNAME, PROXY_PASSWORD, PROXY_URL")
        # Skip proxy attempt and go directly to direct connection
        try:
            print("Attempting direct connection...")
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            print("Successfully connected directly.")
            return transcript_list, YouTubeTranscriptApi
        except Exception as e:
            print(f"Direct connection failed: {e}")
            raise e
    
    PROXY_HTTP = f"http://{PROXY_USERNAME}:{PROXY_PASSWORD}@{PROXY_URL}"
    PROXY_HTTPS = f"https://{PROXY_USERNAME}:{PROXY_PASSWORD}@{PROXY_URL}"
    
    # First try with proxy
    try:
        print("Attempting to fetch transcript using proxy...")
        proxy_config = GenericProxyConfig(
            http_url=PROXY_HTTP,
            https_url=PROXY_HTTPS,
        )
        ytt_api = YouTubeTranscriptApi(proxy_config=proxy_config)
        transcript_list = ytt_api.list_transcripts(video_id)
        print("Successfully connected using proxy.")
        return transcript_list, ytt_api
    except Exception as e:
        print(f"Proxy connection failed: {e}")
        print("Falling back to direct connection...")
    
    # If proxy fails, try direct connection
    try:
        print("Attempting direct connection...")
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        print("Successfully connected directly.")
        return transcript_list, YouTubeTranscriptApi
    except Exception as e:
        print(f"Direct connection also failed: {e}")
        raise e

def main():
    parser = argparse.ArgumentParser(description="Fetches the transcript for a YouTube video.")
    parser.add_argument("--url", required=True, help="The URL of the YouTube video (e.g., \'\'\'https://www.youtube.com/watch?v=iYSaXtFvBwQ\'\'\')")
    args = parser.parse_args()

    video_url = args.url
    video_id = get_video_id(video_url)

    if not video_id:
        print(f"Error: Could not extract video ID from URL: {video_url}")
        return

    try:
        print(f"Fetching transcript for video ID: {video_id}...")
        transcript_list, api_instance = fetch_transcript_with_fallback(video_id)
        transcript_to_fetch = None

        # 1. Try manually created English
        try:
            transcript_to_fetch = transcript_list.find_manually_created_transcript(['en'])
            print("Found manually created English transcript.")
        except NoTranscriptFound:
            print("No manually created English transcript found.")

        # 2. If not found, try any other manually created
        if not transcript_to_fetch:
            print("Trying any manually created transcript...")
            # Get all language codes of available manual transcripts
            manual_lang_codes = [t.language_code for t in transcript_list if not t.is_generated]
            if manual_lang_codes:
                try:
                    transcript_to_fetch = transcript_list.find_manually_created_transcript(manual_lang_codes)
                    print(f"Found manually created transcript in: {transcript_to_fetch.language} ({transcript_to_fetch.language_code})")
                except NoTranscriptFound: 
                    # This might happen if lang_codes were stale or some other issue
                    print("Could not fetch any of the identified available manual transcripts.")
            else:
                print("No manually created transcripts (any language) available.")

        # 3. If not found, try auto-generated English
        if not transcript_to_fetch:
            print("Trying auto-generated English transcript...")
            try:
                transcript_to_fetch = transcript_list.find_generated_transcript(['en'])
                print("Found auto-generated English transcript.")
            except NoTranscriptFound:
                print("No auto-generated English transcript found.")

        # 4. If not found, try any other auto-generated
        if not transcript_to_fetch:
            print("Trying any auto-generated transcript...")
            # Get all language codes of available auto-generated transcripts
            generated_lang_codes = [t.language_code for t in transcript_list if t.is_generated]
            if generated_lang_codes:
                try:
                    transcript_to_fetch = transcript_list.find_generated_transcript(generated_lang_codes)
                    print(f"Found auto-generated transcript in: {transcript_to_fetch.language} ({transcript_to_fetch.language_code})")
                except NoTranscriptFound:
                    print("Could not fetch any of the identified available auto-generated transcripts.")
            else:
                print("No auto-generated transcripts (any language) available.")
        
        # After all attempts, check if a transcript was found
        if transcript_to_fetch:
            full_transcript = transcript_to_fetch.fetch()
            
            # Prepare filename and output directory
            now = datetime.now()
            timestamp = now.strftime("%Y%m%d%H%M%S")
            filename = f"youtube_transcript_{timestamp}.txt"
            output_dir = "outputs"

            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            filepath = os.path.join(output_dir, filename)

            print(f"\\nSaving transcript to: {filepath}...")
            transcript_text_content = ""
            for entry in full_transcript:
                transcript_text_content += entry.text + "\n"
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(transcript_text_content)
            
            print(f"Transcript saved successfully.")

            # Optionally, still print to console if desired
            # print("\nTranscript:")
            # for entry in full_transcript:
            # print(f"{entry.text}")
        else:
            # If no transcript was found by any of our preferred methods,
            # raise NoTranscriptFound in a way the library understands,
            # so it's caught by the main handler below.
            # This is done by requesting a transcript for a language code that is virtually guaranteed not to exist.
            transcript_list.find_transcript(['__very_unlikely_language_code_due_to_no_prior_match__'])


    except TranscriptsDisabled:
        print(f"Transcripts are disabled for video: {video_url}")
    except NoTranscriptFound:
        print(f"No transcript found for video: {video_url}. This might be a live stream or a video with no captions.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
