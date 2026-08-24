import os
import requests
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from .logger import Logger
from .browser_cookies import get_cookies_from_browser, apply_cookies_to_driver

logger = Logger("MediaDownloader", "media_downloader.log")

try:
    import yt_dlp
except ImportError:
    yt_dlp = None


def download_twitter_video(tweet_links, usernames, cookies_file=None, cookies_from_browser=None):
    """Download media (images via headless Firefox, videos via yt-dlp) from tweet links."""
    if not tweet_links or len(tweet_links) == 0:
        logger.error("No tweet links provided for media download.")
        return

    logger.info(f"Extracting media from {len(tweet_links)} tweets...")

    # --- Images: still scraped via a headless browser, since there's no
    # reliable API/yt-dlp path for X's image CDN URLs. Uses Firefox (already
    # required elsewhere in this project) instead of Chrome, so it doesn't
    # need a separate Chrome install.
    scraper = TweetMediaScraper(tweet_links, cookies_file=cookies_file, cookies_from_browser=cookies_from_browser)
    image_links_by_tweet = scraper.get_image_links_by_tweet()
    total_image_count = sum(len(links) for links in image_links_by_tweet.values())

    for tweet_url, image_links in image_links_by_tweet.items():
        if not image_links:
            continue
        tweet_id = extract_tweet_id(tweet_url)
        username_index = tweet_links.index(tweet_url) if tweet_url in tweet_links else 0
        username = usernames[username_index] if username_index < len(usernames) else "twitter_media"

        logger.info(f"Downloading {len(image_links)} image(s) for tweet ID: {tweet_id} from user: {username}")
        downloader = MediaDownloader(image_links)
        downloader.download(username, tweet_id)

    # --- Videos/GIFs: yt-dlp. Far more reliable than scraping the DOM for a
    # <video> tag and shelling out to a third-party site (twitsave.com) to
    # resolve the real media URL - yt-dlp's twitter extractor talks to X's
    # own API directly and handles GIFs, multi-bitrate video selection, etc.
    total_video_count = 0
    if yt_dlp is None:
        logger.error(
            "yt-dlp is not installed, skipping video/GIF downloads. "
            "Install it with: pip install yt-dlp"
        )
    else:
        for i, tweet_url in enumerate(tweet_links):
            username = usernames[i] if i < len(usernames) else "twitter_media"
            tweet_id = extract_tweet_id(tweet_url)
            result_path = download_video_ytdlp(tweet_url, username, tweet_id, cookies_file)
            if result_path:
                total_video_count += 1

    if total_image_count == 0 and total_video_count == 0:
        logger.error("No media found in the provided tweets.")
        return

    logger.info(f"Found {total_image_count} images and {total_video_count} videos across {len(tweet_links)} tweets.")
    logger.info("Media downloaded successfully to images/ directory.")
    return


def extract_tweet_id(tweet_url):
    """Extract the tweet ID from a Twitter URL"""
    match = re.search(r'/status/(\d+)', tweet_url)
    if match:
        return match.group(1)
    return None


def download_video_ytdlp(tweet_url, username, tweet_id=None, cookies_file=None):
    """
    Download video/GIF from a tweet using yt-dlp. Returns the output file
    path on success, or None if the tweet has no downloadable video (this is
    the common case for text/image-only tweets, so it's not treated as an
    error) or the download failed.
    """
    video_dir = f"./images/{username}/videos"
    os.makedirs(video_dir, exist_ok=True)

    outtmpl = os.path.join(video_dir, f"%(id)s{'_tweet' + tweet_id if tweet_id else ''}.%(ext)s")

    ydl_opts = {
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        # Don't blow up the whole run if this particular tweet has no video -
        # that's expected for most tweets.
        "ignoreerrors": True,
        "format": "best",
    }
    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(tweet_url, download=True)
            if not info:
                # No video in this tweet - not an error.
                return None
            downloaded_path = ydl.prepare_filename(info)
            if os.path.exists(downloaded_path):
                logger.info(f"Downloaded video for tweet ID {tweet_id}: {downloaded_path}")
                return downloaded_path
            return None
    except Exception as e:
        # yt-dlp raises for tweets with no video too, in some versions -
        # log at debug level so it doesn't look like a hard failure for the
        # common "no video in this tweet" case.
        logger.debug(f"No video downloaded for {tweet_url}: {e}")
        return None


