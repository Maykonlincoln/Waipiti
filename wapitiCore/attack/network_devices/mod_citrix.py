import json
import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from httpx import RequestError

from wapitiCore.attack.attack import Attack
from wapitiCore.net import Request
from wapitiCore.net.response import Response
from wapitiCore.definitions.fingerprint import NAME as TECHNO_DETECTED, WSTG_CODE
from wapitiCore.main.log import log_blue, logging

MSG_NO_CITRIX = "No Citrix Product Detected"
MSG_CITRIX_DETECTED = "{0}{1} Detected !"


class ModuleCitrix(Attack):
    """Detect Citrix Devices."""

    device_name = "Citrix"
    version = ""

    async def check_citrix(self, url):
        check_list = ['logon/LogonPoint/']

        for item in check_list:
            full_url = urljoin(url, item)
            request = Request(full_url, 'GET')
            try:
                response: Response = await self.crawler.async_send(request, follow_redirects=False)
            except RequestError:
                self.network_errors += 1
                continue

            if response.is_success:
                return await self.detect_citrix_product(response.content)

        return False

    async def detect_citrix_product(self, response_content):
        soup = BeautifulSoup(response_content, 'html.parser')
        title_tag = soup.title
        # If title tag exists and has a class attribute
        if title_tag:
            if 'class' in title_tag.attrs:
                title_class = title_tag['class']
                # Assuming class is a list, extracting the first class
                if title_class:
                    extract_pattern = r"^_ctxstxt_(.*)$"
                    match = re.search(extract_pattern, title_class[0])
                    if match:
                        self.device_name = match.group(1)
                        return True

                    return False
            else:
                title = title_tag.text
                if "Citrix" in title:
                    # Extract the product name from the title
                    self.device_name = title
                    return True
        return False

    async def attack(self, request: Request, response: Optional[Response] = None):
        self.finished = True
        request_to_root = Request(request.url)

        try:
            if await self.check_citrix(request_to_root.url):
                citrix_detected = {
                    "name": self.device_name,
                    "version": "",
                    "categories": ["Network Equipment"],
                    "groups": ["Content"]
                }
                log_blue(
                    MSG_CITRIX_DETECTED,
                    self.device_name,
                    self.version
                )

                await self.add_addition(
                    category=TECHNO_DETECTED,
                    request=request_to_root,
                    info=json.dumps(citrix_detected),
                    wstg=WSTG_CODE
                )
            else:
                log_blue(MSG_NO_CITRIX)
        except RequestError as req_error:
            self.network_errors += 1
            logging.error(f"Request Error occurred: {req_error}")
