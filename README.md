# rephraseX - Automatic Twitter Posting Bot

An automated Twitter bot that scrapes tweets from a target user, downloads media, rephrases content using **Ollama + Llama 3.2 (offline)**, and reposts to your authenticated account.

<p align="center">
  <img src="https://github.com/user-attachments/assets/4367e6b1-36a0-499d-9bf8-3790435f2512" alt="rephraseX Bot" height=200px width=480px>
</p>

## Features

- **🔐 Cookie-Based Authentication** — Extract cookies directly from your browser (Vivaldi, Chrome, Edge, Firefox, Brave, Opera, Safari) — no login automation needed
- **🌐 Multi-Browser Support** — Firefox, Chrome, Vivaldi, Edge, Brave, Opera, Opera GX, Safari
- **📥 Tweet & Media Scraping** — Scrapes tweets, images, and videos from any public profile
- **🤖 Offline AI Rephrasing** — Uses Ollama + Llama 3.2 locally (no API keys, no internet required)
- **📤 Auto-Posting** — Reposts rephrased tweets with media to your account
- **💾 Persistent Profiles** — Reuse browser profiles across sessions
- **📊 Rich Logging** — Beautiful terminal output with tables and progress bars
- **⏱️ Rate Limiting** — Configurable delays to respect Twitter limits

## Quick Start

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) installed and running
- Llama 3.2 model: `ollama pull llama3.2`
- A browser where you're logged into Twitter (Vivaldi, Chrome, Edge, Firefox, etc.)

### Installation

```bash
git clone https://github.com/bitArtisan1/rephraseX-Automatic-Twitter-Posting-Bot.git
cd rephraseX-Automatic-Twitter-Posting-Bot
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```env
TWITTER_USERNAME=your_twitter_username
TWITTER_PASSWORD=your_twitter_password
TWITTER_MAIL=your_email_or_phone  # optional, for 2FA prompts
```  

~~### Step 2: Create a New Project and App~~  
~~1. After your developer account is approved, log into the [Twitter Developer Dashboard](https://developer.twitter.com/en/portal/dashboard).~~  
~~2. Click on "Projects & Apps" in the top menu, then click the **Create Project** button.~~  
~~3. Choose an appropriate name for your project and specify how you will use the API (for example, "scraping tweets for analysis" or "media download").~~  
~~4. After creating the project, click **Create App** within the project dashboard. Name your app, and then Twitter will automatically create the required credentials.~~  

~~### Step 3: Generate API Keys and Tokens~~  
~~1. Inside your app's dashboard, navigate to the **Keys and Tokens** tab.~~  
~~2. Here, you will find your **API Key** (Consumer Key) and **API Secret Key** (Consumer Secret).~~  
~~3. Scroll down to the **Access Token & Access Token Secret** section. Click **Create** to generate an **Access Token** and **Access Token Secret**.~~  
~~4. Copy all four credentials (API Key, API Secret Key, Access Token, Access Token Secret) and store them securely. These are required for authenticating your app to interact with Twitter’s API.~~  

> **Important:** Never expose these keys publicly (e.g., in your source code or on GitHub). Store them securely in environment variables or a .env file.

## Usage

### 🎯 Recommended: Use Browser Cookies (Easiest, Avoids Anti-Bot)

If you're already logged into Twitter in your browser, extract cookies directly:

```bash
# Use cookies from Vivaldi (default profile)
python -m scraper --cookies-from-browser vivaldi -u target_username -t 10

# Use cookies from Vivaldi with specific profile
python -m scraper --cookies-from-browser vivaldi --cookie-profile Default -u target_username -t 10

# Use cookies from Edge
python -m scraper --cookies-from-browser edge -u target_username -t 10

# Use cookies from Chrome
python -m scraper --cookies-from-browser chrome -u target_username -t 10

