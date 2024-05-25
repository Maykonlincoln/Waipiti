#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of the Wapiti project (https://wapiti-scanner.github.io)
# Copyright (C) 2023-2024 Cyberwatch
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
import json
import re
from os.path import join as path_join
from typing import Optional
from urllib.parse import urljoin

from httpx import RequestError

from wapitiCore.net import Request
from wapitiCore.attack.cms.cms_common import CommonCMS, MSG_TECHNO_VERSIONED
from wapitiCore.net.response import Response
from wapitiCore.definitions.fingerprint_webapp import NAME as WEB_APP_VERSIONED, WSTG_CODE as WEB_WSTG_CODE
from wapitiCore.definitions.fingerprint import WSTG_CODE as TECHNO_DETECTED_WSTG_CODE
from wapitiCore.definitions.fingerprint import NAME as TECHNO_DETECTED, WSTG_CODE
from wapitiCore.main.log import log_blue, logging

MSG_NO_WP = "No WordPress Detected"


class ModuleWpEnum(CommonCMS):
    """Detect WordPress version."""
    PAYLOADS_HASH = "wp_hash_files.json"
    PAYLOADS_FILE_PLUGINS = "wordpress_plugins.txt"
    PAYLOADS_FILE_THEMES = "wordpress_themes.txt"
    versions = []

    async def check_wp(self, url):
        check_list = [
            "wp-content",
            "wp-json",
            "wp-includes",
            "wp-admin",
            "generator\" content=\"wordpress",  # Check for the generator meta tag
            "wp-embed-responsive",  # Check for WordPress oEmbed script
        ]
        request = Request(url, 'GET')
        try:
            response: Response = await self.crawler.async_send(request, follow_redirects=True)
        except RequestError:
            self.network_errors += 1
        except Exception as exception:
            logging.exception(exception)
        else:
            if any(indicator in response.content for indicator in check_list):
                return True  # WordPress indicator found

        return False

    def get_plugin(self):
        with open(
            path_join(self.DATA_DIR, self.PAYLOADS_FILE_PLUGINS),
            errors="ignore",
            encoding='utf-8'
        ) as plugin_list:
            for line in plugin_list:
                plugin = line.strip()
                if plugin:
                    yield plugin

    def get_theme(self):
        with open(
            path_join(self.DATA_DIR, self.PAYLOADS_FILE_THEMES),
            errors="ignore",
            encoding='utf-8'
        ) as theme_list:
            for line in theme_list:
                theme = line.strip()
                if theme:
                    yield theme

    async def detect_plugin(self, url):
        for plugin in self.get_plugin():
            if self._stop_event.is_set():
                break

            plugin_path = f'/wp-content/plugins/{plugin}/readme.txt'
            plugin_url = urljoin(url, plugin_path)
            request = Request(plugin_url, 'GET')
            response = await self.crawler.async_send(request)

            if response.is_success:
                version = re.search(r'tag:\s*([\d.]+)', response.content)

                # This check was added to detect invalid format of "Readme.txt" who can cause a crashe
                if version:
                    version = version.group(1)
                else:
                    logging.warning("Readme.txt is not in a valid format")
                    version = ""

                plugin_detected = {
                    "name": plugin,
                    "versions": [version],
                    "categories": ["WordPress plugins"],
                    "groups": ['Add-ons']
                }

                log_blue(
                    MSG_TECHNO_VERSIONED,
                    plugin,
                    version
                )

                await self.add_addition(
                    category=TECHNO_DETECTED,
                    request=request,
                    info=json.dumps(plugin_detected),
                    wstg=TECHNO_DETECTED_WSTG_CODE,
                    response=response
                )
            elif response.status == 403:
                plugin_detected = {
                    "name": plugin,
                    "versions": [""],
                    "categories": ["WordPress plugins"],
                    "groups": ['Add-ons']
                }
                log_blue(
                    MSG_TECHNO_VERSIONED,
                    plugin,
                    [""]
                )
                await self.add_addition(
                    category=TECHNO_DETECTED,
                    request=request,
                    info=json.dumps(plugin_detected),
                    wstg=TECHNO_DETECTED_WSTG_CODE,
                    response=response
                )

    async def detect_theme(self, url):
        for theme in self.get_theme():
            if self._stop_event.is_set():
                break

            theme_path = f'/wp-content/themes/{theme}/readme.txt'
            theme_url = urljoin(url, theme_path)
            request = Request(theme_url, 'GET')
            response = await self.crawler.async_send(request)

            if response.is_success:
                version = re.search(r'tag:\s*([\d.]+)', response.content)
                # This check was added to detect invalid format of "Readme.txt" who can cause a crashe
                if version:
                    version = version.group(1)
                else:
                    version = ""
                theme_detected = {
                    "name": theme,
                    "versions": [version],
                    "categories": ["WordPress themes"],
                    "groups": ['Add-ons']
                }
                log_blue(
                    MSG_TECHNO_VERSIONED,
                    theme,
                    version
                )
                await self.add_addition(
                    category=TECHNO_DETECTED,
                    request=request,
                    info=json.dumps(theme_detected),
                    wstg=TECHNO_DETECTED_WSTG_CODE,
                    response=response
                )
            elif response.status == 403:
                theme_detected = {
                    "name": theme,
                    "versions": [""],
                    "categories": ["WordPress themes"],
                    "groups": ['Add-ons']
                }
                log_blue(
                    MSG_TECHNO_VERSIONED,
                    theme,
                    [""]
                )
                await self.add_addition(
                    category=TECHNO_DETECTED,
                    request=request,
                    info=json.dumps(theme_detected),
                    wstg=TECHNO_DETECTED_WSTG_CODE,
                    response=response
                )

    async def must_attack(self, request: Request, response: Optional[Response] = None):
        if self.finished or request.method == "POST":
            return False

        return request.url == await self.persister.get_root_url()

    async def attack(self, request: Request, response: Optional[Response] = None):
        self.finished = True
        is_wp_detected = False
        target_url = [request.url]
        root_url = self.get_root_url(request.url)
        if request.url != root_url:
            target_url.append(root_url)

        request_to_root = request

        for url in target_url:
            request_to_root = Request(url)

            if await self.check_wp(url):
                is_wp_detected = True
                await self.detect_version(self.PAYLOADS_HASH, url)  # Call the method on the instance
                self.versions = sorted(self.versions, key=lambda x: x.split('.')) if self.versions else []
                if self.versions:
                    break

        wp_detected = {
            "name": "WordPress",
            "versions": self.versions,
            "categories": ["CMS WordPress"],
            "groups": ["Content"]
        }
        if self.versions:
            await self.add_vuln_info(
                category=WEB_APP_VERSIONED,
                request=request_to_root,
                info=json.dumps(wp_detected),
                wstg=WEB_WSTG_CODE
            )
        if is_wp_detected:
            log_blue(
                MSG_TECHNO_VERSIONED,
                "WordPress",
                self.versions
            )
            await self.add_addition(
                category=TECHNO_DETECTED,
                request=request_to_root,
                info=json.dumps(wp_detected),
                wstg=WSTG_CODE
            )

            log_blue("Enumeration of WordPress Plugins :")
            await self.detect_plugin(request_to_root.url)
            log_blue("----")
            log_blue("Enumeration of WordPress Themes :")
            await self.detect_theme(request_to_root.url)
        else:
            log_blue(MSG_NO_WP)
