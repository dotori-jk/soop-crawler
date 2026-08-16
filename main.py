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
            # DOM 구조 로딩 후 댓글 요소 대기
            await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(4000)

            comments_data = await page.evaluate('''() => {
                const list = [];
                // SOOP 댓글 영역을 포괄하는 선택자
                const items = document.querySelectorAll('div[class*="comment"] li, ul[class*="comment"] li, li[class*="comment"]');
                
                items.forEach(item => {
                    const textContent = item.innerText || "";
                    const linkEl = item.querySelector('a[href*="/station/"]');
                    
                    // 닉네임 구출 (링크 태그나 강조 태그에서 수집)
                    let nick = "";
                    if (linkEl && linkEl.innerText.trim()) {
                        nick = linkEl.innerText.trim();
                    } else {
                        const strongEl = item.querySelector('strong, em');
                        if (strongEl) nick = strongEl.innerText.trim();
                    }

                    // 좋아요 수 추출 (숫자 추출)
                    let likes = 0;
                    const numbers = textContent.match(/\\d+/g);
                    if (numbers && numbers.length > 0) {
                        likes = parseInt(numbers[numbers.length - 1]) || 0;
                    }

                    if (nick && nick.length < 30) {
                        list.push({
                            nickname: nick,
                            station_url: linkEl ? linkEl.href : '',
                            likes: likes
                        });
                    }
                });
                return list;
            }''')
            await browser.close()

            # Supabase DB 저장
            if comments_data and len(comments_data) > 0:
                try:
                    supabase.table("comments").delete().neq("id", 0).execute()
                    supabase.table("comments").insert(comments_data).execute()
                except Exception as db_err:
                    return {"status": "partial_success", "db_error": str(db_err), "count": len(comments_data), "sample": comments_data[:3]}

            return {"status": "success", "count": len(comments_data), "sample": comments_data[:3]}

        except Exception as e:
            await browser.close()
            return {"status": "error", "message": str(e)}
