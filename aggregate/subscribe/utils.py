# -*- coding: utf-8 -*-

# @Author  : wzdnzd
# @Time    : 2022-07-15

import gzip
import os
import platform
import random
import re
import ssl
import string
import subprocess
import sys
import time
import urllib
import urllib.parse
import urllib.request

from logger import logger
from urlvalidator import isurl

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36 Edg/105.0.1343.27"


# 本地路径协议标识
FILEPATH_PROTOCAL = "file:///"


# ChatGPT 标识
CHATGPT_FLAG = "-GPT"


DEFAULT_HTTP_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
}


def random_chars(length: int, punctuation: bool = False) -> str:
    length = max(length, 1)
    if punctuation:
        chars = "".join(
            random.sample(
                string.ascii_letters + string.digits + string.punctuation, length
            )
        )
    else:
        chars = "".join(random.sample(string.ascii_letters + string.digits, length))

    return chars


def http_get(
    url: str,
    headers: dict = None,
    params: dict = None,
    retry: int = 3,
    proxy: str = "",
    interval: float = 0,
) -> str:
    if not isurl(url=url):
        logger.error(f"invalid url: {url}")
        return ""

    if retry <= 0:
        logger.debug(f"achieves max retry, url={mask_url(url=url)}")
        return ""

    headers = DEFAULT_HTTP_HEADERS if not headers else headers

    interval = max(0, interval)
    try:
        url = encoding_url(url=url)
        if params and isinstance(params, dict):
            data = urllib.parse.urlencode(params)
            if "?" in url:
                url += f"&{data}"
            else:
                url += f"?{data}"

        request = urllib.request.Request(url=url, headers=headers)
        if proxy and (proxy.startswith("https://") or proxy.startswith("http://")):
            host, protocal = "", ""
            if proxy.startswith("https://"):
                host, protocal = proxy[8:], "https"
            else:
                host, protocal = proxy[7:], "http"
            request.set_proxy(host=host, type=protocal)

        response = urllib.request.urlopen(request, timeout=10, context=CTX)
        content = response.read()
        status_code = response.getcode()
        try:
            content = str(content, encoding="utf8")
        except:
            content = gzip.decompress(content).decode("utf8")
        if status_code != 200:
            logger.debug(
                f"request failed, status code: {status_code}\t message: {content}"
            )
            return ""

        return content
    except urllib.error.HTTPError as e:
        logger.debug(f"request failed, url=[{mask_url(url=url)}], code: {e.code}")
        try:
            message = str(e.read(), encoding="utf8")
        except UnicodeDecodeError:
            message = str(e.read(), encoding="utf8")
        if e.code == 503 and "token" not in message:
            time.sleep(interval)
            return http_get(
                url=url,
                headers=headers,
                params=params,
                retry=retry - 1,
                proxy=proxy,
                interval=interval,
            )
        return ""
    except (urllib.error.URLError, TimeoutError) as e:
        message = "timeout" if isinstance(e, TimeoutError) else e.reason
        logger.debug(f"request failed, url=[{mask_url(url=url)}], message: {message}")
        return ""
    except Exception as e:
        logger.debug(e)
        time.sleep(interval)
        return http_get(
            url=url,
            headers=headers,
            params=params,
            retry=retry - 1,
            proxy=proxy,
            interval=interval,
        )


def extract_domain(url: str, include_protocal: bool = False) -> str:
    if not url:
        return ""

    start = url.find("//")
    if start == -1:
        start = -2

    end = url.find("/", start + 2)
    if end == -1:
        end = len(url)

    if include_protocal:
        return url[:end]

    return url[start + 2 : end]


def extract_cookie(text: str) -> str:
    # ?: 标识后面的内容不是一个group
    regex = "((?:v2board)?_session)=((?:.+?);|.*)"
    if not text:
        return ""

    content = re.findall(regex, text)
    cookie = ";".join(["=".join(x) for x in content]).strip()
    return cookie


def cmd(command: list) -> bool:
    if command is None or len(command) == 0:
        return False

    logger.info("command: {}".format(" ".join(command)))

    p = subprocess.Popen(command)
    p.wait()
    return p.returncode == 0


def chmod(binfile: str) -> None:
    if not os.path.exists(binfile) or os.path.isdir(binfile):
        raise ValueError(f"cannot found bin file: {binfile}")

    operating_system = str(platform.platform())
    if operating_system.startswith("Windows"):
        return
    elif operating_system.startswith("macOS") or operating_system.startswith("Linux"):
        cmd(["chmod", "+x", binfile])
    else:
        logger.error("Unsupported Platform")
        sys.exit(0)


def encoding_url(url: str) -> str:
    if not url:
        return ""

    url = url.strip()

    # 正则匹配中文汉字
    cn_chars = re.findall("[\u4e00-\u9fa5]+", url)
    if not cn_chars:
        return url

    # 遍历进行 punycode 编码
    punycodes = list(
        map(lambda x: "xn--" + x.encode("punycode").decode("utf-8"), cn_chars)
    )

    # 对原 url 进行替换
    for c, pc in zip(cn_chars, punycodes):
        url = url[: url.find(c)] + pc + url[url.find(c) + len(c) :]

    return url


def write_file(filename: str, lines: list) -> bool:
    if not filename or not lines:
        logger.error(f"filename or lines is empty, filename: {filename}")
        return False

    try:
        if not isinstance(lines, str):
            lines = "\n".join(lines)

        filepath = os.path.abspath(os.path.dirname(filename))
        os.makedirs(filepath, exist_ok=True)
        with open(filename, "w+", encoding="UTF8") as f:
            f.write(lines)
            f.flush()

        return True
    except:
        return False


def isb64encode(content: str, padding: bool = True) -> bool:
    if not content:
        return False

    # 判断是否为base64编码
    regex = (
        "^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{4}|[A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)$"
    )

    # 不是标准base64编码的情况，padding
    b64flag = re.match(regex, content)
    if not b64flag and len(content) % 4 != 0 and padding:
        content += "=" * (4 - len(content) % 4)
        b64flag = re.match(regex, content)

    return b64flag is not None


def isblank(text: str) -> bool:
    return not text or type(text) != str or not text.strip()


def trim(text: str) -> str:
    if not text or type(text) != str:
        return ""

    return text.strip()


def load_dotenv() -> None:
    path = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    filename = os.path.join(path, ".env")

    if not os.path.exists(filename) or os.path.isdir(filename):
        return

    with open(filename, mode="r", encoding="utf8") as f:
        for line in f.readlines():
            content = line.strip()
            if not content or content.startswith("#") or "=" not in content:
                continue

            content = content.split("#", maxsplit=1)[0]
            words = content.split("=", maxsplit=1)
            k, v = words[0].strip(), words[1].strip()
            if k and v:
                os.environ[k] = v


def mask_url(url: str) -> str:
    # len('http://') equals 7
    if isblank(url) or len(url) < 7:
        return url

    return url[:-7] + "*" * 7