# Use cookies from Firefox
python -m scraper --cookies-from-browser firefox -u target_username -t 10
```

**Supported browsers:** `chrome`, `vivaldi`, `edge`, `brave`, `opera`, `opera_gx`, `firefox`, `safari`

### 🍪 Alternative: Use a cookies.txt File (Netscape Format)

Export cookies from your browser using extensions like **"Get cookies.txt LOCALLY"** (Chrome/Edge/Vivaldi/Brave/Opera) or **"cookies.txt"** (Firefox), then use the file directly:

```bash
# Use a manually exported cookies.txt file
python -m scraper --cookies-file ./cookies.txt -u target_username -t 10
```

This is the **most reliable method** — works with any browser, no browser detection needed, and avoids all anti-bot detection since you're using real session cookies.

**How to export cookies.txt:**
1. Install "Get cookies.txt LOCALLY" extension (Chrome/Edge/Vivaldi/Brave/Opera) or "cookies.txt" (Firefox)
2. Go to x.com (or twitter.com) and ensure you're logged in
3. Click the extension → "Export" → save as `cookies.txt`
4. Place it in the project folder and use `--cookies-file ./cookies.txt`

### 🔄 Alternative: Persistent Browser Profile

Create a dedicated browser profile for the bot:

```bash
# First run: creates profile, logs in manually
python -m scraper --browser vivaldi --profile-dir ./my_profile -u target_username -t 10

