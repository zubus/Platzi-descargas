import time
import random
import os
import json
import traceback
import hashlib
import base64
from datetime import datetime

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import requests
import yt_dlp

USER_DATA_DIR = os.path.expanduser('~/Library/Application Support/Google/Chrome')
PLATZI_URL = 'https://platzi.com'
MAX_LOGIN_ATTEMPTS = 3
DOWNLOAD_RETRIES = 3

class DebugLogger:
    def __init__(self, base_path):
        debug_dir = os.path.join(base_path, 'debug')
        os.makedirs(debug_dir, exist_ok=True)
        debug_file = os.path.join(debug_dir, f'debug_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')
        self.file = open(debug_file, 'a', encoding='utf-8')

    def log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"{timestamp} - DEBUG: {message}"
        print(log_message)
        self.file.write(log_message + "\n")
        self.file.flush()

    def close(self):
        self.file.close()

def sanitize_filename(filename):
    return ''.join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()

def sanitize_pdf_filename(filename):
    if filename[-5:].lower().endswith('min'):
        filename = filename[:-5].strip()

    return sanitize_filename(filename)

def wait_for_page_load(driver, timeout=30):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script('return document.readyState') == 'complete'
    )

def is_logged_in(driver, logger):
    selectors = [
        "/html/body/div/header/nav/div[3]/div/div/div",
        "/html/body/div[1]/div[2]/header/div/div[3]/div/button/div[1]"
    ]
    for selector in selectors:
        try:
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, selector)))
            logger.log(f"Profile element found with selector: {selector}")
            return True

        except TimeoutException:
            logger.log(f"Profile element not found with selector: {selector}")

    return False

def ensure_login(driver, logger):
    logger.log("Verifying session...")
    driver.get(PLATZI_URL)
    wait_for_page_load(driver)

    for attempt in range(MAX_LOGIN_ATTEMPTS):
        if is_logged_in(driver, logger):
            logger.log("Active session detected")
            return True

        if attempt < MAX_LOGIN_ATTEMPTS - 1:
            logger.log(f"Attempt {attempt + 1} of {MAX_LOGIN_ATTEMPTS}: No active session detected. Please log in manually.")
            print("Please log in manually in the Chrome window.")
            print("If a captcha appears, solve it.")
            input("Press Enter when you have logged in...")

            driver.refresh()
            wait_for_page_load(driver)
        else:
            logger.log("Login attempts exhausted")
            return False

    return False

def save_performance_entries(driver, logger):
    logger.log("Saving performance entries...")
    performance_entries = driver.execute_script("return window.performance.getEntriesByType('resource');")
    entries_file = os.path.join(os.path.dirname(logger.file.name), 'performance_entries.json')
    with open(entries_file, 'w', encoding='utf-8') as f:
        json.dump(performance_entries, f, indent=2)

    logger.log(f"Performance entries saved to {entries_file}")

def get_video_url_from_performance(driver, logger):
    logger.log("Searching for video URL in performance entries...")
    performance_entries = driver.execute_script("return window.performance.getEntriesByType('resource');")
    for entry in performance_entries:
        if 'mediastream.platzi.com' in entry['name'] and '.m3u8' in entry['name']:
            logger.log(f"Found video URL: {entry['name']}")
            return entry['name']

    logger.log("No video URL found in performance entries")
    return None

def download_video(path, class_title, video_url, cookies, headers, logger):
    if os.path.exists(path):
        logger.log(f'Video already downloaded: {class_title}')
        return

    if video_url:
        logger.log(f'Downloading video: {class_title}')
        logger.log(f'Video URL: {video_url}')

        os.makedirs(os.path.dirname(path), exist_ok=True)

        ydl_opts = {
            'outtmpl': path,
            'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
            'quiet': False,
            'no_warnings': False,
            'cookiesfrombrowser': ('chrome',),
            'referer': 'https://platzi.com/',
            'http_headers': headers,
            'hls_prefer_native': True,
            'hls_use_mpegts': True,
        }

        for attempt in range(DOWNLOAD_RETRIES):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([video_url])
                logger.log(f'Video downloaded successfully: {class_title}')
                break

            except Exception as e:
                logger.log(f'Error downloading video (attempt {attempt + 1}/{DOWNLOAD_RETRIES}): {str(e)}')
                logger.log(traceback.format_exc())
                if attempt < DOWNLOAD_RETRIES - 1:
                    logger.log("Retrying in 5 seconds...")
                    time.sleep(random.uniform(3.1, 7.7))

                else:
                    logger.log(f'Failed to download video after {DOWNLOAD_RETRIES} attempts')

    else:
        logger.log('No video link found')

