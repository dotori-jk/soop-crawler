import os
from fastapi import FastAPI
from playwright.async_api import async_playwright
from supabase import create_client, Client

app = FastAPI()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TARGET_URL = "https://www.sooplive.com/station/ecvhao/post/204516133"

@app.get("/")
def home():
    return {"status": "ok", "message": "SOOP Crawler Server"}

@app.get("/scrape")
async def scrape_comments():
    captured_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # 브라우저가 주고받는 네트워크 응답 중 댓글 JSON 데이터를 직접 가로챔
        async def handle_response(response):
            if "comment" in response.url and response.status == 200:
                try:
                    res_json = await response.json()
                    raw_list = res_json.get("data", {}).get("list", []) or res_json.get("list", [])
                    
                    for item in raw_list:
                        nick = item.get("user_nick") or item.get("writer_nick")
                        user_id = item.get("user_id") or item.get("writer_id")
                        likes = item.get("like_cnt") or item.get("like_count") or 0
                        
                        if nick and user_id:
                            captured_data.append({
                                "nickname": str(nick).strip(),
                                "station_url": f"https://www.sooplive.com/station/{str(user_id).strip()}",
                                "likes": int(likes)
                            })
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            await browser.close()

            # 중복 닉네임 제거
            unique_comments = list({c['nickname']: c for c in captured_data}.values())

            # Supabase DB 저장
            if unique_comments:
                supabase.table("comments").delete().neq("id", 0).execute()
                supabase.table("comments").insert(unique_comments).execute()

            return {
                "status": "success", 
                "count": len(unique_comments), 
                "sample": unique_comments[:3]
            }

        except Exception as e:
            await browser.close()
            return {"status": "error", "message": str(e)}