class TweetMediaScraper:
    def __init__(self, urls, cookies_file=None, cookies_from_browser=None):
        self.urls = urls
        self.cookies_file = cookies_file
        self.cookies_from_browser = cookies_from_browser
        self.image_links_by_tweet = {}

    def _build_driver(self):
        options = FirefoxOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--disable-gpu")
        options.add_argument("--log-level=3")
        options.add_argument("--headless")
        # Let Selenium's own manager resolve both geckodriver and the
        # Firefox binary (same approach twitter_scraper.py uses, which is
        # known to work on this setup) - forcing an explicit
        # GeckoDriverManager-built Service here was causing Selenium to fail
        # finding the Firefox binary itself, even though it's installed.
        driver = webdriver.Firefox(options=options)

        # If we have a way to authenticate, apply cookies so we can see
        # media on tweets that require a logged-in session to view.
        if self.cookies_file or self.cookies_from_browser:
            try:
                driver.get("https://x.com")
                time.sleep(1)
                cookies = get_cookies_from_browser(
                    self.cookies_from_browser or "firefox",
                    domain="x.com",
                    cookies_file=self.cookies_file,
                )
                if cookies:
                    apply_cookies_to_driver(driver, cookies)
            except Exception as e:
                logger.debug(f"Could not apply cookies to media-extraction driver: {e}")

        return driver

    def get_image_links_by_tweet(self):
        """Get image links for each tweet URL"""
        try:
            logger.info("Setting up Firefox driver for media extraction (images)...")
            driver = self._build_driver()
            for i, url in enumerate(self.urls, 1):
                logger.info(f"Processing tweet {i}/{len(self.urls)}: {url}")
                self.image_links_by_tweet[url] = self.get_images_from_tweet(driver, url)
            driver.quit()
            return self.image_links_by_tweet
        except Exception as e:
            logger.error(f"Error setting up Firefox driver for images: {e}", exc_info=True)
            return {}

    def get_images_from_tweet(self, driver, tweet_url):
        """Extract image links from a tweet"""
        try:
            driver.get(tweet_url)
            time.sleep(5)
            images = driver.find_elements(By.CSS_SELECTOR, "img[src*='pbs.twimg.com/media']")
            links = [img.get_attribute('src') for img in images]
            if links:
                logger.info(f"Found {len(links)} images in tweet.")
            else:
                logger.info("No images found in tweet.")
            return links
        except Exception as e:
            logger.error(f"Error fetching images from {tweet_url}: {e}", exc_info=True)
            return []


class MediaDownloader:
    def __init__(self, urls):
        self.urls = urls

    def sanitize_filename(self, filename):
        return re.sub(r'[<>:"/\\|?*]', '', filename)

    def download(self, folder, tweet_id=None):
        if not os.path.exists("images"):
            os.makedirs("images")
            logger.info("Created 'images' directory")
        folder_path = f"images/{folder}"
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            logger.info(f"Created '{folder_path}' directory")

        logger.info(f"Downloading {len(self.urls)} media files for tweet {'ID: ' + tweet_id if tweet_id else ''}...")
        for i, link in enumerate(self.urls, 1):
            try:
                logger.info(f"Downloading file {i}/{len(self.urls)}")
                r = requests.get(link, allow_redirects=True, stream=True)
                if r.status_code != 200:
                    logger.error(f"Failed to download {link} - Status code: {r.status_code}")
                    continue
                base_filename = link.split("/")[-1].split('?')[0]
                if tweet_id:
                    filename_parts = os.path.splitext(base_filename)
                    sanitized_filename = f"{self.sanitize_filename(filename_parts[0])}_tweet{tweet_id}{filename_parts[1]}"
                else:
                    sanitized_filename = self.sanitize_filename(base_filename)
                file_path = os.path.join(folder_path, sanitized_filename)
                if not os.path.splitext(file_path)[1]:
                    file_path += ".jpg"

                total_size = int(r.headers.get('content-length', 0))
                block_size = 1024  # 1KB

                with open(file_path, 'wb') as f, \
                     logger.progress_bar(total=total_size if total_size > 0 else None,
                                           description=f"Downloading {sanitized_filename[:25]}") as progress:
                    for data in r.iter_content(block_size):
                        f.write(data)
                        progress.update(advance=len(data))

                logger.info(f"Downloaded: {file_path}")
            except Exception as e:
                logger.error(f"Error downloading {link}: {e}", exc_info=True)

        logger.info("Download complete.")