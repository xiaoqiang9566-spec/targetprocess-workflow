from __future__ import annotations

import json
import os
import sys
import urllib.request


def main() -> int:
    url = os.environ["TP_URL"]
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Origin": "https://suuntomap.suunto.cn",
        "Referer": "https://suuntomap.suunto.cn/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/148.0.0.0 Safari/537.36"
        ),
        'sec-ch-ua': '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        'sec-ch-ua-platform': '"Windows"',
    }
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    print(
        json.dumps(
            {
                "status": getattr(response, "status", 200),
                "count": len(payload.get("Items", [])),
                "first_id": (payload.get("Items") or [{}])[0].get("Id"),
                "keys": list((payload.get("Items") or [{}])[0].keys())[:6],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
