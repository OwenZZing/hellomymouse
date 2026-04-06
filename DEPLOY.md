# 배포 가이드 — hellomymouse.com

## 구조

```
Frontend (Next.js) → Vercel  →  hellomymouse.com
Backend  (FastAPI) → Railway →  api.hellomymouse.com
```

---

## 1단계: 로컬 테스트 (배포 전 확인)

### 백엔드
```bash
cd backend
pip install -r requirements.txt
python main.py
# → http://localhost:8000
```

### 프론트엔드
```bash
cd frontend
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
# → http://localhost:3000
```

브라우저에서 http://localhost:3000 열어서 동작 확인.

---

## 2단계: GitHub에 올리기

```bash
cd C:\Users\kby93\Documents\hellomymouse
git init
git add .
git commit -m "initial commit"
# GitHub에서 hellomymouse 레포 생성 후:
git remote add origin https://github.com/YOUR_USERNAME/hellomymouse.git
git push -u origin main
```

---

## 3단계: Railway (백엔드 배포)

1. railway.app 가입 (GitHub 연동)
2. New Project → Deploy from GitHub repo → `hellomymouse`
3. **Root Directory** 설정: `backend`
4. 자동으로 `requirements.txt` 감지해서 Python 앱으로 배포
5. Settings → Networking → Generate Domain
   → `https://xxx.railway.app` 같은 URL 생성됨

---

## 4단계: Vercel (프론트엔드 배포)

1. vercel.com 가입 (GitHub 연동)
2. New Project → Import `hellomymouse` 레포
3. **Root Directory** 설정: `frontend`
4. Environment Variables 추가:
   ```
   NEXT_PUBLIC_API_URL = https://xxx.railway.app  ← Railway URL
   ```
5. Deploy

---

## 5단계: 도메인 연결 (hellomymouse.com)

1. Namecheap / Cloudflare 등에서 `hellomymouse.com` 구매
2. Vercel 프로젝트 → Settings → Domains → `hellomymouse.com` 추가
3. DNS 레코드 설정 (Vercel이 안내해줌)

---

## 비용 요약

| 항목 | 비용 |
|------|------|
| Vercel (프론트) | 무료 |
| Railway (백엔드) | 무료 $5 크레딧 / 이후 ~$5/월 |
| 도메인 | 연 ~$10~15 |

---

## 업데이트 방법

코드 수정 후 `git push` 하면 Vercel + Railway 자동 재배포.
