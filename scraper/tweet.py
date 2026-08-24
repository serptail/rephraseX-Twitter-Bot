from time import sleep
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
)
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.action_chains import ActionChains


class Tweet:
    def __init__(
        self,
        card: WebDriver,
        driver: WebDriver,
        actions: ActionChains,
        scrape_poster_details=False,
    ) -> None:
        self.card = card
        self.error = False
        self.tweet = None

        try:
            self.user = card.find_element(
                "xpath", './/div[@data-testid="User-Name"]//span'
            ).text
        except NoSuchElementException:
            self.error = True
            self.user = "skip"

        try:
            self.handle = card.find_element(
                "xpath", './/span[contains(text(), "@")]'
            ).text
        except NoSuchElementException:
            self.error = True
            self.handle = "skip"

        try:
            self.date_time = card.find_element("xpath", ".//time").get_attribute(
                "datetime"
            )

            if self.date_time is not None:
                self.is_ad = False
        except NoSuchElementException:
            self.is_ad = True
            self.error = True
            self.date_time = "skip"

        if self.error:
            return

        # Updated content extraction to properly handle Twitter handles
        self.content = ""
        try:
            # First try to get all text spans and anchor elements that might contain handles and hashtags
            contents = card.find_elements(
                "xpath",
                '(.//div[@data-testid="tweetText"])[1]/span | (.//div[@data-testid="tweetText"])[1]/a',
            )
            
            for index, content in enumerate(contents):
                if content.tag_name == "a":
                    # Special handling for links that might be handles or hashtags
                    link_text = content.text
                    if link_text.startswith("@") or link_text.startswith("#"):
                        # This is a handle or hashtag, preserve it with a space
                        self.content += link_text + " "
                    else:
                        # Regular link
                        self.content += link_text + " "
                else:
                    # Regular text
                    self.content += content.text + " "
                    
            # Trim extra spaces
            self.content = self.content.strip()
            
            # If no content found, try the alternative method
            if not self.content:
                self.content = card.find_element(
                    "xpath", '(.//div[@data-testid="tweetText"])[1]'
                ).text
                
        except NoSuchElementException:
            # If tweet has no text content
            self.content = ""

        try:
            self.tags = card.find_elements(
                "xpath",
                './/a[contains(@href, "src=hashtag_click")]',
            )

            self.tags = [tag.text for tag in self.tags]
        except NoSuchElementException:
            self.tags = []

        try:
            self.tweet_link = self.card.find_element(
                "xpath",
                ".//a[contains(@href, '/status/')]",
            ).get_attribute("href")
            self.tweet_id = str(self.tweet_link.split("/")[-1])
        except NoSuchElementException:
            self.tweet_link = ""
            self.tweet_id = ""

        self.following_cnt = "0"
        self.followers_cnt = "0"
        self.user_id = None

        if scrape_poster_details:
            el_name = card.find_element(
                "xpath", './/div[@data-testid="User-Name"]//span'
            )

            ext_hover_card = False
            ext_user_id = False
            ext_following = False
            ext_followers = False
            hover_attempt = 0

            while (
                not ext_hover_card
                or not ext_user_id
                or not ext_following
                or not ext_followers
            ):
                try:
                    actions.move_to_element(el_name).perform()

                    hover_card = driver.find_element(
                        "xpath", '//div[@data-testid="hoverCardParent"]'
                    )

                    ext_hover_card = True

                    while not ext_user_id:
                        try:
                            raw_user_id = hover_card.find_element(
                                "xpath",
                                '(.//div[contains(@data-testid, "-follow")]) | (.//div[contains(@data-testid, "-unfollow")])',
                            ).get_attribute("data-testid")

                            if raw_user_id == "":
                                self.user_id = None
                            else:
                                self.user_id = str(raw_user_id.split("-")[0])

                            ext_user_id = True
                        except NoSuchElementException:
                            continue
                        except StaleElementReferenceException:
                            self.error = True
                            return

                    while not ext_following:
                        try:
                            self.following_cnt = hover_card.find_element(
                                "xpath", './/a[contains(@href, "/following")]//span'
                            ).text

                            if self.following_cnt == "":
                                self.following_cnt = "0"

                            ext_following = True
                        except NoSuchElementException:
                            continue
                        except StaleElementReferenceException:
                            self.error = True
                            return

                    while not ext_followers:
                        try:
                            self.followers_cnt = hover_card.find_element(
                                "xpath",
                                './/a[contains(@href, "/verified_followers")]//span',
                            ).text

                            if self.followers_cnt == "":
                                self.followers_cnt = "0"

                            ext_followers = True
                        except NoSuchElementException:
                            continue
                        except StaleElementReferenceException:
                            self.error = True
                            return
                except NoSuchElementException:
                    if hover_attempt == 3:
                        self.error
                        return
                    hover_attempt += 1
                    sleep(0.5)
                    continue
                except StaleElementReferenceException:
                    self.error = True
                    return

            if ext_hover_card and ext_following and ext_followers:
                actions.reset_actions()

        self.tweet = {
            'user': self.user,
            'handle': self.handle,
            'content': self.content,
            'tweet_link': self.tweet_link
            }

        pass
        
    def get_tweet_link(self):
        return self.tweet_link
