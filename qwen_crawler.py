#!/usr/bin/env python3
"""
Gemini Deep Research Automation
Script for automated Deep Research query processing and results extraction
"""

from doctest import debug
import json
import os
import random
import re
import argparse
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, NavigableString, Tag
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


# --- Data Classes ---

@dataclass
class ConversationEntry:
    """Represents a single entry (query or response) in a conversation."""
    timestamp: str
    query: str
    response: str
    entry_type: str  # 'user' or 'assistant'
    deep_research_sources: str = ""
    thinking_panel: str = ""
    execution_time_seconds: float = 0.0


@dataclass
class ConversationData:
    """Represents the entire conversation and its metadata."""
    url: str
    title: str
    timestamp: str
    entries: List[ConversationEntry]
    query_id: Optional[int] = None
    topic: Optional[str] = None
    language: Optional[str] = None


# --- Main Crawler Class ---

class QwenCrawler:
    """
    A Selenium-based web crawler to automate 'Deep Research' queries on Qwen
    and extract the results.
    """

    def __init__(self, headless: bool = False, wait_timeout: int = 20, debug: bool = False):
        self.wait_timeout = wait_timeout
        self.driver = None
        self.wait = None
        self.debug = debug
        self._setup_driver(headless)

    def _setup_driver(self, headless: bool):
        """Initializes the Chrome WebDriver with anti-detection options."""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")

        # Anti-detection measures
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        # Performance and stability options
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")

        prefs = {
            "profile.default_content_setting_values": {"notifications": 2, "geolocation": 2},
        }
        chrome_options.add_experimental_option("prefs", prefs)

        service = Service(ChromeDriverManager().install())

        try:
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, self.wait_timeout)
            print("✅ Chrome driver initialized successfully.")
        except Exception as e:
            print(f"❌ Chrome driver initialization failed: {e}")
            raise

    def _simulate_human_behavior(self):
        """Simulates human-like scrolling and pauses."""
        try:
            for _ in range(random.randint(1, 2)):
                scroll_height = "document.body.scrollHeight"
                scroll_pos = random.choice([100, f"{scroll_height}/4", f"{scroll_height}/2", 0])
                self.driver.execute_script(f"window.scrollTo(0, {scroll_pos});")
                time.sleep(random.uniform(0.5, 1.5))
        except Exception as e:
            print(f"🤖 Human behavior simulation completed with minor issues: {e}")

    def navigate_to_conversation(self, url: str):
        """Navigates to the specified URL and waits for manual login."""
        print(f"🔗 Accessing: {url}")
        self.driver.get(url)
        wait_time = random.uniform(2, 5)
        print(f"⏳ Waiting {wait_time:.1f}s for page load...")
        time.sleep(wait_time)
        self._simulate_human_behavior()
        input("Press Enter to continue after successful login...")

    def click_new_chat(self) -> bool:
        """Clicks the 'New chat' button to start a fresh session."""
        print("🆕 Clicking 'New chat' button...")
        try:
            new_chat_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "div.sidebar-entry-list-content"))
            )
            new_chat_button.click()
            print("✅ 'New chat' button clicked successfully.")
            time.sleep(random.uniform(1, 3))
            return True
        except TimeoutException:
            print("⚠️ Could not find 'New chat' button, continuing with current conversation.")
            return False

    def perform_deep_research(self, query: str, attachments: List[str] = None) -> Optional[ConversationEntry]:
        """Automates the entire Deep Research process from query to result extraction."""
        print(f"🔍 Starting Deep Research for query: '{query[:100]}...'")

        start_time = time.time()
        try:
            # Step 1: Select Deep Research mode via the "+" dropdown menu
            print("📍 Step 1: Selecting Deep Research mode...")
            plus_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".mode-select-open"))
            )
            plus_button.click()
            time.sleep(1)

            deep_research_item = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR,
                    "[data-menu-id*='deep_research']"))
            )
            deep_research_item.click()
            print("✅ Deep Research mode selected.")
            time.sleep(2)

            # Step 1.5: Switch to Advanced mode
            print("📍 Step 1.5: Switching to Advanced mode...")
            normal_dropdown = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".message-input-column-footer-submode .advanced"))
            )
            normal_dropdown.click()
            time.sleep(1)

            advanced_option = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".advanced-dropdown-content-label"))
            )
            advanced_option.click()
            print("✅ Advanced mode selected.")
            time.sleep(1)

            # Step 2: Type the query (without sending yet)
            print("📍 Step 2: Typing query...")
            self._type_message(query.replace('\n', ' '))

            # Step 3: Upload attachments
            if attachments:
                print("📍 Step 3: Uploading attachments...")
                self._upload_attachments(attachments)

            # Step 4: Send the query (with attachments)
            print("📍 Step 4: Sending query...")
            self._click_send()

            # Record start time
            start_time = time.time()
            # Step 5: Send the confirmation message to start the research
            print("📍 Step 5: Sending 'Start Research' confirmation...")
            self._submit_chat_message("开始研究")

            # Step 5: Wait for research to complete
            self._wait_for_completion()

            # Step 6: Extract results
            print("📍 Step 6: Extracting Deep Research results...")
            end_time = time.time()
            execution_time = end_time - start_time
            result_entry = self._extract_deep_research_results(query, execution_time)

            if result_entry:
                print("✅ Deep Research results extracted successfully.")
                return result_entry
            else:
                print("❌ Failed to extract research results.")
                return None

        except Exception as e:
            print(f"❌ An error occurred during the Deep Research process: {e}")
            end_time = time.time()
            execution_time = end_time - start_time
            print(f"⏱️ Process ran for {execution_time:.2f} seconds before the error.")
            return None

    def _type_message(self, message: str):
        """Types a message into the chat input without sending."""
        try:
            query_box = self.wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "textarea.message-input-textarea"))
            )
            query_box.clear()
            query_box.send_keys(message)
            print(f"✅ Message typed: {message[:80]}")
            time.sleep(1)
        except TimeoutException:
            print("❌ Failed to type message.")
            raise

    def _click_send(self):
        """Clicks the send button."""
        try:
            send_button = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.send-button"))
            )
            send_button.click()
            print("✅ Message sent.")
            time.sleep(3)
        except TimeoutException:
            print("❌ Failed to click send button.")
            raise

    def _submit_chat_message(self, message: str):
        """Types a message and sends it."""
        self._type_message(message)
        self._click_send()
    
    def _upload_attachments(self, file_paths: List[str]):
        """Upload attachment files to Qwen by simulating drop event with File objects."""
        if not file_paths:
            return

        import base64
        import mimetypes

        print(f"📎 Uploading {len(file_paths)} attachment(s)...")
        try:
            for file_path in file_paths:
                abs_path = os.path.abspath(file_path)
                if not os.path.isfile(abs_path):
                    print(f"   ⚠️ File not found, skipping: {abs_path}")
                    continue

                # Read file and encode as base64
                with open(abs_path, 'rb') as f:
                    file_data = base64.b64encode(f.read()).decode('utf-8')

                filename = os.path.basename(file_path)
                mime_type = mimetypes.guess_type(abs_path)[0] or 'image/png'

                # Simulate drag-and-drop onto the input area
                self.driver.execute_script("""
                    const base64Data = arguments[0];
                    const fileName = arguments[1];
                    const mimeType = arguments[2];

                    const byteCharacters = atob(base64Data);
                    const byteArray = new Uint8Array(byteCharacters.length);
                    for (let i = 0; i < byteCharacters.length; i++) {
                        byteArray[i] = byteCharacters.charCodeAt(i);
                    }
                    const file = new File([byteArray], fileName, { type: mimeType });

                    const dropTarget = document.querySelector('.message-input-container');
                    const dt = new DataTransfer();
                    dt.items.add(file);
                    ['dragenter', 'dragover', 'drop'].forEach(eventType => {
                        dropTarget.dispatchEvent(new DragEvent(eventType, {
                            dataTransfer: dt,
                            bubbles: true,
                            cancelable: true
                        }));
                    });
                """, file_data, filename, mime_type)

                print(f"   ✅ Uploaded: {os.path.basename(file_path)}")
                time.sleep(3)

            # Wait for upload previews/thumbnails to finish rendering
            time.sleep(3)
            print("✅ All attachments uploaded successfully.")

        except Exception as e:
            print(f"❌ Error uploading attachments: {e}")
            raise

    def _wait_for_completion(self):
        """Waits for loading indicators to disappear, signaling research is complete."""
        print("📍 Step 4: Waiting for Deep Research to complete (this may take several minutes)...")
        try:
            long_wait = WebDriverWait(self.driver, 3600)  # 60-minute timeout
            
            # This is the locator for the status text element
            status_locator = (By.CSS_SELECTOR, "span.deep-research-text")

            # --- Stage 1: Wait for the "loading" text to appear ---
            # This confirms that the deep research process has successfully started.
            # We check for partial text "深入研究" which covers the loading state.
            print("⏳ Confirming that the research process has started...")
            long_wait.until(lambda d:
                EC.text_to_be_present_in_element(status_locator, "深入研究...")(d)
                or EC.text_to_be_present_in_element(status_locator, "Deep Research...")(d)
            )
            print("✅ Research is in progress. Now waiting for completion...")

            # --- Stage 2: Wait for the "completed" text to appear ---
            print("⏳ Waiting for the completion message...")
            long_wait.until(lambda d:
                EC.text_to_be_present_in_element(status_locator, "深入研究已完成")(d)
                or EC.text_to_be_present_in_element(status_locator, "Deep Research Completed")(d)
            )
            print("✅ Deep Research completion confirmed.")
            
            time.sleep(5)  # Allow content to fully render
            
        except TimeoutException:
            print("⚠️ Timed out waiting for research completion, but will try to extract results anyway.")

    def _extract_deep_research_results(self, query: str, execution_time: float) -> Optional[ConversationEntry]:
        """Extracts all components of the deep research results from the page."""
        try:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            print("🔍 Extracting all result components...")

            # Extract main response content (specifically the phase-answer, not clarification questions)
            response_text = ""
            try:
                response_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, "div.response-message-content.phase-answer div.custom-qwen-markdown"
                )
                if response_elements:
                    response_element = response_elements[-1]  # Last match = final answer
                    response_text = self.html_to_markdown(response_element.get_attribute('outerHTML'))
                    print(f"✅ Found and converted main response content ({len(response_text)} chars).")
                else:
                    print("⚠️ Could not find the response content container.")
            except NoSuchElementException:
                print("⚠️ Could not find the response content container.")
            except Exception as e:
                print(f"⚠️ Error extracting main response: {e}")

            if not response_text:
                print("❌ No response text found.")
                return None

            # Extract thinking panel (research steps) and sources
            thinking_panel = self._extract_research_steps()
            deep_research_sources = self._extract_sources_content_deep_research()

            entry = ConversationEntry(
                timestamp=datetime.now().isoformat(),
                query=query,
                response=response_text,
                entry_type='assistant',
                deep_research_sources=deep_research_sources,
                thinking_panel=thinking_panel,
                execution_time_seconds=execution_time
            )

            print("\n📊 Deep Research Extraction Summary:")
            print(f"   ✅ Response: {len(response_text)} characters")
            print(f"   {'✅' if deep_research_sources else '❌'} Sources: {'Found' if deep_research_sources else 'Not Found'}")
            print(f"   {'✅' if thinking_panel else '❌'} Thinking Panel: {'Found' if thinking_panel else 'Not Found'}")
            print(f"   ⏱️ Execution time: {execution_time:.2f}s ({execution_time/60:.2f}m)")
            return entry

        except Exception as e:
            print(f"❌ Error during final result extraction: {e}")
            return None

    def _extract_research_steps(self) -> str:
        """Extracts the research steps list from the Deep Research panel."""
        print("🔍 Extracting research steps...")
        try:
            panel = self.driver.find_element(
                By.CSS_SELECTOR, "div.deep-research-list-container.research-panel"
            )
            html = panel.get_attribute("outerHTML")
            soup = BeautifulSoup(html, "html.parser")

            steps = []
            for item in soup.select("div.list-card-step-item"):
                text_el = item.select_one("span.list-card-step-item-text")
                if text_el:
                    steps.append(text_el.get_text(strip=True))

            if steps:
                result = "\n".join(f"{i+1}. {step}" for i, step in enumerate(steps))
                print(f"✅ Extracted {len(steps)} research steps.")
                return result
            else:
                print("⚠️ No research steps found in panel.")
                return ""
        except NoSuchElementException:
            print("⚠️ Research steps panel not found.")
            return ""
        except Exception as e:
            print(f"❌ Error extracting research steps: {e}")
            return ""

    def _extract_thinking_panel_deep_research_for_static(self) -> str:
        """Extracts thinking panel content and converts it to Markdown."""
        print("🔍 Extracting thinking panel...")
        try:
            long_wait = WebDriverWait(self.driver, 180)  # 3-minute timeout

            panel_selector = "[class*='deep_research_time_slot']"
            thinking_panel_element = long_wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, panel_selector)))
            markdown_content = self._convert_element_to_markdown(thinking_panel_element)
            result = "\n".join([line.strip() for line in markdown_content.strip().split('\n')])
            print("✅ Successfully converted thinking panel to Markdown.")
            return result
        except (TimeoutException, NoSuchElementException):
            print("⚠️ Thinking panel not found.")
            return ""
        except Exception as e:
            print(f"❌ Error extracting thinking panel: {e}")
            return ""

    def _extract_thinking_panel_deep_research(self) -> str:
        """
        Clicks the expansion icon to reveal the thinking panel, then extracts
        its content and converts it to Markdown.
        """
        print("🔍 Extracting thinking panel...")
        try:
            # Use a sufficiently long wait to handle variations in page load speed
            long_wait = WebDriverWait(self.driver, 180)  # 3-minute timeout

            # Step 1: Find and click the icon to expand the thinking panel.
            # The selector targets the <span> you identified.
            expansion_icon_selector = (By.CSS_SELECTOR, "span.deep_research_alls_icon")
            
            print("   - Waiting for the thinking panel expansion icon to be clickable...")
            expansion_icon = long_wait.until(
                EC.element_to_be_clickable(expansion_icon_selector)
            )
            
            # Use JavaScript to click, which can be more reliable for complex elements
            self.driver.execute_script("arguments[0].click();", expansion_icon)
            print("   - ✅ Clicked the expansion icon.")

            # Step 2: Now wait for the actual panel to appear in the DOM.
            # The selector is the one you originally used for the panel itself.
            panel_selector = "[class*='deep_research_time_slot']"
            
            print("   - Waiting for the thinking panel to appear after click...")
            thinking_panel_element = long_wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, panel_selector))
            )
            
            # Step 3: Once the panel is present, extract its content.
            # This uses your existing, correct logic.
            print("   - ✅ Thinking panel is present. Converting content to Markdown...")
            markdown_content = self._convert_element_to_markdown(thinking_panel_element)
            result = "\n".join([line.strip() for line in markdown_content.strip().split('\n')])
            
            print("✅ Successfully converted thinking panel to Markdown.")
            return result
            
        except (TimeoutException, NoSuchElementException):
            print("⚠️ Thinking panel not found. The expansion icon may not have appeared or the panel did not load after the click.")
            return ""
        except Exception as e:
            print(f"❌ An error occurred while extracting the thinking panel: {e}")
            return ""

    def _extract_sources_content_deep_research(self) -> str:
        """Clicks the sources button and extracts source details into Markdown."""
        print("🔍 Extracting sources...")
        try:
            source_btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".sources_container")))
            source_btn.click()
            print("✅ Clicked sources button.")

            popup = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".deep-research-origins-pc")))
            print("✅ Sources popup is visible.")
            time.sleep(1)  # Wait for content to render

            # Use BeautifulSoup for robust parsing of the popup's HTML
            html = popup.get_attribute("outerHTML")
            soup = BeautifulSoup(html, "html.parser")
            formatted_sources = ["Sources used in the report"]

            for item in soup.select("div.deep-research-origins-item"):
                url_element = item.select_one("span.hostnameText")
                title_element = item.select_one("div.deep-research-origins-item-content-title")

                if url_element and title_element:
                    url = url_element.get_text(strip=True)
                    title = title_element.get_text(strip=True)
                    if url.startswith(('http://', 'https://')):
                        domain = urlparse(url).netloc
                        markdown_link = f"[{domain}{title}Opens in a new window]({url})"
                        formatted_sources.append(markdown_link)

            # Close the popup
            try:
                close_btn = popup.find_element(By.CSS_SELECTOR, ".close-icon, [class*='close-button']")
                close_btn.click()
                print("✅ Closed sources popup.")
            except Exception:
                print("⚠️ Could not find a close button, proceeding anyway.")

            return "\n".join(formatted_sources)
        except (TimeoutException, NoSuchElementException):
            print("⚠️ Sources button or popup not found.")
            return ""
        except Exception as e:
            print(f"❌ Error extracting sources: {e}")
            return ""

    def html_to_markdown(self, html: str) -> str:
        """Converts a given HTML string to a structured Markdown string."""
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")

        # Pre-process: remove empty spacer divs
        for spacer in soup.find_all("div", class_="qwen-markdown-space"):
            spacer.decompose()

        # Pre-process citation buttons (old format)
        for wrap in soup.find_all("span", class_="citation-button-wrap"):
            btn = wrap.find("button", {"data-index": True})
            if btn:
                wrap.insert_after(NavigableString(f"[^{btn['data-index']}]"))
            wrap.decompose()

        # Pre-process LaTeX formulas: extract the TeX annotation text
        for latex in soup.find_all("span", class_="qwen-markdown-latex"):
            annotation = latex.find("annotation")
            if annotation:
                tex = annotation.get_text(strip=True)
                latex.replace_with(NavigableString(f"${tex}$"))
            else:
                latex.replace_with(NavigableString(latex.get_text(strip=True)))

        # Pre-process Qwen citations into inline references
        for cite in soup.find_all("span", class_="qwen-markdown-citation"):
            hostnames = cite.find_all("div", class_="qwen-chat-markdown-tokens-hostname")
            if hostnames:
                source = hostnames[0].get_text(strip=True)
                cite.replace_with(NavigableString(f" [{source}]"))
            else:
                cite.decompose()

        def _convert_tag(node) -> str:
            if isinstance(node, NavigableString):
                return str(node)
            if not isinstance(node, Tag):
                return ""

            classes = node.get('class', [])
            tag = node.name.lower()

            # Qwen paragraph divs → treat as <p>
            if tag == "div" and "qwen-markdown-paragraph" in classes:
                inner_md = "".join(_convert_tag(c) for c in node.children).strip()
                return f"\n\n{inner_md}\n\n"

            # Table handling
            if tag == "table":
                return self._convert_table_to_markdown(node)
            # Skip table wrapper/header chrome
            if tag == "div" and "qwen-markdown-table-wrapper" in classes:
                table = node.find("table")
                if table:
                    return self._convert_table_to_markdown(table)
                return ""
            if tag == "div" and "qwen-markdown-table-header" in classes:
                return ""

            inner_md = "".join(_convert_tag(c) for c in node.children).strip()

            if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                level = int(tag[1])
                return f'\n\n{"#" * level} {inner_md}\n\n'
            if tag == "p":
                return f"\n\n{inner_md}\n\n"
            if tag == "ul":
                items = [_convert_tag(li).strip() for li in node.find_all("li", recursive=False)]
                return "\n" + "\n".join(f"- {item}" for item in items) + "\n"
            if tag == "ol":
                items = [_convert_tag(li).strip() for li in node.find_all("li", recursive=False)]
                return "\n" + "\n".join(f"{i+1}. {item}" for i, item in enumerate(items)) + "\n"
            if tag in {"strong", "b"}:
                return f"**{inner_md}**"
            if tag in {"em", "i"}:
                return f"*{inner_md}*"

            # Handle special class for visited links in thinking panel
            if 'link-card-item-title' in classes:
                return f"- {inner_md}\n"

            return inner_md  # Default: strip tag, keep content

        markdown = _convert_tag(soup.body or soup).strip()
        return re.sub(r"\n{3,}", "\n\n", markdown)  # Clean up excess newlines

    def _convert_table_to_markdown(self, table_node) -> str:
        """Converts an HTML <table> node to a Markdown table string."""
        rows = []
        # Extract header
        thead = table_node.find("thead")
        if thead:
            headers = [th.get_text(strip=True) for th in thead.find_all("th")]
            if headers:
                rows.append("| " + " | ".join(headers) + " |")
                rows.append("| " + " | ".join(["---"] * len(headers)) + " |")

        # Extract body rows
        tbody = table_node.find("tbody")
        if tbody:
            for tr in tbody.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                rows.append("| " + " | ".join(cells) + " |")

        if rows:
            return "\n\n" + "\n".join(rows) + "\n\n"
        return ""


    def _convert_element_to_markdown(self, element) -> str:
        """
        Recursively traverses a web element and its children to convert its
        HTML structure into a Markdown formatted string.
        """
        # Get the tag name of the current element
        tag = element.tag_name.lower()
        
        # Get the text content of the element
        # We use execute_script for a cleaner text extraction without unexpected whitespace
        try:
            text = self.driver.execute_script("return arguments[0].textContent;", element).strip()
        except Exception:
            text = ""

        # Base cases for formatting tags
        if tag == 'h1':
            return f"\n# {text}\n"
        if tag == 'h2':
            return f"\n## {text}\n"
        if tag == 'h3':
            return f"\n### {text}\n"
        if tag == 'li':
            # For list items, just format the text with a bullet
            return f"- {text}\n"
        if tag == 'p':
            # Add extra newlines for paragraph spacing
            return f"\n{text}\n"
        
        # Special handling for visited link cards
        if 'link-card-item-title' in element.get_attribute('class'):
            return f"- {text}\n"

        # Recursive step for container tags (div, ul, etc.)
        output = ""
        children = element.find_elements(By.XPATH, "./*")
        
        # If an element has no child elements but contains text, return it.
        # This handles simple divs or other tags with just text.
        if not children and text:
            return text

        # Recursively call the function for each child and build the output
        for child in children:
            output += self._convert_element_to_markdown(child)
            
        return output

    def save_data(self, conversation_data: ConversationData, output_file: str):
        """Saves the conversation data to a JSON file."""
        try:
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(asdict(conversation_data), f, ensure_ascii=False, indent=2)
            print(f"✅ Data saved to: {output_file}")
        except Exception as e:
            print(f"❌ Failed to save data: {e}")

    def close(self):
        """Closes the WebDriver."""
        if self.driver:
            self.driver.quit()
            print("🔒 Browser closed.")

    def debug_extract_now(self):
        """Immediately extracts content from the current page for debugging."""
        print("\n" + "="*80)
        print("🧪 DEBUG MODE: Attempting to extract from current page...")
        result_entry = self._extract_deep_research_results(query="debug_query", execution_time=0.0)

        if result_entry:
            conversation_data = ConversationData(
                url=self.driver.current_url,
                title="Debug Extraction",
                timestamp=datetime.now().isoformat(),
                entries=[result_entry],
                query_id=9999
            )
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"results/debug_results/debug_extraction_{timestamp}.json"
            self.save_data(conversation_data, output_file)
        else:
            print("❌ Debug extraction failed to find any results.")


