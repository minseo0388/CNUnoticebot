import requests
from bs4 import BeautifulSoup
import json

BASE_URL = "https://www.cnu.ac.kr"
DEPT_LIST_URL = "https://www.cnu.ac.kr/html/kr/guide/guide_0107.html"
OUTPUT_FILE = "departments.json"

def get_department_links():
    res = requests.get(DEPT_LIST_URL)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    departments = {}
    for a_tag in soup.select("a"):
        href = a_tag.get("href", "")
        if "/html/kr/" in href and ("학과" in a_tag.text or "과" in a_tag.text):
            name = a_tag.text.strip()
            full_url = href if href.startswith("http") else BASE_URL + href
            # 추정 후 공지사항 페이지 링크
            notice_url = full_url.replace("/html/kr/", "/") + "undergrad/notice.do"
            departments[name] = notice_url

    return departments

def save_to_json(data, filename):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ 저장 완료: {filename}")

if __name__ == "__main__":
    print("🔍 학과 정보를 수집 중...")
    dept_links = get_department_links()
    save_to_json(dept_links, OUTPUT_FILE)
    print("📁 학과 링크를 JSON 파일로 저장했습니다.")