def get_attached_files(driver, logger):
    logger.log("Searching for attached files...")
    performance_entries = driver.execute_script("return window.performance.getEntriesByType('resource');")
    for entry in performance_entries:
        if 'api.platzi.com/api/v4/material/files-links/' in entry['name']:
            files_url = entry['name']
            logger.log(f"Found files URL: {files_url}")
            return files_url

    logger.log("No files URL found in performance entries")
    return None

def download_attached_files(session, files_url, course_path, class_index, cookies, headers, logger):
    try:
        response = session.get(files_url, cookies=cookies, headers=headers)
        response.raise_for_status()
        data = response.json()

        log_file = os.path.join(course_path, 'downloaded_files.json')
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                downloaded_files = json.load(f)

        else:
            downloaded_files = {}

        logger.log(f"Received data structure: {json.dumps(data, indent=2)}")

        def process_files(file_data, current_path=""):
            if isinstance(file_data, list):
                for file in file_data:
                    download_file(file, current_path)

            elif isinstance(file_data, dict):

                if 'type' in file_data and file_data['type'] == 'file':
                    download_file(file_data, current_path)

                elif 'childNodes' in file_data:
                    for name, child in file_data['childNodes'].items():
                        process_files(child, os.path.join(current_path, name))

        def download_file(file, current_path):
            file_url = file.get('url') or file.get('zip_url')
            original_name = file.get('name')
            if not file_url or not original_name:
                logger.log(f"Missing 'url' or 'name' in file data: {file}")
                return

            file_name = f"{class_index:02d}_{sanitize_filename(os.path.join(current_path, original_name))}"
            file_path = os.path.join(course_path, file_name)

            if os.path.exists(file_path):
                logger.log(f"File already exists: {file_name}")
                return

            file_response = session.get(file_url, cookies=cookies, headers=headers)
            file_response.raise_for_status()
            file_content = file_response.content
            file_hash = hashlib.md5(file_content).hexdigest()

            if file_hash in downloaded_files.values():
                logger.log(f"File already downloaded (different name): {original_name}")
                return

            logger.log(f"Downloading file: {file_name}")
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'wb') as f:
                f.write(file_content)

            downloaded_files[file_name] = file_hash
            logger.log(f"File downloaded successfully: {file_name}")

        if 'files' in data:
            process_files(data['files'])
        elif 'zip_url' in data:
            download_file(data, "")
        else:
            logger.log("Unexpected data structure for files")

        with open(log_file, 'w') as f:
            json.dump(downloaded_files, f, indent=2)

    except Exception as e:
        logger.log(f"Error downloading attached files: {str(e)}")
        logger.log(traceback.format_exc())

def save_page_as_pdf(driver, output_path, logger):
    if os.path.exists(output_path):
        logger.log(f"PDF already exists: {output_path}")
        return

    logger.log(f"Saving page as PDF: {output_path}")
    try:
        print_options = {
            'landscape': False,
            'displayHeaderFooter': False,
            'printBackground': True,
            'preferCSSPageSize': True,
        }

        result = driver.execute_cdp_cmd("Page.printToPDF", print_options)
        pdf_data = base64.b64decode(result['data'])

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(pdf_data)

        logger.log("PDF saved successfully")
    except Exception as e:
        logger.log(f"Error saving page as PDF: {str(e)}")
        logger.log(traceback.format_exc())

def process_class(driver, class_title, class_url, course_path, session, cookies, headers, logger):
    try:
        logger.log(f"Processing class: {class_title}")
        driver.get(class_url)
        wait_for_page_load(driver)
        time.sleep(random.uniform(2.5, 4.5))

        save_performance_entries(driver, logger)

        video_url = get_video_url_from_performance(driver, logger)
        if video_url:
            video_path = os.path.join(course_path, f"{sanitize_filename(class_title)}.mp4")
            download_video(video_path, class_title, video_url, cookies, headers, logger)
        else:
            logger.log(f"No video found for class: {class_title}. Saving page as PDF.")
            pdf_path = os.path.join(course_path, f"{sanitize_pdf_filename(class_title)}.pdf")
            save_page_as_pdf(driver, pdf_path, logger)

        files_url = get_attached_files(driver, logger)
        if files_url:
            download_attached_files(session, files_url, course_path, int(class_title.split('_')[0]), cookies, headers, logger)

    except Exception as exc:
        error_info = f"Error processing class '{class_title}': {str(exc)}"
        logger.log(error_info)
        logger.log(traceback.format_exc())

