"""
Browser cookie extraction module - similar to yt-dlp's --cookies-from-browser functionality.
Supports extracting cookies from Chrome, Vivaldi, Edge, Brave, Opera, Firefox, and Safari.
"""

import os
import sys
import sqlite3
import json
import base64
import platform
import shutil
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from .logger import Logger

logger = Logger("BrowserCookies", "browser_cookies.log")


def _get_chromium_master_key(cookie_db_path: str) -> Optional[bytes]:
    """
    Chromium-based browsers (Chrome/Vivaldi/Edge/Brave/Opera) encrypt cookie
    values on disk. The AES key used to decrypt them is itself encrypted with
    Windows DPAPI and stored in the browser's "Local State" file, which lives
    two directories up from .../Default/Network/Cookies.
    """
    if platform.system() != "Windows":
        return None

    try:
        import win32crypt  # provided by pywin32
    except ImportError:
        logger.error(
            "pywin32 is required to decrypt Chromium cookie values. "
            "Install it with: pip install pywin32"
        )
        return None

    # cookie_db_path: .../User Data/Default/Network/Cookies
    # Local State:    .../User Data/Local State
    user_data_dir = Path(cookie_db_path).parent.parent.parent
    local_state_path = user_data_dir / "Local State"

    if not local_state_path.exists():
        logger.error(f"Could not find Local State file at {local_state_path}")
        return None

    try:
        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)

        encrypted_key_b64 = local_state["os_crypt"]["encrypted_key"]
        encrypted_key = base64.b64decode(encrypted_key_b64)

        # Strip the "DPAPI" prefix Chromium adds before the DPAPI blob
        encrypted_key = encrypted_key[5:]

        master_key = win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
        return master_key
    except Exception as e:
        logger.error(f"Failed to obtain Chromium master key: {e}")
        return None


def _decrypt_chromium_value(encrypted_value: bytes, master_key: Optional[bytes]) -> str:
    """Decrypt a single Chromium cookie's encrypted_value blob."""
    if not encrypted_value:
        return ""

    # Older/legacy cookies may just be DPAPI-protected with no v10/v20 prefix
    if not encrypted_value.startswith((b"v10", b"v20")):
        if platform.system() != "Windows":
            return ""
        try:
            import win32crypt
            return win32crypt.CryptUnprotectData(encrypted_value, None, None, None, 0)[1].decode("utf-8", errors="ignore")
        except Exception:
            return ""

    if master_key is None:
        return ""

    try:
        from Crypto.Cipher import AES  # pycryptodome
    except ImportError:
        logger.error(
            "pycryptodome is required to decrypt Chromium cookie values. "
            "Install it with: pip install pycryptodome"
        )
        return ""

    try:
        nonce = encrypted_value[3:15]
        ciphertext = encrypted_value[15:-16]
        tag = encrypted_value[-16:]
        cipher = AES.new(master_key, AES.MODE_GCM, nonce=nonce)
        decrypted = cipher.decrypt_and_verify(ciphertext, tag)
        return decrypted.decode("utf-8", errors="ignore")
    except Exception as e:
        logger.debug(f"Failed to decrypt cookie value: {e}")
        return ""