# Subsequent runs: reuses the logged-in session
python -m scraper --browser vivaldi --profile-dir ./my_profile -u target_username -t 10
```

### 📋 All Options

```bash
python -m scraper --help
```

| Option | Description |
|--------|-------------|
| `-u, --username` | Target username to scrape (without @) |
| `-ht, --hashtag` | Scrape tweets from a hashtag |
| `-q, --query` | Scrape tweets from a search query |
| `-t, --tweets` | Number of tweets to scrape (default: 50) |
| `--latest` | Scrape latest tweets |
| `--top` | Scrape top tweets |
| `--no-post` | Only scrape and rephrase, don't post |
| `--no-media` | Skip downloading media |
| `--keep-media` | Don't delete media after posting |
| `--delay` | Delay between posts in seconds (default: 60) |
| `--browser` | Browser to use (default: firefox) |
| `--profile-dir` | Persistent profile directory |
| `--cookies-from-browser` | Extract cookies from browser |
| `--cookie-profile` | Browser profile name (e.g., Default, Profile 1) |
| `--cookies-file` | Path to Netscape-format cookies.txt file |

## How It Works

1. **Authentication** — Uses cookies from your browser OR persistent profile OR manual login
2. **Scraping** — Navigates to target profile, scrolls to load tweets, extracts content + media URLs
3. **Downloading** — Downloads images/videos from tweets
4. **Rephrasing** — Sends tweet text to local Ollama (Llama 3.2) for rewriting
5. **Posting** — Posts rephrased tweet with media to your authenticated account

## Project Structure

```
scraper/
├── __main__.py          # CLI entry point
├── twitter_scraper.py   # Tweet scraping logic
├── twitter_poster.py    # Tweet posting logic
├── twitter_downloader.py# Media downloading
├── twitter_rephraser.py # Ollama integration
├── browser_cookies.py   # Cookie extraction (NEW)
├── tweet.py             # Tweet parsing
├── scroller.py          # Infinite scroll handling
└── logger.py            # Rich logging
```

## Requirements

See `requirements.txt` for full list. Key dependencies:
- `selenium` + `webdriver-manager` — Browser automation
- `ollama` (running locally) — LLM inference
- `rich` — Terminal UI
- `beautifulsoup4` — HTML parsing
- `requests` — HTTP requests

## License

MIT License — See [LICENSE](LICENSE) for details.

---

**⚠️ Disclaimer:** Use responsibly. Comply with Twitter's Terms of Service. Only repost content you have permission to use.

While the bot previously relied on Twitter API keys for rephrasing, this version no longer uses API calls. Instead, **offline rephrasing** is powered by **Ollama** and the **Llama 3.2 model**. This change allows the bot to function without internet access for rephrasing tweets.

Here’s how to set it up:

### Step 1: Install Ollama  
You can install **Ollama** manually or use **Chocolatay** for installation.

#### Manual Installation  
1. Go to the [Ollama official website](https://www.ollama.com/) and download the installer for your platform (Windows/macOS/Linux).  
2. Follow the installation instructions provided on the site.

#### Installation via Chocolatay  
Alternatively, you can use the **Chocolatay** package manager to install Ollama easily by running the following command in your terminal:

```chocolatay install ollama```

### Step 2: Install the Llama 3.2 Model  
Once Ollama is installed, you can add the Llama 3.2 model to Ollama. 

#### Installing Llama 3.2  
1. After you have installed Ollama, open your terminal or command prompt.
2. Run the following command to download and install the Llama 3.2 model:

```ollama pull llama3.2```

This will download the model to your local machine, making it available for offline usage.

> **Note:** Ensure that you have sufficient storage space for the model, as it requires a decent amount of space on your local drive.

---

## Llama 3.2 Model Details

The Llama 3.2 model is a powerful language model designed for a variety of NLP tasks, including text generation, summarization, translation, and rephrasing. It can perform effectively on a range of text-based tasks, including the rephrasing of tweets in this bot.

| **Specification**        | **Details**                                |
|--------------------------|--------------------------------------------|
| **Model Name**            | Llama 3.2                                  |
| **Model Size**            | ~13GB                                      |
| **Max Tokens**            | 4096 tokens                                |
| **Architecture**          | Transformer-based model                   |
| **Training Data**         | Trained on a large corpus of text from diverse domains. |
| **Performance**           | High quality text generation and rephrasing with the ability to maintain context across multiple sentences. |
| **Offline Usage**         | Fully offline once installed via Ollama.    |
| **Supported Tasks**       | Text rephrasing, summarization, language modeling, question answering. |
| **Storage Space**         | Requires approximately 13 GB of free disk space for the full model. |

### Key Features of Llama 3.2:
- **Max Tokens**: Llama 3.2 can handle up to **4096 tokens** in a single processing request. This allows the model to manage long tweets or threaded conversations with ease.
- **Size**: The model is **13GB** in size, so ensure you have sufficient space on your machine for installation.
- **Performance**: Llama 3.2 is fine-tuned for multiple language processing tasks, making it ideal for the rephrasing tasks this bot performs.
- **Offline Functionality**: Once installed, you don’t need an internet connection to interact with the model, which is great for both privacy and performance.

---

## Prerequisites  
Ensure you have the following installed:  
- Python 3.10.x >=  
- Pip (Python package installer)  
- Ollama (for offline rephrasing)  
- Selenium  
- BeautifulSoup4  
- Requests  

## Installation

1. **Clone the Repository:**  

```
git clone https://github.com/bitArtisan1/rephraseX-Automatic-Twitter-Posting-Bot.git  
cd rephraseX-Automatic-Twitter-Posting-Bot
```

2. **Install the Required Dependencies:** Install the required Python libraries using pip:

```pip install -r requirements.txt```

## Usage

### 1. Add Twitter Authentication Details  

You can either store your Twitter username and password in the .env file or provide them directly as command-line arguments when running the scraper.

#### Option 1: Storing credentials in .env  

1. Create a .env file in the root directory of your project.  
2. Add the following lines to the .env file:

`TWITTER_USERNAME=your-twitter-username`  
`TWITTER_PASSWORD=your-twitter-password`

3. After configuring the .env file, run the following command to scrape tweets:

`python scraper.py -t {number_of_tweets} -u {username}`

**Example:**

```python scraper.py -t 5 -u elonmusk```

#### Option 2: Providing credentials as command-line arguments  

Alternatively, you can provide your Twitter username and password directly in the command when running the scraper:

```python scraper.py --user=@yourusername --password=yourpassword -t {number_of_tweets} -u {username}```

## Contribution  
We welcome contributions to this project! To contribute, follow these steps:

- Fork the repository.
- Create a new branch for your feature or bug fix.
- Commit your changes and push them to your fork.
- Open a pull request to the main repository with a detailed explanation of your changes.

## License and Legal Use  
This project is licensed under the MIT License. However, please ensure your use of this bot complies with Twitter's Developer Agreement and Policy, and respect any intellectual property rights of the media you download and re-post. Always ensure you have permission to use any content you download before sharing it.

## Support Me  
If you find RepoUp useful, consider supporting me by:

- Starring the repository on GitHub  
- Sharing the tool with others  
- Providing feedback and suggestions  
- Follow me for more :)


<center>
    
---
For any issues or feature requests, please open an issue on GitHub. Happy coding!

</center>
