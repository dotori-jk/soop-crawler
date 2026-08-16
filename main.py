import os
from fastapi import FastAPI
from playwright.async_api import async_playwright
from supabase import create_client, Client

app = FastAPI()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TARGET_URL = "https://www.sooplive.com/station/ecvhao/post/204516133"

@app.get("/scrape")
async def scrape_comments():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(TARGET_URL)
        await page.wait_for_selector("li")

        comments_data = await page.evaluate('''() => {
            const list = [];
            document.querySelectorAll('ul.comment_list > li, div.comment_list li').forEach(item => {
                const nickEl = item.querySelector('.user_id') || item.querySelector('strong');
                const linkEl = item.querySelector('a[href*="/station/"]');
                const likeEl = item.querySelector('.like_count') || item.querySelector('[class*="like"]');
                
                if (nickEl) {
                    list.push({
                        nickname: nickEl.innerText.trim(),
                        station_url: linkEl ? linkEl.href : '',
                        likes: likeEl ? parseInt(likeEl.innerText.replace(/[^0-9]/g, '')) || 0 : 0
                    });
                }
            });
            return list;
        }''')
        await browser.close()

        supabase.table("comments").delete().neq("id", 0).execute()
        if comments_data:
            supabase.table("comments").insert(comments_data).execute()

        return {"status": "success", "count": len(comments_data)}