# Browser cookie database paths by OS
BROWSER_PATHS = {
    "chrome": {
        "Windows": [
            os.path.join(os.getenv("LOCALAPPDATA", ""), "Google", "Chrome", "User Data", "Default", "Network", "Cookies"),
            os.path.join(os.getenv("LOCALAPPDATA", ""), "Google", "Chrome", "User Data", "Profile *", "Network", "Cookies"),
        ],
        "Darwin": [
            os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Google", "Chrome", "Default", "Cookies"),
            os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Google", "Chrome", "Profile *", "Cookies"),
        ],
        "Linux": [
            os.path.join(os.path.expanduser("~"), ".config", "google-chrome", "Default", "Cookies"),
            os.path.join(os.path.expanduser("~"), ".config", "google-chrome", "Profile *", "Cookies"),
        ],
    },
    "vivaldi": {
        "Windows": [
            os.path.join(os.getenv("LOCALAPPDATA", ""), "Vivaldi", "User Data", "Default", "Network", "Cookies"),
            os.path.join(os.getenv("LOCALAPPDATA", ""), "Vivaldi", "User Data", "Profile *", "Network", "Cookies"),
        ],
        "Darwin": [
            os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Vivaldi", "Default", "Cookies"),
            os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Vivaldi", "Profile *", "Cookies"),
        ],
        "Linux": [
            os.path.join(os.path.expanduser("~"), ".config", "vivaldi", "Default", "Cookies"),
            os.path.join(os.path.expanduser("~"), ".config", "vivaldi", "Profile *", "Cookies"),
        ],
    },
    "edge": {
        "Windows": [
            os.path.join(os.getenv("LOCALAPPDATA", ""), "Microsoft", "Edge", "User Data", "Default", "Network", "Cookies"),
            os.path.join(os.getenv("LOCALAPPDATA", ""), "Microsoft", "Edge", "User Data", "Profile *", "Network", "Cookies"),
        ],
        "Darwin": [
            os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Microsoft Edge", "Default", "Cookies"),
            os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Microsoft Edge", "Profile *", "Cookies"),
        ],
        "Linux": [
            os.path.join(os.path.expanduser("~"), ".config", "microsoft-edge", "Default", "Cookies"),
            os.path.join(os.path.expanduser("~"), ".config", "microsoft-edge", "Profile *", "Cookies"),
        ],
    },
    "brave": {
        "Windows": [
            os.path.join(os.getenv("LOCALAPPDATA", ""), "BraveSoftware", "Brave-Browser", "User Data", "Default", "Network", "Cookies"),
            os.path.join(os.getenv("LOCALAPPDATA", ""), "BraveSoftware", "Brave-Browser", "User Data", "Profile *", "Network", "Cookies"),
        ],
        "Darwin": [
            os.path.join(os.path.expanduser("~"), "Library", "Application Support", "BraveSoftware", "Brave-Browser", "Default", "Cookies"),
            os.path.join(os.path.expanduser("~"), "Library", "Application Support", "BraveSoftware", "Brave-Browser", "Profile *", "Cookies"),
        ],
        "Linux": [
            os.path.join(os.path.expanduser("~"), ".config", "BraveSoftware", "Brave-Browser", "Default", "Cookies"),
            os.path.join(os.path.expanduser("~"), ".config", "BraveSoftware", "Brave-Browser", "Profile *", "Cookies"),
        ],
    },
    "opera": {
        "Windows": [
            os.path.join(os.getenv("APPDATA", ""), "Opera Software", "Opera Stable", "Network", "Cookies"),
            os.path.join(os.getenv("APPDATA", ""), "Opera Software", "Opera Stable", "Profile *", "Network", "Cookies"),
        ],
        "Darwin": [
            os.path.join(os.path.expanduser("~"), "Library", "Application Support", "com.operasoftware.Opera", "Cookies"),
        ],
        "Linux": [
            os.path.join(os.path.expanduser("~"), ".config", "opera", "Cookies"),
        ],
    },
    "opera_gx": {
        "Windows": [
            os.path.join(os.getenv("APPDATA", ""), "Opera Software", "Opera GX Stable", "Network", "Cookies"),
            os.path.join(os.getenv("APPDATA", ""), "Opera Software", "Opera GX Stable", "Profile *", "Network", "Cookies"),
        ],
        "Darwin": [
            os.path.join(os.path.expanduser("~"), "Library", "Application Support", "com.operasoftware.OperaGX", "Cookies"),
        ],
        "Linux": [
            os.path.join(os.path.expanduser("~"), ".config", "opera-gx", "Cookies"),
        ],
    },
    "firefox": {
        "Windows": [
            os.path.join(os.getenv("APPDATA", ""), "Mozilla", "Firefox", "Profiles", "*", "cookies.sqlite"),
        ],
        "Darwin": [
            os.path.join(os.path.expanduser("~"), "Library", "Application Support", "Firefox", "Profiles", "*", "cookies.sqlite"),
        ],
        "Linux": [
            os.path.join(os.path.expanduser("~"), ".mozilla", "firefox", "*", "cookies.sqlite"),
        ],
    },
    "safari": {
        "Darwin": [
            os.path.join(os.path.expanduser("~"), "Library", "Cookies", "Cookies.binarycookies"),
        ],
    },
}


