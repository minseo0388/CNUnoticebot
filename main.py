import discord
from discord.ext import commands, tasks
from bs4 import BeautifulSoup
import requests
import json
import os
import math
from datetime import datetime

TOKEN = "YOUR_DISCORD_BOT_TOKEN"
NOTICE_FILE = "notices.json"
DEPT_FILE = "departments.json"
CHANNEL_DEPT_FILE = "channel_dept.json"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# 채널별 학과 정보 로드 및 저장
def load_channel_departments():
    if os.path.exists(CHANNEL_DEPT_FILE):
        with open(CHANNEL_DEPT_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_channel_departments(channel_depts):
    with open(CHANNEL_DEPT_FILE, "w", encoding="utf-8") as f:
        json.dump(channel_depts, f, ensure_ascii=False, indent=2)

def get_dept_for_channel(channel_id):
    channel_depts = load_channel_departments()
    departments = load_departments()
    dept_name = channel_depts.get(str(channel_id), "화학과")
    if dept_name in departments:
        return {"name": dept_name, "url": departments[dept_name]}
    return {"name": "화학과", "url": "https://chem.cnu.ac.kr/chem/undergrad/notice.do"}

# 공지 본문 수집
def fetch_notice_detail(article_url):
    res = requests.get(article_url)
    soup = BeautifulSoup(res.text, "html.parser")
    content_div = soup.select_one(".view_con")
    return content_div.get_text(strip=True) if content_div else ""

# 공지 전체 크롤링 (본문 포함)
def fetch_all_notices(dept_url, max_pages=5):
    notices = []
    base_url = dept_url.split("/undergrad/")[0]
    for page in range(1, max_pages + 1):
        res = requests.get(dept_url, params={"viewType": "list", "page": page})
        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.select(".board_list tbody tr")
        for row in rows:
            a_tag = row.select_one("td.subject a")
            date = row.select_one("td.date").text.strip()
            if not a_tag:
                continue
            title = a_tag.text.strip()
            href = a_tag["href"]
            url = base_url + href
            content = fetch_notice_detail(url)
            notices.append({"title": title, "url": url, "date": date, "content": content})
    return notices

def load_notices():
    if os.path.exists(NOTICE_FILE):
        with open(NOTICE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []

def save_notices(notices):
    with open(NOTICE_FILE, "w", encoding="utf-8") as f:
        json.dump(notices, f, ensure_ascii=False, indent=2)

def load_departments():
    if os.path.exists(DEPT_FILE):
        with open(DEPT_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}

@bot.event
async def on_ready():
    print(f"✅ 봇 로그인: {bot.user}")
    check_new_notice.start()

@tasks.loop(minutes=5)
async def check_new_notice():
    print("🔍 공지사항 확인 중...")
    channel_depts = load_channel_departments()
    departments = load_departments()
    for channel_id_str, dept_name in channel_depts.items():
        channel_id = int(channel_id_str)
        dept_url = departments.get(dept_name)
        if not dept_url:
            continue
        current_notices = fetch_all_notices(dept_url)
        saved_notices = load_notices()
        saved_urls = {n['url'] for n in saved_notices}
        new_notices = [n for n in current_notices if n["url"] not in saved_urls]
        if new_notices:
            save_notices(current_notices)
            channel = bot.get_channel(channel_id)
            if channel:
                for notice in new_notices:
                    embed = discord.Embed(
                        title=notice["title"],
                        url=notice["url"],
                        description=f"작성일: {notice['date']}\n\n{notice['content'][:200]}...",
                        color=0x1abc9c
                    )
                    await channel.send(embed=embed)
        else:
            print(f"✅ 채널 {channel_id} - 새 공지 없음.")

class NoticeView(discord.ui.View):
    def __init__(self, notices, page=1, timeout=60):
        super().__init__(timeout=timeout)
        self.notices = notices
        self.page = page
        self.per_page = 5
        self.max_page = math.ceil(len(self.notices) / self.per_page)
        self.update_buttons()

    def update_buttons(self):
        self.clear_items()
        start = (self.page - 1) * self.per_page
        end = start + self.per_page
        page_notices = self.notices[start:end]
        for i, notice in enumerate(page_notices):
            self.add_item(NoticeButton(notice, i + 1))
        if self.page > 1:
            self.add_item(PageButton(label="◀️", direction=-1, parent=self))
        if self.page < self.max_page:
            self.add_item(PageButton(label="▶️", direction=1, parent=self))

class NoticeButton(discord.ui.Button):
    def __init__(self, notice, index):
        super().__init__(label=f"{index}️⃣", style=discord.ButtonStyle.primary)
        self.notice = notice

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=self.notice["title"],
            url=self.notice["url"],
            description=f"📅 {self.notice['date']}\n\n{self.notice['content'][:1024]}",
            color=0x2ecc71
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class PageButton(discord.ui.Button):
    def __init__(self, label, direction, parent):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.direction = direction
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.page += self.direction
        self.parent_view.update_buttons()
        await interaction.response.edit_message(
            content=f"📄 공지 목록 (페이지 {self.parent_view.page}/{self.parent_view.max_page})",
            view=self.parent_view
        )

@bot.command(name="목록")
async def show_notice_list(ctx):
    dept = get_dept_for_channel(ctx.channel.id)
    notices = fetch_all_notices(dept["url"])
    if not notices:
        await ctx.send("❌ 저장된 공지가 없습니다.")
        return
    view = NoticeView(notices)
    await ctx.send(
        content=f"📄 [{dept['name']}] 공지 목록 (페이지 {view.page}/{view.max_page})",
        view=view
    )

@bot.command(name="검색")
async def search_notice(ctx, *, keyword: str):
    notices = load_notices()
    results = [
        n for n in notices
        if keyword.lower() in n["title"].lower() or keyword.lower() in n["content"].lower()
    ]
    if not results:
        await ctx.send("❌ 해당 키워드를 포함한 공지가 없습니다.")
        return
    view = NoticeView(results)
    await ctx.send(
        content=f"🔍 검색 결과 (페이지 {view.page}/{view.max_page})",
        view=view
    )

@bot.command(name="날짜")
async def filter_by_date(ctx, date: str):
    try:
        target = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        await ctx.send("❌ 날짜 형식이 잘못되었습니다. (예: 2025-06-08)")
        return
    notices = load_notices()
    results = [n for n in notices if datetime.strptime(n['date'], "%Y.%m.%d").date() == target]
    if not results:
        await ctx.send("❌ 해당 날짜의 공지가 없습니다.")
        return
    view = NoticeView(results)
    await ctx.send(f"📆 {date} 공지 목록 (페이지 {view.page}/{view.max_page})", view=view)

@bot.command(name="학과")
async def change_department(ctx, *, dept_name: str):
    departments = load_departments()
    if dept_name not in departments:
        await ctx.send("❌ 등록되지 않은 학과입니다. !학과목록 명령어로 지원 목록을 확인하세요.")
        return
    channel_depts = load_channel_departments()
    channel_depts[str(ctx.channel.id)] = dept_name
    save_channel_departments(channel_depts)
    await ctx.send(f"✅ 이 채널의 학과가 '{dept_name}'(으)로 변경되었습니다.")

@bot.command(name="학과목록")
async def list_departments(ctx):
    departments = load_departments()
    if not departments:
        await ctx.send("❌ 등록된 학과 정보가 없습니다.")
        return
    embed = discord.Embed(title="📚 지원 학과 목록", color=0x3498db)
    for name in sorted(departments):
        embed.add_field(name=name, value="", inline=True)
    await ctx.send(embed=embed)

bot.run(TOKEN)
