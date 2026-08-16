import os
import httpx
from fastapi import FastAPI
from supabase import create_client, Client

app = FastAPI()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 우왁굳 게시글 댓글 API URL (title_no: 204516133)
SOOP_API_URL = "https://stapi.sooplive.com/api/post/comments?title_no=204516133&limit=300"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.sooplive.com/station/ecvhao/post/204516133"
}

@app.get("/")
def home():
    return {"status": "ok", "message": "SOOP Fast API Crawler is Running"}

@app.get("/scrape")
async def scrape_comments():
    try:
        # 1. API 초고속 호출 (Playwright 없이 0.2초 만에 응답)
        async with httpx.AsyncClient(headers=HEADERS, timeout=10.0) as client:
            response = await client.get(SOOP_API_URL)
            res_data = response.json()

        # 2. JSON 데이터 파싱
        raw_comments = res_data.get("data", {}).get("list", [])
        
        comments_data = []
        for c in raw_comments:
            nick = c.get("user_nick", "").strip()
            user_id = c.get("user_id", "").strip()
            likes = int(c.get("like_cnt", 0))

            if nick and user_id:
                comments_data.append({
                    "nickname": nick,
                    "station_url": f"https://www.sooplive.com/station/{user_id}",
                    "likes": likes
                })

        # 3. 중복 닉네임 제거
        unique_comments = list({c['nickname']: c for c in comments_data}.values())

        # 4. Supabase DB 저장
        if unique_comments:
            supabase.table("comments").delete().neq("id", 0).execute()
            supabase.table("comments").insert(unique_comments).execute()

        return {
            "status": "success", 
            "count": len(unique_comments), 
            "sample": unique_comments[:3]
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