def get_browser_cookie_paths(browser: str) -> List[str]:
    """Get possible cookie database paths for a browser on the current OS."""
    system = platform.system()
    browser = browser.lower()
    
    if browser not in BROWSER_PATHS:
        return []
    
    if system not in BROWSER_PATHS[browser]:
        return []
    
    paths = BROWSER_PATHS[browser][system]
    expanded_paths = []
    
    for path in paths:
        if "*" in path:
            # Expand glob patterns
            import glob
            expanded_paths.extend(glob.glob(path))
        else:
            expanded_paths.append(path)
    
    return expanded_paths


def find_cookie_database(browser: str, profile: Optional[str] = None) -> Optional[str]:
    """Find the cookie database file for a browser."""
    paths = get_browser_cookie_paths(browser)
    
    if profile:
        # Filter paths to match the specific profile
        filtered = [p for p in paths if profile in p]
        if filtered:
            paths = filtered
    
    for path in paths:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    
    return None


def extract_chromium_cookies(cookie_db_path: str, domain_filter: Optional[str] = None) -> List[Dict]:
    """Extract cookies from Chromium-based browser cookie database (SQLite)."""
    cookies = []
    
    # Copy the database to a temp location to avoid "database is locked" errors
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        shutil.copy2(cookie_db_path, tmp_path)
        
        conn = sqlite3.connect(tmp_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        master_key = _get_chromium_master_key(cookie_db_path)
        
        # Chromium cookies table schema
        query = """
            SELECT name, value, encrypted_value, host_key, path, expires_utc, is_secure, is_httponly, has_expires, is_persistent
            FROM cookies
        """
        
        if domain_filter:
            query += " WHERE host_key LIKE ? OR host_key LIKE ?"
            cursor.execute(query, (f"%twitter.com%", f"%x.com%"))
        else:
            cursor.execute(query)

        for row in cursor.fetchall():
            # Modern Chromium leaves `value` empty and stores the real
            # (encrypted) data in `encrypted_value` instead.
            plain_value = row["value"]
            if not plain_value and row["encrypted_value"]:
                plain_value = _decrypt_chromium_value(row["encrypted_value"], master_key)

            cookie = {
                "name": row["name"],
                "value": plain_value,
                "domain": row["host_key"],
                "path": row["path"],
                "secure": bool(row["is_secure"]),
                "httpOnly": bool(row["is_httponly"]),
            }
            
            # Convert Chrome's expires_utc (microseconds since 1601-01-01) to Unix timestamp
            if row["has_expires"] and row["expires_utc"] > 0:
                # Chrome time: microseconds since 1601-01-01
                # Unix time: seconds since 1970-01-01
                # Difference: 11644473600 seconds
                expires = (row["expires_utc"] / 1_000_000) - 11644473600
                cookie["expiry"] = int(expires)
            
            cookies.append(cookie)
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error extracting Chromium cookies: {e}")
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    return cookies


def extract_firefox_cookies(cookie_db_path: str, domain_filter: Optional[str] = None) -> List[Dict]:
    """Extract cookies from Firefox cookie database (SQLite)."""
    cookies = []
    
    # Copy the database to a temp location
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        shutil.copy2(cookie_db_path, tmp_path)
        
        conn = sqlite3.connect(tmp_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Firefox cookies table schema (moz_cookies)
        query = """
            SELECT name, value, host, path, expiry, isSecure, isHttpOnly
            FROM moz_cookies
        """
        
        if domain_filter:
            query += " WHERE host LIKE ? OR host LIKE ?"
            cursor.execute(query, (f"%twitter.com%", f"%x.com%"))
        else:
            cursor.execute(query)
        
        for row in cursor.fetchall():
            cookie = {
                "name": row["name"],
                "value": row["value"],
                "domain": row["host"],
                "path": row["path"],
                "secure": bool(row["isSecure"]),
                "httpOnly": bool(row["isHttpOnly"]),
            }
            
            if row["expiry"] and row["expiry"] > 0:
                cookie["expiry"] = int(row["expiry"])
            
            cookies.append(cookie)
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error extracting Firefox cookies: {e}")
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    return cookies


def extract_safari_cookies(cookie_db_path: str, domain_filter: Optional[str] = None) -> List[Dict]:
    """Extract cookies from Safari cookie database (binarycookies format)."""
    # Safari uses a proprietary binary format - this is a simplified version
    # For full support, you'd need to parse the binarycookies format
    logger.warning("Safari cookie extraction not fully implemented")
    return []


def get_cookies_via_ytdlp(browser: str, domain: str = "x.com", profile: Optional[str] = None) -> List[Dict]:
    """
    Extract cookies by shelling out to yt-dlp's --cookies-from-browser support.

    yt-dlp maintains up-to-date, correct decryption for Chromium cookies,
    including "App-Bound Encryption" (introduced in Chrome 127+ and inherited
    by Chromium forks like Vivaldi/Brave/Edge), which requires calling into a
    Windows elevation service and is not something worth re-implementing here.
    This exports cookies to a temporary Netscape-format cookies.txt via yt-dlp,
    then parses that file into Selenium-compatible cookie dicts.

    Requires yt-dlp to be installed: pip install yt-dlp
    """
    import subprocess

    if shutil.which("yt-dlp") is None:
        logger.error("yt-dlp is not installed or not on PATH. Install it with: pip install yt-dlp")
        return []

    browser_arg = browser.lower()
    if profile:
        browser_arg = f"{browser_arg}:{profile}"

    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        cookies_txt_path = tmp.name

    try:
        cmd = [
            "yt-dlp",
            "--cookies-from-browser", browser_arg,
            "--cookies", cookies_txt_path,
            "--skip-download",
            "--simulate",
            "--ignore-errors",
            "--no-warnings",
            "https://www.youtube.com/watch?v=BaW_jenozKc",  # any yt-dlp-recognized URL; cookie
            # export happens independently of which site this is - x.com/twitter.com URLs can
            # cause yt-dlp to bail before the cookie jar gets flushed to disk.
        ]
        logger.info(f"Exporting cookies via yt-dlp ({browser_arg})...")

        # Chromium cookie DBs can be transiently locked (browser flushing to
        # disk, antivirus scan, etc.) which yt-dlp surfaces as "Could not
        # copy Chrome cookie database" - this is usually resolved by a quick
        # retry, so attempt a few times before giving up.
        result = None
        for attempt in range(1, 4):
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if os.path.exists(cookies_txt_path) and os.path.getsize(cookies_txt_path) > 0:
                break
            if "Could not copy" in (result.stderr or ""):
                logger.warning(f"Cookie database locked, retrying ({attempt}/3)...")
                time.sleep(2)
                continue
            break

        if not os.path.exists(cookies_txt_path) or os.path.getsize(cookies_txt_path) == 0:
            logger.error(f"yt-dlp cookie export produced no file. stdout: {result.stdout.strip()[-500:]} stderr: {result.stderr.strip()[-500:]}")
            return []

        cookies = []
        with open(cookies_txt_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Netscape cookie file format (tab-separated):
                # domain  include_subdomains  path  secure  expiry  name  value
                parts = line.split("\t")
                if len(parts) != 7:
                    continue
                cdomain, _include_sub, cpath, csecure, cexpiry, cname, cvalue = parts

                cookie_domain = cdomain.lstrip(".")
                if domain and domain not in cookie_domain and cookie_domain not in ("twitter.com", "x.com"):
                    continue

                cookie = {
                    "name": cname,
                    "value": cvalue,
                    "domain": cdomain if cdomain.startswith(".") else "." + cdomain,
                    "path": cpath or "/",
                    "secure": csecure.upper() == "TRUE",
                    "httpOnly": False,
                }
                if cexpiry and cexpiry.isdigit() and int(cexpiry) > 0:
                    cookie["expiry"] = _normalize_expiry(int(cexpiry))

                cookies.append(cookie)

        logger.info(f"Extracted {len(cookies)} cookies via yt-dlp for {domain}")
        if len(cookies) == 0:
            logger.debug(f"yt-dlp exported cookies.txt had entries but none matched domain filter '{domain}'. stderr: {result.stderr.strip()[-500:]}")
        return cookies

    except subprocess.TimeoutExpired:
        logger.error("yt-dlp cookie export timed out.")
        return []
    except Exception as e:
        logger.error(f"Error exporting cookies via yt-dlp: {e}")
        return []
    finally:
        if os.path.exists(cookies_txt_path):
            try:
                os.unlink(cookies_txt_path)
            except:
                pass


def load_cookies_from_netscape_file(cookies_file: str, domain: str = "x.com") -> List[Dict]:
    """
    Load cookies from a manually-provided Netscape-format cookies.txt file
    (e.g. exported yourself via yt-dlp, the "Get cookies.txt" browser
    extension, curl --cookie-jar, etc.). Use this to bypass automatic
    browser extraction entirely if it's unreliable on your machine.
    """
    if not os.path.exists(cookies_file):
        logger.error(f"Cookies file not found: {cookies_file}")
        return []

    cookies = []
    try:
        with open(cookies_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) != 7:
                    continue
                cdomain, _include_sub, cpath, csecure, cexpiry, cname, cvalue = parts

                cookie_domain = cdomain.lstrip(".")
                if domain and domain not in cookie_domain and cookie_domain not in ("twitter.com", "x.com"):
                    continue

                cookie = {
                    "name": cname,
                    "value": cvalue,
                    "domain": cdomain if cdomain.startswith(".") else "." + cdomain,
                    "path": cpath or "/",
                    "secure": csecure.upper() == "TRUE",
                    "httpOnly": False,
                }
                if cexpiry and cexpiry.isdigit() and int(cexpiry) > 0:
                    cookie["expiry"] = _normalize_expiry(int(cexpiry))

                cookies.append(cookie)

        logger.info(f"Loaded {len(cookies)} cookies from {cookies_file}")
        return cookies
    except Exception as e:
        logger.error(f"Error reading cookies file {cookies_file}: {e}")
        return []


def _normalize_expiry(expiry: int) -> int:
    """
    Selenium/Firefox's WebDriver requires the cookie "expiry" field to be a
    sane Unix timestamp in seconds (must fit a signed 32-bit int per the
    WebDriver spec). Some Netscape-format cookies.txt exports (e.g. from
    certain browser extensions) write expiry in milliseconds, microseconds,
    or some other inflated unit, which Firefox's Marionette driver rejects
    outright with "Expected cookie expiry to be a positive integer".

    This clamps any value outside the plausible range down to a valid
    32-bit timestamp, trying to detect the unit first (ms/us/ns) before
    falling back to a hard cap far in the future.
    """
    MAX_32BIT = 2147483647  # year 2038, the ceiling WebDriver will accept

    if expiry <= MAX_32BIT:
        return expiry

    # Try to detect the unit by how many extra digits it has vs a normal
    # ~10-digit seconds timestamp, and convert down to seconds.
    for divisor in (1_000, 1_000_000, 1_000_000_000):
        candidate = expiry // divisor
        if 0 < candidate <= MAX_32BIT:
            return candidate

    # Couldn't cleanly infer the unit - just cap it so the cookie is still
    # applied (as a long-lived, non-expiring-for-practical-purposes cookie)
    # instead of being dropped entirely.
    return MAX_32BIT


def get_cookies_from_browser(browser: str, domain: str = "x.com", profile: Optional[str] = None, cookies_file: Optional[str] = None) -> List[Dict]:
    """
    Extract cookies from a browser for a specific domain.
    
    Args:
        browser: Browser name (chrome, vivaldi, edge, brave, opera, opera_gx, firefox, safari)
        domain: Domain to filter cookies for (e.g., "twitter.com", "x.com")
        profile: Optional profile name to use
    
    Returns:
        List of cookie dictionaries compatible with Selenium's add_cookie()
    """
    browser = browser.lower()
    logger.info(f"Extracting cookies from {browser} for domain: {domain}")

    # If the user supplied a pre-exported cookies.txt, use it directly and
    # skip live browser extraction entirely.
    if cookies_file:
        return load_cookies_from_netscape_file(cookies_file, domain)

    # Prefer yt-dlp for Chromium-based browsers: it correctly handles
    # "App-Bound Encryption" on modern Chrome/Vivaldi/Edge/Brave, which the
    # manual SQLite+DPAPI path below cannot decrypt correctly and will
    # silently produce garbage cookie values.
    if browser in ["chrome", "vivaldi", "edge", "brave", "opera", "opera_gx"]:
        ytdlp_cookies = get_cookies_via_ytdlp(browser, domain, profile)
        if ytdlp_cookies:
            return ytdlp_cookies
        logger.warning("yt-dlp cookie export unavailable or empty, falling back to manual extraction (may fail on modern Chromium builds due to App-Bound Encryption).")

    cookie_db = find_cookie_database(browser, profile)
    
    if not cookie_db:
        logger.error(f"Could not find cookie database for {browser}")
        return []
    
    logger.info(f"Found cookie database: {cookie_db}")
    
    if browser in ["chrome", "vivaldi", "edge", "brave", "opera", "opera_gx"]:
        cookies = extract_chromium_cookies(cookie_db, domain)
    elif browser == "firefox":
        cookies = extract_firefox_cookies(cookie_db, domain)
    elif browser == "safari":
        cookies = extract_safari_cookies(cookie_db, domain)
    else:
        logger.error(f"Unsupported browser: {browser}")
        return []
    
    # Filter for Twitter/X domains
    twitter_domains = ["twitter.com", "x.com", ".twitter.com", ".x.com"]
    filtered_cookies = []
    
    for cookie in cookies:
        cookie_domain = cookie.get("domain", "").lstrip(".")
        if any(td in cookie_domain for td in twitter_domains):
            if not cookie.get("value"):
                logger.debug(f"Skipping cookie {cookie.get('name')} - empty/undecrypted value")
                continue
            # Ensure domain starts with . for Selenium
            if not cookie["domain"].startswith("."):
                cookie["domain"] = "." + cookie["domain"]
            filtered_cookies.append(cookie)
    
    logger.info(f"Extracted {len(filtered_cookies)} cookies for Twitter/X")
    return filtered_cookies


def apply_cookies_to_driver(driver, cookies: List[Dict]) -> bool:
    """
    Apply cookies to a Selenium WebDriver.
    
    Args:
        driver: Selenium WebDriver instance
        cookies: List of cookie dictionaries
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Navigate directly to x.com — twitter.com 301-redirects to x.com,
        # and Selenium will only accept cookies whose domain matches the
        # page currently loaded, so we need to already be on x.com here.
        driver.get("https://x.com")
        import time
        time.sleep(2)
        
        for cookie in cookies:
            try:
                # Selenium requires specific cookie format.
                # Force domain to .x.com regardless of what was stored
                # (twitter.com-domain cookies will be rejected on x.com).
                selenium_cookie = {
                    "name": cookie["name"],
                    "value": cookie["value"],
                    "domain": ".x.com",
                    "path": cookie.get("path", "/"),
                    "secure": cookie.get("secure", True),
                    "httpOnly": cookie.get("httpOnly", True),
                }
                
                if "expiry" in cookie:
                    selenium_cookie["expiry"] = cookie["expiry"]
                
                driver.add_cookie(selenium_cookie)
            except Exception as e:
                logger.debug(f"Failed to add cookie {cookie.get('name')}: {e}")
        
        logger.info(f"Applied {len(cookies)} cookies to driver")
        return True
        
    except Exception as e:
        logger.error(f"Error applying cookies to driver: {e}")
        return False


def list_available_browsers() -> List[str]:
    """List browsers that have cookie databases on this system."""
    available = []
    system = platform.system()
    
    for browser in BROWSER_PATHS:
        if system in BROWSER_PATHS[browser]:
            paths = get_browser_cookie_paths(browser)
            for path in paths:
                if os.path.exists(path) and os.path.getsize(path) > 0:
                    available.append(browser)
                    break
    
    return available


if __name__ == "__main__":
    # Test the module
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract cookies from browser")
    parser.add_argument("browser", help="Browser name (chrome, vivaldi, edge, brave, opera, firefox, safari)")
    parser.add_argument("--domain", default="twitter.com", help="Domain to filter cookies for")
    parser.add_argument("--profile", help="Profile name")
    parser.add_argument("--list", action="store_true", help="List available browsers")
    
    args = parser.parse_args()
    
    if args.list:
        browsers = list_available_browsers()
        print("Available browsers with cookies:")
        for b in browsers:
            print(f"  - {b}")
    else:
        cookies = get_cookies_from_browser(args.browser, args.domain, args.profile)
        print(json.dumps(cookies, indent=2))