def process_course(driver, course, course_path, session, cookies, headers, logger):
    course_title = course['title']
    course_url = course['url']
    logger.log(f"Processing course: {course_title}")

    if os.path.exists(course_path):
        logger.log(f"Course folder already exists: {course_path}")
    else:
        os.makedirs(course_path, exist_ok=True)
        logger.log(f"Created course folder: {course_path}")

    logger.log(f"Navigating to course page: {course_url}")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            driver.get(course_url)
            wait_for_page_load(driver, timeout=60)

            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.ContentClass-item-link'))
            )

            class_data = driver.execute_script("""
                return Array.from(document.querySelectorAll('.ContentClass-item-link')).map(el => ({
                    text: el.textContent.trim(),
                    href: el.href
                }));
            """)

            if not class_data:
                raise Exception("No class links found")

            logger.log(f"Found {len(class_data)} class links for the course: {course_title}")

            for index, data in enumerate(class_data, start=1):
                class_title = f"{index:02d}_{data['text']}"
                class_url = data['href']
                try:
                    process_class(driver, class_title, class_url, course_path, session, cookies, headers, logger)
                except Exception as exc:
                    error_info = f"Error processing class '{class_title}': {str(exc)}"
                    logger.log(error_info)
                    logger.log(traceback.format_exc())

                time.sleep(random.uniform(2.1, 5.9))

            logger.log(f"Completed processing course: {course_title}")
            return

        except Exception as e:
            logger.log(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                logger.log("Retrying...")
                time.sleep(random.uniform(5, 10))
            else:
                logger.log(f"Failed to process course after {max_retries} attempts")
                logger.log(traceback.format_exc())

def process_learning_path(driver, learning_path_url, base_path, session, cookies, headers, logger, start_from_course=1):
    logger.log(f"Processing learning path: {learning_path_url}")
    driver.get(learning_path_url.strip())
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a.Course_Course__bLjGn')))

    learning_path_title = driver.find_element(By.XPATH, '/html/body/div/div[2]/div/div/div[1]/div[1]/div[1]/h1').text
    learning_path_folder = os.path.join(base_path, sanitize_filename(learning_path_title))

    if os.path.exists(learning_path_folder):
        logger.log(f"Learning path folder already exists: {learning_path_folder}")
    else:
        os.makedirs(learning_path_folder, exist_ok=True)
        logger.log(f"Created learning path folder: {learning_path_folder}")

    courses = []
    course_elements = driver.find_elements(By.CSS_SELECTOR, 'a.Course_Course__bLjGn')
    for index, course in enumerate(course_elements, start=1):
        title = course.find_element(By.CSS_SELECTOR, 'h3').text
        url = course.get_attribute('href')
        courses.append({'title': f"{index:02d}_{title}", 'url': url})
        logger.log(f"Found course: {title} - {url}")

    for course in courses[start_from_course - 1:]:
        course_path = os.path.join(learning_path_folder, sanitize_filename(course['title']))
        process_course(driver, course, course_path, session, cookies, headers, logger)

def main():
    print('Platzi Course Downloader')
    learning_paths = input('Enter the URLs of the learning paths (comma-separated): ').split(',')

    base_path = os.path.join(os.getcwd(), "Platzi_Downloads")
    if not os.path.exists(base_path):
        os.makedirs(base_path)
        print(f"Created base directory: {base_path}")
    else:
        print(f"Using existing base directory: {base_path}")

    logger = DebugLogger(base_path)

    options = uc.ChromeOptions()
    options.add_argument(f"user-data-dir={USER_DATA_DIR}")
    options.add_argument("--start-maximized")
    driver = uc.Chrome(options=options)
    session = requests.Session()

    try:
        if not ensure_login(driver, logger):
            raise Exception("Failed to login after multiple attempts")

        headers = {
            'User-Agent': driver.execute_script("return navigator.userAgent;"),
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Origin': 'https://platzi.com',
            'Referer': 'https://platzi.com/',
            'Connection': 'keep-alive',
        }

        cookies = {c['name']: c['value'] for c in driver.get_cookies()}

        if len(learning_paths) == 1:
            learning_path_url = learning_paths[0].strip()
            driver.get(learning_path_url)
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a.Course_Course__bLjGn')))

            course_elements = driver.find_elements(By.CSS_SELECTOR, 'a.Course_Course__bLjGn')
            course_titles = [course.find_element(By.CSS_SELECTOR, 'h3').text for course in course_elements]

            print("Courses in this learning path:")
            for i, title in enumerate(course_titles, 1):
                print(f"{i}. {title}")

            start_from = int(input("Enter the number of the course to start from: "))
            process_learning_path(driver, learning_path_url, base_path, session, cookies, headers, logger, start_from)
        else:
            for learning_path_url in learning_paths:
                process_learning_path(driver, learning_path_url, base_path, session, cookies, headers, logger)

    except Exception as e:
        logger.log(f"An error occurred: {str(e)}")
        logger.log(traceback.format_exc())

    finally:
        driver.quit()
        logger.close()

if __name__ == "__main__":
    main()
