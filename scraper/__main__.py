import os
import sys
import argparse
from pprint import pprint
import logging
import getpass
import re
sys.stdout.reconfigure(encoding='utf-8')

from .twitter_scraper import Twitter_Scraper
from .twitter_downloader import download_twitter_video
from .twitter_poster import post_tweets_with_selenium, Twitter_Poster
from .logger import Logger

from selenium.webdriver.chrome.options import Options

logger = Logger("AppLogger", "app.log")
try:
    from dotenv import load_dotenv
    logger.info("Loading .env file")
    load_dotenv()
    logger.info("Loaded .env file")
except Exception as e:
    print(f"Error loading .env file: {e}")
    sys.exit(1)


def main():
    try:
        parser = argparse.ArgumentParser(
            add_help=True,
            usage="python scraper [option] ... [arg] ...",
            description="Twitter Scraper is a tool that allows you to scrape tweets from Twitter without using Twitter's API.",
        )

        parser.add_argument("--mail", type=str, default=os.getenv("TWITTER_MAIL"), help="Your Twitter mail.")
        parser.add_argument("--user", type=str, default=os.getenv("TWITTER_USERNAME"), help="Your Twitter username.")
        parser.add_argument("--password", type=str, default=os.getenv("TWITTER_PASSWORD"), help="Your Twitter password.")
        parser.add_argument("-t", "--tweets", type=int, default=50, help="Number of tweets to scrape (default: 50)")
        parser.add_argument("-u", "--username", type=str, default=None, help="Twitter username to scrape.")
        parser.add_argument("-ht", "--hashtag", type=str, default=None, help="Twitter hashtag to scrape.")
        parser.add_argument("-ntl", "--no_tweets_limit", nargs="?", default=False, help="Scrape tweets without limit.")
        parser.add_argument("-q", "--query", type=str, default=None, help="Scrape tweets from a query or search.")
        parser.add_argument("-a", "--add", type=str, default="", help="Additional data to scrape and save in CSV.")
        parser.add_argument("--latest", action="store_true", help="Scrape latest tweets")
        parser.add_argument("--top", action="store_true", help="Scrape top tweets")
        parser.add_argument("--no-post", action="store_true", help="Only scrape and rephrase, don't post tweets")
        parser.add_argument("--delay", type=int, default=60, help="Delay between posting tweets (seconds)")
        parser.add_argument("--no-media", action="store_true", help="Skip downloading media from tweets")
        parser.add_argument("--keep-media", action="store_true", help="Don't delete media files after posting")
        parser.add_argument("--profile-dir", type=str, default=None, help="Persistent browser profile directory (e.g., ./twitter_profile)")
        parser.add_argument("--browser", type=str, default="firefox", choices=["firefox", "chrome", "vivaldi", "edge", "brave", "opera", "opera_gx"], help="Browser to use")
        parser.add_argument("--cookies-from-browser", type=str, default=None, choices=["chrome", "vivaldi", "edge", "brave", "opera", "opera_gx", "firefox", "safari"], help="Extract cookies from browser (like yt-dlp --cookies-from-browser)")
        parser.add_argument("--cookie-profile", type=str, default=None, help="Browser profile name to extract cookies from (e.g., Default, Profile 1)")
        parser.add_argument("--cookies-file", type=str, default=None, help="Path to a manually-exported Netscape-format cookies.txt file (bypasses live browser extraction)")

        args = parser.parse_args()

        # Load user credentials
        USER_MAIL = args.mail
        USER_UNAME = args.user
        USER_PASSWORD = args.password

        if USER_UNAME is None:
            USER_UNAME = input("Twitter Username:")

        if USER_PASSWORD is None:
            USER_PASSWORD = input("Enter Password:")

        logger.info("Validating scraping parameters...")
        tweet_type_args = []
        if args.username:
            tweet_type_args.append(args.username)
        if args.hashtag:
            tweet_type_args.append(args.hashtag)
        if args.query:
            tweet_type_args.append(args.query)

        additional_data = args.add.split(",")

        if len(tweet_type_args) > 1:
            logger.error("Please specify only one of --username, --hashtag, or --query.")
            sys.exit(1)

        if args.latest and args.top:
            logger.error("Please specify either --latest or --top, not both.")
            sys.exit(1)

        # Step 1: Scrape Tweets
        if USER_UNAME and USER_PASSWORD:
            scraper = Twitter_Scraper(
                mail=USER_MAIL, 
                username=USER_UNAME, 
                password=USER_PASSWORD,
                profile_dir=args.profile_dir,
                browser=args.browser,
                cookies_from_browser=args.cookies_from_browser,
                cookies_file=args.cookies_file
            )
            scraper.login()
            scraper.scrape_tweets(
                max_tweets=args.tweets,
                no_tweets_limit=args.no_tweets_limit if args.no_tweets_limit is not None else True,
                scrape_username=args.username,
                scrape_hashtag=args.hashtag,
                scrape_query=args.query,
                scrape_latest=args.latest,
                scrape_top=args.top,
                scrape_poster_details="pd" in additional_data,
            )

            scraped_tweets = scraper.get_tweets()

            table_rows = []
            for tweet in scraped_tweets:
                user = tweet.get('user', '')
                content = tweet.get('content', '')
                tweet_link = tweet.get('tweet_link', '')
                table_rows.append([user, content, tweet_link])
            
            headers = ["User", "Content", "Tweet Link"]
            logger.log_table(headers, table_rows, title="Scraped Tweets Summary")

            scraper.save_to_csv()

            # Step 2: Download media from tweet links
            if not args.no_media:
                logger.info("Starting media download process...")
                tweet_links = [tweet.get('tweet_link', '') for tweet in scraped_tweets if tweet.get('tweet_link', '')]
                users = [tweet.get('user', '') for tweet in scraped_tweets if tweet.get('user', '')]
                download_twitter_video(
                    tweet_links,
                    users,
                    cookies_file=args.cookies_file,
                    cookies_from_browser=args.cookies_from_browser,
                )
            else:
                logger.info("Skipping media download (--no-media flag provided).")

            # Step 3: Rephrase and Post Tweets
            tweets_data = []
            for tweet in scraped_tweets:
                content = tweet.get('content', '')
                tweet_link = tweet.get('tweet_link', '')
                tweet_id = None
                if tweet_link:
                    match = re.search(r'/status/(\d+)', tweet_link)
                    if match:
                        tweet_id = match.group(1)
                tweet_data = {
                    "text": content,
                    "media_urls": [],
                    "user": tweet.get('user', ''),
                    "tweet_link": tweet_link
                }
                if tweet_id:
                    tweet_data["tweet_id"] = tweet_id
                tweets_data.append(tweet_data)

            if not args.no_post:
                if not scraper.interrupted and hasattr(scraper, 'driver'):
                    poster = Twitter_Poster(
                        driver=scraper.driver,
                        username=USER_UNAME,
                        password=USER_PASSWORD,
                        mail=USER_MAIL,
                        profile_dir=args.profile_dir,
                        browser=args.browser,
                        cookies_from_browser=args.cookies_from_browser,
                        cookies_file=args.cookies_file
                    )
                    poster.logged_in = True
                else:
                    poster = Twitter_Poster(
                        username=USER_UNAME,
                        password=USER_PASSWORD,
                        mail=USER_MAIL,
                        profile_dir=args.profile_dir,
                        browser=args.browser,
                        cookies_from_browser=args.cookies_from_browser,
                        cookies_file=args.cookies_file
                    )
                    poster.login()

                post_tweets_with_selenium(
                    poster,
                    tweets_data,
                    delay_between_tweets=args.delay,
                    keep_media=args.keep_media
                )
            else:
                logger.info("Skipping posting (--no-post flag provided).")

            if not scraper.interrupted and hasattr(scraper, 'driver'):
                scraper.driver.close()
        else:
            logger.error("Missing Twitter username or password environment variables. Please check your .env file.")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("Script Interrupted by user. Exiting...")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()