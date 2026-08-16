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
        page = await browser.new_page()
        
        try:
            # 페이지 로드 대기
            await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000) # 댓글 렌더링 안정화 3초 대기

            # 댓글 데이터 추출
            comments_data = await page.evaluate('''() => {
                const list = [];
                const items = document.querySelectorAll('ul.comment_list > li, div.comment_list li, .comment_area li');
                
                items.forEach(item => {
                    const nickEl = item.querySelector('.user_id') || item.querySelector('strong') || item.querySelector('.nickname');
                    const linkEl = item.querySelector('a[href*="/station/"]');
                    const likeEl = item.querySelector('.like_count') || item.querySelector('[class*="like"]');
                    
                    if (nickEl) {
                        const nickText = nickEl.innerText.trim();
                        if (nickText) {
                            list.push({
                                nickname: nickText,
                                station_url: linkEl ? linkEl.href : '',
                                likes: likeEl ? (parseInt(likeEl.innerText.replace(/[^0-9]/g, '')) || 0) : 0
                            });
                        }
                    }
                });
                return list;
            }''')
            await browser.close()

            # Supabase DB 업데이트
            if comments_data:
                supabase.table("comments").delete().neq("id", 0).execute()
                supabase.table("comments").insert(comments_data).execute()

            return {"status": "success", "count": len(comments_data)}
        except Exception as e:
            await browser.close()
            return {"status": "error", "message": str(e)}
