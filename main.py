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
            await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)

            # 댓글 데이터 추출
            comments_data = await page.evaluate('''() => {
                const list = [];
                const items = document.querySelectorAll('ul.comment_list > li, div.comment_list li, .comment_area li');
                
                items.forEach(item => {
                    const nickEl = item.querySelector('.user_id') || item.querySelector('strong') || item.querySelector('.nickname');
                    const linkEl = item.querySelector('a[href*="/station/"]');
                    const likeEl = item.querySelector('.like_count') || item.querySelector('[class*="like"]');
                    
                    if (nickEl && nickEl.innerText.trim()) {
                        let likeNum = 0;
                        if (likeEl) {
                            likeNum = parseInt(likeEl.innerText.replace(/[^0-9]/g, '')) || 0;
                        }
                        list.push({
                            nickname: nickEl.innerText.trim(),
                            station_url: linkEl ? linkEl.href : '',
                            likes: likeNum
                        });
                    }
                });
                return list;
            }''')
            await browser.close()

            # DB에 데이터 삽입 (오류 방지 예외 처리)
            if comments_data and len(comments_data) > 0:
                try:
                    supabase.table("comments").delete().neq("id", 0).execute()
                    supabase.table("comments").insert(comments_data).execute()
                except Exception as db_err:
                    return {
                        "status": "partial_success", 
                        "db_error": str(db_err), 
                        "scraped_count": len(comments_data), 
                        "sample": comments_data[:2]
                    }

            return {"status": "success", "count": len(comments_data)}

        except Exception as e:
            await browser.close()
            return {"status": "error", "message": str(e)}