# --- Main Execution ---

def load_queries_from_jsonl(file_path: str) -> List[Dict]:
    """Loads queries from a JSONL file."""
    queries = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                if line.strip():
                    try:
                        queries.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        print(f"⚠️ Line {i}: Invalid JSON - {e}")
        print(f"✅ Loaded {len(queries)} queries from {file_path}")
        return queries
    except FileNotFoundError:
        print(f"❌ Query file not found: {file_path}")
        return []


def load_queries_from_mirobench(dir_path: str, begin: int, end: int) -> List[Dict]:
    """Loads queries from mirobench directory structure.

    Each subdirectory contains:
      - query.txt: the original query text
      - rewritten_query.txt: an expanded query
      - attachments/: image files

    Returns a list of dicts with keys: id, prompt, rewritten_query, attachments (list of image paths).
    """
    queries = []
    attachments = []
    if not os.path.isdir(dir_path):
        print(f"❌ Directory not found: {dir_path}")
        return []

    for entry_name in sorted(os.listdir(dir_path)):
        entry_path = os.path.join(dir_path, entry_name)
        if not os.path.isdir(entry_path):
            continue

        # Extract numeric id from directory name (e.g. "image_101_..." -> 101)
        parts = entry_name.split('_')
        if entry_name.startswith("multi"):
            query_id = int(parts[2])
        else:
            query_id = int(parts[1])
    
        if query_id >= begin and query_id <= end:

            # Read query
            query_file = os.path.join(entry_path, 'query.json')
            attachments_dir = os.path.join(entry_path, 'attachments')
            
            with open(query_file, "r", encoding="utf-8") as f:
                data = json.load(f)


            # Collect image attachment paths
            attachment = []
            if os.path.isdir(attachments_dir):
                for fname in sorted(os.listdir(attachments_dir)):
                    fpath = os.path.join(attachments_dir, fname)
                    if os.path.isfile(fpath):
                        attachment.append(fpath)

            attachments.append(attachment)
            queries.append(data)

    print(f"✅ Loaded {len(queries)} queries from {dir_path}")
    return queries, attachments

