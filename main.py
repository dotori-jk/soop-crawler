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
    return {"status": "ok", "message": "SOOP Crawler Server is Running"}

@app.get("/scrape")
async def scrape_comments():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(4000)

            # 프레임 전체 탐색 JS 함수
            js_script = """
            () => {
                const list = [];
                const items = document.querySelectorAll('li');
                
                items.forEach(item => {
                    const linkEl = item.querySelector('a[href*="/station/"]');
                    const text = item.innerText || '';
                    
                    if (linkEl && linkEl.innerText.trim()) {
                        const nick = linkEl.innerText.trim();
                        let likes = 0;
                        const match = text.match(/(\\d+)(?=\\s*\\[답글\\]|\\s*답글|$)/) || text.match(/\\b\\d+\\b/g);
                        if (match) {
                            likes = parseInt(match[match.length - 1]) || 0;
                        }
                        
                        if (nick && !['VOD', '게시판', 'Catch', '우왁굳'].includes(nick)) {
                            list.push({
                                nickname: nick,
                                station_url: linkEl.href,
                                likes: likes
                            });
                        }
                    }
                });
                return list;
            }
            """

            all_comments = []
            for frame in page.frames:
                try:
                    comments = await frame.evaluate(js_script)
                    if comments:
                        all_comments.extend(comments)
                except Exception:
                    continue

            # 중복 닉네임 제거
            unique_comments = list({c['nickname']: c for c in all_comments}.values())

            await browser.close()

            # Supabase DB 저장
            if unique_comments and len(unique_comments) > 0:
                try:
                    supabase.table("comments").delete().neq("id", 0).execute()
                    supabase.table("comments").insert(unique_comments).execute()
                except Exception as db_err:
                    return {"status": "partial_success", "db_error": str(db_err), "count": len(unique_comments), "sample": unique_comments[:3]}

            return {"status": "success", "count": len(unique_comments), "sample": unique_comments[:3]}

        except Exception as e:
            await browser.close()
            return {"status": "error", "message": str(e)}