def main():
    """Main function to run the automation script."""
    parser = argparse.ArgumentParser(description="Qwen Deep Research Automation")
    parser.add_argument("begin", type=int)
    parser.add_argument("end", type=int)
    parser.add_argument("input_dir", type=str)
    args = parser.parse_args()


    print("=" * 60)
    print("🤖 Qwen Deep Research Automation")
    print("=" * 60)

    output_dir = "./qwen3.5-plus-deepresearch-advanced"

    queries, attachments = load_queries_from_mirobench(args.input_dir, args.begin, args.end)
    if not queries:
        return
    
    existing_files = os.listdir(output_dir) if os.path.exists(output_dir) else []
    completed_ids = {
        data['id']
        for filename in existing_files if filename.startswith("deep_research_")
        for data in [json.load(open(os.path.join(output_dir, filename), 'r', encoding='utf-8'))]
        if 'id' in data
    }

    if completed_ids:
        print(f"📁 Found {len(completed_ids)} completed queries.")
        filtered = [(q, a) for q, a in zip(queries, attachments) if q.get('id') not in completed_ids]
        if filtered:
            queries, attachments = zip(*filtered)
            queries, attachments = list(queries), list(attachments)
        else:
            queries, attachments = [], []
        print(f"⏭️  Skipping completed queries. {len(queries)} remaining.")

    if not queries:
        print("✅ All queries are already completed!")
        return

    crawler = QwenCrawler(headless=False)
    completed_count = 0
    failed_count = 0

    try:
        crawler.navigate_to_conversation("https://chat.qwen.ai")
        os.makedirs(output_dir, exist_ok=True)

        for i, query_data in enumerate(queries, 1):
            query_id = query_data.get('id', f"unidentified_{i}")
            print("\n" + "="*60)
            print(f"🔄 Processing Query {i}/{len(queries)} (ID: {query_id})")
            print(f"📋 Topic: {query_data.get('topic', 'N/A')}")
            attachment = attachments[i - 1]
            if attachment:
                print(f"📎 Attachment: {len(attachment)} image(s)")
                for att in attachment:
                    print(f"   - {att}")

            result_entry = crawler.perform_deep_research(query_data.get('rewritten_query'), attachments=attachment)

            if result_entry:
                query_data["response"] = result_entry.response
                query_data["process"] = result_entry.thinking_panel
                output_file = os.path.join(output_dir, f"deep_research_{query_id}.json")
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(query_data, f, ensure_ascii=False, indent=2)
                completed_count += 1
                print(f"✅ Data saved to: {output_file}")
                print(f"📊 Query {query_id} completed successfully!")
            else:
                failed_count += 1
                print(f"❌ Query {query_id} failed.")
            
            print(f"   Progress: {completed_count} completed, {failed_count} failed.")

            if i < len(queries):
                think_time = random.uniform(3, 8)
                print(f"🤔 Taking a {think_time:.1f}s break...")
                time.sleep(think_time)
                crawler.click_new_chat()

    except KeyboardInterrupt:
        print("\n⏹️ Process interrupted by user.")
    except Exception as e:
        print(f"\n❌ A critical error occurred in the main loop: {e}")
    finally:
        print("\n" + "="*60)
        print("🎉 Batch processing finished!")
        print(f"✅ Successful: {completed_count}/{len(queries)}")
        print(f"❌ Failed: {failed_count}/{len(queries)}")
        print(f"📁 Results saved in: {output_dir}")
        crawler.close()


if __name__ == "__main__":
    main()
